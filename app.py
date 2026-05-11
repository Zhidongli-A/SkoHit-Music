import os
import sys

# 强制 stdout 无缓冲输出，确保 Docker 日志实时显示
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)

import hashlib
import requests
import functools
import time
import subprocess
from datetime import timedelta
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, make_response
from threading import Lock, Thread
import json_db
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置项
VERSION = os.getenv('APP_VERSION', 'dev')

# 强制启用自动更新
AUTO_UPDATE_ENABLED = True
UPDATE_CHECK_INTERVAL = 60  # 每60秒检查一次

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
last_commit_hash = None

def is_running_in_container():
    """检测是否在容器环境中运行"""
    # 方法1: 检查 /.dockerenv 文件
    if os.path.exists('/.dockerenv'):
        return True
    # 方法2: 检查 cgroup
    try:
        with open('/proc/self/cgroup', 'r') as f:
            return 'docker' in f.read() or 'containerd' in f.read()
    except:
        pass
    return False

# ==================== Git 更新模式 (本地部署) ====================

def get_remote_commit_hash():
    """获取远程仓库最新 commit hash"""
    try:
        result = subprocess.run(
            ['git', 'ls-remote', 'origin', 'HEAD'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return result.stdout.split()[0]
    except Exception as e:
        print(f"[SkoHit][AutoUpdate] Failed to get remote version: {e}")
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
        print(f"[SkoHit][AutoUpdate] Failed to get local version: {e}")
    return None

def get_default_branch():
    """获取远程默认分支名称"""
    try:
        result = subprocess.run(
            ['git', 'symbolic-ref', 'refs/remotes/origin/HEAD'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            # 输出格式: refs/remotes/origin/main
            return result.stdout.strip().split('/')[-1]
    except Exception:
        pass

    # 回退到常用分支名
    for branch in ['main', 'master']:
        try:
            result = subprocess.run(
                ['git', 'ls-remote', '--heads', 'origin', branch],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                return branch
        except Exception:
            continue

    return 'main'  # 默认回退到 main


def pull_latest_code():
    """拉取最新代码"""
    try:
        branch = get_default_branch()
        print(f"[SkoHit][AutoUpdate] Pulling latest code from origin/{branch}...")
        result = subprocess.run(
            ['git', 'pull', 'origin', branch],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            print("[SkoHit][AutoUpdate] Code updated successfully")
            return True
        else:
            print(f"[SkoHit][AutoUpdate] Code update failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"[SkoHit][AutoUpdate] Pull error: {e}")
        return False

def restart_service():
    """重启服务 - 启动新进程并退出当前进程"""
    print("[SkoHit][AutoUpdate] Restarting service...")

    args = sys.argv.copy()

    if sys.platform == 'win32':
        subprocess.Popen([sys.executable] + args,
                         creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        subprocess.Popen([sys.executable] + args,
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)

    print("[SkoHit][AutoUpdate] New process started, exiting current process")

    # 在容器中使用非零退出码，确保 Docker 的 restart 策略能正确重启容器
    if is_running_in_container():
        os._exit(42)  # 使用特殊退出码表示是更新重启
    else:
        os._exit(0)

def git_update_worker():
    """Git 模式更新工作线程"""
    global last_commit_hash

    last_commit_hash = get_local_commit_hash()
    current_version = last_commit_hash[:8] if last_commit_hash else 'unknown'
    print(f"[SkoHit][GitUpdate] Current version: {current_version}")
    print(f"[SkoHit][GitUpdate] Check interval: {UPDATE_CHECK_INTERVAL}s")

    check_count = 0
    while True:
        time.sleep(UPDATE_CHECK_INTERVAL)
        check_count += 1

        try:
            print(f"[SkoHit][GitUpdate] Check #{check_count}...")

            remote_hash = get_remote_commit_hash()
            if not remote_hash:
                print(f"[SkoHit][GitUpdate] Failed to get remote version, skip")
                continue

            local_short = last_commit_hash[:8] if last_commit_hash else 'none'
            remote_short = remote_hash[:8] if remote_hash else 'none'
            print(f"[SkoHit][GitUpdate] Local: {local_short}... Remote: {remote_short}...")

            if remote_hash != last_commit_hash:
                print(f"[SkoHit][GitUpdate] Update detected!")

                if pull_latest_code():
                    last_commit_hash = get_local_commit_hash()
                    print("[SkoHit][GitUpdate] Update complete, restarting...")
                    time.sleep(3)
                    restart_service()
                else:
                    print("[SkoHit][GitUpdate] Pull failed, cancel restart")
        except Exception as e:
            print(f"[SkoHit][GitUpdate] Error: {e}")



# ==================== 统一入口 ====================

def check_git_requirements():
    """检查 Git 环境要求"""
    is_container = is_running_in_container()
    mode_str = "container" if is_container else "local"
    print(f"[SkoHit] Running in {mode_str} mode, checking Git environment...")

    try:
        result = subprocess.run(['git', '--version'], capture_output=True, text=True)
        if result.returncode != 0:
            print("[SkoHit][FATAL] Git is not installed! Please install Git first.")
            return False
        print(f"[SkoHit] Git version: {result.stdout.strip()}")
    except Exception:
        print("[SkoHit][FATAL] Git is not installed! Please install Git first.")
        return False

    if not os.path.exists('.git'):
        print("[SkoHit][FATAL] Not a Git repository! Please run in a Git repo.")
        return False
    print("[SkoHit] Git repository found")

    try:
        result = subprocess.run(['git', 'remote', '-v'], capture_output=True, text=True)
        if 'origin' not in result.stdout:
            print("[SkoHit][FATAL] No remote 'origin' configured! Please set up Git remote.")
            return False
        print("[SkoHit] Git remote 'origin' configured")
    except Exception:
        print("[SkoHit][FATAL] Git remote check failed!")
        return False

    print("[SkoHit] Git environment check passed")
    return True

def start_auto_update():
    """启动自动更新线程 - 统一使用 Git 更新模式"""
    if not AUTO_UPDATE_ENABLED:
        print("[SkoHit][AutoUpdate] Auto-update is disabled")
        return

    # 统一使用 Git 更新模式（本地和容器都使用）
    is_container = is_running_in_container()
    mode_str = "Container" if is_container else "Local"
    print(f"[SkoHit][AutoUpdate] Mode: Git Source Update ({mode_str})")
    update_thread = Thread(target=git_update_worker, daemon=True)
    update_thread.start()
    print("[SkoHit][AutoUpdate] Git auto-update monitoring started")

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
# Main Entry Point
# ============================================

if __name__ == '__main__':
    init_db()

    import argparse
    parser = argparse.ArgumentParser(description='SkoHit Music Server')
    parser.add_argument('--port', type=int, default=7000, help='Port to run on (default: 7000)')
    args = parser.parse_args()

    # 检测运行环境
    if is_running_in_container():
        print("[SkoHit] Running in Docker container mode")
        print(f"[SkoHit] Version: {VERSION}")
    else:
        print("[SkoHit] Running in native mode")

    # 所有模式都检查 Git 环境（容器也需要 Git 来更新代码）
    if not check_git_requirements():
        print("[SkoHit][FATAL] Git environment check failed, exiting")
        sys.exit(1)

    # 启动自动更新监测
    start_auto_update()

    print(f"Server running on http://0.0.0.0:{args.port}")
    app.run(host="0.0.0.0", debug=True, port=args.port, use_reloader=False)
