#!/bin/bash

# Bifang 系统停止脚本

echo "正在停止Bifang服务..."

# 读取PID并停止服务
if [ -f "logs/django.pid" ]; then
    PID=$(cat logs/django.pid)
    if kill -0 $PID 2>/dev/null; then
        kill $PID
        echo "Django服务已停止 (PID: $PID)"
    fi
    rm -f logs/django.pid
fi

if [ -f "logs/celery_worker.pid" ]; then
    PID=$(cat logs/celery_worker.pid)
    if kill -0 $PID 2>/dev/null; then
        kill $PID
        echo "Celery Worker已停止 (PID: $PID)"
    fi
    rm -f logs/celery_worker.pid
fi

if [ -f "logs/celery_beat.pid" ]; then
    PID=$(cat logs/celery_beat.pid)
    if kill -0 $PID 2>/dev/null; then
        kill $PID
        echo "Celery Beat已停止 (PID: $PID)"
    fi
    rm -f logs/celery_beat.pid
fi

# 钉钉 Stream 推送服务（若由 start.sh 启动）
if [ -f "logs/dingtalk_stream.pid" ]; then
    PID=$(cat logs/dingtalk_stream.pid)
    if kill -0 $PID 2>/dev/null; then
        kill $PID
        echo "钉钉 Stream 服务已停止 (PID: $PID)"
    fi
    rm -f logs/dingtalk_stream.pid
fi

# HexStrike 服务（若由 start_hexstrike.sh 启动）
if [ -f "logs/hexstrike.pid" ]; then
    PID=$(cat logs/hexstrike.pid)
    if kill -0 $PID 2>/dev/null; then
        kill $PID
        echo "HexStrike 服务已停止 (PID: $PID)"
    fi
    rm -f logs/hexstrike.pid
fi

# 也尝试通过进程名停止
pkill -f "manage.py runserver"
pkill -f "celery -A app.celery_app worker"
pkill -f "celery -A app.celery_app beat"
pkill -f "manage.py start_dingtalk_stream"
pkill -f "hexstrike_server.py"

echo "所有服务已停止"




