import os
import sys
import hashlib
import requests
import functools
import time
import subprocess
import shutil
from datetime import timedelta
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, make_response
from threading import Lock, Thread
import json_db
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

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
# 备份目录放在项目目录之外，避免被 Git 覆盖
BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'skohit_backup')
UPDATE_CHECK_INTERVAL = 60  # 每分钟检查一次
last_commit_hash = None

def ensure_backup_dir():
    """确保备份目录存在（在项目目录之外）"""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
        print(f"[AutoUpdate] 创建备份目录: {BACKUP_DIR}")

def backup_database():
    """备份数据库到项目目录之外"""
    ensure_backup_dir()
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    
    try:
        if os.path.exists('data/users.json'):
            backup_file = os.path.join(BACKUP_DIR, f'users.json.{timestamp}')
            shutil.copy2('data/users.json', backup_file)
            print(f"[AutoUpdate] 用户数据库已备份: {backup_file}")
        
        if os.path.exists('data/favorites.json'):
            backup_file = os.path.join(BACKUP_DIR, f'favorites.json.{timestamp}')
            shutil.copy2('data/favorites.json', backup_file)
            print(f"[AutoUpdate] 收藏数据库已备份: {backup_file}")
        
        return True
    except Exception as e:
        print(f"[AutoUpdate] 备份失败: {e}")
        return False

