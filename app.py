import os
import sys
import zipfile
import io

# 强制 stdout 无缓冲输出，确保 Docker 日志实时显示
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)

import requests
import functools
import time
import subprocess
import shutil
from datetime import timedelta
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, make_response, send_file
from threading import Lock, Thread
import json_db
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置项
VERSION = os.getenv('APP_VERSION', 'dev')

# 强制启用自动更新
AUTO_UPDATE_ENABLED = True
UPDATE_CHECK_INTERVAL = 300  # 每5分钟检查一次

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.permanent_session_lifetime = timedelta(days=90)

# --- Online Users Tracking ---
active_users = {}
online_users_lock = Lock()

# --- Database ---
def init_db():
    """初始化 JSON 数据库"""
    json_db.init_db()

# --- Online Users Tracking ---
@app.before_request
def track_user_activity():
    if 'user_id' in session:
        user_id = session['user_id']
        with online_users_lock:
            active_users[user_id] = {'username': session.get('username'), 'last_activity': time.time()}

# Clean up inactive users (remove users inactive for more than 30 minutes)
def cleanup_inactive_users():
    current_time = time.time()
    with online_users_lock:
        inactive_users = [user_id for user_id, data in active_users.items() 
                          if current_time - data['last_activity'] > 1800]  # 30 minutes
        for user_id in inactive_users:
            del active_users[user_id]

# --- Auto Update ---
# 根据平台选择版本文件路径
if sys.platform == 'win32':
    VERSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.version')
else:
    VERSION_FILE = '/app/.version'
current_version = None

def is_running_in_container():
    """检测是否在容器环境中运行"""
    if os.path.exists('/.dockerenv'):
        return True
    try:
        with open('/proc/self/cgroup', 'r') as f:
            return 'docker' in f.read() or 'containerd' in f.read()
    except:
        pass
    return False

def read_local_version():
    """读取本地版本（从文件）"""
    try:
        if os.path.exists(VERSION_FILE):
            with open(VERSION_FILE, 'r') as f:
                return f.read().strip()
    except:
        pass
    return None

def write_local_version(version):
    """写入本地版本到文件"""
    try:
        with open(VERSION_FILE, 'w') as f:
            f.write(version)
    except Exception as e:
        print(f"[SkoHit][Update] Failed to write version: {e}")

