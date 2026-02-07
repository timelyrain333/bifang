"""
HexStrike AI 客户端
对接 HexStrike AI MCP Server (https://github.com/0x4m4/hexstrike-ai)，实现对资产的安全评估能力。

官方 API 参考: https://github.com/0x4m4/hexstrike-ai#api-reference
- GET /health - 健康检查与工具可用性
- POST /api/intelligence/analyze-target - AI 目标分析
- POST /api/intelligence/select-tools - 智能工具选择
- POST /api/intelligence/optimize-parameters - 参数优化
- POST /api/command - 执行命令（带缓存）

常用工具名（与官方 MCP 一致）:
- 网络: nmap_scan, rustscan_scan, masscan_scan, autorecon_scan, amass_enum
- Web: gobuster_scan, feroxbuster_scan, ffuf_scan, nuclei_scan, sqlmap_scan, wpscan_scan
- 云: prowler_assess, scout_suite_audit, trivy_scan, kube_hunter_scan, kube_bench_check
"""
import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class HexStrikeClient:
    """HexStrike AI HTTP 客户端"""

    def __init__(self, base_url: str, timeout: int = 300):
        """
        Args:
            base_url: HexStrike Server 地址，如 http://localhost:8888
            timeout: 请求超时秒数（安全扫描可能较长，默认300秒）
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({'Content-Type': 'application/json'})

    def health(self) -> Dict[str, Any]:
        """
        健康检查，确认 HexStrike 服务是否可用。
        GET /health
        """
        try:
            r = self._session.get(f'{self.base_url}/health', timeout=10)
            r.raise_for_status()
            return {'success': True, 'data': r.json() if r.text else {}}
        except requests.RequestException as e:
            logger.warning(f"HexStrike health check failed: {e}")
            return {'success': False, 'message': str(e), 'data': None}

    def clear_cache(self) -> Dict[str, Any]:
        """
        清除 HexStrike 缓存，确保下次扫描返回最新结果。
        POST /api/cache/clear
        """
        try:
            r = self._session.post(f'{self.base_url}/api/cache/clear', timeout=10)
            r.raise_for_status()
            data = r.json() if r.text else {}
            logger.info("HexStrike: 缓存已清除")
            return {'success': True, 'data': data}
        except requests.RequestException as e:
            logger.warning(f"HexStrike clear cache failed: {e}")
            return {'success': False, 'message': str(e), 'data': None}

    def analyze_target(self, target: str, analysis_type: str = 'comprehensive') -> Dict[str, Any]:
        """
        AI 驱动的目标分析（官方: POST /api/intelligence/analyze-target）。
        由 HexStrike 决策引擎分析目标并选择策略；实际扫描需通过 run_command 执行具体工具。
        请求体与官方示例一致: {"target": "example.com", "analysis_type": "comprehensive"}
        """
        logger.info("HexStrike: 调用 analyze_target, target=%s, analysis_type=%s", target, analysis_type)
        try:
            payload = {'target': target, 'analysis_type': analysis_type}
            r = self._session.post(
                f'{self.base_url}/api/intelligence/analyze-target',
                json=payload,
                timeout=self.timeout
            )
            r.raise_for_status()
            data = r.json() if r.text else {}
            logger.info("HexStrike: analyze_target 成功, target=%s", target)
            return {'success': True, 'data': data}
        except requests.RequestException as e:
            logger.exception(f"HexStrike analyze_target failed: {e}")
            return {'success': False, 'message': str(e), 'data': None}

    def select_tools(self, target: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        智能工具选择（官方: POST /api/intelligence/select-tools）。
        返回针对目标推荐的工具列表，可用于在 run_command 前决定执行哪些扫描。
        """
        logger.info("HexStrike: 调用 select_tools, target=%s", target)
        try:
            payload = {'target': target, **(context or {})}
            r = self._session.post(
                f'{self.base_url}/api/intelligence/select-tools',
                json=payload,
                timeout=60,
            )
            r.raise_for_status()
            data = r.json() if r.text else {}
            logger.info("HexStrike: select_tools 成功, target=%s", target)
            return {'success': True, 'data': data}
        except requests.RequestException as e:
            logger.exception("HexStrike select_tools failed: %s", e)
            return {'success': False, 'message': str(e), 'data': None}

    # HexStrike 服务端将工具名当作 shell 命令执行，需用实际可执行文件名（nmap/nuclei）而非 MCP 名（nmap_scan/nuclei_scan）
    _TOOL_NAME_TO_BINARY = {
        'nmap_scan': 'nmap',
        'nuclei_scan': 'nuclei',
        'gobuster_scan': 'gobuster',
        'masscan_scan': 'masscan',
        'ffuf_scan': 'ffuf',
        'sqlmap_scan': 'sqlmap',
    }

    def run_command(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        执行指定安全工具。优先尝试 POST /api/tools/<tool_name>（请求体=arguments），
        若 404 再尝试 POST /api/command。工具名支持 MCP 名（nmap_scan）或二进制名（nmap），
        内部会映射为实际可执行文件名以避免 "not found"。
        """
        arguments = arguments or {}
        # 若传入的是 MCP 名，映射为实际可执行文件名（HexStrike 将工具名当作 shell 命令执行）
        api_tool_name = self._TOOL_NAME_TO_BINARY.get(tool_name, tool_name)
        logger.info("HexStrike: 调用 run_command, tool=%s (api=%s), arguments=%s", tool_name, api_tool_name, arguments)
        try:
            # 方式1: POST /api/tools/<tool_name>，请求体为 arguments；使用实际可执行文件名
            r = self._session.post(
                f'{self.base_url}/api/tools/{api_tool_name}',
                json=arguments,
                timeout=self.timeout
            )
            if r.status_code == 200:
                data = r.json() if r.text else {}
                logger.info("HexStrike: run_command 成功 (api/tools), tool=%s", api_tool_name)
                return {'success': True, 'data': data}
            # 404 或 400 时尝试 POST /api/command，多种请求体格式（使用 api_tool_name 即二进制名）
            if r.status_code in (404, 400):
                for payload in (
                    {'tool': api_tool_name, 'arguments': arguments},
                    {'name': api_tool_name, 'arguments': arguments},
                    {'command': api_tool_name, **arguments},
                ):
                    r2 = self._session.post(
                        f'{self.base_url}/api/command',
                        json=payload,
                        timeout=self.timeout
                    )
                    if r2.status_code == 200:
                        data = r2.json() if r2.text else {}
                        logger.info("HexStrike: run_command 成功 (api/command), tool=%s", api_tool_name)
                        return {'success': True, 'data': data}
                    if r2.status_code not in (400, 404):
                        r2.raise_for_status()
            r.raise_for_status()
        except requests.RequestException as e:
            logger.exception(f"HexStrike run_command {tool_name} failed: {e}")
            return {'success': False, 'message': str(e), 'data': None}
