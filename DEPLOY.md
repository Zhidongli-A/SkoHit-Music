# 部署指南

## 问题解答

### 为什么服务器有数据库文件，而本地没有？

这是**正常现象**！

1. **本地开发环境**：没有运行过应用或运行后删除了 `data/` 目录
2. **服务器环境**：运行应用后，`json_db.py` 中的 `init_db()` 自动创建了空的数据库文件
3. **Git 管理**：`.gitignore` 已配置 `data/*.json`，数据库文件不会被提交到 Git

### 服务器端数据库会被代码推送覆盖吗？

**不会！**

- `data/*.json` 在 `.gitignore` 中，Git 不会跟踪这些文件
- 使用 `git reset --hard origin/master` 只会重置被跟踪的文件
- 服务器端的数据库文件会保留，不受代码更新影响

---

## 部署方案

### 方案一：手动部署（推荐）

在服务器上直接运行部署脚本：

**Linux/Mac:**
```bash
chmod +x deploy.sh
./deploy.sh
```

**Windows:**
```cmd
deploy.bat
```

### 方案二：GitHub Actions 自动部署

配置步骤：

1. **在 GitHub 仓库设置 Secrets**：
   - `SERVER_HOST`: 服务器 IP 地址
   - `SERVER_USER`: SSH 用户名
   - `SERVER_PASSWORD`: SSH 密码（或 `SERVER_SSH_KEY` SSH 密钥）
   - `PROJECT_PATH`: 服务器上的项目路径（如 `/opt/SkoHit-Music`）
   - `SERVER_PORT`: SSH 端口（默认 22，可选）

2. **推送代码自动触发部署**：
   ```bash
   git push origin master
   ```
   GitHub Actions 会自动执行部署流程。

### 方案三：Webhook 自动部署

在服务器上配置 Git Webhook：

1. **创建 webhook 脚本**（服务器端）：
   ```bash
   #!/bin/bash
   # /opt/deploy-hook.sh
   
   cd /opt/SkoHit-Music
   git pull origin master
   pip3 install -r requirements.txt
   systemctl restart skohit-music
   ```

2. **设置 GitHub Webhook**：
   - 仓库 Settings -> Webhooks -> Add webhook
   - Payload URL: `http://你的服务器:端口号/webhook`
   - Content type: `application/json`
   - Events: Push

---

## 部署流程说明

每次部署执行以下步骤：

1. **备份数据库**
   ```bash
   cp data/*.json backup/
   ```

2. **拉取最新代码**
   ```bash
   git fetch origin
   git reset --hard origin/master
   ```
   > 注意：`reset --hard` 只会影响被 Git 跟踪的文件，`.gitignore` 中的数据库文件不受影响。

3. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

4. **检查数据库**
   ```python
   python -c "import json_db; json_db.init_db()"
   ```
   > 如果数据库文件不存在会自动创建空文件，已存在则保持不变。

5. **重启服务**
   ```bash
   systemctl restart skohit-music
   # 或使用其他方式重启
   ```

---

## 常见问题

### Q: 如何查看服务器端数据库内容？

```bash
ssh user@server
cd /path/to/SkoHit-Music
cat data/users.json
```

### Q: 服务器数据库如何迁移到新服务器？

```bash
# 1. 备份原服务器数据库
scp -r user@old-server:/path/to/SkoHit-Music/data/* ./backup/

# 2. 在新服务器上恢复
cp backup/* /path/to/SkoHit-Music/data/
```

### Q: 数据库文件被意外删除了怎么办？

部署脚本会在 `backup/` 目录保留备份：
```bash
cp backup/*.json data/
```

### Q: 如何避免服务器数据库被清空？

- **不要**手动删除服务器上的 `data/` 目录
- **不要**修改 `.gitignore` 让数据库文件被 Git 跟踪
- 定期备份：`cp -r data backup/$(date +%Y%m%d)`

---

## 系统服务配置（Linux）

创建系统服务实现开机自启：

```bash
sudo nano /etc/systemd/system/skohit-music.service
```

内容：
```ini
[Unit]
Description=SkoHit Music
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/SkoHit-Music
ExecStart=/usr/bin/python3 app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

启用服务：
```bash
sudo systemctl daemon-reload
sudo systemctl enable skohit-music
sudo systemctl start skohit-music
```
