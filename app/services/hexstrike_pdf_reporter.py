"""
HexStrike 扫描报告 PDF 生成器
基于 HTML 报告生成 PDF 格式
"""
import os
import logging
from typing import Dict, Any, Optional
from django.conf import settings

logger = logging.getLogger(__name__)


class HexStrikePDFReporter:
    """HexStrike PDF 报告生成器"""

    def __init__(self, reports_dir: Optional[str] = None):
        """
        初始化 PDF 报告生成器

        Args:
            reports_dir: 报告保存目录，默认为 BASE_DIR/reports
        """
        if reports_dir is None:
            from pathlib import Path
            base_dir = Path(settings.BASE_DIR)
            reports_dir = base_dir / 'reports'

        self.reports_dir = reports_dir
        os.makedirs(self.reports_dir, exist_ok=True)

    def generate_pdf_from_html(
        self,
        html_file_path: str,
        target: str
    ) -> Optional[str]:
        """
        从 HTML 文件生成 PDF 报告

        Args:
            html_file_path: HTML 报告文件路径
            target: 扫描目标

        Returns:
            PDF 报告文件路径（相对于 reports 目录），失败返回 None
        """
        try:
            from weasyprint import HTML, CSS

            # 生成 PDF 文件名
            pdf_filename = html_file_path.replace('.html', '.pdf')
            pdf_file_path = os.path.join(self.reports_dir, pdf_filename)

            # 读取 HTML 文件并转换为 PDF
            logger.info(f"开始生成 PDF 报告: {pdf_filename}")

            # 从 HTML 文件生成 PDF
            HTML(filename=html_file_path).write_pdf(
                pdf_file_path,
                stylesheets=[
                    CSS(string='''
                        @page {
                            size: A4;
                            margin: 2cm;
                        }
                        body {
                            font-family: Arial, "Microsoft YaHei", sans-serif;
                        }
                        table {
                            page-break-inside: avoid;
                        }
                        h1, h2, h3 {
                            page-break-after: avoid;
                        }
                    ''')
                ]
            )

            logger.info(f"PDF 报告生成成功: {pdf_filename}")
            return pdf_filename

        except ImportError:
            logger.error("weasyprint 未安装，无法生成 PDF 报告")
            return None
        except Exception as e:
            logger.error(f"生成 PDF 报告失败: {e}", exc_info=True)
            return None

    def generate_pdf_report(
        self,
        target: str,
        nmap_results: Optional[Dict] = None,
        nuclei_results: Optional[Dict] = None,
        target_profile: Optional[Dict] = None
    ) -> Optional[str]:
        """
        生成 PDF 报告（先生成 HTML，再转换为 PDF）

        Args:
            target: 扫描目标
            nmap_results: Nmap 扫描结果
            nuclei_results: Nuclei 扫描结果
            target_profile: 目标画像

        Returns:
            PDF 报告文件路径（相对于 reports 目录），失败返回 None
        """
        try:
            # 先生成 HTML 报告
            from app.services.hexstrike_html_reporter import HexStrikeHTMLReporter

            html_reporter = HexStrikeHTMLReporter(self.reports_dir)
            html_filename = html_reporter.generate_report(
                target=target,
                nmap_results=nmap_results,
                nuclei_results=nuclei_results,
                target_profile=target_profile
            )

            if not html_filename:
                logger.error("HTML 报告生成失败，无法生成 PDF")
                return None

            # 从 HTML 生成 PDF
            html_file_path = os.path.join(self.reports_dir, html_filename)
            pdf_filename = self.generate_pdf_from_html(html_file_path, target)

            return pdf_filename

        except Exception as e:
            logger.error(f"生成 PDF 报告失败: {e}", exc_info=True)
            return None