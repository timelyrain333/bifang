#!/bin/bash

# Celery服务启动脚本

cd "$(dirname "$0")"

echo "================================"
echo "启动Celery服务"
echo "================================"
echo ""

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "错误: 虚拟环境不存在，请先运行: python3 -m venv venv"
    exit 1
fi

# 激活虚拟环境
source venv/bin/activate

# 检查Redis连接
echo "1. 检查Redis服务..."
if ! python -c "import redis; r = redis.Redis(host='localhost', port=6379, socket_connect_timeout=1); r.ping()" 2>/dev/null; then
    echo "   Redis服务未运行，正在尝试启动..."
    
    # 尝试使用brew启动Redis
    if command -v brew &> /dev/null; then
        if brew list redis &> /dev/null; then
            brew services start redis 2>/dev/null || redis-server --daemonize yes 2>/dev/null
            sleep 2
        else
            echo "   错误: Redis未安装"
            echo "   请运行: brew install redis"
            echo "   然后运行: brew services start redis"
            exit 1
        fi
    else
        echo "   错误: 未找到Homebrew，请手动启动Redis服务"
        echo "   或者安装Redis: brew install redis"
        exit 1
    fi
    
    # 再次检查Redis
    if ! python -c "import redis; r = redis.Redis(host='localhost', port=6379, socket_connect_timeout=1); r.ping()" 2>/dev/null; then
        echo "   错误: Redis服务启动失败，请手动启动"
        exit 1
    fi
fi

echo "   ✅ Redis服务运行正常"
echo ""

# 创建日志目录
mkdir -p logs

# 检查Celery Worker是否已运行
if ps aux | grep -E "celery.*worker" | grep -v grep > /dev/null; then
    echo "⚠️  Celery Worker已在运行"
else
    echo "2. 启动Celery Worker..."
    celery -A app.celery_app worker -l info --logfile=logs/celery_worker.log --detach
    echo "   ✅ Celery Worker已启动"
fi

# 检查Celery Beat是否已运行
if ps aux | grep -E "celery.*beat" | grep -v grep > /dev/null; then
    echo "⚠️  Celery Beat已在运行"
else
    echo "3. 启动Celery Beat..."
    celery -A app.celery_app beat -l info --logfile=logs/celery_beat.log --detach
    echo "   ✅ Celery Beat已启动"
fi

echo ""
echo "================================"
echo "服务状态"
echo "================================"
echo ""
echo "Celery Worker:"
ps aux | grep -E "celery.*worker" | grep -v grep || echo "  未运行"
echo ""
echo "Celery Beat:"
ps aux | grep -E "celery.*beat" | grep -v grep || echo "  未运行"
echo ""
echo "Redis:"
redis-cli ping 2>/dev/null && echo "  ✅ 运行中" || echo "  ❌ 未运行"
echo ""
echo "日志文件:"
echo "  Worker: logs/celery_worker.log"
echo "  Beat: logs/celery_beat.log"
echo ""
echo "停止服务:"
echo "  pkill -f 'celery.*worker'"
echo "  pkill -f 'celery.*beat'"
echo ""
