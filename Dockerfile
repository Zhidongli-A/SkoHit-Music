# SkoHit Music - Docker 镜像
FROM python:3.11-slim

# 构建参数 - 用于注入版本号
ARG VERSION=dev
ENV APP_VERSION=${VERSION}

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

# 暴露端口
EXPOSE 7000

# 启动命令
CMD ["python", "app.py"]
