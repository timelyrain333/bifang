"""
HexStrike 扫描报告 ZIP 打包服务
将 HTML 和 PDF 报告打包成 ZIP 文件
"""
import os
import zipfile
import logging
from typing import List, Optional
from django.conf import settings

logger = logging.getLogger(__name__)


class HexStrikeZipReporter:
    """HexStrike 报告 ZIP 打包服务"""

    def __init__(self, reports_dir: Optional[str] = None):
        """
        初始化 ZIP 打包服务

        Args:
            reports_dir: 报告保存目录，默认为 BASE_DIR/reports
        """
        if reports_dir is None:
            from pathlib import Path
            base_dir = Path(settings.BASE_DIR)
            reports_dir = base_dir / 'reports'

        self.reports_dir = reports_dir
        os.makedirs(self.reports_dir, exist_ok=True)

    def create_zip_report(
        self,
        target: str,
        report_files: List[str],
        zip_filename: Optional[str] = None
    ) -> Optional[str]:
        """
        创建包含多个报告的 ZIP 文件

        Args:
            target: 扫描目标
            report_files: 报告文件列表（相对于 reports 目录的文件名）
            zip_filename: ZIP 文件名（可选，自动生成）

        Returns:
            ZIP 文件路径（相对于 reports 目录），失败返回 None
        """
        try:
            from datetime import datetime

            # 生成 ZIP 文件名
            if zip_filename is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                zip_filename = f"hexstrike_report_{target.replace('.', '_').replace(':', '_')}_{timestamp}.zip"

            zip_file_path = os.path.join(self.reports_dir, zip_filename)

            logger.info(f"开始创建 ZIP 报告: {zip_filename}")

            # 创建 ZIP 文件
            with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for report_file in report_files:
                    # 完整文件路径
                    full_path = os.path.join(self.reports_dir, report_file)

                    # 检查文件是否存在
                    if not os.path.exists(full_path):
                        logger.warning(f"报告文件不存在，跳过: {report_file}")
                        continue

                    # 添加到 ZIP，使用简化的文件名
                    arcname = report_file  # 使用相对路径
                    zipf.write(full_path, arcname)
                    logger.info(f"已添加到 ZIP: {report_file}")

            logger.info(f"ZIP 报告创建成功: {zip_filename}")
            return zip_filename

        except Exception as e:
            logger.error(f"创建 ZIP 报告失败: {e}", exc_info=True)
            return None

    def create_zip_from_html_and_pdf(
        self,
        target: str,
        html_filename: str,
        pdf_filename: Optional[str] = None,
        zip_filename: Optional[str] = None
    ) -> Optional[str]:
        """
        从 HTML 和 PDF 文件创建 ZIP 报告

        Args:
            target: 扫描目标
            html_filename: HTML 报告文件名
            pdf_filename: PDF 报告文件名（可选）
            zip_filename: ZIP 文件名（可选，自动生成）

        Returns:
            ZIP 文件路径（相对于 reports 目录），失败返回 None
        """
        report_files = [html_filename]

        # 如果 PDF 文件存在且有效，添加到列表
        if pdf_filename:
            pdf_path = os.path.join(self.reports_dir, pdf_filename)
            if os.path.exists(pdf_path):
                report_files.append(pdf_filename)

        return self.create_zip_report(target, report_files, zip_filename)