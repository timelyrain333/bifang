"""
HexStrike 扫描报告 PDF 生成器
使用 ReportLab 直接生成 PDF（无需系统依赖）
备用方案：WeasyPrint/xhtml2pdf (需要 HTML 转换)
参考 SysReptor 的 PDF 生成架构
"""
import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
from django.conf import settings

logger = logging.getLogger(__name__)


class HexStrikePDFReporter:
    """HexStrike PDF 报告生成器（使用 ReportLab）"""

    def __init__(self, reports_dir: Optional[str] = None):
        """
        初始化 PDF 报告生成器

        Args:
            reports_dir: 报告保存目录，默认为 BASE_DIR/reports
        """
        if reports_dir is None:
            base_dir = Path(settings.BASE_DIR)
            reports_dir = base_dir / 'reports'

        self.reports_dir = reports_dir
        os.makedirs(self.reports_dir, exist_ok=True)

        # 加载 PDF 样式文件
        self._load_pdf_styles()

    def _load_pdf_styles(self):
        """加载 PDF 专用 CSS 样式"""
        try:
            css_path = Path(__file__).parent / 'pdf_styles.css'
            if css_path.exists():
                with open(css_path, 'r', encoding='utf-8') as f:
                    self.pdf_css = f.read()
                logger.info("成功加载 PDF 样式文件")
            else:
                logger.warning("PDF 样式文件不存在，使用默认样式")
                self.pdf_css = self._get_default_css()
        except Exception as e:
            logger.error(f"加载 PDF 样式文件失败: {e}")
            self.pdf_css = self._get_default_css()

    def _get_default_css(self) -> str:
        """获取默认 CSS 样式"""
        return """
        @page { size: A4; margin: 20mm; }
        body { font-family: sans-serif; font-size: 11pt; }
        .section { page-break-inside: avoid; }
        """

    def generate_pdf_report(
        self,
        target: str,
        nmap_results: Optional[Dict] = None,
        nuclei_results: Optional[Dict] = None,
        target_profile: Optional[Dict] = None
    ) -> Optional[str]:
        """
        生成 PDF 报告（优先使用 ReportLab，无需系统依赖）

        Args:
            target: 扫描目标
            nmap_results: Nmap 扫描结果
            nuclei_results: Nuclei 扫描结果
            target_profile: 目标画像

        Returns:
            PDF 报告文件路径（相对于 reports 目录），失败返回 None
        """
        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"hexstrike_report_{target.replace('.', '_').replace(':', '_')}_{timestamp}.pdf"
        filepath = self.reports_dir / filename

        # 提取统计数据
        stats = self._extract_stats(nmap_results, nuclei_results)
        timestamp_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 方法 1: 使用 ReportLab（首选，无需系统依赖）
        try:
            result = self._generate_with_reportlab(
                filepath=filepath,
                target=target,
                stats=stats,
                nmap_results=nmap_results,
                nuclei_results=nuclei_results,
                target_profile=target_profile,
                timestamp=timestamp_str
            )
            if result:
                logger.info(f"PDF 报告生成成功 (ReportLab): {filename}")
                return filename
        except Exception as e:
            logger.warning(f"ReportLab 生成失败: {e}，尝试备用方案")

        # 方法 2: 回退到 HTML 转 PDF（WeasyPrint）
        try:
            html_content = self._generate_html(
                target=target,
                stats=stats,
                nmap_results=nmap_results,
                nuclei_results=nuclei_results,
                target_profile=target_profile,
                timestamp=timestamp_str
            )
            from weasyprint import HTML, CSS
            html_doc = HTML(string=html_content, base_url='file://')
            css_doc = CSS(string=self.pdf_css)
            html_doc.write_pdf(
                target=str(filepath),
                stylesheets=[css_doc],
                presentational_hints=True
            )
            logger.info(f"PDF 报告生成成功 (WeasyPrint): {filename}")
            return filename
        except ImportError:
            logger.warning("WeasyPrint 未安装")
        except Exception as e:
            logger.warning(f"WeasyPrint 生成失败: {e}")

        # 方法 3: 最后回退 - xhtml2pdf
        try:
            if not html_content:
                html_content = self._generate_html(
                    target=target,
                    stats=stats,
                    nmap_results=nmap_results,
                    nuclei_results=nuclei_results,
                    target_profile=target_profile,
                    timestamp=timestamp_str
                )
            from xhtml2pdf import pisa
            from io import BytesIO
            pdf_buffer = BytesIO()
            pisa.CreatePDF(
                src=html_content,
                dest=pdf_buffer,
                encoding='utf-8'
            )
            with open(filepath, 'wb') as f:
                f.write(pdf_buffer.getvalue())
            logger.info(f"PDF 报告生成成功 (xhtml2pdf): {filename}")
            return filename
        except ImportError:
            logger.warning("xhtml2pdf 未安装")
        except Exception as e:
            logger.warning(f"xhtml2pdf 生成失败: {e}")

        # 所有方法都失败
        logger.error("所有 PDF 生成方法都失败了")
        logger.error("ReportLab 应该已安装，请检查")
        return None

    def _generate_with_reportlab(
        self,
        filepath: Path,
        target: str,
        stats: Dict,
        nmap_results: Optional[Dict],
        nuclei_results: Optional[Dict],
        target_profile: Optional[Dict],
        timestamp: str
    ) -> bool:
        """使用 ReportLab 直接生成 PDF"""
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
        )
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        # 注册中文字体（如果可用）
        try:
            pdfmetrics.registerFont(TTFont('ChineseFont', '/System/Library/Fonts/PingFang.ttc', subfontIndex=0))
            font_name = 'ChineseFont'
        except:
            try:
                pdfmetrics.registerFont(TTFont('ChineseFont', '/System/Library/Fonts/STHeiti Light.ttc'))
                font_name = 'ChineseFont'
            except:
                font_name = 'Helvetica'  # 回退到默认字体

        # 创建 PDF 文档
        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )

        # 样式
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontName=font_name,
            fontSize=24,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=30,
            alignment=1  # 居中
        )
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Heading2'],
            fontName=font_name,
            fontSize=16,
            textColor=colors.HexColor('#7f8c8d'),
            spaceAfter=20,
            alignment=1
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontName=font_name,
            fontSize=18,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=12,
            spaceBefore=20
        )
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontName=font_name,
            fontSize=11,
            textColor=colors.HexColor('#34495e'),
            spaceAfter=8
        )

        # 构建内容
        story = []

        # 标题页
        story.append(Paragraph("安全评估报告", title_style))
        story.append(Paragraph(f"目标：{target}", subtitle_style))
        story.append(Spacer(1, 1*cm))
        story.append(Paragraph(f"生成时间：{timestamp}", normal_style))
        story.append(Paragraph("评估工具：HexStrike AI (Nmap + Nuclei)", normal_style))
        story.append(PageBreak())

        # 统计摘要
        story.append(Paragraph("扫描统计摘要", heading_style))
        summary_data = [
            ['项目', '数量'],
            ['严重漏洞', str(stats['vulnerabilities']['critical'])],
            ['高危漏洞', str(stats['vulnerabilities']['high'])],
            ['中危漏洞', str(stats['vulnerabilities']['medium'])],
            ['低危漏洞', str(stats['vulnerabilities']['low'])],
            ['开放端口', str(stats['ports']['open'])],
        ]
        summary_table = Table(summary_data, colWidths=[8*cm, 4*cm])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), font_name),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('FONTNAME', (0, 1), (-1, -1), font_name),
            ('FONTSIZE', (0, 1), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 1*cm))

        # 漏洞详情
        if nuclei_results and nuclei_results.get('success'):
            vulnerabilities = self._parse_vulnerabilities(nuclei_results)
            if vulnerabilities:
                story.append(Paragraph("漏洞扫描结果", heading_style))

                for severity in ['critical', 'high', 'medium', 'low', 'info']:
                    vulns = [v for v in vulnerabilities if v['severity'] == severity]
                    if not vulns:
                        continue

                    severity_labels = {
                        'critical': '严重',
                        'high': '高危',
                        'medium': '中危',
                        'low': '低危',
                        'info': '信息'
                    }
                    severity_colors = {
                        'critical': colors.HexColor('#e74c3c'),
                        'high': colors.HexColor('#e67e22'),
                        'medium': colors.HexColor('#f39c12'),
                        'low': colors.HexColor('#3498db'),
                        'info': colors.HexColor('#95a5a6')
                    }

                    story.append(Paragraph(
                        f"{severity_labels[severity].upper()} ({len(vulns)})",
                        ParagraphStyle(
                            f'Severity{severity}',
                            parent=styles['Heading3'],
                            fontName=font_name,
                            fontSize=14,
                            textColor=severity_colors[severity],
                            spaceAfter=10
                        )
                    ))

                    for vuln in vulns[:20]:  # 最多显示 20 个
                        name = vuln.get('name', 'Unknown')
                        tags = ', '.join(vuln.get('tags', [])[:5])
                        description = vuln.get('description', '')[:200]

                        vuln_data = [
                            ['漏洞名称', name],
                            ['标签', tags if tags else '-'],
                        ]
                        if description:
                            vuln_data.append(['描述', f'{description}...'])

                        vuln_table = Table(vuln_data, colWidths=[5*cm, 10*cm])
                        vuln_table.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
                            ('FONTNAME', (0, 0), (-1, -1), font_name),
                            ('FONTSIZE', (0, 0), (-1, -1), 10),
                            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
                        ]))
                        story.append(vuln_table)
                        story.append(Spacer(1, 0.3*cm))

                    if len(vulns) > 20:
                        story.append(Paragraph(
                            f"<i>还有 {len(vulns) - 20} 个{severity_labels[severity]}漏洞未显示</i>",
                            normal_style
                        ))
                        story.append(Spacer(1, 0.5*cm))

        # 端口详情
        if nmap_results and nmap_results.get('success'):
            ports = self._parse_ports(nmap_results)
            if ports:
                story.append(Paragraph("端口扫描结果", heading_style))

                port_data = [['端口/协议', '服务', '版本', '风险等级']]
                for port_info in ports:
                    risk = self._assess_port_risk(port_info['port'], port_info['service'])
                    risk_label = risk['label'] if risk else '-'
                    port_data.append([
                        f"{port_info['port']}/tcp",
                        port_info['service'],
                        port_info['version'] or '-',
                        risk_label
                    ])

                port_table = Table(port_data, colWidths=[3*cm, 4*cm, 5*cm, 3*cm])
                port_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, -1), font_name),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                story.append(port_table)
                story.append(Spacer(1, 1*cm))

        # 安全建议
        recommendations = self._extract_recommendations(nmap_results, nuclei_results)
        if recommendations:
            story.append(Paragraph("安全建议", heading_style))
            for rec in recommendations:
                story.append(Paragraph(rec['title'], ParagraphStyle(
                    'RecTitle',
                    parent=styles['Heading3'],
                    fontName=font_name,
                    fontSize=12,
                    spaceAfter=5
                )))
                for item in rec['items']:
                    story.append(Paragraph(f"• {item}", normal_style))
                story.append(Spacer(1, 0.5*cm))

        # 页脚
        story.append(PageBreak())
        story.append(Paragraph("报告说明", heading_style))
        story.append(Paragraph("本报告由 HexStrike AI 自动生成", normal_style))
        story.append(Paragraph("建议：定期进行安全评估，及时修复发现的漏洞", normal_style))
        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph(f"生成时间：{timestamp}", normal_style))

        # 生成 PDF
        doc.build(story)
        return True

    def _parse_vulnerabilities(self, nuclei_results: Dict) -> List[Dict]:
        """解析漏洞列表"""
        try:
            import json
            stdout = nuclei_results.get('stdout', '')
            if not stdout:
                return []

            vulnerabilities = []
            lines = stdout.strip().split('\n')
            for line in lines:
                try:
                    vuln = json.loads(line)
                    info = vuln.get('info', {})
                    vulnerabilities.append({
                        'name': info.get('name', 'Unknown'),
                        'severity': info.get('severity', 'info').lower(),
                        'tags': info.get('tags', []),
                        'description': info.get('description', '')
                    })
                except json.JSONDecodeError:
                    pass
            return vulnerabilities
        except Exception:
            return []

    def _parse_ports(self, nmap_results: Dict) -> List[Dict]:
        """解析端口列表"""
        try:
            import re
            stdout = nmap_results.get('stdout', '')
            if not stdout:
                return []

            ports = []
            port_pattern = re.compile(r'(\d+)/tcp\s+open\s+(\S+)(?:\s+(.+))?')
            for match in port_pattern.finditer(stdout):
                ports.append({
                    'port': match.group(1),
                    'service': match.group(2),
                    'version': match.group(3) or ''
                })
            return ports
        except Exception:
            return []

    def _extract_recommendations(self, nmap_results: Optional[Dict], nuclei_results: Optional[Dict]) -> List[Dict]:
        """提取安全建议"""
        recommendations = []

        if nmap_results and nmap_results.get('success'):
            stdout = nmap_results.get('stdout', '')

            if 'ssh' in stdout.lower():
                recommendations.append({
                    'title': 'SSH 安全加固',
                    'items': [
                        '禁用密码登录，只允许密钥认证',
                        '修改默认端口（22）',
                        '配置 fail2ban 防暴力破解',
                        '限制访问来源 IP（防火墙）'
                    ]
                })

            if 'elasticsearch' in stdout.lower() or ':9200' in stdout:
                recommendations.append({
                    'title': 'Elasticsearch 安全加固',
                    'items': [
                        '启用 X-Pack 安全认证',
                        '配置访问控制列表（ACL）',
                        '禁用或限制 HTTP 接口',
                        '升级到最新版本'
                    ]
                })

        if nuclei_results and nuclei_results.get('success'):
            try:
                stdout = nuclei_results.get('stdout', '')
                if 'critical' in stdout.lower() or 'high' in stdout.lower():
                    recommendations.append({
                        'title': '漏洞修复优先级',
                        'items': [
                            '立即修复严重和高危漏洞',
                            '隔离受影响的系统',
                            '检查是否存在已遭受攻击的迹象',
                            '应用最新的安全补丁'
                        ]
                    })
            except:
                pass

        return recommendations

    def _generate_html(
        self,
        target: str,
        stats: Dict,
        nmap_results: Optional[Dict],
        nuclei_results: Optional[Dict],
        target_profile: Optional[Dict],
        timestamp: str
    ) -> str:
        """生成 HTML 内容（用于 PDF 转换）"""

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>安全评估报告 - {target}</title>
    <style>
        {self.pdf_css}
    </style>
