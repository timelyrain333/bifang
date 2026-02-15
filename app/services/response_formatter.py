"""
响应格式化器
统一处理 HexStrike 结果格式化、HTML 报告生成等
"""
import json
import logging
from typing import Dict, Any, Optional, Generator
from pathlib import Path
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class ResponseFormatter:
    """统一的响应格式化器"""

    @staticmethod
    def format_target_profile(target_profile: Dict[str, Any]) -> str:
        """
        格式化目标画像为友好的 Markdown 文本

        Args:
            target_profile: 目标画像数据

        Returns:
            str: 格式化后的 Markdown 文本
        """
        if not target_profile:
            return "_暂无目标画像信息_\n"

        lines = []

        # 基本信息
        target = target_profile.get('target', 'Unknown')
        target_type = target_profile.get('target_type', 'Unknown')
        risk_level = target_profile.get('risk_level', 'unknown')
        attack_surface_score = target_profile.get('attack_surface_score', 0)

        # 风险等级图标
        risk_icons = {
            'critical': '🔴 严重',
            'high': '🟠 高危',
            'medium': '🟡 中危',
            'low': '🟢 低危',
            'info': '🔵 信息'
        }
        risk_display = risk_icons.get(risk_level.lower(), f'⚪ {risk_level}')

        lines.append(f"**🎯 扫描目标**：`{target}`")
        lines.append(f"**📋 目标类型**：{target_type}")
        lines.append(f"**⚠️ 风险等级**：{risk_display}")
        lines.append(f"**📊 攻击面评分**：{attack_surface_score}/10")
        lines.append("")

        # IP 地址
        if target_profile.get('ip_addresses'):
            lines.append("**🌐 IP 地址**：")
            for ip in target_profile['ip_addresses']:
                lines.append(f"  - `{ip}`")
            lines.append("")

        # 域名/子域名
        if target_profile.get('subdomains'):
            lines.append("**🔗 子域名**：")
            for subdomain in target_profile['subdomains'][:10]:  # 限制显示数量
                lines.append(f"  - `{subdomain}`")
            if len(target_profile['subdomains']) > 10:
                lines.append(f"  - _还有 {len(target_profile['subdomains']) - 10} 个子域名..._")
            lines.append("")

        # 开放端口
        if target_profile.get('open_ports'):
            lines.append("**🔌 开放端口**：")
            for port_info in target_profile['open_ports'][:15]:  # 限制显示数量
                port = port_info.get('port', 'Unknown')
                service = port_info.get('service', 'Unknown')
                lines.append(f"  - **{port}** ({service})")
            if len(target_profile['open_ports']) > 15:
                lines.append(f"  - _还有 {len(target_profile['open_ports']) - 15} 个端口..._")
            lines.append("")

        # 服务
        if target_profile.get('services'):
            lines.append("**⚙️ 发现的服务**：")
            for service_name, service_info in list(target_profile['services'].items())[:10]:
                lines.append(f"  - **{service_name}**：{service_info}")
            if len(target_profile['services']) > 10:
                lines.append(f"  - _还有 {len(target_profile['services']) - 10} 个服务..._")
            lines.append("")

        # 技术/框架
        if target_profile.get('technologies'):
            lines.append("**💻 识别的技术**：")
            for tech in target_profile['technologies'][:15]:
                lines.append(f"  - {tech}")
            if len(target_profile['technologies']) > 15:
                lines.append(f"  - _还有 {len(target_profile['technologies']) - 15} 个技术..._")
            lines.append("")

        # 云服务提供商
        if target_profile.get('cloud_provider'):
            lines.append(f"**☁️ 云服务提供商**：{target_profile['cloud_provider']}")
            lines.append("")

        # CMS
        if target_profile.get('cms_type'):
            lines.append(f"**📝 CMS 类型**：{target_profile['cms_type']}")
            lines.append("")

        # SSL/TLS 信息
        if target_profile.get('ssl_info'):
            lines.append("**🔐 SSL/TLS 信息**：")
            ssl_info = target_profile['ssl_info']
            if ssl_info.get('valid'):
                lines.append("  - ✅ 证书有效")
            else:
                lines.append("  - ⚠️ 证书无效或过期")
            if ssl_info.get('issuer'):
                lines.append(f"  - 颁发者：{ssl_info['issuer']}")
            lines.append("")

        # 安全头部
        if target_profile.get('security_headers'):
            lines.append("**🛡️ 安全头部**：")
            for header_name, header_value in target_profile['security_headers'].items():
                status = "✅" if header_value else "❌"
                lines.append(f"  - {status} {header_name}")
            lines.append("")

        # 端点
        if target_profile.get('endpoints'):
            lines.append("**🔗 发现的端点**：")
            for endpoint in target_profile['endpoints'][:15]:
                lines.append(f"  - `{endpoint}`")
            if len(target_profile['endpoints']) > 15:
                lines.append(f"  - _还有 {len(target_profile['endpoints']) - 15} 个端点..._")
            lines.append("")

        # 如果没有任何详细信息
        if len(lines) <= 4:  # 只有基本标题行
            lines.append("_目标画像信息较少，等待扫描结果补充..._\n")

        return '\n'.join(lines)

    @staticmethod
    def format_hexstrike_result(
        target: str,
        result: Dict[str, Any],
        include_html_report: bool = True
    ) -> Generator[str, None, None]:
        """
        格式化 HexStrike 分析结果为 Markdown

        Args:
            target: 目标地址
            result: HexStrike 返回结果
            include_html_report: 是否包含 HTML 报告链接

        Yields:
            str: Markdown 文本片段
        """
        if not result.get('success') or result.get('data') is None:
            yield f"### ❌ {result.get('message', 'HexStrike 分析失败')}\n\n"
            return

        data = result.get('data', {})

        if not isinstance(data, dict):
            yield f"### ✅ 已对目标 {target} 完成安全分析\n\n"
            yield f"```\n{str(data)[:2000]}\n```\n\n"
            return

        # 标题
        yield f"### ✅ 已对目标 {target} 完成安全分析\n\n"

        # 1. 显示目标画像
        if 'target_profile' in data and data['target_profile']:
            target_profile = data['target_profile']
            formatted_profile = ResponseFormatter.format_target_profile(target_profile)
            yield "## 📊 目标画像\n\n"
            yield formatted_profile
            yield "\n\n"

        # 2. 格式化 Nmap 结果
        if 'nmap_results' in data and data['nmap_results']:
            nmap_data = data['nmap_results']
            stdout = nmap_data.get('stdout', '')
            stderr = nmap_data.get('stderr', '')

            if stdout or stderr:
                try:
                    from app.services.nmap_result_parser import format_nmap_result
                    formatted_nmap = format_nmap_result(stdout, stderr)
                    yield "## 🔍 Nmap 端口扫描结果\n\n"
                    yield formatted_nmap
                    yield "\n\n"
                except Exception as e:
                    logger.warning(f"Nmap 结果格式化失败: {e}")
                    yield "## 🔍 Nmap 端口扫描结果\n\n"
                    yield f"```\n{stdout[:1000]}\n```\n\n"

        # 3. 格式化 Nuclei 结果
        if 'nuclei_results' in data and data['nuclei_results']:
            nuclei_data = data['nuclei_results']
            stdout = nuclei_data.get('stdout', '')
            stderr = nuclei_data.get('stderr', '')

            # 检查是否超时
            if nuclei_data.get('timed_out') or 'timed out' in str(nuclei_data).lower():
                yield "## 🔍 Nuclei 漏洞扫描结果\n\n"
                yield "⚠️ 扫描超时（超过10分钟），建议分端口扫描或减少扫描范围\n\n"
            elif stdout or stderr:
                try:
                    from app.services.nuclei_result_parser import format_nuclei_result
                    formatted_nuclei = format_nuclei_result(stdout, stderr)
                    yield "## 🔍 Nuclei 漏洞扫描结果\n\n"
                    yield formatted_nuclei
                    yield "\n\n"
                except Exception as e:
                    logger.warning(f"Nuclei 结果格式化失败: {e}")
                    yield "## 🔍 Nuclei 漏洞扫描结果\n\n"
                    yield f"```\n{stdout[:1000]}\n```\n\n"

        # 4. 如果没有 nmap/nuclei 结果，但有其他数据
        if 'nmap_results' not in data and 'nuclei_results' not in data:
            yield "## 📊 分析结果\n\n"
            yield f"```json\n{json.dumps(data, ensure_ascii=False, indent=2)}\n```\n\n"

        # 5. 生成 ZIP 报告包（如果需要）
        if include_html_report:
            try:
                report_filename = ResponseFormatter.generate_zip_report(
                    target=target,
                    nmap_results=data.get('nmap_results'),
                    nuclei_results=data.get('nuclei_results'),
                    target_profile=data.get('target_profile')
                )

                if report_filename:
                    # 构建下载链接
                    download_url = ResponseFormatter.build_report_download_url(report_filename)
                    yield f"---\n\n"
                    yield f"📦 **完整报告下载**：[点击下载报告包 (HTML + PDF)]({download_url})\n"
            except Exception as e:
                logger.warning(f"生成 ZIP 报告失败: {e}", exc_info=True)

    @staticmethod
    def generate_zip_report(
        target: str,
        nmap_results: Optional[Dict] = None,
        nuclei_results: Optional[Dict] = None,
        target_profile: Optional[Dict] = None
    ) -> Optional[str]:
        """
        生成 ZIP 格式的报告包（包含 HTML 和 PDF）

        Args:
            target: 目标地址
            nmap_results: Nmap 扫描结果
            nuclei_results: Nuclei 扫描结果
            target_profile: 目标画像

        Returns:
            str: ZIP 报告文件名，失败返回 None
        """
        try:
            from app.services.hexstrike_html_reporter import HexStrikeHTMLReporter
            from app.services.hexstrike_pdf_reporter import HexStrikePDFReporter
            from app.services.hexstrike_zip_reporter import HexStrikeZipReporter

            # 1. 生成 HTML 报告
            html_reporter = HexStrikeHTMLReporter()
            html_filename = html_reporter.generate_report(
                target=target,
                nmap_results=nmap_results,
                nuclei_results=nuclei_results,
                target_profile=target_profile
            )

            if not html_filename:
                logger.error("HTML 报告生成失败")
                return None

            logger.info(f"HTML 报告已生成: {html_filename}")

            # 2. 生成 PDF 报告
            pdf_reporter = HexStrikePDFReporter()
            pdf_filename = pdf_reporter.generate_pdf_report(
                target=target,
                nmap_results=nmap_results,
                nuclei_results=nuclei_results,
                target_profile=target_profile
            )

            if pdf_filename:
                logger.info(f"PDF 报告已生成: {pdf_filename}")
            else:
                logger.warning("PDF 报告生成失败，ZIP 包中将只包含 HTML 报告")
                pdf_filename = None

            # 3. 打包成 ZIP
            zip_reporter = HexStrikeZipReporter()
            zip_filename = zip_reporter.create_zip_from_html_and_pdf(
                target=target,
                html_filename=html_filename,
                pdf_filename=pdf_filename
            )

            if zip_filename:
                logger.info(f"ZIP 报告包已生成: {zip_filename} (包含 HTML 和 PDF)")
            else:
                logger.error("ZIP 报告包生成失败")

            return zip_filename

        except Exception as e:
            logger.error(f"生成 ZIP 报告失败: {e}", exc_info=True)
            return None

    @staticmethod
    def generate_html_report(
        target: str,
        nmap_results: Optional[Dict] = None,
        nuclei_results: Optional[Dict] = None,
        target_profile: Optional[Dict] = None
    ) -> Optional[str]:
        """
        生成 HTML 安全评估报告（保留以兼容旧代码）

        Args:
            target: 目标地址
            nmap_results: Nmap 扫描结果
            nuclei_results: Nuclei 扫描结果
            target_profile: 目标画像

        Returns:
            str: 报告文件名，失败返回 None
        """
        try:
            from app.services.hexstrike_html_reporter import HexStrikeHTMLReporter

            reporter = HexStrikeHTMLReporter()

            report_filename = reporter.generate_report(
                target=target,
                nmap_results=nmap_results,
                nuclei_results=nuclei_results,
                target_profile=target_profile
            )

            logger.info(f"HTML 报告已生成: {report_filename}")
            return report_filename

        except Exception as e:
            logger.error(f"生成 HTML 报告失败: {e}", exc_info=True)
            return None

    @staticmethod
    def build_report_download_url(filename: str) -> str:
        """
        构建报告下载 URL

        Args:
            filename: 报告文件名

        Returns:
            str: 下载 URL
        """
        # 获取服务器地址
        allowed_hosts = getattr(settings, 'ALLOWED_HOSTS', ['localhost'])

        # 优先使用配置的域名
        if allowed_hosts and allowed_hosts[0] not in ['*', 'localhost']:
            host = allowed_hosts[0]
        else:
            # 本地开发环境
            host = 'localhost:8000'

        # 构建完整 URL
        return f"http://{host}/api/reports/hexstrike/{filename}"

    @staticmethod
    def format_hexstrike_result_simple(
        target: str,
        result: Dict[str, Any],
        include_html_report: bool = True
    ) -> str:
        """
        格式化 HexStrike 分析结果（非流式，返回完整字符串）

        Args:
            target: 目标地址
            result: HexStrike 返回结果
            include_html_report: 是否包含 HTML 报告链接

        Returns:
            str: 格式化后的完整文本
        """
        parts = []
        for chunk in ResponseFormatter.format_hexstrike_result(
            target, result, include_html_report
        ):
            parts.append(chunk)

        return ''.join(parts)

    @staticmethod
    def format_hexstrike_result_with_html_download(
        target: str,
        nmap_data: Optional[Dict],
        nuclei_data: Optional[Dict],
        target_profile: Optional[Dict],
        base_url: Optional[str] = None
    ) -> str:
        """
        格式化 HexStrike 结果并添加 HTML 下载链接（兼容旧代码）

        Args:
            target: 目标地址
            nmap_data: Nmap 结果
            nuclei_data: Nuclei 结果
            target_profile: 目标画像
            base_url: 基础 URL（可选，用于钉钉等）

        Returns:
            str: 格式化后的文本
        """
        # 构造结果对象
        result = {
            'success': True,
            'data': {}
        }

        if nmap_data:
            result['data']['nmap_results'] = nmap_data
        if nuclei_data:
            result['data']['nuclei_results'] = nuclei_data
        if target_profile:
            result['data']['target_profile'] = target_profile

        # 生成格式化文本
        formatted = ResponseFormatter.format_hexstrike_result_simple(
            target=target,
            result=result,
            include_html_report=False  # 我们手动添加下载链接
        )

        # 生成 HTML 报告并添加下载链接
        try:
            report_filename = ResponseFormatter.generate_html_report(
                target=target,
                nmap_results=nmap_data,
                nuclei_results=nuclei_data,
                target_profile=target_profile
            )

            if report_filename:
                # 如果提供了 base_url，使用它；否则使用默认
                if base_url:
                    download_url = f"{base_url}/api/reports/hexstrike/{report_filename}"
                else:
                    download_url = ResponseFormatter.build_report_download_url(report_filename)

                formatted += f"\n\n---\n\n"
                formatted += f"📄 **完整报告下载**：[点击下载 HTML 报告]({download_url})\n"
        except Exception as e:
            logger.warning(f"生成 HTML 报告失败: {e}")

        return formatted