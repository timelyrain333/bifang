# Bifang 后端（仅 API + Admin，前端独立部署于 frontend 服务）
FROM python:3.11-slim-bookworm
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# 系统依赖（curl；mysqlclient 编译需 gcc、pkg-config、libmysqlclient）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    pkg-config \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 后端依赖
COPY requirements.txt ./
RUN pip install --no-cache-dir --timeout 300 -r requirements.txt

# 后端代码与入口脚本
COPY manage.py ./
COPY app ./app/
COPY bifang ./bifang/
COPY docker/entrypoint.sh /app/docker/entrypoint.sh
RUN chmod +x /app/docker/entrypoint.sh

RUN mkdir -p staticfiles logs

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
