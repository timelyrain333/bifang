#!/bin/bash
# HexStrike AI 安装脚本
# 在 bifang 项目根目录下执行，或将 BIFANG_ROOT 指向项目根目录

set -e

# 项目根目录（脚本所在目录的上一级）
BIFANG_ROOT="${BIFANG_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
HEXSTRIKE_DIR="${HEXSTRIKE_DIR:-$BIFANG_ROOT/hexstrike-ai}"
HEXSTRIKE_REPO="${HEXSTRIKE_REPO:-https://github.com/0x4m4/hexstrike-ai.git}"
HEXSTRIKE_PORT="${HEXSTRIKE_PORT:-8888}"

echo "================================"
echo "HexStrike AI 安装"
echo "================================"
echo "  项目根目录: $BIFANG_ROOT"
echo "  HexStrike 目录: $HEXSTRIKE_DIR"
echo ""

# 检查 Python3
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3，请先安装 Python 3.8+"
    exit 1
fi

# 克隆仓库（若不存在）
if [ ! -d "$HEXSTRIKE_DIR" ]; then
    echo "1. 克隆 HexStrike AI 仓库..."
    git clone "$HEXSTRIKE_REPO" "$HEXSTRIKE_DIR"
    echo "   已克隆到 $HEXSTRIKE_DIR"
else
    echo "1. 目录已存在: $HEXSTRIKE_DIR"
    if [ -z "${NONINTERACTIVE}" ]; then
        read -p "   是否拉取最新代码? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            (cd "$HEXSTRIKE_DIR" && git pull)
        fi
    else
        echo "   非交互模式，跳过拉取"
    fi
fi

# 创建虚拟环境
VENV_DIR="$HEXSTRIKE_DIR/hexstrike-env"
if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo ""
    echo "2. 创建虚拟环境..."
    python3 -m venv "$VENV_DIR"
    echo "   已创建: $VENV_DIR"
else
    echo ""
    echo "2. 虚拟环境已存在: $VENV_DIR"
fi

# 安装 Python 依赖
echo ""
echo "3. 安装 Python 依赖..."
source "$VENV_DIR/bin/activate"
if [ -f "$HEXSTRIKE_DIR/requirements.txt" ]; then
    # 使用 trusted-host 避免 macOS 等环境下 SSL 证书验证失败
    if pip install -r "$HEXSTRIKE_DIR/requirements.txt" -q \
        --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org 2>/dev/null; then
        echo "   已安装 requirements.txt"
    else
        echo "   自动安装失败（常见于 SSL 或网络问题），请手动执行:"
        echo "   cd $HEXSTRIKE_DIR && source hexstrike-env/bin/activate"
        echo "   pip install -r requirements.txt --trusted-host pypi.org --trusted-host files.pythonhosted.org"
    fi
else
    echo "   警告: 未找到 $HEXSTRIKE_DIR/requirements.txt，跳过 pip 安装"
fi
deactivate

# 可选：安装常用安全工具（macOS 用 brew）
echo ""
echo "4. 可选：安装常用安全工具（用于扫描）"
if command -v brew &> /dev/null; then
    echo "   检测到 Homebrew，可安装: nmap, nuclei (需先安装 go)"
    echo "   安装 nmap: brew install nmap"
    echo "   安装 nuclei: 参考 https://github.com/projectdiscovery/nuclei"
    if [ -z "${NONINTERACTIVE}" ]; then
        read -p "   是否现在安装 nmap? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            brew install nmap
        fi
    fi
else
    echo "   未检测到 Homebrew。Linux 可安装: sudo apt install nmap (或 yum/dnf)"
fi

echo ""
echo "================================"
echo "安装完成!"
echo "================================"
echo "启动 HexStrike 服务: $BIFANG_ROOT/scripts/start_hexstrike.sh"
echo "或手动: cd $HEXSTRIKE_DIR && source hexstrike-env/bin/activate && python3 hexstrike_server.py --port $HEXSTRIKE_PORT"
echo ""
