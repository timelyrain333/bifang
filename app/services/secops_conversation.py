"""
SecOps 统一对话服务
处理所有对话逻辑（意图分析、工具调用、HexStrike 集成等）
提供统一的接口给前端和钉钉机器人
"""
import json
import logging
import re
import subprocess
import sys
import time
from typing import Dict, Any, List, Optional, Generator, Tuple
from django.conf import settings
from django.utils import timezone

from app.services.response_formatter import ResponseFormatter
from app.services.hexstrike_client import HexStrikeClient

logger = logging.getLogger(__name__)


# 可用操作列表
AVAILABLE_ACTIONS = [
    {
        'name': 'collect_vulnerabilities',
        'description': '采集最新漏洞信息',
        'plugin_name': 'oss-security漏洞采集',
        'parameters': {
            'days': '采集最近N天的漏洞（默认1天）'
        }
    },
    {
        'name': 'collect_assets',
        'description': '采集资产信息',
        'plugin_name': '阿里云安全中心资产采集',
        'parameters': {}
    },
    {
        'name': 'match_vulnerabilities',
        'description': '匹配漏洞与资产，检查是否有受影响资产',
        'plugin_name': None,
        'parameters': {
            'days': '匹配最近N天的漏洞（默认1天）'
        }
    }
]


class ConversationIntent:
    """对话意图分析结果"""

    def __init__(self):
        self.needs_vulnerability_collection = False
        self.needs_asset_collection = False
        self.needs_matching = False
        self.needs_hexstrike_assessment = False  # 是否需要对指定目标做安全评估
        self.hexstrike_target = None  # 从消息中提取的目标 IP/域名
        self.days = 1  # 默认1天
        self.is_query = False  # 是否是查询类消息