</head>
<body>
    <!-- 封面页 -->
    <div class="cover-page">
        <div class="cover-content">
            <h1>🔒 安全评估报告</h1>
            <div class="subtitle">目标：{target}</div>
            <div class="meta">
                <p>生成时间：{timestamp}</p>
                <p>评估工具：HexStrike AI (Nmap + Nuclei)</p>
            </div>
        </div>
    </div>

    <div class="container">
        <!-- 报告头部 -->
        <div class="header">
            <h1>🔒 安全评估报告</h1>
            <div class="subtitle">目标：{target}</div>
            <div class="meta">
                <div>生成时间：{timestamp}</div>
                <div>评估工具：HexStrike AI (Nmap + Nuclei)</div>
            </div>
        </div>

        <!-- 统计摘要 -->
        <div class="summary">
            <div class="summary-card risk-critical">
                <div class="number">{stats['vulnerabilities']['critical']}</div>
                <div class="label">严重漏洞</div>
            </div>
            <div class="summary-card risk-high">
                <div class="number">{stats['vulnerabilities']['high']}</div>
                <div class="label">高危漏洞</div>
            </div>
            <div class="summary-card risk-medium">
                <div class="number">{stats['vulnerabilities']['medium']}</div>
                <div class="label">中危漏洞</div>
            </div>
            <div class="summary-card risk-low">
                <div class="number">{stats['vulnerabilities']['low']}</div>
                <div class="label">低危漏洞</div>
            </div>
            <div class="summary-card">
                <div class="number">{stats['ports']['open']}</div>
                <div class="label">开放端口</div>
            </div>
        </div>

        {self._generate_vulnerabilities_html(nuclei_results)}

        {self._generate_ports_html(nmap_results)}

        {self._generate_recommendations_html(nmap_results, nuclei_results)}

        <!-- 报告尾部 -->
        <div class="footer">
            <p>本报告由 HexStrike AI 自动生成</p>
            <p>建议：定期进行安全评估，及时修复发现的漏洞</p>
            <p>生成时间：{timestamp}</p>
        </div>
    </div>
