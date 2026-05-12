# SkoHit Music

一个依赖于 Meting 的免费音乐项目。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 项目原理

SkoHit Music 是一个基于 Flask 的 Web 音乐应用，通过代理 Meting API 来获取音乐数据。项目采用 JSON 文件作为轻量级数据库，实现了用户系统和收藏功能。

应用的工作流程如下：

1. 用户通过 Web 界面登录系统，会话数据存储在服务端
2. 前端通过 AJAX 请求调用后端 API 获取音乐数据
3. 后端通过 Meting API 代理请求网易云音乐等平台的歌单、歌曲信息
4. 用户收藏的歌曲 ID 会存储在本地 JSON 数据库中
5. 播放时，前端通过 Meting API 获取真实的音乐播放地址

## 功能特性

用户注册与登录系统、收藏喜爱的歌曲、实时在线用户统计、歌单搜索与浏览、响应式 Web 界面、基于 Meting API 的音乐播放。

## 技术栈

Flask (Python)、JSON 文件存储、HTML5 + CSS3 + JavaScript、Meting API

## 快速开始

### 方式一：Docker 部署（推荐）

#### 环境要求

- Docker
- Docker Compose

#### 部署步骤

**1. 创建配置文件**

新建 `docker-compose.yml` 文件，粘贴以下内容：

```yaml
version: '3.8'

services:
  skohit-music:
    image: skohit/skohit-music:latest
    container_name: skohit-music
    ports:
      - "7000:7000"
    environment:
      # Meting API 地址（必填）- 修改为你的 API 地址
      - METING_API_URL=https://your-meting-api.com/api
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

**2. 启动容器**

```bash
docker-compose up -d
```

**3. 访问应用**

打开浏览器访问 `http://localhost:7000`

#### 更新版本

```bash
docker-compose pull && docker-compose up -d
```

---

### 方式二：本地部署

#### 环境要求

- Python 3.8+
- Git

#### 安装步骤

**1. 克隆仓库**

```bash
git clone https://github.com/Zhidongli-A/SkoHit-Music.git
cd SkoHit-Music
```

**2. 安装依赖**

```bash
pip install -r requirements.txt
```

**3. 配置环境变量**

```bash
cp .env.example .env
```

编辑 `.env` 文件，设置你的 Meting API 地址：

```
METING_API_URL=http://your-meting-api-server:3000/api
```

**4. 运行应用**

```bash
python app.py
```

或使用启动脚本：

```bash
# Windows
start.bat

# Linux/Mac
./start.sh
```

**5. 访问应用**

打开浏览器访问 `http://localhost:7000`

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
├── app.py                    # 主应用入口
├── json_db.py                # JSON 数据库操作
├── requirements.txt          # Python 依赖
├── .env.example              # 环境变量示例配置
├── .env                      # 环境变量（本地配置，不提交到 Git）
├── .gitignore               # Git 忽略文件
├── Dockerfile               # Docker 镜像构建文件
├── docker-compose.yml       # Docker Compose 配置
├── .dockerignore            # Docker 构建忽略文件
├── start.bat                # Windows 启动脚本
├── start.sh                 # Linux/Mac 启动脚本
├── data/                    # 数据存储目录（自动创建）
│   ├── users.json           # 用户数据
│   └── favorites.json       # 收藏数据
├── static/                  # 静态资源
│   ├── css/
│   └── js/
└── templates/               # HTML 模板
    ├── index.html
    └── login.html
```

## 获取 Meting API

SkoHit Music 依赖 Meting API 获取音乐数据，您可以：

- 使用公共 API（自行寻找）
- 自行部署：[Meting API 项目地址](https://github.com/metowolf/Meting)

## 许可证

本项目采用 [MIT License](LICENSE) 开源许可证。

Copyright 2026 枝动力

## 致谢

- [Meting](https://github.com/metowolf/Meting) - 免费的音乐 API 框架
