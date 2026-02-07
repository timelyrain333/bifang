"""
SecOps智能体服务
基于通义千问大模型，理解用户意图并执行安全运营任务
"""
import json
import logging
import re
import subprocess
import sys
from typing import Dict, Any, List, Optional, Generator
from app.services.task_executor import TaskExecutor
from app.services.asset_matcher import AssetMatcher
from app.models import Vulnerability, Asset, Plugin, HexStrikeExecution
from app.services.task_tools import (
    create_task, list_tasks, update_task, parse_cron_from_natural_language,
    get_plugin_by_name_or_keyword,
    list_assets,
)
from django.conf import settings
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

# AI工具函数定义（Function Calling）
TOOLS = [
        {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "创建任务。可以创建手动执行任务或定时执行任务。**重要**：只能为插件相关的操作创建任务，系统操作（如match_vulnerabilities）不能创建为定时任务。可用的插件：collect_oss_security（漏洞采集）、data_aliyun_security（资产采集）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "任务名称"
                    },
                    "plugin_name_or_keyword": {
                        "type": "string",
                        "description": "插件名称或关键词。可用选项：'collect_oss_security'或'漏洞采集'（用于漏洞采集）、'data_aliyun_security'或'资产采集'（用于资产采集）。**注意**：不能使用'match_vulnerabilities'，因为这不是一个插件。"
                    },
                    "trigger_type": {
                        "type": "string",
                        "enum": ["manual", "cron"],
                        "description": "触发类型：manual（手动执行）或cron（定时执行）"
                    },
                    "cron_expression": {
                        "type": "string",
                        "description": "Cron表达式（当trigger_type为cron时必需），格式：分钟 小时 日 月 周。例如：'0 0 * * *'表示每天0点执行。也可以使用自然语言，如'每天0点'、'每小时'等。"
                    },
                    "task_config": {
                        "type": "object",
                        "description": "任务配置参数（JSON格式），可选"
                    },
                    "is_active": {
                        "type": "boolean",
                        "description": "是否启用任务，默认为true"
                    }
                },
                "required": ["name", "plugin_name_or_keyword", "trigger_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "查询任务列表。可以根据插件名称、触发类型、启用状态等条件查询。",
            "parameters": {
                "type": "object",
                "properties": {
                    "plugin_name": {
                        "type": "string",
                        "description": "插件名称或关键词（可选）"
                    },
                    "trigger_type": {
                        "type": "string",
                        "enum": ["manual", "cron", "interval"],
                        "description": "触发类型（可选）"
                    },
                    "is_active": {
                        "type": "boolean",
                        "description": "是否启用（可选）"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回数量限制，默认20"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_task",
            "description": "更新任务配置。可以修改任务名称、触发类型、cron表达式、启用状态等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "任务ID"
                    },
                    "name": {
                        "type": "string",
                        "description": "任务名称（可选）"
                    },
                    "trigger_type": {
                        "type": "string",
                        "enum": ["manual", "cron", "interval"],
                        "description": "触发类型（可选）"
                    },
                    "cron_expression": {
                        "type": "string",
                        "description": "Cron表达式（可选）"
                    },
                    "is_active": {
                        "type": "boolean",
                        "description": "是否启用（可选）"
                    }
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "parse_cron",
            "description": "将自然语言描述转换为cron表达式。例如：'每天0点' -> '0 0 * * *'，'每小时' -> '0 * * * *'",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "自然语言描述，如'每天0点'、'每周一'、'每小时'、'每6小时'等"
                    }
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_assets",
            "description": "查询资产列表，用于安全评估时选择目标。返回资产摘要（含可用于扫描的目标地址：IP/域名/主机名）。在对资产做安全评估前，可先调用此工具获取要评估的资产列表。",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "返回数量限制，默认50"
                    },
                    "asset_type": {
                        "type": "string",
                        "description": "资产类型筛选（可选），如 server, web_service, web_site"
                    },
                    "source": {
                        "type": "string",
                        "description": "数据来源筛选（可选），如 aliyun_security, aws_inspector"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "hexstrike_analyze_target",
            "description": "使用 HexStrike AI 对指定目标进行安全分析。目标可以是 IP、域名或主机名。会由 HexStrike 智能选择扫描策略与工具，适合「对某资产做安全评估」类请求。需先确保 HexStrike 服务已启动（默认 http://localhost:8888）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "要分析的目标，如 IP 地址、域名或主机名，例如 192.168.1.1 或 example.com"
                    },
                    "analysis_type": {
                        "type": "string",
                        "description": "分析类型，默认 comprehensive（综合评估）"
                    }
                },
                "required": ["target"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "hexstrike_run_scan",
            "description": "使用 HexStrike AI 执行指定的安全扫描工具（与官方 MCP 工具名一致）。网络: nmap_scan, masscan_scan, rustscan_scan；Web: nuclei_scan, gobuster_scan, ffuf_scan, sqlmap_scan；云: trivy_scan, kube_hunter_scan。适合用户明确要求某种扫描时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "description": "工具名称，如 nmap_scan, nuclei_scan, gobuster_scan, masscan_scan, ffuf_scan（参见官方 API 文档）"
                    },
                    "arguments": {
                        "type": "object",
                        "description": "工具参数，如 {\"target\": \"192.168.1.1\"} 或 {\"target\": \"https://example.com\"}"
                    }
                },
                "required": ["tool_name", "arguments"]
            }
        }
    }
]


