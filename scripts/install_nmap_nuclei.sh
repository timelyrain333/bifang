#!/bin/bash
# 安装 nmap 和 nuclei（供 HexStrike / 资产安全评估使用）
# 在项目根目录执行: ./scripts/install_nmap_nuclei.sh

set -e

echo "================================"
echo "安装 nmap 和 nuclei"
echo "================================"

# 跳过 brew 自动更新以加快安装
export HOMEBREW_NO_AUTO_UPDATE=1

if ! command -v brew &>/dev/null; then
    echo "未检测到 Homebrew，请先安装: https://brew.sh"
    echo "或手动安装:"
    echo "  nmap: https://nmap.org/download.html"
    echo "  nuclei: https://github.com/projectdiscovery/nuclei/releases"
    exit 1
fi

# 清除可能残留的下载锁（避免之前中断导致的锁文件）
rm -f "$HOME/Library/Caches/Homebrew/downloads/"*.incomplete 2>/dev/null || true

echo ""
echo "1. 安装 nmap..."
if command -v nmap &>/dev/null; then
    echo "   nmap 已安装: $(nmap --version | head -1)"
else
    brew install nmap
    echo "   nmap 安装完成"
fi

echo ""
echo "2. 安装 nuclei..."
if command -v nuclei &>/dev/null; then
    echo "   nuclei 已安装: $(nuclei -version 2>&1 | head -1)"
else
    brew install nuclei
    echo "   nuclei 安装完成"
fi

echo ""
echo "================================"
echo "安装完成"
echo "================================"
echo "  nmap:  $(which nmap 2>/dev/null || echo '未找到')"
echo "  nuclei: $(which nuclei 2>/dev/null || echo '未找到')"
echo ""
echo "nuclei 首次使用建议更新模板: nuclei -update-templates"
echo ""
