#!/bin/bash

# Bifang 系统启动脚本

echo "================================"
echo "Bifang 云端网络安全威胁感知系统"
echo "================================"
echo ""

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到Python3，请先安装Python 3.8+"
    exit 1
fi

# 检查 Redis 是否可达（支持本机 redis-cli 或 Docker 暴露的 6379 端口）
_redis_ok=0
if command -v redis-cli &> /dev/null && redis-cli ping &> /dev/null; then
    _redis_ok=1
fi
if [ $_redis_ok -eq 0 ]; then
    # 无 redis-cli 或 ping 失败时，用 Python 检测端口（适用于 Docker 启动的 Redis）
    if python3 -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(2)
try:
    s.connect(('127.0.0.1', 6379))
    s.close()
except Exception:
    exit(1)
" 2>/dev/null; then
        _redis_ok=1
    fi
fi
if [ $_redis_ok -eq 0 ]; then
    echo "警告: Redis 不可达（未找到 redis-cli 且 127.0.0.1:6379 无响应）"
    echo "若 Redis 通过 Docker 启动，请确保已映射 6379 端口，例如: docker run -d -p 6379:6379 redis"
    exit 1
fi
echo "   Redis 检查通过"

echo "1. 检查依赖..."
if [ ! -f "venv/bin/activate" ]; then
    echo "   创建虚拟环境..."
    python3 -m venv venv
fi

echo "   激活虚拟环境..."
source venv/bin/activate

echo "   安装依赖..."
pip install -r requirements.txt -q

echo ""
echo "2. 检查数据库迁移..."
python manage.py migrate --no-input

echo ""
echo "3. 加载插件..."
python manage.py load_plugins

echo ""
echo "================================"
echo "启动服务..."
echo "================================"
echo ""
echo "提示: 使用 Ctrl+C 停止所有服务"
echo ""

mkdir -p logs

# 启动Django服务（后台）
echo "启动Django服务..."
python manage.py runserver > logs/django.log 2>&1 &
DJANGO_PID=$!

# 启动Celery Worker（后台）
echo "启动Celery Worker..."
celery -A app.celery_app worker -l info > logs/celery_worker.log 2>&1 &
CELERY_WORKER_PID=$!

# 启动Celery Beat（后台）
echo "启动Celery Beat..."
celery -A app.celery_app beat -l info > logs/celery_beat.log 2>&1 &
CELERY_BEAT_PID=$!

# 启动钉钉 Stream 推送服务（后台，若有启用配置则保持连接）
# 注意：钉钉 WebSocket 直连，禁用代理可避免 "python-socks" 相关错误
echo "启动钉钉 Stream 推送..."
( unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy 2>/dev/null; python manage.py start_dingtalk_stream ) >> logs/dingtalk_stream.log 2>&1 &
DINGTALK_STREAM_PID=$!

echo ""
echo "服务已启动!"
echo ""
echo "Django服务: http://localhost:8000"
echo "API地址: http://localhost:8000/api/"
echo "Admin地址: http://localhost:8000/admin/"
echo ""
echo "PID信息:"
echo "  Django: $DJANGO_PID"
echo "  Celery Worker: $CELERY_WORKER_PID"
echo "  Celery Beat: $CELERY_BEAT_PID"
echo "  钉钉 Stream: $DINGTALK_STREAM_PID"
echo ""
echo "日志文件:"
echo "  Django: logs/django.log"
echo "  Celery Worker: logs/celery_worker.log"
echo "  Celery Beat: logs/celery_beat.log"
echo "  钉钉 Stream: logs/dingtalk_stream.log"
echo ""

# 保存PID到文件
echo $DJANGO_PID > logs/django.pid
echo $CELERY_WORKER_PID > logs/celery_worker.pid
echo $CELERY_BEAT_PID > logs/celery_beat.pid
echo $DINGTALK_STREAM_PID > logs/dingtalk_stream.pid

# 等待用户中断
trap "echo ''; echo '正在停止服务...'; kill $DJANGO_PID $CELERY_WORKER_PID $CELERY_BEAT_PID $DINGTALK_STREAM_PID 2>/dev/null; rm -f logs/*.pid; echo '服务已停止'; exit" INT TERM

wait




