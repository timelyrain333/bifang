"""
HexStrike 扫描报告 PDF 生成器
使用 ReportLab 直接生成 PDF 格式报告
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
                fontSize=24,
                textColor=colors.HexColor('#667eea'),
                spaceAfter=30,
                alignment=TA_CENTER,
                fontName=chinese_font
            )

            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=16,
                textColor=colors.HexColor('#667eea'),
                spaceAfter=12,
                spaceBefore=20,
                fontName=chinese_font
            )

            normal_style = ParagraphStyle(
                'BodyText',
                parent=styles['BodyText'],
                fontName=chinese_font,
                fontSize=10
            )

            # 标题
            story.append(Paragraph("安全评估报告", title_style))
            story.append(Paragraph(f"目标: {target}", normal_style))
            story.append(Paragraph(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", normal_style))
            story.append(Paragraph(f"评估工具: HexStrike AI (Nmap + Nuclei)", normal_style))
            story.append(Spacer(1, 0.3*inch))

            # 统计数据
            stats = self._extract_stats(nmap_results, nuclei_results)

            # 统计卡片表格
            stats_data = [
                ['严重漏洞', str(stats['vulnerabilities']['critical'])],
                ['高危漏洞', str(stats['vulnerabilities']['high'])],
                ['中危漏洞', str(stats['vulnerabilities']['medium'])],
                ['低危漏洞', str(stats['vulnerabilities']['low'])],
                ['开放端口', str(stats['ports']['open'])],
            ]

            stats_table = Table(stats_data, colWidths=[2.5*inch, 2.5*inch])
            stats_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), chinese_font),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))

            story.append(stats_table)
            story.append(Spacer(1, 0.3*inch))

            # 漏洞列表
            if nuclei_results and nuclei_results.get('success'):
                vuln_section = self._generate_vulnerabilities_section(nuclei_results, styles, chinese_font)
                if vuln_section:
                    story.extend(vuln_section)

            # 端口列表
            if nmap_results and nmap_results.get('success'):
                port_section = self._generate_ports_section(nmap_results, styles, chinese_font)
                if port_section:
                    story.extend(port_section)

            # 安全建议
            recommendations = self._generate_recommendations_section(nmap_results, nuclei_results, styles, chinese_font)
            if recommendations:
                story.extend(recommendations)

            # 页脚
            story.append(PageBreak())
            story.append(Paragraph("本报告由 HexStrike AI 自动生成", normal_style))
            story.append(Spacer(1, 0.1*inch))
            story.append(Paragraph("建议: 定期进行安全评估，及时修复发现的漏洞", normal_style))
            story.append(Spacer(1, 0.1*inch))
            story.append(Paragraph(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", normal_style))

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

    def _generate_vulnerabilities_section(self, nuclei_results: Optional[Dict], styles, chinese_font: str) -> list:
        """生成漏洞列表部分"""
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
                heading_style = ParagraphStyle(
                    'CustomHeading2',
                    parent=styles['Heading2'],
                    fontName=chinese_font
                )
                body_style = ParagraphStyle(
                    'CustomBody',
                    parent=styles['BodyText'],
                    fontName=chinese_font
                )
                return [Paragraph("未发现漏洞", heading_style), Spacer(1, 0.2*inch)]

            # 按严重性分组
            by_severity = {'critical': [], 'high': [], 'medium': [], 'low': [], 'info': []}
            for vuln in vulnerabilities:
                severity = vuln.get('info', {}).get('severity', 'info').lower()
                if severity not in by_severity:
                    severity = 'info'
                by_severity[severity].append(vuln)

            story = []
            heading2_style = ParagraphStyle(
                'CustomHeading2',
                parent=styles['Heading2'],
                fontName=chinese_font
            )
            heading3_style = ParagraphStyle(
                'CustomHeading3',
                parent=styles['Heading3'],
                fontName=chinese_font
            )
            body_style = ParagraphStyle(
                'CustomBody',
                parent=styles['BodyText'],
                fontName=chinese_font
            )

            story.append(Paragraph("漏洞扫描结果", heading2_style))

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
                story.append(Paragraph(f"{label.upper()} ({len(vulns)})", heading3_style))

                for vuln in vulns[:20]:  # 最多显示 20 个
                    info = vuln.get('info', {})
                    name = info.get('name', 'Unknown')
                    description = info.get('description', '')[:200]

                    vuln_text = f"<b>{name}</b>"
                    if description:
                        vuln_text += f"<br/>{description}..."

                    story.append(Paragraph(vuln_text, body_style))
                    story.append(Spacer(1, 0.1*inch))

                if len(vulns) > 20:
                    story.append(Paragraph(f"还有 {len(vulns) - 20} 个{label}漏洞未显示", body_style))

                story.append(Spacer(1, 0.2*inch))

            return story

        except Exception as e:
            logger.warning(f"生成漏洞部分失败: {e}")
            return []

    def _generate_ports_section(self, nmap_results: Optional[Dict], styles, chinese_font: str) -> list:
        """生成端口列表部分"""
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
                heading_style = ParagraphStyle(
                    'CustomHeading2',
                    parent=styles['Heading2'],
                    fontName=chinese_font
                )
                body_style = ParagraphStyle(
                    'CustomBody',
                    parent=styles['BodyText'],
                    fontName=chinese_font
                )
                return [Paragraph("端口扫描结果", heading_style), Spacer(1, 0.2*inch), Paragraph("未发现开放端口。", body_style), Spacer(1, 0.2*inch)]

            story = []
            heading_style = ParagraphStyle(
                'CustomHeading2',
                parent=styles['Heading2'],
                fontName=chinese_font
            )
            story.append(Paragraph("端口扫描结果", heading_style))

            # 创建端口表格
            port_data = [['端口', '服务', '版本']]
            for port_info in ports:
                port_data.append([
                    f"{port_info['port']}/tcp",
                    port_info['service'],
                    port_info['version'][:30] if port_info['version'] else ''
                ])

            port_table = Table(port_data, colWidths=[1.5*inch, 2*inch, 2.5*inch])
            port_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), chinese_font),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('FONTSIZE', (0, 1), (-1, -1), 9)
            ]))

            story.append(port_table)
            story.append(Spacer(1, 0.2*inch))

            return story

        except Exception as e:
            logger.warning(f"生成端口部分失败: {e}")
            return []

    def _generate_recommendations_section(self, nmap_results: Optional[Dict], nuclei_results: Optional[Dict], styles, chinese_font: str) -> list:
        """生成修复建议部分"""
        try:
            from reportlab.platypus import Paragraph, Spacer
            from reportlab.lib.styles import ParagraphStyle

            recommendations = []

            # 基于 Nmap 结果的建议
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

            # 基于 Nuclei 结果的建议
            if nuclei_results and nuclei_results.get('success'):
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

            if not recommendations:
                return []

            heading_style = ParagraphStyle(
                'CustomHeading2',
                parent=styles['Heading2'],
                fontName=chinese_font
            )
            heading3_style = ParagraphStyle(
                'CustomHeading3',
                parent=styles['Heading3'],
                fontName=chinese_font
            )
            body_style = ParagraphStyle(
                'CustomBody',
                parent=styles['BodyText'],
                fontName=chinese_font
            )

            story = []
            story.append(Paragraph("安全建议", heading_style))

            for rec in recommendations:
                story.append(Paragraph(f"<b>{rec['title']}</b>", heading3_style))
                for item in rec['items']:
                    story.append(Paragraph(f"• {item}", body_style))
                story.append(Spacer(1, 0.1*inch))

            return story

        except Exception as e:
            logger.warning(f"生成建议部分失败: {e}")
            return []
