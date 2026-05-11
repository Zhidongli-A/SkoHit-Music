# SkoHit Music - Docker 镜像
FROM python:3.11-slim

# 构建参数 - 用于注入版本号
ARG VERSION=dev
ENV APP_VERSION=${VERSION}

# 强制 Python 无缓冲输出，确保日志实时显示
ENV PYTHONUNBUFFERED=1

# 设置工作目录
WORKDIR /app

# 安装系统依赖（包括 Git）
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码（包括 .git 目录）
COPY . .

# 设置 .git 目录权限（确保可写，以便 git pull 可以更新）
RUN chmod -R 755 .git 2>/dev/null || true

# 创建数据目录
RUN mkdir -p data

# 暴露端口
EXPOSE 7000

# 启动命令
CMD ["python", "app.py"]
