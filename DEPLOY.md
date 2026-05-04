# 部署指南

## 自动更新功能（内置）

SkoHit Music 现在内置了**自动更新监测**功能！

### 工作原理

服务器启动后会自动：

```
每分钟检查一次远程仓库
       ↓
发现更新？
       ↓ 是
备份数据库（到项目目录之外）
       ↓
拉取最新代码
       ↓
更新完成，下次重启生效
```

### 数据库安全

**关键设计：**
- 备份目录放在**项目目录之外**（`../skohit_backup/`）
- `git pull` 不会覆盖备份目录
- `init_db()` 不会覆盖已有数据库
- `.gitignore` 已排除 `data/*.json`

### 使用方法

**1. 正常启动（启用自动更新）**
```bash
python app.py
```

**2. 禁用自动更新**
```bash
python app.py --no-auto-update
```

### 服务器控制台输出示例

```
[AutoUpdate] 当前版本: abc1234
[AutoUpdate] 更新检查间隔: 60秒
[AutoUpdate] 自动更新监测已启动
API Service running on http://0.0.0.0:8000
Main App running on http://0.0.0.0:7000
...
[AutoUpdate] 检测到更新!
[AutoUpdate] 本地: abc1234
[AutoUpdate] 远程: def5678
[AutoUpdate] 用户数据库已备份: /home/user/skohit_backup/users.json.20260504_120000
[AutoUpdate] 收藏数据库已备份: /home/user/skohit_backup/favorites.json.20260504_120000
[AutoUpdate] 正在拉取最新代码...
[AutoUpdate] 代码更新成功
[AutoUpdate] 更新完成，服务将在下次重启后生效
[AutoUpdate] 提示: 如需立即生效，请手动重启服务
```

### 更新后重启服务

代码已更新，但需要重启才能生效：

```bash
# 查找并杀死进程
pkill -f "python app.py"

# 重新启动
python app.py
```

或者使用 systemd（推荐）：
```bash
sudo systemctl restart skohit-music
```

---

## 手动部署（备用方案）

如果自动更新出现问题，可手动执行：

```bash
# 1. 进入项目目录
cd /path/to/SkoHit-Music

# 2. 备份数据库（可选但推荐）
cp data/users.json ~/backup_users.json
cp data/favorites.json ~/backup_favorites.json

# 3. 拉取最新代码
git pull origin master

# 4. 安装依赖
pip install -r requirements.txt

# 5. 重启服务
pkill -f "python app.py"
python app.py
```

---

## 系统服务配置（Linux）

使用 systemd 实现开机自启和自动重启：

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
ExecStart=/usr/bin/python3 /opt/SkoHit-Music/app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启用服务：
```bash
sudo systemctl daemon-reload
sudo systemctl enable skohit-music
sudo systemctl start skohit-music
```

查看状态：
```bash
sudo systemctl status skohit-music
sudo journalctl -u skohit-music -f  # 实时查看日志
```

---

## 常见问题

### Q: 自动更新会删除我的用户数据吗？

**不会！** 三重保护：
1. 备份目录在项目之外（`../skohit_backup/`）
2. `init_db()` 只创建空文件，不覆盖已有数据
3. `.gitignore` 排除数据库文件

### Q: 更新后需要手动重启吗？

**是的**。代码更新后需要重启服务才能生效。这是为了：
- 确保代码变更完全加载
- 避免运行时冲突
- 保证服务稳定性

### Q: 如何查看备份的数据库？

```bash
ls ../skohit_backup/
# 或
cat ../skohit_backup/users.json.20260504_120000
```

### Q: 自动更新失败了怎么办？

查看日志排查问题：
```bash
# 如果使用 systemd
sudo journalctl -u skohit-music -f

# 如果直接运行
python app.py  # 查看控制台输出
```

常见问题：
- **Git 权限问题**：确保服务器有拉取权限（使用 HTTPS 或配置 SSH 密钥）
- **网络问题**：检查服务器能否访问 GitHub
- **磁盘空间不足**：清理日志或备份文件

### Q: 可以调整检查间隔吗？

修改 `app.py` 中的 `UPDATE_CHECK_INTERVAL`：
```python
UPDATE_CHECK_INTERVAL = 300  # 改为 5 分钟
```

### Q: 如何完全禁用自动更新？

启动时加参数：
```bash
python app.py --no-auto-update
```

---

## 备份恢复

如果数据库损坏，可从备份恢复：

```bash
# 查看最新备份
ls -la ../skohit_backup/

# 恢复
 cp ../skohit_backup/users.json.20260504_120000 data/users.json
cp ../skohit_backup/favorites.json.20260504_120000 data/favorites.json

# 重启服务
sudo systemctl restart skohit-music
```
