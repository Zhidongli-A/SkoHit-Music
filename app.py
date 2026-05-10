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
UPDATE_IMAGE = os.getenv('UPDATE_IMAGE', 'skohit/skohit-music:latest')
CONTAINER_NAME = os.getenv('CONTAINER_NAME', 'skohit-music')

last_commit_hash = None
last_image_digest = None

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

def pull_latest_code():
    """拉取最新代码"""
    try:
        print("[SkoHit][AutoUpdate] Pulling latest code...")
        result = subprocess.run(
            ['git', 'pull', 'origin', 'master'],
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
    os._exit(0)

def git_update_worker():
    """Git 模式更新工作线程"""
    global last_commit_hash
    
    last_commit_hash = get_local_commit_hash()
    print(f"[SkoHit][GitUpdate] Current version: {last_commit_hash[:8] if last_commit_hash else 'unknown'}")
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
            
            print(f"[SkoHit][GitUpdate] Local: {last_commit_hash[:8] if last_commit_hash else 'none'}... Remote: {remote_hash[:8]}...")
            
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

# ==================== Docker 更新模式 (容器部署) ====================

def get_docker_client():
    """获取 Docker 客户端，支持多种连接方式"""
    import docker
    
    # 1. 首先尝试从环境变量获取 Docker 主机地址
    # 支持 DOCKER_HOST=tcp://host:port 或 DOCKER_HOST=unix:///path/to.sock
    docker_host = os.getenv('DOCKER_HOST', '').strip()
    
    if docker_host:
        print(f"[SkoHit][DockerUpdate] Using DOCKER_HOST: {docker_host}")
        return docker.DockerClient(base_url=docker_host)
    
    # 2. 尝试默认方式 (从环境变量或默认 socket)
    try:
        client = docker.from_env()
        # 测试连接
        client.ping()
        return client
    except Exception as e:
        # 检查 socket 文件是否存在
        default_sock = '/var/run/docker.sock'
        if os.path.exists(default_sock):
            print(f"[SkoHit][DockerUpdate] Socket exists but connection failed: {e}")
        else:
            print(f"[SkoHit][DockerUpdate] Docker socket not found at {default_sock}")
            print(f"[SkoHit][DockerUpdate] Please ensure:")
            print(f"  1. Docker is running on the host")
            print(f"  2. /var/run/docker.sock is mounted to container")
            print(f"  3. Or set DOCKER_HOST environment variable (e.g., tcp://host:2375)")
        raise

def get_image_digest(image_name):
    """获取镜像的 digest"""
    try:
        client = get_docker_client()
        image = client.images.get(image_name)
        if image.attrs.get('RepoDigests'):
            return image.attrs['RepoDigests'][0].split('@')[1]
    except Exception as e:
        print(f"[SkoHit][DockerUpdate] Failed to get local digest: {e}")
    return None

def get_remote_image_digest(image_name):
    """获取远程仓库镜像 digest"""
    try:
        client = get_docker_client()
        # 查询 registry 不拉取
        distribution = client.api.inspect_distribution(image_name)
        if 'Descriptor' in distribution:
            return distribution['Descriptor']['digest']
    except Exception as e:
        print(f"[SkoHit][DockerUpdate] Failed to get remote digest: {e}")
    return None

def parse_bind_mount(bind):
    r"""
    安全地解析 bind mount 字符串，支持 Windows 和 Linux 路径
    格式: host_path:container_path[:mode]
    Windows 示例: C:\data:/app/data:rw
    Linux 示例: /var/data:/app/data:ro
    """
    # 找到最后一个冒号后面是否是 mode (ro/rw)
    # 从右向左找，最后一个冒号如果是 rw 或 ro，则是 mode
    parts = bind.rsplit(':', 2)
    
    if len(parts) == 3 and parts[2] in ('ro', 'rw'):
        # host_path:container_path:mode
        host_path = parts[0]
        container_path = parts[1]
        mode = parts[2]
    elif len(parts) >= 2:
        # host_path:container_path (default mode: rw)
        host_path = parts[0] if len(parts) == 2 else ':'.join(parts[:-1])
        container_path = parts[-1]
        mode = 'rw'
    else:
        return None
    
    return {'host_path': host_path, 'container_path': container_path, 'mode': mode}


def convert_port_bindings(port_bindings):
    """
    将 PortBindings 格式转换为 ports 格式
    PortBindings: {'7000/tcp': [{'HostIp': '', 'HostPort': '7000'}]}
    ports: {'7000/tcp': 7000} 或 {'7000/tcp': ('0.0.0.0', 7000)}
    """
    ports = {}
    for container_port, bindings in port_bindings.items():
        if bindings:
            for binding in bindings:
                host_ip = binding.get('HostIp', '0.0.0.0')
                host_port = binding.get('HostPort')
                if host_port:
                    if host_ip and host_ip != '0.0.0.0':
                        ports[container_port] = (host_ip, int(host_port))
                    else:
                        ports[container_port] = int(host_port)
    return ports


def convert_restart_policy(restart_policy):
    """
    将 HostConfig.RestartPolicy 转换为 docker-py 可用的格式
    HostConfig: {'Name': 'unless-stopped', 'MaximumRetryCount': 0}
    docker-py: {'Name': 'unless-stopped'} 或 {'Name': 'on-failure', 'MaximumRetryCount': 5}
    """
    if not restart_policy or not restart_policy.get('Name'):
        return {'Name': 'unless-stopped'}
    
    result = {'Name': restart_policy['Name']}
    if restart_policy['Name'] == 'on-failure' and restart_policy.get('MaximumRetryCount', 0) > 0:
        result['MaximumRetryCount'] = restart_policy['MaximumRetryCount']
    return result


def docker_self_update():
    """Docker 容器自更新 - 方案一：先删后建"""
    try:
        import docker
        client = get_docker_client()
        
        print(f"[SkoHit][DockerUpdate] Starting self-update...")
        print(f"[SkoHit][DockerUpdate] Target image: {UPDATE_IMAGE}")
        print(f"[SkoHit][DockerUpdate] Container name: {CONTAINER_NAME}")
        
        # 1. 拉取最新镜像
        print("[SkoHit][DockerUpdate] Pulling latest image...")
        client.images.pull(UPDATE_IMAGE)
        print("[SkoHit][DockerUpdate] Image pulled successfully")
        
        # 2. 获取当前容器的配置
        current_container = None
        current_config = None
        try:
            current_container = client.containers.get(CONTAINER_NAME)
            # 保存配置用于重建
            host_config = current_container.attrs['HostConfig']
            config = current_container.attrs['Config']
            
            # 转换端口映射格式
            port_bindings = host_config.get('PortBindings', {})
            ports = convert_port_bindings(port_bindings)
            
            # 转换 restart_policy 格式
            restart_policy = convert_restart_policy(host_config.get('RestartPolicy'))
            
            current_config = {
                'image': UPDATE_IMAGE,
                'name': CONTAINER_NAME,
                'detach': True,
                'ports': ports,
                'volumes': {},
                'environment': config.get('Env', []),
                'restart_policy': restart_policy,
                'network_mode': host_config.get('NetworkMode'),
            }
            
            # 处理卷挂载 - 使用安全的解析方法
            binds = host_config.get('Binds', [])
            for bind in binds:
                parsed = parse_bind_mount(bind)
                if parsed:
                    current_config['volumes'][parsed['host_path']] = {
                        'bind': parsed['container_path'],
                        'mode': parsed['mode']
                    }
                    print(f"[SkoHit][DockerUpdate] Volume: {parsed['host_path']} -> {parsed['container_path']} ({parsed['mode']})")
                else:
                    print(f"[SkoHit][DockerUpdate] Warning: Failed to parse bind mount: {bind}")
            
            print(f"[SkoHit][DockerUpdate] Port config: {ports}")
            print(f"[SkoHit][DockerUpdate] Restart policy: {restart_policy}")
            
        except docker.errors.NotFound:
            print(f"[SkoHit][DockerUpdate] Container {CONTAINER_NAME} not found, using default config")
            current_config = {
                'image': UPDATE_IMAGE,
                'name': CONTAINER_NAME,
                'detach': True,
                'ports': {7000: 7000},
                'volumes': {
                    '/var/run/docker.sock': {'bind': '/var/run/docker.sock', 'mode': 'rw'}
                },
                'environment': ['AUTO_UPDATE=true', 'CONTAINER_MODE=true'],
                'restart_policy': {'Name': 'unless-stopped'}
            }
        
        # 3. 停止并删除旧容器（释放名称和端口）
        if current_container:
            print("[SkoHit][DockerUpdate] Stopping old container...")
            try:
                current_container.stop(timeout=10)
                current_container.remove(force=True)
                print("[SkoHit][DockerUpdate] Old container removed")
            except Exception as e:
                print(f"[SkoHit][DockerUpdate] Warning: failed to remove old container: {e}")
        
        # 等待一下确保端口释放
        time.sleep(2)
        
        # 4. 启动新容器
        print("[SkoHit][DockerUpdate] Starting new container...")
        print(f"[SkoHit][DockerUpdate] Config: {current_config}")
        new_container = client.containers.run(**current_config)
        print(f"[SkoHit][DockerUpdate] New container started: {new_container.short_id}")
        
        # 5. 自己退出
        print("[SkoHit][DockerUpdate] Update complete, exiting...")
        time.sleep(2)
        os._exit(0)
        
    except Exception as e:
        print(f"[SkoHit][DockerUpdate] Update failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def docker_update_worker():
    """Docker 模式更新工作线程"""
    global last_image_digest
    
    print(f"[SkoHit][DockerUpdate] Container mode enabled")
    print(f"[SkoHit][DockerUpdate] Image: {UPDATE_IMAGE}")
    print(f"[SkoHit][DockerUpdate] Check interval: {UPDATE_CHECK_INTERVAL}s")
    
    # 获取当前镜像 digest
    last_image_digest = get_image_digest(UPDATE_IMAGE)
    print(f"[SkoHit][DockerUpdate] Current digest: {last_image_digest[:19] if last_image_digest else 'unknown'}...")
    
    check_count = 0
    while True:
        time.sleep(UPDATE_CHECK_INTERVAL)
        check_count += 1
        
        try:
            print(f"[SkoHit][DockerUpdate] Check #{check_count}...")
            
            # 获取远程 digest
            remote_digest = get_remote_image_digest(UPDATE_IMAGE)
            if not remote_digest:
                print(f"[SkoHit][DockerUpdate] Failed to get remote digest, skip")
                continue
            
            print(f"[SkoHit][DockerUpdate] Local: {last_image_digest[:19] if last_image_digest else 'none'}... Remote: {remote_digest[:19]}...")
            
            if remote_digest != last_image_digest:
                print(f"[SkoHit][DockerUpdate] Update detected!")
                if docker_self_update():
                    print("[SkoHit][DockerUpdate] Self-update triggered")
                    # docker_self_update 会调用 os._exit(0)，这里不会执行
                else:
                    print("[SkoHit][DockerUpdate] Self-update failed")
            else:
                print(f"[SkoHit][DockerUpdate] Already up to date")
                
        except Exception as e:
            print(f"[SkoHit][DockerUpdate] Error: {e}")

# ==================== 统一入口 ====================

def check_git_requirements():
    """检查 Git 环境要求"""
    if is_running_in_container():
        print("[SkoHit] Running in container, skip Git check")
        return True
        
    try:
        result = subprocess.run(['git', '--version'], capture_output=True, text=True)
        if result.returncode != 0:
            print("[SkoHit][FATAL] Git is not installed! Please install Git first.")
            return False
    except Exception:
        print("[SkoHit][FATAL] Git is not installed! Please install Git first.")
        return False
    
    if not os.path.exists('.git'):
        print("[SkoHit][FATAL] Not a Git repository! Please run in a Git repo.")
        return False
    
    try:
        result = subprocess.run(['git', 'remote', '-v'], capture_output=True, text=True)
        if 'origin' not in result.stdout:
            print("[SkoHit][FATAL] No remote 'origin' configured! Please set up Git remote.")
            return False
    except Exception:
        print("[SkoHit][FATAL] Git remote check failed!")
        return False
    
    print("[SkoHit] Git environment check passed")
    return True

def start_auto_update():
    """启动自动更新线程 - 根据环境自动选择模式"""
    if not AUTO_UPDATE_ENABLED:
        print("[SkoHit][AutoUpdate] Auto-update is disabled")
        return
    
    if is_running_in_container():
        # 容器模式 - 使用 Docker 自更新
        print("[SkoHit][AutoUpdate] Mode: Docker Container Self-Update")
        update_thread = Thread(target=docker_update_worker, daemon=True)
        update_thread.start()
        print("[SkoHit][AutoUpdate] Docker auto-update monitoring started")
    else:
        # 本地模式 - 使用 Git 更新
        print("[SkoHit][AutoUpdate] Mode: Git Source Update")
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
        print(f"[SkoHit] Image: {UPDATE_IMAGE}")
    else:
        print("[SkoHit] Running in native mode")
        # 本地模式检查 Git 环境
        if not check_git_requirements():
            print("[SkoHit][FATAL] Git environment check failed, exiting")
            sys.exit(1)

    # 启动自动更新监测
    start_auto_update()

    print(f"Server running on http://0.0.0.0:{args.port}")
    app.run(host="0.0.0.0", debug=True, port=args.port, use_reloader=False)