def get_remote_version():
    """获取远程最新版本（GitHub API）"""
    try:
        api_url = "https://api.github.com/repos/Zhidongli-A/SkoHit-Music/commits/master"
        headers = {'Accept': 'application/vnd.github.v3+json'}
        resp = requests.get(api_url, headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json()['sha']
        else:
            print(f"[SkoHit][Update] API error: {resp.status_code}")
    except Exception as e:
        print(f"[SkoHit][Update] Error: {e}")
    return None

def download_and_update():
    """下载并更新代码（GitHub 源码包）"""
    try:
        zip_url = "https://github.com/Zhidongli-A/SkoHit-Music/archive/refs/heads/master.zip"
        print(f"[SkoHit][Update] Downloading...")
        
        resp = requests.get(zip_url, timeout=30)
        if resp.status_code != 200:
            print(f"[SkoHit][Update] Download failed: {resp.status_code}")
            return False
        
        print("[SkoHit][Update] Extracting...")
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            root_dir = zf.namelist()[0].split('/')[0]
            # 根据平台选择临时目录
            if sys.platform == 'win32':
                temp_dir = os.path.join(os.environ.get('TEMP', '.'), 'skohit_update')
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                zf.extractall(temp_dir)
                src_dir = os.path.join(temp_dir, root_dir)
                app_dir = os.path.dirname(os.path.abspath(__file__))
            else:
                zf.extractall('/tmp')
                src_dir = f'/tmp/{root_dir}'
                app_dir = '/app'
        
        print(f"[SkoHit][Update] Updating...")
        
        for item in os.listdir(src_dir):
            if item == 'data':
                continue
            src = os.path.join(src_dir, item)
            dst = os.path.join(app_dir, item)
            
            if os.path.isdir(src):
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
        
        # 清理临时目录
        if sys.platform == 'win32' and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        elif os.path.exists('/tmp/' + root_dir):
            shutil.rmtree('/tmp/' + root_dir)
            
        print("[SkoHit][Update] Done")
        return True
        
    except Exception as e:
        print(f"[SkoHit][Update] Error: {e}")
    return False

def restart_service():
    """重启服务 - 根据平台选择不同的重启策略"""
    print("[SkoHit][Update] Restarting...")
    args = sys.argv.copy()
    
    if is_running_in_container():
        # 容器端：直接异常退出，让容器重启
        print("[SkoHit][Update] Container mode: exit with code 42")
        os._exit(42)
    else:
        # 桌面端（Windows/Linux/Mac）：先启动新进程，再退出旧进程
        print("[SkoHit][Update] Desktop mode: start new process then exit")
        if sys.platform == 'win32':
            # Windows：使用当前控制台，不创建新窗口
            subprocess.Popen([sys.executable] + args, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        else:
            # Linux/Mac：后台启动新进程
            subprocess.Popen([sys.executable] + args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        # 旧进程正常退出
        os._exit(0)

def update_worker():
    """更新工作线程 - 简化逻辑：只要版本不同就更新"""
    global current_version
    
    current_version = read_local_version()
    print(f"[SkoHit][Update] Current: {current_version[:8] if current_version else 'unknown'}, interval: {UPDATE_CHECK_INTERVAL}s")
    
    check_count = 0
    while True:
        time.sleep(UPDATE_CHECK_INTERVAL)
        check_count += 1
        
        try:
            print(f"[SkoHit][Update] Check #{check_count}")
            
            remote_version = get_remote_version()
            if not remote_version:
                continue
            
            local_short = current_version[:8] if current_version else 'none'
            remote_short = remote_version[:8]
            print(f"[SkoHit][Update] Local: {local_short}, Remote: {remote_short}")
            
            # 简化逻辑：只要版本不同就更新（包括第一次运行）
            if remote_version != current_version:
                print("[SkoHit][Update] Updata is starting")
                
                if download_and_update():
                    current_version = remote_version
                    write_local_version(current_version)
                    time.sleep(3)
                    restart_service()
            else:
                print("[SkoHit][Update] Already latest")
                
        except Exception as e:
            print(f"[SkoHit][Update] Error: {e}")

def check_update_available():
    """检查更新功能是否可用"""
    try:
        resp = requests.get("https://api.github.com/repos/Zhidongli-A/SkoHit-Music/commits/master", timeout=5)
        if resp.status_code == 200:
            print("[SkoHit] Update check OK")
            return True
    except:
        pass
    print("[SkoHit] Update check unavailable")
    return False

def start_auto_update():
    """启动自动更新线程"""
    if not AUTO_UPDATE_ENABLED:
        print("[SkoHit] Auto-update disabled")
        return

    print("[SkoHit] Auto-update enabled")
    update_thread = Thread(target=update_worker, daemon=True)
    update_thread.start()

# --- Helpers ---
# (helper functions removed - now handled in json_db.py)

@functools.lru_cache(maxsize=100)
def cached_scraper_request(cat, limit, offset):
    base_url = "https://music.163.com/discover/playlist/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': 'https://music.163.com/'
    }
    params = {
        'order': 'hot',
        'cat': cat,
        'limit': limit,
        'offset': offset
    }
    return requests.get(base_url, headers=headers, params=params, timeout=5)

# --- Routes: Auth ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.json
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'success': False, 'message': 'Missing fields'})
        
        user = json_db.verify_user(username, password)
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session.permanent = True
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': 'Invalid credentials'})
    
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    confirm = data.get('confirm_password')
    
    if not username or not password or not confirm:
        return jsonify({'success': False, 'message': 'Missing fields'})
    
    if password != confirm:
        return jsonify({'success': False, 'message': 'Passwords do not match'})
    
    # 检查用户名是否已存在
    existing = json_db.get_user_by_username(username)
    if existing:
        return jsonify({'success': False, 'message': 'Username already exists'})
    
    json_db.create_user(username, password)
    return jsonify({'success': True})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', username=session['username'])

@app.route('/api/favorites', methods=['GET', 'POST', 'DELETE'])
def favorites():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    user_id = session['user_id']

    if request.method == 'GET':
        # 返回 song_id 列表，前端通过 Meting API 获取歌曲详情
        song_ids = json_db.get_user_favorites(user_id)
        return jsonify(song_ids)

    elif request.method == 'POST':
        data = request.json
        song_id = str(data.get('id', '')).strip()
        if not song_id:
            return jsonify({'error': 'Missing song id'}), 400

        try:
            success = json_db.add_favorite(user_id, song_id)
            if success:
                return jsonify({'success': True, 'message': 'Added to favorites'})
            else:
                return jsonify({'success': False, 'message': 'Already in favorites'}), 409
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    elif request.method == 'DELETE':
        song_id = request.args.get('id')
        if not song_id:
             return jsonify({'error': 'Missing id'}), 400

        success = json_db.remove_favorite(user_id, song_id)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': 'Not found'}), 404