def get_remote_commit_hash():
    """获取远程仓库最新 commit hash"""
    try:
        # 获取远程分支最新 commit
        result = subprocess.run(
            ['git', 'ls-remote', 'origin', 'HEAD'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return result.stdout.split()[0]
    except Exception as e:
        print(f"[AutoUpdate] 获取远程版本失败: {e}")
    return None

def get_local_commit_hash():
    """获取本地当前 commit hash"""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as e:
        print(f"[AutoUpdate] 获取本地版本失败: {e}")
    return None

def pull_latest_code():
    """拉取最新代码"""
    try:
        print("[AutoUpdate] 正在拉取最新代码...")
        result = subprocess.run(
            ['git', 'pull', 'origin', 'master'],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            print("[AutoUpdate] 代码更新成功")
            return True
        else:
            print(f"[AutoUpdate] 代码更新失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"[AutoUpdate] 拉取代码异常: {e}")
        return False

def auto_update_worker():
    """自动更新工作线程"""
    global last_commit_hash
    
    # 初始获取本地版本
    last_commit_hash = get_local_commit_hash()
    print(f"[AutoUpdate] 当前版本: {last_commit_hash}")
    print(f"[AutoUpdate] 更新检查间隔: {UPDATE_CHECK_INTERVAL}秒")
    
    while True:
        time.sleep(UPDATE_CHECK_INTERVAL)
        
        try:
            # 检查远程是否有更新
            remote_hash = get_remote_commit_hash()
            if not remote_hash:
                continue
            
            if remote_hash != last_commit_hash:
                print(f"[AutoUpdate] 检测到更新!")
                print(f"[AutoUpdate] 本地: {last_commit_hash}")
                print(f"[AutoUpdate] 远程: {remote_hash}")
                
                # 1. 备份数据库（到项目目录之外）
                if backup_database():
                    # 2. 拉取最新代码
                    if pull_latest_code():
                        # 3. 更新本地版本记录
                        last_commit_hash = get_local_commit_hash()
                        print("[AutoUpdate] 更新完成，服务将在下次重启后生效")
                        print("[AutoUpdate] 提示: 如需立即生效，请手动重启服务")
                    else:
                        print("[AutoUpdate] 拉取代码失败，请手动处理")
                else:
                    print("[AutoUpdate] 备份失败，取消更新")
        except Exception as e:
            print(f"[AutoUpdate] 检查更新异常: {e}")

def start_auto_update():
    """启动自动更新线程"""
    # 检查是否在 Git 仓库中
    if not os.path.exists('.git'):
        print("[AutoUpdate] 当前目录不是 Git 仓库，自动更新已禁用")
        return
    
    # 检查是否有远程仓库配置
    try:
        result = subprocess.run(['git', 'remote', '-v'], capture_output=True, text=True)
        if 'origin' not in result.stdout:
            print("[AutoUpdate] 未配置远程仓库，自动更新已禁用")
            return
    except Exception:
        print("[AutoUpdate] Git 检查失败，自动更新已禁用")
        return
    
    # 启动后台线程
    update_thread = Thread(target=auto_update_worker, daemon=True)
    update_thread.start()
    print("[AutoUpdate] 自动更新监测已启动")

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
                return redirect(resp.headers['Location'])
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
            title = a.text.strip()
            toplist.append({'id': song_id, 'title': title, 'source': 'netease'})
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
# API Extension Routes
# These routes provide additional API endpoints for admin/extension use
# ============================================

@app.route('/api/users', methods=['GET'])
def api_get_users():
    """Get all users (for admin/extension use)"""
    try:
        users = json_db.get_all_users()
        # 不返回密码字段
        result = [{'id': u['id'], 'username': u['username']} for u in users]
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/users/<int:user_id>', methods=['GET'])
def api_get_user(user_id):
    """Get user by ID"""
    try:
        user = json_db.get_user_by_id(user_id)
        if user:
            return jsonify({'success': True, 'data': {'id': user['id'], 'username': user['username']}})
        return jsonify({'success': False, 'error': 'User not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/users', methods=['POST'])
def api_create_user():
    """Create new user via API"""
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({'success': False, 'error': 'Username and password are required'}), 400

        # Check if user exists
        existing = json_db.get_user_by_username(username)
        if existing:
            return jsonify({'success': False, 'error': 'Username already exists'}), 400

        user = json_db.create_user(username, password)
        return jsonify({'success': True, 'data': {'id': user['id'], 'username': user['username']}}), 201
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/users/<int:user_id>', methods=['PUT'])
def api_update_user(user_id):
    """Update user"""
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')

        if not username and not password:
            return jsonify({'success': False, 'error': 'No fields to update'}), 400

        user = json_db.update_user(user_id, username, password)
        if user:
            return jsonify({'success': True, 'data': {'id': user['id'], 'username': user['username']}})
        return jsonify({'success': False, 'error': 'User not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def api_delete_user(user_id):
    """Delete user"""
    try:
        success = json_db.delete_user(user_id)
        if success:
            return jsonify({'success': True, 'message': 'User deleted'})
        return jsonify({'success': False, 'error': 'User not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/all-favorites', methods=['GET'])
def api_get_all_favorites():
    """Get all favorites (for admin/extension use)"""
    try:
        favorites = json_db.get_all_favorites()
        return jsonify({'success': True, 'data': favorites})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user-favorites/<int:user_id>', methods=['GET'])
def api_get_user_favorites(user_id):
    """Get favorites by user ID - 返回 song_id 列表"""
    try:
        song_ids = json_db.get_user_favorites(user_id)
        return jsonify({'success': True, 'data': song_ids})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/favorites', methods=['POST'])
def api_add_favorite_admin():
    """Add favorite (admin/extension API with explicit user_id)"""
    try:
        data = request.json
        user_id = data.get('user_id')
        song_id = data.get('id') or data.get('song_id')

        if not user_id or not song_id:
            return jsonify({'success': False, 'error': 'user_id and song_id are required'}), 400

        success = json_db.add_favorite(user_id, str(song_id))
        if success:
            return jsonify({'success': True, 'message': 'Favorite added'}), 201
        return jsonify({'success': False, 'error': 'Already in favorites'}), 409
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/favorites', methods=['DELETE'])
def api_delete_favorite_admin():
    """Delete favorite (admin/extension API with explicit user_id)"""
    try:
        user_id = request.args.get('user_id')
        song_id = request.args.get('song_id') or request.args.get('id')

        if not user_id or not song_id:
            return jsonify({'success': False, 'error': 'user_id and song_id are required'}), 400

        success = json_db.remove_favorite(int(user_id), song_id)
        if success:
            return jsonify({'success': True, 'message': 'Favorite deleted'})
        return jsonify({'success': False, 'error': 'Favorite not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
# Main Entry Point
# ============================================

if __name__ == '__main__':
    init_db()

    import argparse
    parser = argparse.ArgumentParser(description='SkoHit Music Server')
    parser.add_argument('--port', type=int, default=7000, help='Port to run on (default: 7000)')
    parser.add_argument('--no-api-service', action='store_true', help='Do not start API sub-service on port 8000')
    parser.add_argument('--is-subprocess', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--no-auto-update', action='store_true', help='Disable auto update check')
    args = parser.parse_args()

    main_port = args.port
    api_process = None

    # 启动自动更新监测（如果不是子进程且未禁用）
    if not args.is_subprocess and not args.no_auto_update:
        start_auto_update()

    # Start API sub-service on port 8000 (unless disabled or this is already a subprocess)
    if not args.no_api_service and not args.is_subprocess and main_port != 8000:
        # Prepare subprocess arguments (cross-platform)
        popen_kwargs = {
            'stdout': subprocess.DEVNULL,
            'stderr': subprocess.DEVNULL
        }

        # Windows-specific: hide console window
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE
            popen_kwargs['startupinfo'] = startupinfo

        api_process = subprocess.Popen([sys.executable, __file__, '--port', '8000', '--is-subprocess'], **popen_kwargs)
        print(f"API Service running on http://0.0.0.0:8000")

    print(f"Main App running on http://0.0.0.0:{main_port}")

    try:
        app.run(host="0.0.0.0", debug=True, port=main_port, use_reloader=False)
    finally:
        if api_process:
            api_process.terminate()
