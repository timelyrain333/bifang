# PDF 报告生成器优化说明

## 📋 优化概述

本次优化重构了 HexStrike PDF 报告生成器，采用 **HTML → PDF** 的架构（参考 SysReptor），解决了原有 ReportLab 方案的以下问题：

### 原有问题
1. ❌ 字体超出边框 - 表格列宽固定
2. ❌ 设计不够美观 - ReportLab 样式系统受限
3. ❌ 中文字体支持不稳定 - 复杂的字体注册逻辑
4. ❌ 维护困难 - 需要手动计算布局

### 新方案优势
1. ✅ **自动文本换行** - CSS 自动处理，不会超出边界
2. ✅ **更美观的设计** - 灵活的 CSS 样式系统
3. ✅ **更好的中文字体支持** - 使用系统默认中文字体
4. ✅ **易于维护** - HTML + CSS 比 Python 代码更直观
5. ✅ **多种备用方案** - WeasyPrint → xhtml2pdf → pdfkit

## 🏗️ 架构设计

```
数据 (扫描结果)
    ↓
生成 HTML (带有专业 CSS 样式)
    ↓
转换为 PDF
    ├─ 优先: WeasyPrint (最佳效果)
    ├─ 备用1: xhtml2pdf (纯 Python)
    └─ 备用2: pdfkit (需要 wkhtmltopdf)
```

## 📁 文件结构

```
app/services/
├── hexstrike_pdf_reporter.py  # PDF 生成器（重构）
├── hexstrike_html_reporter.py # HTML 报告（参考）
└── pdf_styles.css             # PDF 专用样式（新增）
```

## 🎨 CSS 特性

### 页面布局
- A4 纸张，自动分页
- 页眉：显示报告标题和页码
- 页脚：显示生成工具

### 封面页
- 渐变背景（紫色系）
- 大标题居中显示
- 目标和元数据信息

### 内容样式
- **统计卡片** - 5 个卡片一行，颜色编码
- **漏洞列表** - 按严重性分组，彩色左边框
- **端口列表** - 卡片式布局，风险标签
- **安全建议** - 蓝色背景高亮

### 打印优化
- `page-break-inside: avoid` - 防止内容被分割
- `page-break-after: always` - 控制分页
- 打印颜色保留 `-webkit-print-color-adjust: exact`

## 🚀 安装依赖

### 方案 1: WeasyPrint（推荐）

```bash
# 安装 Python 库
pip install weasyprint

# macOS - 安装系统库
brew install python-tk python@3.12 pango gdk-pixbuf libffi cairo

# Ubuntu/Debian
sudo apt-get install python3-dev python3-pip python3-cffi libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info

# Windows - 下载 GTK3 Runtime
# https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer
```

### 方案 2: xhtml2pdf（备用）

```bash
pip install xhtml2pdf
```

### 方案 3: pdfkit（最后备用）

```bash
pip install pdfkit
brew install wkhtmltopdf  # macOS
```

## 💻 使用方法

### 1. 基本使用

```python
from app.services.hexstrike_pdf_reporter import HexStrikePDFReporter

# 创建报告生成器
reporter = HexStrikePDFReporter()

# 生成 PDF 报告
filename = reporter.generate_pdf_report(
    target="example.com",
    nmap_results=nmap_results,
    nuclei_results=nuclei_results
)

if filename:
    print(f"PDF 报告已生成: reports/{filename}")
else:
    print("PDF 生成失败")
```

### 2. 自定义样式

编辑 `app/services/pdf_styles.css` 修改样式：

```css
/* 修改主题色 */
:root {
    --primary-color: #667eea;  /* 改为你喜欢的颜色 */
}

/* 调整字体大小 */
.summary-card .number {
    font-size: 40pt;  /* 改为更大 */
}
```

### 3. 自定义报告目录

```python
# 指定自定义目录
reporter = HexStrikePDFReporter(reports_dir='/path/to/reports')
```

## 🔧 配置选项

### 在 CSS 中调整

```css
/* 页面边距 */
@page {
    margin: 20mm;  /* 可改为 15mm, 25mm 等 */
}

/* 字体 */
body {
    font-family: 'Noto Sans SC', sans-serif;
    font-size: 11pt;  /* 调整基础字体大小 */
}

/* 卡片数量 */
.summary {
    /* 默认 5 个，可通过修改 HTML 改为 3 个或 4 个 */
}
```

## 📊 生成的报告内容

1. **封面页** - 标题、目标、时间
2. **统计摘要** - 漏洞数量、开放端口
3. **漏洞详情** - 按严重性分组，最多显示 20 个/级别
4. **端口列表** - 开放端口、服务、风险评级
5. **安全建议** - 根据扫描结果自动生成
6. **页脚** - 生成时间、建议

## 🐛 故障排除

### WeasyPrint 导入失败

```bash
# 检查系统库
# macOS
brew list pango cairo gdk-pixbuf

# Ubuntu
dpkg -l | grep libpango

# 如果缺少，重新安装（参考上面的安装命令）
```

### 所有方法都失败

查看日志获取详细错误信息：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

会显示哪个库失败以及原因。

### 中文显示问题

确保系统安装了中文字体：

```bash
# macOS
ls /System/Library/Fonts/ | grep -i sans

# Linux
fc-list :lang=zh
```

## 📚 参考资料

- **SysReptor**: https://github.com/Syslifters/sysreptor
- **WeasyPrint 文档**: https://doc.courtbouillon.org/weasyprint/
- **CSS Paged Media**: https://www.w3.org/TR/css-page-3/

## 🔄 迁移说明

### 从旧版本迁移

旧版本使用 ReportLab，新版本完全兼容：

```python
# 旧代码仍然有效
filename = reporter.generate_pdf_report(
    target="example.com",
    nmap_results=nmap_results,
    nuclei_results=nuclei_results
)
```

无需修改调用代码！

### 性能对比

| 方案 | 速度 | 质量 | 依赖 |
|------|------|------|------|
| WeasyPrint | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 系统库 |
| xhtml2pdf | ⭐⭐⭐ | ⭐⭐⭐ | 纯 Python |
| ReportLab (旧) | ⭐⭐ | ⭐⭐ | 纯 Python |

## 🎯 后续优化建议

1. **添加目录** - 使用 CSS `counter()` 生成目录
2. **图表支持** - 集成 Chart.js 生成可视化图表
3. **自定义模板** - 允许用户自定义 HTML 模板
4. **批量生成** - 支持同时生成多个目标的报告
5. **报告对比** - 对比不同时间段的扫描结果

---

**生成时间**: 2026-02-08
**版本**: v2.0
**架构**: HTML → PDF (WeasyPrint)