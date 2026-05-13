import json
import os
import hashlib
import threading
from typing import List, Dict, Optional, Any

DATA_DIR = 'data'
AVATARS_DIR = os.path.join(DATA_DIR, 'avatars')
USERS_FILE = os.path.join(DATA_DIR, 'users.json')
FAVORITES_FILE = os.path.join(DATA_DIR, 'favorites.json')

def _ensure_avatars_dir():
    """确保头像目录存在"""
    if not os.path.exists(AVATARS_DIR):
        os.makedirs(AVATARS_DIR)

_lock = threading.Lock()

def _ensure_data_dir():
    """确保数据目录存在"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def _load_json(filepath: str) -> List[Dict]:
    """加载 JSON 文件，如果不存在返回空列表"""
    with _lock:
        if not os.path.exists(filepath):
            return []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

def _save_json(filepath: str, data: List[Dict]):
    """保存数据到 JSON 文件"""
    _ensure_data_dir()
    with _lock:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

# --- Users ---

def init_db():
    """初始化数据库（确保文件存在）"""
    _ensure_data_dir()
    _ensure_avatars_dir()
    if not os.path.exists(USERS_FILE):
        _save_json(USERS_FILE, [])
    if not os.path.exists(FAVORITES_FILE):
        _save_json(FAVORITES_FILE, [])

def _get_all_users() -> List[Dict]:
    """获取所有用户（内部使用）"""
    return _load_json(USERS_FILE)

def get_user_by_username(username: str) -> Optional[Dict]:
    """根据用户名获取用户"""
    users = _get_all_users()
    for user in users:
        if user.get('username') == username:
            return user
    return None

def create_user(username: str, password: str) -> Dict:
    """创建新用户"""
    users = _get_all_users()
    
    # 生成新 ID
    new_id = 1
    if users:
        new_id = max(u.get('id', 0) for u in users) + 1
    
    hashed_password = hashlib.md5(password.encode()).hexdigest()
    
    new_user = {
        'id': new_id,
        'username': username,
        'password': hashed_password
    }
    
    users.append(new_user)
    _save_json(USERS_FILE, users)
    
    return new_user

def verify_user(username: str, password: str) -> Optional[Dict]:
    """验证用户密码"""
    user = get_user_by_username(username)
    if user:
        hashed = hashlib.md5(password.encode()).hexdigest()
        if user.get('password') == hashed:
            return user
    return None

def count_users() -> int:
    """获取用户总数"""
    return len(_get_all_users())

def update_user(user_id: int, new_username: str = None, new_password: str = None) -> Dict:
    """更新用户信息"""
    users = _get_all_users()
    user = None
    user_index = -1
    
    for i, u in enumerate(users):
        if u.get('id') == user_id:
            user = u
            user_index = i
            break
    
    if user is None:
        return {'success': False, 'message': '用户不存在'}
    
    # 检查新用户名是否已被其他用户使用
    if new_username and new_username != user.get('username'):
        for u in users:
            if u.get('id') != user_id and u.get('username') == new_username:
                return {'success': False, 'message': '用户名已被使用', 'field': 'new_username'}
        user['username'] = new_username
    
    # 更新密码
    if new_password:
        user['password'] = hashlib.md5(new_password.encode()).hexdigest()
    
    users[user_index] = user
    _save_json(USERS_FILE, users)
    
    return {'success': True, 'user': user}

def get_user_avatar_path(user_id: int) -> str:
    """获取用户头像路径"""
    _ensure_avatars_dir()
    avatar_path = os.path.join(AVATARS_DIR, f'{user_id}.png')
    if os.path.exists(avatar_path):
        return avatar_path
    return None

def save_user_avatar(user_id: int, image_data: bytes) -> bool:
    """保存用户头像"""
    try:
        _ensure_avatars_dir()
        avatar_path = os.path.join(AVATARS_DIR, f'{user_id}.png')
        with open(avatar_path, 'wb') as f:
            f.write(image_data)
        return True
    except Exception as e:
        print(f"Error saving avatar: {e}")
        return False

# --- Favorites (简化版，仅存储 song_id) ---

def get_user_favorites(user_id: int) -> List[str]:
    """获取用户的收藏歌曲 ID 列表"""
    favorites = _load_json(FAVORITES_FILE)
    result = []
    for fav in favorites:
        if fav.get('user_id') == user_id:
            song_id = fav.get('song_id')
            if song_id and song_id not in result:
                result.append(song_id)
    return result

def add_favorite(user_id: int, song_id: str) -> bool:
    """添加收藏"""
    if not song_id:
        return False
    
    favorites = _load_json(FAVORITES_FILE)
    
    # 检查是否已存在
    for fav in favorites:
        if fav.get('user_id') == user_id and fav.get('song_id') == song_id:
            return False  # 已存在
    
    # 生成新 ID
    new_id = 1
    if favorites:
        new_id = max(f.get('id', 0) for f in favorites) + 1
    
    new_favorite = {
        'id': new_id,
        'user_id': user_id,
        'song_id': song_id
    }
    
    favorites.append(new_favorite)
    _save_json(FAVORITES_FILE, favorites)
    return True

def remove_favorite(user_id: int, song_id: str) -> bool:
    """移除收藏"""
    favorites = _load_json(FAVORITES_FILE)
    original_len = len(favorites)
    favorites = [f for f in favorites if not (f.get('user_id') == user_id and f.get('song_id') == song_id)]
    if len(favorites) < original_len:
        _save_json(FAVORITES_FILE, favorites)
        return True
    return False
