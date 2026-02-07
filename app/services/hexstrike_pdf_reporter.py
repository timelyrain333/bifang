"""
HexStrike 扫描报告 PDF 生成器
使用 ReportLab 直接生成 PDF 格式报告
格式与 HTML 报告保持一致
"""
import os
import logging
from typing import Dict, Any, Optional
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

    def generate_pdf_report(
        self,
        target: str,
        nmap_results: Optional[Dict] = None,
        nuclei_results: Optional[Dict] = None,
        target_profile: Optional[Dict] = None
    ) -> Optional[str]:
        """
        生成 PDF 报告

        Args:
            target: 扫描目标
            nmap_results: Nmap 扫描结果
            nuclei_results: Nuclei 扫描结果
            target_profile: 目标画像

        Returns:
            PDF 报告文件路径（相对于 reports 目录），失败返回 None
        """
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.lib import colors
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                PageBreak, KeepTogether
            )
            from reportlab.lib.enums import TA_CENTER, TA_LEFT
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont

            # 生成文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"hexstrike_report_{target.replace('.', '_').replace(':', '_')}_{timestamp}.pdf"
            filepath = self.reports_dir / filename

            # 注册中文字体
            chinese_font = 'Helvetica'  # 默认字体
            try:
                # 尝试注册系统自带的冬青黑体（使用 .ttc 的简化路径）
                font_path = '/System/Library/Fonts/Hiragino Sans GB.ttc'
                if os.path.exists(font_path):
                    # 对于 TTC 文件，我们使用子字体索引 1（简体中文）
                    from reportlab.pdfbase.ttfonts import TTFError
                    try:
                        # 注册为简体中文字体
                        pdfmetrics.registerFont(TTFont('ChineseFont', font_path, subfontIndex=1))
                        chinese_font = 'ChineseFont'
                        logger.info(f"成功注册中文字体: Hiragino Sans GB (subfontIndex=1)")
                    except TTFError:
                        # 如果失败尝试其他索引
                        try:
                            pdfmetrics.registerFont(TTFont('ChineseFont', font_path, subfontIndex=0))
                            chinese_font = 'ChineseFont'
                            logger.info(f"成功注册中文字体: Hiragino Sans GB (subfontIndex=0)")
                        except:
                            logger.warning("Hiragino Sans GB 注册失败，尝试其他字体")
            except Exception as e:
                logger.warning(f"字体注册异常: {e}")

            # 如果主字体失败，尝试备用字体
            if chinese_font == 'Helvetica':
                try:
                    # 尝试 STHeiti（黑体-简）
                    stheiti_path = '/System/Library/Fonts/STHeiti Light.ttc'
                    if os.path.exists(stheiti_path):
                        pdfmetrics.registerFont(TTFont('ChineseFont', stheiti_path, subfontIndex=0))
                        chinese_font = 'ChineseFont'
                        logger.info("成功注册中文字体: STHeiti Light")
                except:
                    pass

            # 创建 PDF 文档
            doc = SimpleDocTemplate(
                str(filepath),
                pagesize=A4,
                rightMargin=0.75*inch,
                leftMargin=0.75*inch,
                topMargin=0.75*inch,
                bottomMargin=0.75*inch
            )

            # 构建文档内容
            story = []
            styles = getSampleStyleSheet()

            # 自定义样式
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=28,
                textColor=colors.whitesmoke,
                spaceAfter=12,
                alignment=TA_CENTER,
                fontName=chinese_font,
                leading=36
            )

            subtitle_style = ParagraphStyle(
                'CustomSubtitle',
                parent=styles['Normal'],
                fontSize=14,
                textColor=colors.whitesmoke,
                alignment=TA_CENTER,
                fontName=chinese_font
            )

            meta_style = ParagraphStyle(
                'CustomMeta',
                parent=styles['Normal'],
                fontSize=11,
                textColor=colors.white,
                alignment=TA_CENTER,
                fontName=chinese_font,
                leading=16
            )

            heading2_style = ParagraphStyle(
                'Heading2',
                parent=styles['Heading2'],
                fontSize=18,
                textColor=colors.HexColor('#667eea'),
                spaceAfter=12,
                spaceBefore=20,
                fontName=chinese_font,
                leading=24
            )

            heading3_style = ParagraphStyle(
                'Heading3',
                parent=styles['Heading3'],
                fontSize=14,
                textColor=colors.HexColor('#667eea'),
                spaceAfter=10,
                fontName=chinese_font
            )

            normal_style = ParagraphStyle(
                'BodyText',
                parent=styles['BodyText'],
                fontName=chinese_font,
                fontSize=10,
                leading=14,
                spaceAfter=6
            )

            # 1. 报告头部（渐变背景效果用紫色表格模拟）
            header_data = [
                [Paragraph("安全评估报告", title_style)],
                [Paragraph(f"目标: {target}", subtitle_style)],
                [Paragraph(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", meta_style)],
                [Paragraph(f"评估工具: HexStrike AI (Nmap + Nuclei)", meta_style)]
            ]

            header_table = Table(header_data, colWidths=[6.5*inch])
            header_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#667eea')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 20),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 20),
                ('LEFTPADDING', (0, 0), (-1, -1), 20),
                ('RIGHTPADDING', (0, 0), (-1, -1), 20),
            ]))

            story.append(header_table)
            story.append(Spacer(1, 0.3*inch))

            # 统计数据
            stats = self._extract_stats(nmap_results, nuclei_results)

            # 2. 统计卡片（5个卡片一行）
            card_data = []
            card_row = []

            # 定义卡片颜色
            card_colors = {
                'critical': colors.HexColor('#f56c6c'),
                'high': colors.HexColor('#e6a23c'),
                'medium': colors.HexColor('#409eff'),
                'low': colors.HexColor('#67c23a'),
                'ports': colors.HexColor('#909399')
            }

            # 创建5个统计卡片
            cards = [
                ('严重漏洞', stats['vulnerabilities']['critical'], card_colors['critical']),
                ('高危漏洞', stats['vulnerabilities']['high'], card_colors['high']),
                ('中危漏洞', stats['vulnerabilities']['medium'], card_colors['medium']),
                ('低危漏洞', stats['vulnerabilities']['low'], card_colors['low']),
                ('开放端口', stats['ports']['open'], card_colors['ports'])
            ]

            for label, value, color in cards:
                card_content = [
                    Paragraph(f"<b>{value}</b>", ParagraphStyle('CardNumber', fontName=chinese_font, fontSize=24, textColor=color, alignment=TA_CENTER)),
                    Paragraph(label, ParagraphStyle('CardLabel', fontName=chinese_font, fontSize=11, textColor=colors.grey, alignment=TA_CENTER))
                ]
                card_table = Table(card_content, colWidths=[1.2*inch])
                card_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('TOPPADDING', (0, 0), (-1, -1), 15),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey)
                ]))
                card_row.append(card_table)

            card_data.append(card_row)
            cards_table = Table(card_data)
            story.append(cards_table)
            story.append(Spacer(1, 0.3*inch))

            # 3. 漏洞扫描结果
            if nuclei_results and nuclei_results.get('success'):
                vuln_section = self._generate_vulnerabilities_section(nuclei_results, heading2_style, heading3_style, normal_style, chinese_font)
                if vuln_section:
                    story.extend(vuln_section)

            # 4. 端口扫描结果
            if nmap_results and nmap_results.get('success'):
                port_section = self._generate_ports_section(nmap_results, heading2_style, heading3_style, normal_style, chinese_font)
                if port_section:
                    story.extend(port_section)

            # 5. 安全建议
            recommendations = self._generate_recommendations_section(nmap_results, nuclei_results, heading2_style, heading3_style, normal_style, chinese_font)
            if recommendations:
                story.extend(recommendations)

            # 6. 页脚
            story.append(PageBreak())
            footer_style = ParagraphStyle(
                'Footer',
                parent=styles['Normal'],
                fontName=chinese_font,
                fontSize=10,
                textColor=colors.grey,
                alignment=TA_CENTER,
                leading=16
            )
            story.append(Paragraph("本报告由 HexStrike AI 自动生成", footer_style))
            story.append(Spacer(1, 0.1*inch))
            story.append(Paragraph("建议：定期进行安全评估，及时修复发现的漏洞", footer_style))
            story.append(Spacer(1, 0.1*inch))
            story.append(Paragraph(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", footer_style))

            # 生成 PDF
            doc.build(story)

            logger.info(f"PDF 报告生成成功: {filename}")
            return filename

        except ImportError:
            logger.error("reportlab 未安装，无法生成 PDF 报告")
            return None
        except Exception as e:
            logger.error(f"生成 PDF 报告失败: {e}", exc_info=True)
            return None

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

    def _generate_vulnerabilities_section(self, nuclei_results: Optional[Dict], heading2_style, heading3_style, normal_style, chinese_font: str) -> list:
        """生成漏洞列表部分（与HTML格式一致）"""
        try:
            import json
            from reportlab.platypus import Paragraph, Spacer, KeepTogether
            from reportlab.lib.enums import TA_LEFT
            from reportlab.lib import colors
            from reportlab.lib.styles import ParagraphStyle

            stdout = nuclei_results.get('stdout', '')
            if not stdout:
                return []

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
                story = []
                story.append(Paragraph("漏洞扫描结果", heading2_style))
                story.append(Paragraph("未发现已知漏洞", normal_style))
                story.append(Spacer(1, 0.2*inch))
                return story

            # 按严重性分组
            by_severity = {'critical': [], 'high': [], 'medium': [], 'low': [], 'info': []}
            for vuln in vulnerabilities:
                severity = vuln.get('info', {}).get('severity', 'info').lower()
                if severity not in by_severity:
                    severity = 'info'
                by_severity[severity].append(vuln)

            story = []
            story.append(Paragraph("🔍 漏洞扫描结果", heading2_style))

            severity_labels = {
                'critical': ('严重', colors.red),
                'high': ('高危', colors.orange),
                'medium': ('中危', colors.blue),
                'low': ('低危', colors.green),
                'info': ('信息', colors.grey)
            }

            for severity in ['critical', 'high', 'medium', 'low', 'info']:
                vulns = by_severity.get(severity, [])
                if not vulns:
                    continue

                label, color = severity_labels[severity]

                # 创建带边框的漏洞项
                for vuln in vulns[:20]:  # 最多显示 20 个
                    info = vuln.get('info', {})
                    name = info.get('name', 'Unknown')
                    description = info.get('description', '')[:200]
                    tags = info.get('tags', [])[:5]

                    # 漏洞标题（带严重性标签）
                    vuln_title = f'<font color="{self._color_to_hex(color)}"><b>[{label}]</b></font> <b>{name}</b>'

                    # 构建漏洞内容
                    vuln_content = [Paragraph(vuln_title, normal_style)]

                    # 添加标签
                    if tags:
                        tag_text = ' '.join([f'<font color="#409eff">#{tag}</font>' for tag in tags])
                        vuln_content.append(Paragraph(tag_text, ParagraphStyle('Tags', parent=normal_style, fontSize=9)))

                    # 添加描述
                    if description:
                        vuln_content.append(Paragraph(description + '...', ParagraphStyle('Desc', parent=normal_style, fontSize=9, textColor=colors.grey)))

                    # 创建漏洞项表格（带左边框颜色）
                    vuln_table = Table([
                        [vuln_content[0]],
                        [vuln_content[1]] if len(vuln_content) > 1 else [''],
                        [vuln_content[2]] if len(vuln_content) > 2 else ['']
                    ])
                    vuln_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                        ('LEFTPADDING', (0, 0), (-1, -1), 12),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                        ('TOPPADDING', (0, 0), (-1, -1), 10),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                        ('LINEBELOW', (0, 0), (0, -1), 4, color),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ]))

                    story.append(vuln_table)
                    story.append(Spacer(1, 0.05*inch))

                if len(vulns) > 20:
                    story.append(Paragraph(f"<i>还有 {len(vulns) - 20} 个{label}漏洞未显示...</i>", ParagraphStyle('Note', parent=normal_style, fontSize=9, textColor=colors.grey)))

                story.append(Spacer(1, 0.15*inch))

            return story

        except Exception as e:
            logger.warning(f"生成漏洞部分失败: {e}")
            return []

    def _generate_ports_section(self, nmap_results: Optional[Dict], heading2_style, heading3_style, normal_style, chinese_font: str) -> list:
        """生成端口列表部分（与HTML格式一致）"""
        try:
            import re
            from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
            from reportlab.lib import colors
            from reportlab.lib.styles import ParagraphStyle

            stdout = nmap_results.get('stdout', '')
            if not stdout:
                return []

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
                story = []
                story.append(Paragraph("🔌 端口扫描结果", heading2_style))
                story.append(Paragraph("未发现开放端口", normal_style))
                story.append(Spacer(1, 0.2*inch))
                return story

            story = []
            story.append(Paragraph("🔌 端口扫描结果", heading2_style))

            # 为每个端口创建卡片
            for port_info in ports:
                port = port_info['port']
                service = port_info['service']
                version = port_info['version']

                # 评估端口风险
                risk = self._assess_port_risk(port, service)
                risk_color = {
                    'critical': colors.HexColor('#f56c6c'),
                    'medium': colors.HexColor('#409eff'),
                    'low': colors.HexColor('#67c23a')
                }.get(risk['level'], colors.grey)

                # 端口号和服务
                port_content = [
                    Paragraph(f"<b>端口 {port}/tcp</b>", ParagraphStyle('PortNum', parent=normal_style, fontSize=13, fontName=chinese_font)),
                    Paragraph(f"服务：{service}", ParagraphStyle('Service', parent=normal_style, fontSize=10))
                ]

                # 风险标签
                if risk:
                    risk_label = f'<font color="{self._color_to_hex(risk_color)}">⚠️ {risk["label"]}</font>'
                    port_content[1] = Paragraph(f'服务：{service}  {risk_label}', ParagraphStyle('ServiceRisk', parent=normal_style, fontSize=10))

                # 版本信息
                if version:
                    port_content.append(Paragraph(version[:50], ParagraphStyle('Version', parent=normal_style, fontSize=9, textColor=colors.grey)))

                # 创建端口卡片表格
                port_table = Table([[content] for content in port_content])
                port_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f9f9f9')),
                    ('LEFTPADDING', (0, 0), (-1, -1), 12),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                    ('TOPPADDING', (0, 0), (-1, -1), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                    ('LINEBELOW', (0, 0), (0, -1), 4, risk_color),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]))

                story.append(port_table)
                story.append(Spacer(1, 0.1*inch))

            return story

        except Exception as e:
            logger.warning(f"生成端口部分失败: {e}")
            return []

    def _generate_recommendations_section(self, nmap_results: Optional[Dict], nuclei_results: Optional[Dict], heading2_style, heading3_style, normal_style, chinese_font: str) -> list:
        """生成修复建议部分（与HTML格式一致）"""
        try:
            from reportlab.platypus import Paragraph, Spacer
            from reportlab.lib import colors

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

            if not recommendations:
                return []

            story = []
            story.append(Paragraph("💡 安全建议", heading2_style))

            for rec in recommendations:
                # 建议卡片
                rec_style = ParagraphStyle(
                    'Recommendation',
                    parent=normal_style,
                    fontName=chinese_font,
                    backColor=colors.HexColor('#f0f9ff'),
                    leftIndent=12,
                    rightIndent=12,
                    topIndent=12,
                    bottomIndent=12
                )

                story.append(Paragraph(f"<b>{rec['title']}</b>", heading3_style))

                for item in rec['items']:
                    story.append(Paragraph(f"• {item}", rec_style))

                story.append(Spacer(1, 0.1*inch))

            return story

        except Exception as e:
            logger.warning(f"生成建议部分失败: {e}")
            return []

    def _assess_port_risk(self, port: str, service: str) -> Optional[Dict]:
        """评估端口风险（与HTML一致）"""
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

    def _color_to_hex(self, color) -> str:
        """将ReportLab颜色转换为十六进制字符串"""
        if hasattr(color, 'red'):  # 是CMYKColor或RGBColor
            try:
                return f"#{int(color.red*255):02x}{int(color.green*255):02x}{int(color.blue*255):02x}"
            except:
                return "#000000"
        return "#000000"