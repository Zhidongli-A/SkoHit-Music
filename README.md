# SkoHit Music 🎵

一个依赖于 Meting 的免费音乐项目。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 功能特性

- 🔐 用户注册/登录系统
- ❤️ 收藏喜爱的歌曲
- 📊 实时在线用户统计
- 🔍 歌单搜索与浏览
- 📱 响应式 Web 界面
- 🎧 基于 Meting API 的音乐播放

## 技术栈

- **后端**: Flask (Python)
- **数据库**: JSON 文件存储
- **前端**: HTML5 + CSS3 + JavaScript
- **音乐 API**: Meting API

## 快速开始

### 环境要求

- Python 3.8+

### 安装步骤

1. 克隆仓库

```bash
git clone https://github.com/Zhidongli-A/SkoHit-Music.git
cd SkoHit-Music
```

2. 安装依赖

```bash
pip install -r requirements.txt
```

3. 运行应用

```bash
python app.py
```

或使用启动脚本：

```bash
start.bat
```

4. 打开浏览器访问 `http://localhost:7000`

## API 文档

### 用户认证

- `POST /login` - 用户登录
- `POST /register` - 用户注册
- `GET /logout` - 退出登录

### 收藏管理

- `GET /api/favorites` - 获取用户收藏列表
- `POST /api/favorites` - 添加收藏
- `DELETE /api/favorites?id={song_id}` - 删除收藏

### 音乐数据

- `GET /api/meting` - Meting API 代理
- `GET /api/163/toplist` - 获取网易云音乐排行榜
- `GET /api/163/playlists` - 获取歌单列表

### 统计信息

- `GET /api/stats` - 获取在线用户统计

### 管理 API

- `GET /api/users` - 获取所有用户
- `GET /api/users/{id}` - 获取指定用户
- `POST /api/users` - 创建用户
- `PUT /api/users/{id}` - 更新用户
- `DELETE /api/users/{id}` - 删除用户

## 项目结构

```
SkoHit-Music/
├── app.py              # 主应用入口
├── json_db.py          # JSON 数据库操作
├── requirements.txt    # Python 依赖
├── start.bat          # Windows 启动脚本
├── data/              # 数据存储目录
│   ├── users.json     # 用户数据
│   └── favorites.json # 收藏数据
├── static/            # 静态资源
│   ├── css/
│   └── js/
└── templates/         # HTML 模板
    ├── index.html
    └── login.html
```

## 许可证

本项目采用 [MIT License](LICENSE) 开源许可证。

Copyright (c) 2026 枝动力

## 致谢

- [Meting](https://github.com/metowolf/Meting) - 强大的音乐 API 框架