class SecOpsConversationService:
    """
    SecOps 统一对话服务

    核心功能：
    1. 意图分析 - 分析用户消息，识别需要执行的操作
    2. HexStrike 调用 - 统一的 HexStrike 集成逻辑
    3. 工具调用 - 任务管理、资产查询等
    4. 操作执行 - 漏洞采集、资产采集、匹配等
    """

    def __init__(self, api_key: str, api_base: str = 'https://dashscope.aliyuncs.com/compatible-mode/v1',
                 model: str = 'qwen-plus'):
        """
        初始化对话服务

        Args:
            api_key: 通义千问 API Key
            api_base: API 地址
            model: 模型名称
        """
        self.api_key = api_key
        self.api_base = api_base
        self.model = model
        self.client = None

        # 创建 OpenAI 客户端
        self._init_openai_client()

    def _init_openai_client(self):
        """初始化 OpenAI 客户端"""
        try:
            import openai
        except ImportError:
            logger.warning("openai 未安装，尝试自动安装: %s", sys.executable)
            try:
                subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', 'openai', '--quiet'],
                    capture_output=True,
                    timeout=120,
                    check=False,
                )
                import openai
            except Exception as e:
                logger.exception("自动安装 openai 失败: %s", e)
                raise ImportError(
                    "openai 库未安装。请执行: pip install openai"
                ) from e

        self.client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.api_base,
            timeout=300.0,  # 5分钟超时
        )

    def analyze_intent(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> ConversationIntent:
        """
        分析用户意图

        Args:
            user_message: 用户消息
            conversation_history: 对话历史（用于上下文理解）

        Returns:
            ConversationIntent: 意图分析结果
        """
        message_lower = user_message.lower()
        intent = ConversationIntent()

        # 1. 先识别「安全评估」类意图并提取目标
        security_assessment_keywords = [
            '安全评估', '渗透测试', '漏洞扫描', '全面评估', '全面的安全评估', '全面安全评估',
            '安全扫描', '扫描一下', '做一次评估', '做一次扫描', '评估', '扫描'
        ]

        # 重新扫描/再次扫描的关键词（从对话历史中提取目标）
        rescan_keywords = ['重新扫描', '再扫描一次', '再次扫描', '再评估', '重新评估', '扫描这个', '再次评估']

        has_security_keyword = any(kw in user_message for kw in security_assessment_keywords)
        has_rescan_keyword = any(kw in user_message for kw in rescan_keywords)

        # 提取 IP/域名
        ipv4_in_msg = re.search(r'(?:\d{1,3}\.){3}\d{1,3}', user_message)
        domain_in_msg = re.search(
            r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}',
            user_message
        )

        # 增强匹配：如果消息中包含IP/域名，且包含"资产"、"服务器"、"目标"、"对"等关键词
        has_asset_keyword = any(kw in user_message for kw in ['资产', '服务器', '目标', '对', '云服务器'])

        # 处理重新扫描的情况：从对话历史中提取之前扫描过的目标
        if has_rescan_keyword and not ipv4_in_msg and not domain_in_msg:
            if conversation_history:
                # 倒序查找最近的 IP/域名
                for msg in reversed(conversation_history):
                    content = msg.get('content', '')
                    # 查找 IPv4 地址
                    ipv4_match = re.search(r'(?:\d{1,3}\.){3}\d{1,3}', content)
                    if ipv4_match:
                        intent.hexstrike_target = ipv4_match.group(0).strip()
                        intent.needs_hexstrike_assessment = True
                        logger.info(
                            "意图分析：从对话历史中提取到重新扫描目标，target=%s",
                            intent.hexstrike_target
                        )
                        break
                    # 查找域名
                    domain_match = re.search(
                        r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}',
                        content
                    )
                    if domain_match:
                        intent.hexstrike_target = domain_match.group(0).strip()
                        intent.needs_hexstrike_assessment = True
                        logger.info(
                            "意图分析：从对话历史中提取到重新扫描目标，target=%s",
                            intent.hexstrike_target
                        )
                        break

        if has_security_keyword or (ipv4_in_msg and has_asset_keyword) or (domain_in_msg and has_asset_keyword):
            intent.needs_hexstrike_assessment = True
            # 提取目标：优先 IPv4
            if ipv4_in_msg:
                intent.hexstrike_target = ipv4_in_msg.group(0).strip()
            elif domain_in_msg:
                intent.hexstrike_target = domain_in_msg.group(0).strip()
            else:
                # 简单主机名：连续字母数字与点、横线
                host_match = re.search(r'([a-zA-Z0-9][a-zA-Z0-9.-]{2,50})', user_message)
                if host_match:
                    intent.hexstrike_target = host_match.group(1).strip()
            logger.info(
                "意图分析：识别到安全评估意图，target=%s, has_security_keyword=%s, has_asset_keyword=%s",
                intent.hexstrike_target,
                has_security_keyword,
                has_asset_keyword
            )

        # 2. 检查是否是查询类消息
        query_keywords = [
            '介绍', '说明', '帮助', 'help', '你是谁', '你能做什么', '你的功能',
            '你的能力', '你能', '你会', '什么是', '如何', '怎么', '怎样',
            '列出', '显示', '查看', '查询', '有哪些', '有什么'
        ]
        if not (intent.needs_hexstrike_assessment and intent.hexstrike_target):
            if any(keyword in message_lower for keyword in query_keywords):
                intent.is_query = True
                return intent

        # 3. 检查是否需要采集漏洞
        vuln_keywords = [
            '采集漏洞', '收集漏洞', '捕获漏洞', '获取漏洞', '执行漏洞采集', '运行漏洞采集',
            '最新漏洞', '漏洞信息', '漏洞数据', '漏洞采集', '漏洞收集'
        ]
        if any(keyword in message_lower for keyword in vuln_keywords):
            intent.needs_vulnerability_collection = True
        elif '漏洞' in message_lower and any(verb in message_lower for verb in ['捕获', '采集', '收集', '获取', '抓取']):
            intent.needs_vulnerability_collection = True

        # 4. 检查是否需要采集资产
        asset_keywords = [
            '采集资产', '收集资产', '获取资产', '同步资产', '执行资产采集', '运行资产采集',
            '资产信息', '资产数据', '资产采集', '资产收集'
        ]
        if any(keyword in message_lower for keyword in asset_keywords):
            intent.needs_asset_collection = True
        elif '资产' in message_lower and any(verb in message_lower for verb in ['采集', '收集', '获取', '同步']):
            intent.needs_asset_collection = True

        # 5. 检查是否需要匹配
        match_keywords = [
            '匹配漏洞', '检查影响', '检查受影响', '是否受影响', '执行匹配',
            '影响资产', '受影响', '资产影响', '漏洞影响', '匹配资产'
        ]
        if any(keyword in message_lower for keyword in match_keywords):
            intent.needs_matching = True
        elif ('资产' in message_lower or '影响' in message_lower) and ('检查' in message_lower or '匹配' in message_lower or '是否' in message_lower):
            intent.needs_matching = True

        # 6. 提取天数
        days_match = re.search(r'(\d+)\s*天', user_message)
        if days_match:
            intent.days = int(days_match.group(1))

        return intent

    def call_hexstrike_analyze(
        self,
        target: str,
        analysis_type: str = 'comprehensive',
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        调用 HexStrike 进行目标分析

        Args:
            target: 目标地址（IP/域名）
            analysis_type: 分析类型（默认 comprehensive）
            user_id: 用户 ID

        Returns:
            Dict: {
                'success': bool,
                'message': str,
                'data': dict,
                'execution_id': int
            }
        """
        if not getattr(settings, 'HEXSTRIKE_ENABLED', True):
            return {
                'success': False,
                'message': 'HexStrike 集成未启用，请在配置中开启 HEXSTRIKE_ENABLED 并启动 HexStrike 服务。',
                'data': None,
                'execution_id': None
            }

        target = target.strip()
        if not target:
            return {
                'success': False,
                'message': '请提供要分析的目标（IP、域名或主机名）。',
                'data': None,
                'execution_id': None
            }

        # 在函数内部导入模型，避免模块级导入问题
        from app.models import HexStrikeExecution

        # 创建执行记录
        execution = HexStrikeExecution.objects.create(
            target=target,
            analysis_type=analysis_type,
            status='running',
            created_by=user_id or '',
        )
        start_time = time.time()

        try:
            client = HexStrikeClient(
                base_url=getattr(settings, 'HEXSTRIKE_SERVER_URL', 'http://localhost:8888'),
                timeout=getattr(settings, 'HEXSTRIKE_TIMEOUT', 600),  # 10分钟
            )

            # 0. 清除 HexStrike 缓存，确保获取最新扫描结果
            client.clear_cache()
            logger.info(f"HexStrike: 缓存已清除, 准备执行扫描, target={target}")

            # 1. 先调用 analyze_target 分析目标
            result = client.analyze_target(target, analysis_type=analysis_type)
            logger.info(f"HexStrike: analyze_target 完成, target={target}, success={result.get('success')}")

            # 2. 显式调用 run_command 执行 nmap 扫描
            nmap_result = client.run_command("nmap_scan", {"target": target})
            logger.info(f"HexStrike: nmap_scan 完成, target={target}, success={nmap_result.get('success')}")
            if result.get('data') is None:
                result['data'] = {}
            result['data']['nmap_results'] = nmap_result.get('data')

            # 3. 显式调用 run_command 执行 nuclei 漏洞扫描
            nuclei_result = client.run_command("nuclei_scan", {"target": target})
            logger.info(f"HexStrike: nuclei_scan 完成, target={target}, success={nuclei_result.get('success')}")
            result['data']['nuclei_results'] = nuclei_result.get('data')

            # 格式化 Nmap 和 Nuclei 结果
            if result.get('success') and result.get('data'):
                data = result['data']

                # 格式化 Nmap 结果
                if 'nmap_results' in data and data['nmap_results']:
                    from app.services.nmap_result_parser import format_nmap_result
                    nmap_data = data['nmap_results']
                    stdout = nmap_data.get('stdout', '')
                    stderr = nmap_data.get('stderr', '')

                    if stdout or stderr:
                        formatted_nmap = format_nmap_result(stdout, stderr)
                        data['nmap_results']['formatted_output'] = formatted_nmap
                        data['nmap_results']['raw_output'] = stdout or stderr

                # 格式化 Nuclei 结果
                if 'nuclei_results' in data and data['nuclei_results']:
                    from app.services.nuclei_result_parser import format_nuclei_result
                    nuclei_data = data['nuclei_results']
                    stdout = nuclei_data.get('stdout', '')
                    stderr = nuclei_data.get('stderr', '')

                    if stdout or stderr:
                        formatted_nuclei = format_nuclei_result(stdout, stderr)
                        data['nuclei_results']['formatted_output'] = formatted_nuclei
                        data['nuclei_results']['raw_output'] = stdout or stderr

                # 处理超时错误
                if 'nuclei_results' in data and isinstance(data['nuclei_results'], dict):
                    if data['nuclei_results'].get('timed_out') or 'timed out' in str(data['nuclei_results']).lower():
                        data['nuclei_results']['error'] = '扫描超时（超过10分钟），建议分端口扫描或减少扫描范围'

            # 更新执行记录
            execution_time = time.time() - start_time
            execution.status = 'success' if result.get('success') else 'failed'
            execution.finished_at = timezone.now()
            execution.execution_time = execution_time
            execution.result = result.get('data', {})
            if not result.get('success'):
                execution.error_message = result.get('message', '执行失败')
            execution.save()

            if result.get('success') and result.get('data') is not None:
                return {
                    'success': True,
                    'message': f'已对目标 {target} 完成安全分析',
                    'data': result['data'],
                    'execution_id': execution.id,
                }
            return {
                'success': False,
                'message': result.get('message', 'HexStrike 分析失败，请确认 HexStrike 服务已启动（默认 http://localhost:8888）。'),
                'data': result.get('data'),
                'execution_id': execution.id,
            }

        except Exception as e:
            # 更新执行记录为失败
            execution_time = time.time() - start_time
            execution.status = 'failed'
            execution.finished_at = timezone.now()
            execution.execution_time = execution_time
            execution.error_message = str(e)
            execution.save()

            logger.error(f"调用 HexStrike 失败: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'HexStrike 调用异常: {str(e)}',
                'data': None,
                'execution_id': execution.id,
            }

    def format_hexstrike_response(
        self,
        target: str,
        result: Dict[str, Any],
        include_html_report: bool = True
    ) -> Generator[str, None, None]:
        """
        格式化 HexStrike 响应为 Markdown（流式）

        Args:
            target: 目标地址
            result: HexStrike 返回结果
            include_html_report: 是否包含 HTML 报告链接

        Yields:
            str: Markdown 文本片段
        """
        yield from ResponseFormatter.format_hexstrike_result(
            target=target,
            result=result,
            include_html_report=include_html_report
        )

    def format_hexstrike_response_simple(
        self,
        target: str,
        result: Dict[str, Any],
        include_html_report: bool = True
    ) -> str:
        """
        格式化 HexStrike 响应为 Markdown（非流式，返回完整字符串）

        Args:
            target: 目标地址
            result: HexStrike 返回结果
            include_html_report: 是否包含 HTML 报告链接

        Returns:
            str: 格式化后的完整文本
        """
        return ResponseFormatter.format_hexstrike_result_simple(
            target=target,
            result=result,
            include_html_report=include_html_report
        )