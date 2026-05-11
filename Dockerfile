# SkoHit Music - Docker 镜像
FROM python:3.11-slim

# 构建参数 - 用于注入版本号
ARG VERSION=dev
ENV APP_VERSION=${VERSION}

# 强制 Python 无缓冲输出，确保日志实时显示
ENV PYTHONUNBUFFERED=1

# 禁用 Git 交互式用户名密码提示（公开仓库匿名访问）
ENV GIT_TERMINAL_PROMPT=0

# 设置工作目录
WORKDIR /app

# 安装系统依赖（包括 Git）
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖（使用清华大学镜像源）
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 复制项目代码（包括 .git 目录）
COPY . .

# 设置 .git 目录权限（确保可写，以便 git pull 可以更新）
RUN chmod -R 755 .git 2>/dev/null || true

# 配置 Git 全局设置（容器内需要）
RUN git config --global user.email "docker@skohit.local" && \
    git config --global user.name "SkoHit Docker" && \
    git config --global pull.rebase false && \
    git remote set-url origin https://git:@github.com/Zhidongli-A/SkoHit-Music.git

# 创建数据目录
RUN mkdir -p data

# 暴露端口
EXPOSE 7000

# 启动命令
CMD ["python", "app.py"]