@app.route('/api/user/settings', methods=['POST'])
def update_user_settings():
    """更新用户设置（用户名和密码）"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    user_id = session['user_id']
    data = request.json

    new_username = data.get('new_username', '').strip()
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')

    # 获取当前用户信息
    current_user = None
    users = json_db._get_all_users()
    for u in users:
        if u.get('id') == user_id:
            current_user = u
            break

    if not current_user:
        return jsonify({'success': False, 'message': '用户不存在'}), 404

    # 如果要修改密码，验证当前密码
    if new_password:
        import hashlib
        hashed_current = hashlib.md5(current_password.encode()).hexdigest()
        if current_user.get('password') != hashed_current:
            return jsonify({'success': False, 'message': '当前密码不正确', 'field': 'current_password'})

        # 检查新密码是否与当前密码相同
        hashed_new = hashlib.md5(new_password.encode()).hexdigest()
        if hashed_new == current_user.get('password'):
            return jsonify({'success': False, 'message': '新密码不能与当前密码相同', 'field': 'new_password'})

    # 更新用户信息
    result = json_db.update_user(
        user_id=user_id,
        new_username=new_username if new_username else None,
        new_password=new_password if new_password else None
    )

    if result['success']:
        # 更新 session 中的用户名
        if new_username:
            session['username'] = new_username
        return jsonify({'success': True, 'message': '设置已更新'})
    else:
        return jsonify(result), 400

@app.route('/api/user/avatar', methods=['GET', 'POST'])
def user_avatar():
    """获取或上传用户头像"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    user_id = session['user_id']

    if request.method == 'GET':
        # 返回用户头像
        avatar_path = json_db.get_user_avatar_path(user_id)
        if avatar_path and os.path.exists(avatar_path):
            return send_file(avatar_path, mimetype='image/png')
        else:
            # 返回默认头像 (SVG)
            default_avatar = os.path.join(os.path.dirname(__file__), 'static', 'images', 'default-avatar.svg')
            if os.path.exists(default_avatar):
                return send_file(default_avatar, mimetype='image/svg+xml')
            else:
                # 如果没有默认头像，返回一个1x1的透明像素
                from io import BytesIO
                transparent_pixel = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\xfc\xcf\xc0\x50\x0f\x00\x04A\x01\xa1\x3a\xf0\xf7\x7f\x00\x00\x00\x00IEND\xaeB`\x82'
                return send_file(BytesIO(transparent_pixel), mimetype='image/png')

    elif request.method == 'POST':
        # 上传头像
        print(f"[Avatar] Upload request from user {user_id}")
        
        if 'avatar' not in request.files:
            print("[Avatar] No avatar field in request")
            return jsonify({'success': False, 'message': '没有上传文件'})

        file = request.files['avatar']
        if file.filename == '':
            print("[Avatar] Empty filename")
            return jsonify({'success': False, 'message': '没有选择文件'})

        print(f"[Avatar] Received file: {file.filename}, type: {file.content_type}")

        # 验证文件类型
        if not file.content_type or not file.content_type.startswith('image/'):
            return jsonify({'success': False, 'message': '请上传图片文件'})

        try:
            # 确保目录存在
            json_db._ensure_avatars_dir()
            avatar_path = os.path.join(json_db.AVATARS_DIR, f'{user_id}.png')
            print(f"[Avatar] Saving to: {avatar_path}")

            # 保存文件
            file.save(avatar_path)
            print("[Avatar] File saved successfully")

            # 尝试用 PIL 处理（如果有的话）
            try:
                from PIL import Image
                image = Image.open(avatar_path)
                
                # 转换为 RGB（去除透明通道，兼容性好）
                if image.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', image.size, (255, 255, 255))
                    if image.mode == 'P':
                        image = image.convert('RGBA')
                    if image.mode in ('RGBA', 'LA'):
                        background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
                        image = background
                else:
                    image = image.convert('RGB')

                # 裁剪为正方形
                width, height = image.size
                size = min(width, height)
                left = (width - size) // 2
                top = (height - size) // 2
                image = image.crop((left, top, left + size, top + size))

                # 调整大小
                image = image.resize((200, 200), Image.LANCZOS)

                # 保存
                image.save(avatar_path, 'JPEG', quality=90)
                print("[Avatar] Image processed successfully")
            except ImportError:
                print("[Avatar] PIL not available, saving original file")
            except Exception as pil_error:
                print(f"[Avatar] PIL processing error: {pil_error}, keeping original")

            return jsonify({'success': True, 'message': '头像已更新'})
        except Exception as e:
            print(f"[Avatar] Error: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'message': f'上传失败: {str(e)}'})

# --- Routes: API Proxy ---
METING_API_URL = os.getenv('METING_API_URL', '')
if not METING_API_URL:
    raise ValueError("请设置 METING_API_URL 环境变量，或在 .env 文件中配置")

@functools.lru_cache(maxsize=500)
def cached_meting_request(server, type_arg, id_arg):
    params = {
        'server': server,
        'type': type_arg,
        'id': id_arg
    }
    # Don't cache url/pic types as they might expire or be redirects
    if type_arg in ['url', 'pic']:
        return None
        
    try:
        resp = requests.get(METING_API_URL, params=params, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except:
        return None
    return None

@app.route('/api/meting')
def meting_proxy():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    server = request.args.get('server')
    type_arg = request.args.get('type')
    id_arg = request.args.get('id')
    
    # Try cache for json data
    if type_arg not in ['url', 'pic']:
        cached_data = cached_meting_request(server, type_arg, id_arg)
        if cached_data:
            return jsonify(cached_data)
            
    # Forward all query parameters if not cached or cache miss
    params = request.args.to_dict()
    try:
        # Special handling for url/pic to handle redirects properly
        if params.get('type') in ['url', 'pic']:
            resp = requests.get(METING_API_URL, params=params, allow_redirects=False, timeout=10)
            if resp.status_code == 302:
                # 获取真实的音频URL
                real_url = resp.headers['Location']
                # 返回JSON让前端处理，避免直接重定向被CDN拦截
                return jsonify({'url': real_url, 'type': 'redirect'})
            elif resp.status_code == 200:
                return resp.content, 200, {'Content-Type': resp.headers.get('Content-Type')}
        
        # Fallback for non-cached JSON (shouldn't happen often if cache works)
        resp = requests.get(METING_API_URL, params=params, timeout=10)
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- Routes: Scraper (163) ---

@app.route('/api/163/toplist')
def get_toplist():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        return jsonify(cached_toplist())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@functools.lru_cache(maxsize=1)
def cached_toplist():
    """只通过爬虫获取歌曲 ID，详细信息由前端通过 API 加载"""
    url = 'https://music.163.com/discover/toplist?id=3778678'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36',
        'Referer': 'https://music.163.com/'
    }
    resp = requests.get(url, headers=headers, timeout=10)
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(resp.text, 'html.parser')
    toplist = []
    for a in soup.select('ul.f-hide li a'):
        href = a.get('href', '')
        if 'song' in href and 'id=' in href:
            song_id = href.split('id=')[-1]
            # 只返回 ID，不返回标题
            toplist.append({'id': song_id, 'source': 'netease'})
    return toplist

@app.route('/api/163/playlists')
def get_playlists():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    cat = request.args.get('cat', '全部')
    limit = request.args.get('limit', 30)
    offset = request.args.get('offset', 0)
    
    try:
        response = cached_scraper_request(cat, limit, offset)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        playlists = []
        # The list is usually in <ul class="m-cvrlst f-cb">
        # Each item is <li>
        items = soup.select('ul.m-cvrlst li')
        
        for item in items:
            # Title & Link
            link_tag = item.select_one('div.u-cover a.msk')
            title = link_tag['title'] if link_tag else "Unknown"
            playlist_id = link_tag['href'].split('id=')[-1] if link_tag else ""
            
            # Cover Image
            img_tag = item.select_one('img')
            cover_url = img_tag['src'] if img_tag else ""
            
            # Play Count
            nb_tag = item.select_one('span.nb')
            play_count = nb_tag.text if nb_tag else "0"
            
            playlists.append({
                'id': playlist_id,
                'name': title,
                'cover': cover_url,
                'play_count': play_count,
                'source': 'netease' # For frontend to know to use meting with server='netease' type='playlist'
            })
            
        return jsonify(playlists)
        
    except Exception as e:
        print(f"Error scraping: {e}")
        return jsonify({'error': str(e)}), 500

# --- Statistics API ---
@app.route('/api/stats')
def get_stats():
    # Clean up inactive users first
    cleanup_inactive_users()
    
    # Get total user count
    total_users = json_db.count_users()
    
    # Get online user count
    online_count = len(active_users)
    
    # Check if service is running normally
    service_status = True  # Service is running if this endpoint is accessible
    
    return jsonify({
        'online_users': online_count,
        'total_users': total_users,
        'service_status': 'running' if service_status else 'down',
        'active_users_list': [data['username'] for data in active_users.values()]
    })

# ============================================
# Main Entry Point
# ============================================

if __name__ == '__main__':
    init_db()

    import argparse
    parser = argparse.ArgumentParser(description='SkoHit Music Server')
    parser.add_argument('--port', type=int, default=7000, help='Port to run on (default: 7000)')
    args = parser.parse_args()

    check_update_available()
    start_auto_update()

    print(f"Server running on http://0.0.0.0:{args.port}")
    app.run(host="0.0.0.0", debug=True, port=args.port, use_reloader=False)
