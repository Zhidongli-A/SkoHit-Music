# SkoHit Music - Docker 镜像
FROM python:3.11-slim

# 安装 Git（强制依赖）
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 创建数据目录
RUN mkdir -p data

# 设置环境变量（Docker 环境下跳过 Git 检查）
ENV SKIP_GIT_CHECK=true

# 暴露端口
EXPOSE 7000

# 启动命令
CMD ["python", "app.py"]
