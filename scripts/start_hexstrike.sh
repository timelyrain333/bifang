#!/bin/bash
# 启动 HexStrike AI 服务（默认端口 8888）

BIFANG_ROOT="${BIFANG_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
HEXSTRIKE_DIR="${HEXSTRIKE_DIR:-$BIFANG_ROOT/hexstrike-ai}"
HEXSTRIKE_PORT="${HEXSTRIKE_PORT:-8888}"
LOG_DIR="${BIFANG_ROOT}/logs"
PID_FILE="$LOG_DIR/hexstrike.pid"

if [ ! -d "$HEXSTRIKE_DIR" ]; then
    echo "错误: HexStrike 目录不存在: $HEXSTRIKE_DIR"
    echo "请先执行: $BIFANG_ROOT/scripts/install_hexstrike.sh"
    exit 1
fi

VENV_ACTIVATE="$HEXSTRIKE_DIR/hexstrike-env/bin/activate"
if [ ! -f "$VENV_ACTIVATE" ]; then
    echo "错误: 虚拟环境不存在，请先执行 install_hexstrike.sh"
    exit 1
fi

if [ ! -f "$HEXSTRIKE_DIR/hexstrike_server.py" ]; then
    echo "错误: 未找到 hexstrike_server.py，请检查 $HEXSTRIKE_DIR"
    exit 1
fi

# 若已有 PID 且进程存在，先不重复启动
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "HexStrike 已在运行 (PID: $OLD_PID)"
        echo "停止: kill $OLD_PID 或执行 stop.sh"
        exit 0
    fi
    rm -f "$PID_FILE"
fi

mkdir -p "$LOG_DIR"
echo "启动 HexStrike Server (端口 $HEXSTRIKE_PORT)..."
cd "$HEXSTRIKE_DIR"
source "$VENV_ACTIVATE"
nohup python3 hexstrike_server.py --port "$HEXSTRIKE_PORT" >> "$LOG_DIR/hexstrike.log" 2>&1 &
HEXSTRIKE_PID=$!
echo $HEXSTRIKE_PID > "$PID_FILE"
deactivate 2>/dev/null || true
echo "HexStrike 已启动 (PID: $HEXSTRIKE_PID)"
echo "日志: $LOG_DIR/hexstrike.log"
echo "健康检查: curl http://127.0.0.1:$HEXSTRIKE_PORT/health"