</body>
</html>"""
        return html

    def _extract_stats(self, nmap_results: Optional[Dict], nuclei_results: Optional[Dict]) -> Dict:
        """提取统计数据"""
        stats = {
            'vulnerabilities': {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0, 'total': 0},
            'ports': {'open': 0, 'closed': 0, 'filtered': 0, 'total': 0}
        }

        # 提取漏洞统计
        if nuclei_results and nuclei_results.get('success'):
            try:
                import json
                stdout = nuclei_results.get('stdout', '')
                if stdout:
                    lines = stdout.strip().split('\n')
                    for line in lines:
                        try:
                            vuln = json.loads(line)
                            severity = vuln.get('info', {}).get('severity', 'info').lower()
                            if severity in stats['vulnerabilities']:
                                stats['vulnerabilities'][severity] += 1
                                stats['vulnerabilities']['total'] += 1
                        except json.JSONDecodeError:
                            pass
            except Exception:
                pass

        # 提取端口统计
        if nmap_results and nmap_results.get('success'):
            try:
                import re
                stdout = nmap_results.get('stdout', '')
                if stdout:
                    port_matches = re.findall(r'(\d+)/tcp\s+open', stdout)
                    stats['ports']['open'] = len(port_matches)
                    stats['ports']['total'] = len(port_matches)
            except Exception:
                pass

        return stats

    def _generate_vulnerabilities_html(self, nuclei_results: Optional[Dict]) -> str:
        """生成漏洞列表 HTML"""
        if not nuclei_results or not nuclei_results.get('success'):
            return ''

        try:
            import json
            stdout = nuclei_results.get('stdout', '')
            if not stdout:
                return ''

            # 解析漏洞
            vulnerabilities = []
            lines = stdout.strip().split('\n')
            for line in lines:
                try:
                    vuln = json.loads(line)
                    vulnerabilities.append(vuln)
                except json.JSONDecodeError:
                    pass

            if not vulnerabilities:
                return '<div class="section"><h2 class="section-title">🎉 未发现漏洞</h2><p>扫描完成，未发现已知漏洞。</p></div>'

            # 按严重性分组
            by_severity = {'critical': [], 'high': [], 'medium': [], 'low': [], 'info': []}
            for vuln in vulnerabilities:
                severity = vuln.get('info', {}).get('severity', 'info').lower()
                if severity not in by_severity:
                    severity = 'info'
                by_severity[severity].append(vuln)

            html = '<div class="section"><h2 class="section-title">🔍 漏洞扫描结果</h2>'

            for severity in ['critical', 'high', 'medium', 'low', 'info']:
                vulns = by_severity.get(severity, [])
                if not vulns:
                    continue

                severity_labels = {
                    'critical': '严重',
                    'high': '高危',
                    'medium': '中危',
                    'low': '低危',
                    'info': '信息'
                }

                html += f'<h3>{severity_labels[severity].upper()} ({len(vulns)})</h3>'
                html += '<ul class="vulnerability-list">'

                for vuln in vulns[:20]:  # 最多显示 20 个
                    info = vuln.get('info', {})
                    name = info.get('name', 'Unknown')
                    cve_ids = info.get('tags', [])
                    description = info.get('description', '')[:200]

                    html += f'''
                    <li class="vulnerability-item {severity}">
                        <div class="title">
                            <span class="severity severity-{severity}">{severity_labels[severity]}</span>
                            {name}
                        </div>
                        <div style="margin-top: 10px;">
                            {' '.join([f'<span class="tag">{tag}</span>' for tag in cve_ids[:5]])}
                        </div>
                        {f'<div style="margin-top: 8px; color: #666;">{description}...</div>' if description else ''}
                    </li>'''

                if len(vulns) > 20:
                    html += f'<li style="padding: 10px; color: #999;">还有 {len(vulns) - 20} 个{severity_labels[severity]}漏洞未显示</li>'

                html += '</ul>'

            html += '</div>'
            return html

        except Exception as e:
            return f'<div class="section"><h2 class="section-title">漏洞扫描结果</h2><p>解析失败: {str(e)}</p></div>'

    def _generate_ports_html(self, nmap_results: Optional[Dict]) -> str:
        """生成端口列表 HTML"""
        if not nmap_results or not nmap_results.get('success'):
            return ''

        try:
            import re
            stdout = nmap_results.get('stdout', '')
            if not stdout:
                return ''

            # 解析端口信息
            port_pattern = re.compile(r'(\d+)/tcp\s+open\s+(\S+)(?:\s+(.+))?')

            ports = []
            for match in port_pattern.finditer(stdout):
                port = match.group(1)
                service = match.group(2)
                version = match.group(3) or ''

                ports.append({
                    'port': port,
                    'service': service,
                    'version': version
                })

            if not ports:
                return '<div class="section"><h2 class="section-title">端口扫描结果</h2><p>未发现开放端口。</p></div>'

            html = '<div class="section"><h2 class="section-title">🔌 端口扫描结果</h2>'
            html += '<div class="port-list">'

            for port_info in ports:
                port = port_info['port']
                service = port_info['service']
                version = port_info['version']

                # 风险评估
                risk = self._assess_port_risk(port, service)

                html += f'''
                <div class="port-item open">
                    <div class="port-number">端口 {port}/tcp</div>
                    <div class="service">
                        服务：{service}
                        {f'<span class="risk-badge risk-{risk["level"]}">{risk["label"]}</span>' if risk else ''}
                    </div>
                    {f'<div style="font-size: 12px; color: #999; margin-top: 5px;">{version}</div>' if version else ''}
                </div>'''

            html += '</div></div>'
            return html

        except Exception as e:
            return f'<div class="section"><h2 class="section-title">端口扫描结果</h2><p>解析失败: {str(e)}</p></div>'

    def _generate_recommendations_html(self, nmap_results: Optional[Dict], nuclei_results: Optional[Dict]) -> str:
        """生成修复建议 HTML"""
        recommendations = []

        # 基于 Nmap 结果的建议
        if nmap_results and nmap_results.get('success'):
            stdout = nmap_results.get('stdout', '')

            if 'ssh' in stdout.lower():
                recommendations.append({
                    'title': '🔐 SSH 安全加固',
                    'items': [
                        '禁用密码登录，只允许密钥认证',
                        '修改默认端口（22）',
                        '配置 fail2ban 防暴力破解',
                        '限制访问来源 IP（防火墙）'
                    ]
                })

            if 'elasticsearch' in stdout.lower() or ':9200' in stdout:
                recommendations.append({
                    'title': '🔍 Elasticsearch 安全加固',
                    'items': [
                        '启用 X-Pack 安全认证',
                        '配置访问控制列表（ACL）',
                        '禁用或限制 HTTP 接口',
                        '升级到最新版本'
                    ]
                })

        # 基于 Nuclei 结果的建议
        if nuclei_results and nuclei_results.get('success'):
            try:
                stdout = nuclei_results.get('stdout', '')
                if 'critical' in stdout.lower() or 'high' in stdout.lower():
                    recommendations.append({
                        'title': '🚨 漏洞修复优先级',
                        'items': [
                            '立即修复严重和高危漏洞',
                            '隔离受影响的系统',
                            '检查是否存在已遭受攻击的迹象',
                            '应用最新的安全补丁'
                        ]
                    })
            except:
                pass

        if not recommendations:
            return ''

        html = '<div class="section"><h2 class="section-title">💡 安全建议</h2>'

        for rec in recommendations:
            html += f'''
            <div class="recommendations">
                <h3 style="margin-bottom: 10px;">{rec['title']}</h3>
                <ul>
                    {''.join([f'<li>{item}</li>' for item in rec['items']])}
                </ul>
            </div>
            '''

        html += '</div>'
        return html

    def _assess_port_risk(self, port: str, service: str) -> Optional[Dict]:
        """评估端口风险"""
        port_num = int(port) if port.isdigit() else 0
        service_lower = service.lower()

        critical_ports = [22, 23, 135, 139, 445, 3389]
        critical_services = ['telnet', 'ftp', 'rsh', 'rlogin']

        if port_num in critical_ports or service_lower in critical_services:
            return {'level': 'critical', 'label': '严重'}
        elif port_num < 1024:
            return {'level': 'medium', 'label': '中危'}
        else:
            return {'level': 'low', 'label': '低危'}