class SecOpsAgent:
    """SecOps智能体"""

    def __init__(self, api_key: str, api_base: str = 'https://dashscope.aliyuncs.com/compatible-mode/v1',
                 model: str = 'qwen-plus'):
        """
        初始化智能体

        Args:
            api_key: 通义千问API Key
            api_base: API地址
            model: 模型名称
        """
        self.api_key = api_key
        self.api_base = api_base
        self.model = model
        self.client = None

        # 创建时尝试导入 openai；若未安装则用当前进程的 Python 自动安装后重试
        try:
            import openai
        except ImportError:
            logger.warning("openai 未安装，尝试使用当前 Python 自动安装: %s", sys.executable)
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
                    "openai 库未安装。请使用【运行本应用的同一 Python 环境】执行: pip install openai\n"
                    "若使用虚拟环境，请先激活再安装；或执行: pip install -r requirements.txt"
                ) from e
        # 设置超时时间为5分钟，避免长时间等待
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url=api_base,
            timeout=300.0,  # 5分钟超时
        )

        # 初始化统一对话服务
        from app.services.secops_conversation import SecOpsConversationService
        self.conversation_service = SecOpsConversationService(
            api_key=api_key,
            api_base=api_base,
            model=model
        )
    
    def chat(self, user_message: str, conversation_history: Optional[List[Dict]] = None, 
             user=None) -> Generator[str, None, None]:
        """
        与用户对话，流式返回响应
        
        Args:
            user_message: 用户消息
            conversation_history: 对话历史
            user: 用户对象
            
        Yields:
            str: 响应文本片段
        """
        # 限制消息长度（最大20000字符，提升以支持更长的对话）
        MAX_MESSAGE_LENGTH = 20000
        if len(user_message) > MAX_MESSAGE_LENGTH:
            yield f"❌ 消息过长，请控制在{MAX_MESSAGE_LENGTH}字符以内\n"
            return
        
        # 限制对话历史长度
        if conversation_history:
            # 限制历史记录总长度和数量（提升到50000字符，约支持20轮对话）
            MAX_HISTORY_LENGTH = MAX_MESSAGE_LENGTH * 2.5  # 50000字符
            total_length = sum(len(str(msg.get('content', ''))) for msg in conversation_history)
            if total_length > MAX_HISTORY_LENGTH:
                # 只保留最近的消息（提升到10条消息，约5轮对话）
                conversation_history = conversation_history[-10:]
                logger.warning(f"对话历史过长，已截断为最近10条消息")
        
        # 构建系统提示词
        system_prompt = self._build_system_prompt()
        
        # 构建对话消息
        messages = [{"role": "system", "content": system_prompt}]
        
        # 添加历史对话（提升到20轮对话，40条消息）
        if conversation_history:
            messages.extend(conversation_history[-40:])  # 只保留最近40条消息（约20轮对话）
        
        # 添加当前用户消息
        messages.append({"role": "user", "content": user_message})
        
        # 先分析用户意图，判断是否需要执行操作（使用统一对话服务）
        intent_obj = self.conversation_service.analyze_intent(user_message, conversation_history)
        intent_analysis = {
            'needs_vulnerability_collection': intent_obj.needs_vulnerability_collection,
            'needs_asset_collection': intent_obj.needs_asset_collection,
            'needs_matching': intent_obj.needs_matching,
            'needs_hexstrike_assessment': intent_obj.needs_hexstrike_assessment,
            'hexstrike_target': intent_obj.hexstrike_target,
            'days': intent_obj.days,
            'is_query': intent_obj.is_query,
        }
        needs_hexstrike = intent_obj.needs_hexstrike_assessment
        hexstrike_target = intent_obj.hexstrike_target
        logger.info(
            "SecOps 意图分析: needs_hexstrike=%s, hexstrike_target=%s, is_query=%s, user_message_len=%d, user_message_preview=%s",
            needs_hexstrike,
            hexstrike_target,
            intent_obj.is_query,
            len(user_message or ''),
            (user_message or '')[:100],
        )

        # 当用户明确要求对某目标做安全评估且已从消息中提取到目标时，直接调用 HexStrike，不依赖模型是否返回 tool_call
        # 重要：即使有对话历史，也强制执行新扫描，不使用历史结果
        if needs_hexstrike and hexstrike_target:
            target = hexstrike_target
            logger.info("✓ 检测到安全评估意图且已提取目标，直接调用 HexStrike: target=%s", target)
            try:
                # 获取用户 ID
                user_id = None
                if user:
                    if hasattr(user, 'username'):
                        user_id = user.username
                    elif isinstance(user, str):
                        user_id = user

                # 使用统一对话服务调用 HexStrike
                tool_result = self.conversation_service.call_hexstrike_analyze(
                    target=target,
                    analysis_type='comprehensive',
                    user_id=user_id
                )

                # 使用统一对话服务格式化响应（流式）
                yield from self.conversation_service.format_hexstrike_response(
                    target=target,
                    result=tool_result,
                    include_html_report=True
                )
            except Exception as e:
                logger.error(f"调用 HexStrike 失败: {e}", exc_info=True)
                yield f"### ❌ HexStrike 调用异常: {str(e)}\n\n"
            return
        elif needs_hexstrike and not hexstrike_target:
            logger.warning("检测到安全评估意图但未提取到目标，继续执行 AI 调用: user_message=%s", user_message[:100])
        else:
            logger.debug("未检测到安全评估意图，继续执行 AI 调用")
        
        # 调用模型，支持Function Calling
        try:
            # 第一轮调用：可能包含工具调用
            # 设置max_tokens以充分利用模型上下文窗口（qwen-plus支持8192 tokens）
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                tools=TOOLS,
                tool_choice="auto",  # 让AI自动决定是否调用工具
                max_tokens=4000  # 设置最大输出token数，留出足够空间给输入
            )
            
            full_response = ""
            tool_calls = []
            
            # 处理响应
            message = response.choices[0].message
            
            # 准备助手的回复
            assistant_message = {
                "role": "assistant",
                "content": message.content or None
            }
            
            # 如果有工具调用，添加到消息中
            if message.tool_calls:
                assistant_message["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in message.tool_calls
                ]
            
            # 添加助手的回复到消息历史
            messages.append(assistant_message)
            
            # 处理工具调用
            if message.tool_calls:
                # 不输出执行过程信息
                has_valid_tool = False
                has_unknown_tool = False
                
                for tool_call in message.tool_calls:
                    function_name = tool_call.function.name
                    
                    # 安全解析JSON参数
                    try:
                        function_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError as e:
                        logger.error(f"解析工具函数参数失败: {e}, function={function_name}, arguments={tool_call.function.arguments[:100]}")
                        yield f"### ❌ 工具函数参数格式错误\n\n"
                        continue
                    except Exception as e:
                        logger.error(f"解析工具函数参数异常: {e}, function={function_name}", exc_info=True)
                        yield f"### ❌ 处理工具函数参数时发生错误\n\n"
                        continue
                    
                    # 调用工具函数
                    tool_result = self._call_tool(function_name, function_args, user)
                    
                    # 将工具结果添加到消息历史
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result, ensure_ascii=False)
                    })
                    
                    # 输出工具执行结果
                    if tool_result.get('success'):
                        has_valid_tool = True
                        yield f"### ✅ {tool_result.get('message', '操作成功')}\n\n"
                        if 'task_id' in tool_result:
                            yield f"**任务ID**: {tool_result['task_id']}\n\n"
                    else:
                        # 检查是否是未知工具（这些应该是操作，不是工具）
                        if '未知的工具函数' in tool_result.get('message', ''):
                            has_unknown_tool = True
                            logger.warning(f"AI尝试调用未知工具: {function_name}，这应该是操作而不是工具，将自动回退到操作执行方式")
                            # 不输出错误消息，因为系统会自动回退到操作执行方式
                        else:
                            # 只有真正的错误才输出
                            yield f"### ❌ {tool_result.get('message', '操作失败')}\n\n"
                
                # 如果有未知工具调用（如collect_vulnerabilities等），说明AI误解了
                # 这些应该是操作，不是工具，需要回退到操作执行方式
                if has_unknown_tool and not has_valid_tool:
                    logger.info("检测到未知工具调用，回退到操作执行方式")
                    # 不进行第二轮AI调用，直接执行操作
                    if not intent_analysis.get('is_query', False):
                        actions = self._extract_actions("", intent_analysis, user_message)
                        if actions:
                            # 不输出执行过程，只输出结果
                            for i, action in enumerate(actions, 1):
                                yield from self._execute_action(action, user)
                                if i < len(actions):
                                    yield "\n"
                    return
                
                # 第二轮调用：让AI根据工具结果生成回复
                response2 = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.3,
                    stream=True,
                    max_tokens=4000  # 设置最大输出token数
                )
                
                yield "\n"
                for chunk in response2:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_response += content
                        yield content
                
                # 如果已经使用了有效的工具函数（如create_task），就不应该再执行操作
                # 创建任务和执行操作是两回事，不应该同时进行
                # 因此，在有有效工具调用的情况下，不检查actions，直接返回
                if has_valid_tool:
                    return
            else:
                # 没有工具调用
                # 如果有内容，先输出
                if message.content:
                    full_response += message.content
                    yield message.content
                
                # 如果没有内容，使用流式输出（这种情况应该很少）
                if not message.content:
                    stream = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=0.3,
                        stream=True,
                        max_tokens=4000  # 设置最大输出token数
                    )
                    
                    for chunk in stream:
                        if chunk.choices and chunk.choices[0].delta.content:
                            content = chunk.choices[0].delta.content
                            full_response += content
                            yield content
                
                # 分析响应，判断是否需要执行操作（非工具操作）
                # 只有在没有工具调用的情况下才检查actions
                # 但如果是查询类消息，不执行任何操作
                if not intent_analysis.get('is_query', False):
                    actions = self._extract_actions(full_response, intent_analysis, user_message)
                    if actions:
                        # 不输出执行过程，只输出结果
                        for i, action in enumerate(actions, 1):
                            yield from self._execute_action(action, user)
                            if i < len(actions):
                                yield "\n"
            
        except Exception as e:
            logger.error(f"智能体对话失败: {e}", exc_info=True)
            
            # 检查是否是API错误，提供更友好的错误信息
            error_str = str(e)
            error_msg = "❌ 发生错误: "
            
            # 检查是否是账户欠费错误
            if 'Arrearage' in error_str or 'overdue-payment' in error_str or '账户欠费' in error_str:
                error_msg = "❌ 通义千问API账户欠费，请前往阿里云充值后再试。\n"
                error_msg += "   详情: https://help.aliyun.com/zh/model-studio/error-code#overdue-payment\n"
            # 检查是否是API密钥错误
            elif 'invalid_api_key' in error_str or 'Invalid API Key' in error_str or 'API Key' in error_str:
                error_msg = "❌ 通义千问API Key无效，请检查系统配置中的API Key是否正确。\n"
            # 检查是否是API连接错误
            elif 'Connection' in error_str or 'timeout' in error_str.lower():
                error_msg = "❌ 无法连接到通义千问API，请检查网络连接。\n"
            else:
                error_msg += f"{error_str}\n"
            
            yield error_msg
    
    def _is_valid_component_name(self, component: str) -> bool:
        """
        检查组件名称是否有效
        
        Args:
            component: 组件名称
            
        Returns:
            bool: 如果组件名称有效返回True，否则返回False
        """
        if not component or not component.strip():
            return False
        
        component_lower = component.lower().strip()
        
        # 常见编程语言/框架白名单（即使很短也认为是有效的）
        valid_short_names = [
            'go', 'golang', 'python', 'java', 'nodejs', 'node.js', 'rust', 'php', 'ruby',
            'c', 'cpp', 'c++', 'c#', 'js', 'ts', 'tsx', 'jsx', 'html', 'css', 'sql',
            'curl', 'wget', 'git', 'vim', 'emacs', 'bash', 'zsh', 'sh'
        ]
        
        if component_lower in valid_short_names:
            return True
        
        # 无效的组件名称列表
        invalid_exact = [
            'this', 'that', 'these', 'those',  # 代词
            'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten',  # 数字
            'one', 'first', 'second', 'third',
            'heap', 'stack', 'buffer', 'memory',  # 技术词汇
            'unknown', 'unknown component', 'n/a', 'na',  # 未知
            '未知', '未知组件',
        ]
        
        if component_lower in invalid_exact:
            return False
        
        # 无效的组件名称模式
        import re
        invalid_patterns = [
            r'^(two|three|four|five|six|seven|eight|nine|ten)\s+',  # 数字开头的描述（如"two heap"）
            r'^(xxe|xss|csrf|sql\s*injection|rce|rfi|lfi)',  # 漏洞类型
            r'^(before|after|through|to|until|up\s+to|from)\s+',  # 版本范围关键词（必须后面跟内容）
            r'^[<>=]+\s*\d+',  # 版本比较符
            r'^\d+\.\d+',  # 版本号开头
            # 修复：只匹配真正的版本范围字符串（包含数字和版本关键词的组合）
            r'^(before|after|through|to|until|up\s+to|from)\s+\d+',  # "before 2.2.1" 等
            r'^\d+\s+(before|after|through|to|until|up\s+to|from)\s+\d+',  # "2.0.0 before 2.2.1" 等
            r'^[\d\s<>=]+$',  # 只包含数字、空格、比较符（不包含字母，避免误判"go"等）
        ]
        
        for pattern in invalid_patterns:
            if re.match(pattern, component_lower, re.IGNORECASE):
                return False
        
        # 检查是否包含"vulnerability"、"issue"、"bug"等关键词（这些不是组件名称）
        if any(keyword in component_lower for keyword in ['vulnerability', 'issue', 'bug', 'problem', 'error']):
            return False
        
        return True
    
    def _analyze_intent(self, user_message: str, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        """
        分析用户意图

        Args:
            user_message: 用户消息
            conversation_history: 对话历史（用于上下文理解）

        Returns:
            Dict: 意图分析结果
        """
        message_lower = user_message.lower()
        intent = {
            'needs_vulnerability_collection': False,
            'needs_asset_collection': False,
            'needs_matching': False,
            'needs_hexstrike_assessment': False,  # 是否需要对指定目标做安全评估（HexStrike）
            'hexstrike_target': None,           # 从消息中提取的目标 IP/域名
            'days': 1,  # 默认1天
            'is_query': False  # 是否是查询类消息（介绍、说明、帮助等）
        }

        # 先识别「安全评估」类意图并提取目标（优先于 is_query，避免被误判为仅查询）
        security_assessment_keywords = [
            '安全评估', '渗透测试', '漏洞扫描', '全面评估', '全面的安全评估', '全面安全评估',
            '安全扫描', '扫描一下', '做一次评估', '做一次扫描', '评估', '扫描'
        ]

        # 重新扫描/再次扫描的关键词（从对话历史中提取目标）
        rescan_keywords = ['重新扫描', '再扫描一次', '再次扫描', '再评估', '重新评估', '扫描这个', '再次评估']

        has_security_keyword = any(kw in user_message for kw in security_assessment_keywords)
        has_rescan_keyword = any(kw in user_message for kw in rescan_keywords)

        # 若消息中同时包含「评估/扫描」类词和 IP/域名，也视为安全评估（避免漏掉「对 101.37.29.229 扫描」等说法）
        ipv4_in_msg = re.search(r'(?:\d{1,3}\.){3}\d{1,3}', user_message)
        domain_in_msg = re.search(
            r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}',
            user_message
        )

        # 增强匹配：如果消息中包含IP/域名，且包含"资产"、"服务器"、"目标"、"对"等关键词，也视为安全评估意图
        has_asset_keyword = any(kw in user_message for kw in ['资产', '服务器', '目标', '对', '云服务器'])

        # 处理重新扫描的情况：从对话历史中提取之前扫描过的目标
        if has_rescan_keyword and not ipv4_in_msg and not domain_in_msg:
            # 从对话历史中查找最近扫描过的目标
            if conversation_history:
                # 倒序查找最近的 IP/域名
                for msg in reversed(conversation_history):
                    content = msg.get('content', '')
                    # 查找 IPv4 地址
                    ipv4_match = re.search(r'(?:\d{1,3}\.){3}\d{1,3}', content)
                    if ipv4_match:
                        intent['hexstrike_target'] = ipv4_match.group(0).strip()
                        intent['needs_hexstrike_assessment'] = True
                        logger.info(
                            "意图分析：从对话历史中提取到重新扫描目标，target=%s",
                            intent['hexstrike_target']
                        )
                        break
                    # 查找域名
                    domain_match = re.search(
                        r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}',
                        content
                    )
                    if domain_match:
                        intent['hexstrike_target'] = domain_match.group(0).strip()
                        intent['needs_hexstrike_assessment'] = True
                        logger.info(
                            "意图分析：从对话历史中提取到重新扫描目标，target=%s",
                            intent['hexstrike_target']
                        )
                        break

        if has_security_keyword or (ipv4_in_msg and has_asset_keyword) or (domain_in_msg and has_asset_keyword):
            intent['needs_hexstrike_assessment'] = True
            # 提取目标：优先 IPv4（不用 \b，避免 IP 紧邻中文时匹配失败）
            if ipv4_in_msg:
                intent['hexstrike_target'] = ipv4_in_msg.group(0).strip()
            elif domain_in_msg:
                intent['hexstrike_target'] = domain_in_msg.group(0).strip()
            else:
                # 简单主机名：连续字母数字与点、横线
                host_match = re.search(r'([a-zA-Z0-9][a-zA-Z0-9.-]{2,50})', user_message)
                if host_match:
                    intent['hexstrike_target'] = host_match.group(1).strip()
            logger.info(
                "意图分析：识别到安全评估意图，target=%s, has_security_keyword=%s, has_asset_keyword=%s",
                intent.get('hexstrike_target'),
                has_security_keyword,
                has_asset_keyword
            )
        
        # 检查是否是查询类消息（介绍、说明、帮助等），这类消息不应该执行操作
        # 若已识别为安全评估且已提取目标，不按纯查询处理
        query_keywords = [
            '介绍', '说明', '帮助', 'help', '你是谁', '你能做什么', '你的功能',
            '你的能力', '你能', '你会', '什么是', '如何', '怎么', '怎样',
            '列出', '显示', '查看', '查询', '有哪些', '有什么'
        ]
        if not (intent['needs_hexstrike_assessment'] and intent['hexstrike_target']):
            if any(keyword in message_lower for keyword in query_keywords):
                intent['is_query'] = True
                # 查询类消息不执行操作，直接返回
                return intent
        
        # 检查是否需要采集漏洞（更灵活的关键词匹配）
        vuln_keywords = [
            '采集漏洞', '收集漏洞', '捕获漏洞', '获取漏洞', '执行漏洞采集', '运行漏洞采集',
            '最新漏洞', '漏洞信息', '漏洞数据', '漏洞采集', '漏洞收集'
        ]
        # 检查是否包含"漏洞"和"采集/收集/捕获/获取"等动词
        if any(keyword in message_lower for keyword in vuln_keywords):
            intent['needs_vulnerability_collection'] = True
        elif '漏洞' in message_lower and any(verb in message_lower for verb in ['捕获', '采集', '收集', '获取', '抓取']):
            intent['needs_vulnerability_collection'] = True
        
        # 检查是否需要采集资产（更灵活的关键词匹配）
        asset_keywords = [
            '采集资产', '收集资产', '获取资产', '同步资产', '执行资产采集', '运行资产采集',
            '资产信息', '资产数据', '资产采集', '资产收集'
        ]
        if any(keyword in message_lower for keyword in asset_keywords):
            intent['needs_asset_collection'] = True
        elif '资产' in message_lower and any(verb in message_lower for verb in ['采集', '收集', '获取', '同步']):
            intent['needs_asset_collection'] = True
        
        # 检查是否需要匹配（更灵活的关键词匹配）
        match_keywords = [
            '匹配漏洞', '检查影响', '检查受影响', '是否受影响', '执行匹配',
            '影响资产', '受影响', '资产影响', '漏洞影响', '匹配资产'
        ]
        if any(keyword in message_lower for keyword in match_keywords):
            intent['needs_matching'] = True
        elif ('资产' in message_lower or '影响' in message_lower) and ('检查' in message_lower or '匹配' in message_lower or '是否' in message_lower):
            intent['needs_matching'] = True
        
        # 提取天数
        days_match = re.search(r'(\d+)\s*天', user_message)
        if days_match:
            intent['days'] = int(days_match.group(1))
        
        return intent
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        actions_desc = "\n".join([
            f"- {action['name']}: {action['description']}" 
            for action in AVAILABLE_ACTIONS
        ])
        
        # 获取可用插件列表
        plugins = Plugin.objects.filter(is_active=True)
        plugins_desc = "\n".join([
            f"- {p.name} ({p.get_plugin_type_display()})" 
            for p in plugins
        ])
        
        return f"""你是一个专业的安全运营(SecOps)智能助手，可以帮助用户执行安全运营任务和配置管理任务。

可用操作：
{actions_desc}

可用插件：
{plugins_desc}

你的能力：
1. 理解用户的安全运营需求
2. 回答用户的问题和提供帮助（介绍、说明、查询等）
3. 自动执行相应的任务（漏洞采集、资产采集、漏洞匹配等）- **仅在用户明确要求时执行**
4. 创建和管理定时任务（支持cron表达式和自然语言）
5. 分析和解释执行结果
6. 提供专业的安全建议
7. **资产安全评估（HexStrike AI 集成）**：当用户要求对资产做安全评估、渗透测试或漏洞扫描时：
   - 可先使用 list_assets 查询资产列表，获取要评估的目标（IP/域名/主机名）
   - 使用 hexstrike_analyze_target(target) 对指定目标进行综合安全分析（由 HexStrike 智能选择扫描策略）
   - 或使用 hexstrike_run_scan(tool_name, arguments) 执行指定工具（如 nmap_scan、nuclei_scan 等）
   - 仅对用户拥有或明确授权的资产进行评估，并提醒用户确保已获得授权

重要提示：
- **当用户询问"介绍"、"说明"、"帮助"、"你是谁"、"你能做什么"等问题时，只回答，不要执行任何操作**
- **只有在用户明确要求执行任务时（如"请执行漏洞采集"、"开始匹配"、"运行资产采集"等），才执行操作**
- **不要因为响应中提到了操作名称就执行，必须用户明确要求执行**

任务创建说明：
- **重要**：只有插件相关的操作才能创建为定时任务。系统操作（如match_vulnerabilities）不能创建为定时任务。
- 可创建定时任务的操作：
  * collect_vulnerabilities（漏洞采集）- 使用插件：collect_oss_security
  * collect_assets（资产采集）- 使用插件：data_aliyun_security
- **不能创建定时任务的操作**：
  * match_vulnerabilities（漏洞匹配）- 这是系统操作，不是插件，不能创建为定时任务
  * 如果用户要求为match_vulnerabilities创建定时任务，应该说明这是系统操作，无法创建定时任务，但可以在漏洞采集和资产采集任务执行后自动执行匹配
- 当用户要求创建定时任务时，使用create_task工具函数
- cron表达式格式：分钟 小时 日 月 周（5个字段，用空格分隔）
  * 示例：'0 0 * * *' 表示每天0点执行
  * 示例：'0 */6 * * *' 表示每6小时执行一次（注意：*/6表示每6小时，不是/6）
  * 示例：'0 0 * * 1' 表示每周一0点执行
- 支持自然语言转换为cron表达式（使用parse_cron工具函数）：
  * "每天0点" -> "0 0 * * *"
  * "每小时" -> "0 * * * *"
  * "每6小时" -> "0 */6 * * *"（注意：*/6，不是/6）
  * "每周一0点" -> "0 0 * * 1"
- 插件关键词匹配：
  * "漏洞采集"、"CVE"、"oss-security"、"collect_oss_security" -> collect_oss_security插件
  * "资产采集"、"asset"、"data_aliyun_security" -> data_aliyun_security插件
- 创建任务时的注意事项：
  * 如果用户要求创建多个任务的定时任务，应该为每个可创建的操作分别创建任务
  * 如果用户要求为match_vulnerabilities创建定时任务，应该说明无法创建，但可以建议在漏洞采集和资产采集任务执行后，系统会自动执行匹配
  * 创建任务成功后，只返回任务创建结果，不要执行操作

**操作执行说明**：
- `collect_vulnerabilities`、`collect_assets`、`match_vulnerabilities` 是**操作**，不是工具函数
- 这些操作**不能**通过Function Calling调用，它们不在TOOLS列表中
- 当用户要求执行这些操作时（如"捕获漏洞"、"检查资产"等），系统会自动通过意图分析来触发执行
- **绝对不要**尝试调用这些操作作为工具函数，如果AI尝试调用，系统会自动回退到操作执行方式

工作流程：
1. 理解用户的意图
2. 如果是查询类消息（介绍、说明、帮助等），只回答，不执行任何操作
3. 如果需要创建或修改任务，使用相应的工具函数（create_task、update_task、list_tasks）
4. 如果用户明确要求执行操作（如"捕获漏洞"、"检查资产"等），系统会自动通过意图分析来执行，不需要调用工具函数
5. 如果用户要求对资产做安全评估、渗透测试或漏洞扫描，使用 list_assets 获取目标，再使用 hexstrike_analyze_target 或 hexstrike_run_scan（需 HexStrike 服务已启动）
6. 执行操作后，分析和总结结果

请用友好、专业的语气回复用户。"""
    
    def _extract_actions(self, response: str, intent_analysis: Dict[str, Any] = None, 
                        user_message: str = None) -> List[Dict[str, Any]]:
        """
        从响应和意图分析中提取需要执行的操作
        
        Args:
            response: AI响应文本
            intent_analysis: 意图分析结果
            user_message: 用户原始消息（用于判断是否应该执行操作）
            
        Returns:
            List[Dict]: 操作列表
        """
        actions = []
        
        # 如果是查询类消息，不执行任何操作
        if intent_analysis and intent_analysis.get('is_query', False):
            logger.debug("检测到查询类消息，跳过操作执行")
            return []
        
        # 如果用户消息中包含"创建"、"设置"、"配置"等词，且没有"执行"、"运行"等词，则不执行操作
        if user_message:
            user_msg_lower = user_message.lower()
            create_keywords = ['创建', '设置', '配置', '建立', '添加']
            execute_keywords = ['执行', '运行', '开始', '启动', '进行']
            
            has_create_keyword = any(kw in user_msg_lower for kw in create_keywords)
            has_execute_keyword = any(kw in user_msg_lower for kw in execute_keywords)
            
            # 如果用户只是要求创建/设置任务，而不是执行操作，则不执行操作
            if has_create_keyword and not has_execute_keyword:
                logger.debug("用户只是要求创建/设置任务，不执行操作")
                return []
        
        # 优先使用意图分析结果
        if intent_analysis:
            days = intent_analysis.get('days', 1)  # 默认1天
            
            if intent_analysis.get('needs_vulnerability_collection'):
                actions.append({'name': 'collect_vulnerabilities', 'parameters': {'days': days}})
            
            if intent_analysis.get('needs_asset_collection'):
                actions.append({'name': 'collect_assets', 'parameters': {}})
            
            if intent_analysis.get('needs_matching'):
                actions.append({'name': 'match_vulnerabilities', 'parameters': {'days': days}})
        
        # 如果意图分析没有结果，尝试从JSON中提取
        # 注意：只有在用户明确要求执行操作时才提取，不要从AI的说明性回复中提取
        if not actions:
            # 如果用户只是要求创建/设置任务，不从JSON中提取操作
            if user_message:
                user_msg_lower = user_message.lower()
                create_keywords = ['创建', '设置', '配置', '建立', '添加']
                has_create_keyword = any(kw in user_msg_lower for kw in create_keywords)
                if has_create_keyword:
                    logger.debug("用户只是要求创建/设置任务，不从JSON中提取操作")
                    return []
            
            try:
                # 查找JSON块
                json_start = response.rfind('{')
                json_end = response.rfind('}') + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_str = response[json_start:json_end]
                    data = json.loads(json_str)
                    
                    if 'actions' in data and isinstance(data['actions'], list):
                        actions = data['actions']
            except Exception as e:
                logger.debug(f"解析操作JSON失败: {e}")
        
        # 不再从响应文本中提取操作，因为容易误判
        # 操作应该通过以下方式触发：
        # 1. 意图分析（用户消息中明确要求）
        # 2. 工具调用（Function Calling）
        # 3. JSON格式的操作列表（AI明确输出）
        
        return actions
    
    def _execute_action(self, action: Dict[str, Any], user=None) -> Generator[str, None, None]:
        """
        执行操作
        
        Args:
            action: 操作字典
            user: 用户对象
            
        Yields:
            str: 执行日志片段
        """
        action_name = action.get('name')
        parameters = action.get('parameters', {})
        
        if action_name == 'collect_vulnerabilities':
            yield from self._collect_vulnerabilities(parameters, user)
        elif action_name == 'match_vulnerabilities':
            yield from self._match_vulnerabilities(parameters, user)
        elif action_name == 'collect_assets':
            yield from self._collect_assets(parameters, user)
        else:
            yield f"❌ 未知操作: {action_name}\n"
    
    def _collect_vulnerabilities(self, parameters: Dict[str, Any], user=None) -> Generator[str, None, None]:
        """采集漏洞"""
        days = parameters.get('days', 1)  # 默认1天
        
        # 限制天数范围（1-30天）
        try:
            days = int(days) if days else 1
            if days < 1 or days > 30:
                days = min(max(1, days), 30)
                logger.warning(f"天数参数超出范围，已限制为: {days}")
        except (ValueError, TypeError):
            days = 1
            logger.warning(f"无效的天数参数，使用默认值: 1")
        
        # 查找漏洞采集插件（使用数据库中的插件名称）
        plugin = Plugin.objects.filter(name='collect_oss_security', is_active=True).first()
        if not plugin:
            yield "**❌ 未找到漏洞采集插件**\n"
            return
        
        # 配置插件
        config = {
            'max_days': days
        }
        
        # 执行插件（流式输出，使用数据库中的插件名称）
        # 注意：插件执行过程中的日志不会输出，只输出最终结果
        yield from TaskExecutor.execute_plugin_stream('collect_oss_security', config, user)
        
        # 查询采集结果
        from datetime import timedelta
        from django.utils import timezone
        
        since_date = timezone.now() - timedelta(days=days)
        vulnerabilities = Vulnerability.objects.filter(collected_at__gte=since_date).order_by('-published_date', '-collected_at')
        count = vulnerabilities.count()
        
        # 显示捕获的漏洞列表（简化格式）
        if count > 0:
            yield f"\n**📋 捕获的漏洞列表（共 {count} 条）**\n\n"
            for idx, vuln in enumerate(vulnerabilities[:10], 1):  # 只显示前10个
                content = vuln.content if isinstance(vuln.content, dict) else {}
                severity = content.get('severity', '')
                affected_component = content.get('affected_component', '').strip()
                
                # 根据危害等级添加emoji
                severity_text = ""
                if severity and severity != '未知':
                    severity_emoji = {
                        'Critical': '🔴',
                        'High': '🟠',
                        'Medium': '🟡',
                        'Moderate': '🟡',
                        'Low': '🟢',
                        'Important': '🟠'
                    }
                    emoji = severity_emoji.get(severity, '⚪')
                    severity_text = f"{emoji} {severity}"
                
                component_text = ""
                if affected_component and affected_component not in ['未知', ''] and self._is_valid_component_name(affected_component):
                    component_text = f" | 影响组件: {affected_component}"
                
                yield f"{idx}. **{vuln.cve_id}**"
                if severity_text:
                    yield f" ({severity_text})"
                if component_text:
                    yield component_text
                yield "\n"
            
            if count > 10:
                yield f"\n> 还有 {count - 10} 个漏洞未显示\n"
    
    def _match_vulnerabilities(self, parameters: Dict[str, Any], user=None) -> Generator[str, None, None]:
        """匹配漏洞与资产"""
        days = parameters.get('days', 1)  # 默认1天
        
        # 限制天数范围（1-30天）
        try:
            days = int(days) if days else 1
            if days < 1 or days > 30:
                days = min(max(1, days), 30)
                logger.warning(f"天数参数超出范围，已限制为: {days}")
        except (ValueError, TypeError):
            days = 1
            logger.warning(f"无效的天数参数，使用默认值: 1")
        
        # 先检查是否有资产数据
        asset_count = Asset.objects.count()
        if asset_count == 0:
            yield "**⚠️ 当前没有资产数据**\n\n"
            yield "请先执行资产采集任务\n"
            return
        
        # 执行匹配（不重复显示漏洞列表，因为采集时已经显示过了）
        from datetime import timedelta
        from django.utils import timezone
        
        since_date = timezone.now() - timedelta(days=days)
        all_vulnerabilities = Vulnerability.objects.filter(
            collected_at__gte=since_date
        )
        vuln_count = all_vulnerabilities.count()
        
        matches = AssetMatcher.match_recent_vulnerabilities(days=days)
        
        if not matches:
            yield f"\n**✅ 匹配结果**\n\n"
            yield f"共检查了 {vuln_count} 个漏洞和 {asset_count} 个资产，未发现受影响的资产。\n"
            return
        
        # 按漏洞分组
        vuln_groups = {}
        for match in matches:
            cve_id = match['vulnerability'].cve_id
            if cve_id not in vuln_groups:
                vuln_groups[cve_id] = {
                    'vulnerability': match['vulnerability'],
                    'assets': []
                }
            vuln_groups[cve_id]['assets'].append(match)
        
        # 输出结果（简化格式）
        yield f"\n**⚠️ 发现 {len(vuln_groups)} 个漏洞影响了资产**\n\n"
        
        for idx, (cve_id, group) in enumerate(vuln_groups.items(), 1):
            vuln = group['vulnerability']
            assets = group['assets']
            content = vuln.content if isinstance(vuln.content, dict) else {}
            
            severity = content.get('severity', '')
            severity_text = ""
            if severity:
                severity_emoji = {
                    'Critical': '🔴',
                    'High': '🟠',
                    'Medium': '🟡',
                    'Moderate': '🟡',
                    'Low': '🟢',
                    'Important': '🟠'
                }
                emoji = severity_emoji.get(severity, '⚪')
                severity_text = f" ({emoji} {severity})"
            
            affected_component = content.get('affected_component', '').strip()
            component_text = ""
            if affected_component and self._is_valid_component_name(affected_component):
                component_text = f" | 影响组件: {affected_component}"
            
            yield f"**{idx}. {cve_id}**{severity_text}{component_text}\n"
            yield f"   受影响资产: {len(assets)} 个\n"
            
            # 只显示前5个资产
            for match in assets[:5]:
                asset = match['asset']
                asset_type = asset.get_asset_type_display() if hasattr(asset, 'get_asset_type_display') else asset.asset_type
                asset_name = asset.name or asset.uuid
                asset_version = ""
                if isinstance(asset.data, dict):
                    asset_version = asset.data.get('Version', '') or asset.data.get('version', '')
                
                if asset_version:
                    yield f"   - {asset_name} ({asset_version}) - {asset_type}\n"
                else:
                    yield f"   - {asset_name} - {asset_type}\n"
            
            if len(assets) > 5:
                yield f"   - ... 还有 {len(assets) - 5} 个资产\n"
            yield "\n"
        
        yield "\n💡 **建议**: 请尽快处理这些受影响的资产，根据漏洞详情采取相应的修复措施。\n"
    
    def _collect_assets(self, parameters: Dict[str, Any], user=None) -> Generator[str, None, None]:
        """采集资产"""
        # 查找资产采集插件（使用数据库中的插件名称）
        plugin = Plugin.objects.filter(name='data_aliyun_security', is_active=True).first()
        if not plugin:
            yield "**❌ 未找到资产采集插件**\n"
            return
        
        # 执行插件（使用数据库中的插件名称）
        yield from TaskExecutor.execute_plugin_stream('data_aliyun_security', {}, user)
    
    def _call_tool(self, function_name: str, function_args: Dict[str, Any], user=None) -> Dict[str, Any]:
        """
        调用工具函数
        
        Args:
            function_name: 函数名称
            function_args: 函数参数
            user: 用户对象
            
        Returns:
            Dict: 函数执行结果
        """
        try:
            if function_name == 'create_task':
                # 处理cron表达式（可能是自然语言）
                cron_expr = function_args.get('cron_expression')
                if cron_expr and function_args.get('trigger_type') == 'cron':
                    # 尝试从自然语言解析
                    parsed_cron = parse_cron_from_natural_language(cron_expr)
                    if parsed_cron:
                        function_args['cron_expression'] = parsed_cron
                        logger.info(f"将自然语言'{cron_expr}'解析为cron表达式: {parsed_cron}")
                
                # 添加创建者信息
                if user:
                    if hasattr(user, 'username'):
                        function_args['created_by'] = user.username
                    elif isinstance(user, str):
                        function_args['created_by'] = user
                
                return create_task(**function_args)
            
            elif function_name == 'list_tasks':
                # 添加创建者过滤
                if user:
                    if hasattr(user, 'username'):
                        function_args['created_by'] = user.username
                    elif isinstance(user, str):
                        function_args['created_by'] = user
                
                return list_tasks(**function_args)
            
            elif function_name == 'update_task':
                # 传递user参数用于权限检查
                return update_task(**function_args, user=user)
            
            elif function_name == 'parse_cron':
                cron_expr = parse_cron_from_natural_language(function_args.get('text', ''))
                if cron_expr:
                    return {
                        'success': True,
                        'cron_expression': cron_expr,
                        'message': f"已解析：'{function_args.get('text')}' -> '{cron_expr}'"
                    }
                else:
                    return {
                        'success': False,
                        'message': f"无法解析：'{function_args.get('text')}'"
                    }
            
            elif function_name == 'list_assets':
                return list_assets(
                    limit=function_args.get('limit', 50),
                    asset_type=function_args.get('asset_type'),
                    source=function_args.get('source'),
                )
            
            elif function_name == 'hexstrike_analyze_target':
                if not getattr(settings, 'HEXSTRIKE_ENABLED', True):
                    return {
                        'success': False,
                        'message': 'HexStrike 集成未启用，请在配置中开启 HEXSTRIKE_ENABLED 并启动 HexStrike 服务。'
                    }
                target = function_args.get('target', '').strip()
                if not target:
                    return {'success': False, 'message': '请提供要分析的目标（IP、域名或主机名）。'}
                analysis_type = function_args.get('analysis_type') or 'comprehensive'
                
                # 创建执行记录
                import time
                from django.utils import timezone
                execution = HexStrikeExecution.objects.create(
                    target=target,
                    analysis_type=analysis_type,
                    status='running',
                    created_by=getattr(self, 'user_id', None) or '',
                )
                start_time = time.time()
                
                try:
                    client = HexStrikeClient(
                        base_url=getattr(settings, 'HEXSTRIKE_SERVER_URL', 'http://localhost:8888'),
                        timeout=getattr(settings, 'HEXSTRIKE_TIMEOUT', 600),  # 增加到 10 分钟
                    )
                    result = client.analyze_target(target, analysis_type=analysis_type)

                    # 如果成功，格式化 nmap 和 nuclei 的结果
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
                    raise
            
            elif function_name == 'hexstrike_run_scan':
                if not getattr(settings, 'HEXSTRIKE_ENABLED', True):
                    return {
                        'success': False,
                        'message': 'HexStrike 集成未启用，请在配置中开启 HEXSTRIKE_ENABLED 并启动 HexStrike 服务。'
                    }
                tool_name = (function_args.get('tool_name') or '').strip()
                arguments = function_args.get('arguments')
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {}
                if not tool_name:
                    return {'success': False, 'message': '请提供要执行的工具名称（如 nmap_scan, nuclei_scan）。'}
                if arguments is None:
                    arguments = {}
                
                # 从 arguments 中提取 target，如果没有则使用默认值
                target = arguments.get('target', '') or arguments.get('host', '') or 'unknown'
                
                # 创建执行记录
                import time
                from django.utils import timezone
                execution = HexStrikeExecution.objects.create(
                    target=target,
                    tool_name=tool_name,
                    analysis_type='tool_scan',
                    status='running',
                    created_by=getattr(self, 'user_id', None) or '',
                )
                start_time = time.time()
                
                try:
                    client = HexStrikeClient(
                        base_url=getattr(settings, 'HEXSTRIKE_SERVER_URL', 'http://localhost:8888'),
                        timeout=getattr(settings, 'HEXSTRIKE_TIMEOUT', 600),  # 增加到 10 分钟
                    )

                    # Nuclei 扫描优化：添加默认参数以避免超时
                    if tool_name in ('nuclei_scan', 'nuclei'):
                        # 如果用户没有指定严重级别，默认只扫描高危和严重漏洞
                        if isinstance(arguments, dict) and 'severity' not in arguments:
                            arguments['severity'] = 'critical,high'

                        # 限制并发和速率，加快扫描速度
                        if isinstance(arguments, dict):
                            if 'rl' not in arguments:
                                arguments['rl'] = 50  # 每秒请求数
                            if 'c' not in arguments:
                                arguments['c'] = 10  # 并发模板数
                            if 'timeout' not in arguments:
                                arguments['timeout'] = 10  # 单个请求超时（秒）
                            if 'retries' not in arguments:
                                arguments['retries'] = 1  # 减少重试次数
                            # 强制使用 JSON 输出格式，便于解析和美化
                            if 'json' not in arguments:
                                arguments['json'] = True  # 启用 JSON 输出

                    result = client.run_command(tool_name, arguments)

                    # 如果是 Nuclei 扫描，解析和格式化结果
                    if result.get('success') and tool_name in ('nuclei_scan', 'nuclei'):
                        from app.services.nuclei_result_parser import format_nuclei_result

                        data = result.get('data', {})
                        stdout = data.get('stdout', '')
                        stderr = data.get('stderr', '')

                        # 如果有输出，尝试格式化
                        if stdout or stderr:
                            formatted_result = format_nuclei_result(stdout, stderr)

                            # 将格式化结果添加到返回数据中
                            result['data']['formatted_output'] = formatted_result
                            result['data']['raw_output'] = stdout or stderr

                    # 如果是 Nmap 扫描，解析和格式化结果
                    elif result.get('success') and tool_name in ('nmap_scan', 'nmap'):
                        from app.services.nmap_result_parser import format_nmap_result

                        data = result.get('data', {})
                        stdout = data.get('stdout', '')
                        stderr = data.get('stderr', '')

                        # 如果有输出，尝试格式化
                        if stdout or stderr:
                            formatted_result = format_nmap_result(stdout, stderr)

                            # 将格式化结果添加到返回数据中
                            result['data']['formatted_output'] = formatted_result
                            result['data']['raw_output'] = stdout or stderr

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
                            'message': f'已执行 {tool_name}',
                            'data': result['data'],
                            'execution_id': execution.id,
                        }
                    return {
                        'success': False,
                        'message': result.get('message', f'HexStrike 执行 {tool_name} 失败，请确认服务已启动且工具名正确。'),
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
                    raise
            
            else:
                return {
                    'success': False,
                    'message': f'未知的工具函数: {function_name}'
                }
                
        except Exception as e:
            logger.error(f"调用工具函数 {function_name} 失败: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'调用工具函数失败: {str(e)}'
            }

