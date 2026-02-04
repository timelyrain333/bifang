"""
钉钉Stream推送服务
使用钉钉官方SDK建立WebSocket长连接，接收事件推送

常见问题：
1. SOCKS 代理：若环境变量设置了 socks5:// 等代理，连接可能失败。
   解决：启动前清除代理变量，或使用 start.sh（已自动清除）。

2. dingtalk_stream 库的 logging 用法有 bug（logger.exception('msg', e) 会触发 TypeError）。
   若重装 dingtalk-stream 后再次出现该错误，需在 site-packages/dingtalk_stream/stream.py
   第 89 行将 self.logger.exception('unknown exception', e) 改为
   self.logger.exception('unknown exception: %s', e)。
"""
import json
import logging
import os
import re
import threading
import asyncio
import requests
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from django.conf import settings as django_settings
from django.db.models import Q
from app.models import AliyunConfig
from app.services.secops_agent import SecOpsAgent
from app.services.hexstrike_client import HexStrikeClient

logger = logging.getLogger(__name__)

# 钉钉 + HexStrike 调试：显式写文件，不依赖 Django LOGGING（Stream 进程可能未写 bifang.log）
def _dingtalk_hexstrike_debug(msg: str):
    try:
        base = Path(django_settings.BASE_DIR) if hasattr(django_settings, 'BASE_DIR') else Path(__file__).resolve().parent.parent.parent
        log_file = base / 'logs' / 'dingtalk_hexstrike_debug.log'
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"{datetime.now().isoformat()} {msg}\n")
    except Exception:
        pass

try:
    import dingtalk_stream
    HAS_DINGTALK_STREAM_SDK = True
except ImportError as e:
    HAS_DINGTALK_STREAM_SDK = False
    logger.warning(f"钉钉Stream SDK未安装或导入失败: {e}，请运行: pip install dingtalk-stream")


# 全局服务实例字典 {config_id: service_instance}
_services = {}

# AccessToken缓存 {config_id: {'token': str, 'expires_at': float}}
_access_token_cache = {}


def get_dingtalk_access_token(client_id: str, client_secret: str) -> Optional[str]:
    """
    获取钉钉AccessToken
    
    参考钉钉官方文档: https://open.dingtalk.com/document/orgapp/obtain-identity-credentials
    
    Args:
        client_id: 钉钉Client ID (AppKey)
        client_secret: 钉钉Client Secret (AppSecret)
        
    Returns:
        str: AccessToken，失败返回None
    """
    try:
        # 使用新版本的OAuth2接口获取AccessToken
        url = "https://oapi.dingtalk.com/gettoken"
        params = {
            'appkey': client_id,  # 兼容旧版本API
            'appsecret': client_secret
        }
        
        response = requests.get(url, params=params, timeout=10)
        result = response.json()
        
        if result.get('errcode') == 0:
            access_token = result.get('access_token')
            logger.debug(f"成功获取AccessToken")
            return access_token
        else:
            # 如果旧版本API失败，尝试新版本OAuth2接口
            logger.warning(f"旧版本API获取AccessToken失败: {result.get('errmsg')}，尝试新版本API")
            url_v2 = "https://oapi.dingtalk.com/v1.0/oauth2/accessToken"
            data = {
                'appKey': client_id,
                'appSecret': client_secret
            }
            response_v2 = requests.post(url_v2, json=data, timeout=10)
            result_v2 = response_v2.json()
            
            if result_v2.get('accessToken'):
                logger.debug(f"使用新版本API成功获取AccessToken")
                return result_v2.get('accessToken')
            else:
                logger.error(f"新版本API获取AccessToken失败: {result_v2}")
                return None
    except Exception as e:
        logger.error(f"获取AccessToken异常: {e}", exc_info=True)
        return None


def send_dingtalk_group_message(access_token: str, open_conversation_id: str, 
                                text: str, robot_code: str = None) -> bool:
    """
    发送钉钉群聊消息
    
    参考钉钉官方文档: https://open.dingtalk.com/document/dingstart/the-application-robot-in-the-enterprise-sends-group-chat-messages
    
    Args:
        access_token: 钉钉AccessToken
        open_conversation_id: 群会话ID
        text: 消息文本内容
        robot_code: 机器人Code（可选）
        
    Returns:
        bool: 是否发送成功
    """
    try:
        # 尝试使用新版本API：/v1.0/robot/groupMessages/send（应用机器人）
        # 如果失败，会回退到SDK的reply_text方法
        url = "https://oapi.dingtalk.com/v1.0/robot/groupMessages/send"
        
        # 构建请求头（使用Bearer token方式）
        headers = {
            'Content-Type': 'application/json',
            'x-acs-dingtalk-access-token': access_token
        }
        
        # 构建请求体（使用markdown格式）
        data = {
            "openConversationId": open_conversation_id,
            "msg": {
                "msgtype": "markdown",
                "markdown": {
                    "title": "SecOps智能体",
                    "text": text
                }
            }
        }
        
        # 如果提供了robot_code，添加到请求体中
        if robot_code:
            data["robotCode"] = robot_code
        
        response = requests.post(url, headers=headers, json=data, timeout=10)
        result = response.json()
        
        # 记录详细的API响应（用于调试）
        logger.info(f"群聊消息API响应: status_code={response.status_code}, result={result}, url={url}")
        
        # 检查响应：钉钉API返回的是errcode字段，成功时errcode=0
        errcode = result.get('errcode', -1)
        if errcode == 0:
            logger.info(f"群聊消息发送成功: openConversationId={open_conversation_id}, result={result}")
            return True
        else:
            errmsg = result.get('errmsg', '未知错误')
            logger.warning(f"群聊消息API调用失败: errcode={errcode}, errmsg={errmsg}，将回退到SDK方法")
            return False
    except Exception as e:
        logger.error(f"发送群聊消息异常: {e}", exc_info=True)
        return False


class DingTalkStreamChatbotHandler(dingtalk_stream.AsyncChatbotHandler):
    """钉钉Stream推送聊天机器人处理器"""
    
    def __init__(self, config_id: int, logger: logging.Logger = None):
        super().__init__()
        self.config_id = config_id
        self.config = None
        self.ai_config = None
        self.conversation_history = {}  # 存储每个用户的对话历史 {user_id: [messages]}
        self.processing_messages = set()  # 正在处理的消息ID集合，用于去重
        self._access_token = None
        self._access_token_expires_at = 0
        
        if logger:
            self.logger = logger
        else:
            self.logger = logging.getLogger(__name__)
        
        self._load_config()
    
    def _get_access_token(self) -> Optional[str]:
        """获取AccessToken（带缓存）"""
        # 检查缓存是否有效（提前5分钟刷新）
        if self._access_token and time.time() < self._access_token_expires_at - 300:
            return self._access_token
        
        # 获取新的AccessToken
        token = get_dingtalk_access_token(
            self.config.dingtalk_client_id,
            self.config.dingtalk_client_secret
        )
        
        if token:
            self._access_token = token
            # AccessToken有效期通常为2小时（7200秒）
            self._access_token_expires_at = time.time() + 7200
            self.logger.info("已获取新的AccessToken")
        
        return token
    
    def _send_group_message(self, open_conversation_id: str, text: str) -> bool:
        """
        发送群聊消息（使用markdown格式）
        
        Args:
            open_conversation_id: 群会话ID
            text: 消息文本（markdown格式）
            
        Returns:
            bool: 是否发送成功
        """
        access_token = self._get_access_token()
        if not access_token:
            self.logger.error("无法获取AccessToken，无法发送群聊消息")
            return False
        
        # 获取机器人Code（如果有）
        robot_code = getattr(self.config, 'dingtalk_app_id', None)
        
        return send_dingtalk_group_message(
            access_token=access_token,
            open_conversation_id=open_conversation_id,
            text=text,
            robot_code=robot_code
        )
    
    def reply_text(self, text: str, incoming_message: dingtalk_stream.ChatbotMessage):
        """
        重写reply_text方法，使用markdown格式发送消息
        
        Args:
            text: 消息文本（markdown格式）
            incoming_message: 接收到的消息对象
        """
        # 直接使用SDK的reply_markdown方法（推荐方式）
        try:
            # 提取标题（如果有的话，从第一行提取）
            lines = text.split('\n', 1)
            title = "SecOps智能体"
            if lines[0].startswith('#') or lines[0].startswith('**'):
                # 如果第一行是标题，提取作为title
                title_line = lines[0].strip()
                # 移除markdown标题符号
                title = title_line.lstrip('#').lstrip('*').strip()
                if len(title) > 50:
                    title = title[:50]
                markdown_text = lines[1] if len(lines) > 1 else text
            else:
                markdown_text = text
            
            # 使用SDK的reply_markdown方法
            super().reply_markdown(title=title, text=markdown_text, incoming_message=incoming_message)
            self.logger.info(f"使用SDK的reply_markdown方法发送消息成功")
        except Exception as e:
            self.logger.warning(f"使用SDK的reply_markdown方法失败: {e}，回退到reply_text方法")
            # 如果markdown方法失败，回退到普通文本方法
            try:
                super().reply_text(text, incoming_message)
            except Exception as e2:
                self.logger.error(f"使用SDK的reply_text方法也失败: {e2}")
    
    def _load_config(self):
        """加载配置"""
        try:
            self.config = AliyunConfig.objects.get(id=self.config_id)
            
            # 获取关联的AI配置
            if self.config.qianwen_config:
                self.ai_config = self.config.qianwen_config
                self.logger.info(f"使用关联的AI配置: {self.ai_config.name} (ID: {self.ai_config.id})")
            elif self.config.qianwen_enabled and self.config.qianwen_api_key:
                self.ai_config = self.config
                self.logger.info(f"使用当前配置的AI设置: {self.config.name} (ID: {self.config.id})")
            else:
                self.logger.warning(f"配置 {self.config_id} 未关联AI配置，智能体功能将不可用")
                self.ai_config = None
        except AliyunConfig.DoesNotExist:
            self.logger.error(f"配置 {self.config_id} 不存在")
            raise
    
    def process(self, callback: dingtalk_stream.CallbackMessage):
        """
        处理接收到的消息
        
        注意：此方法不能是async，SDK要求是同步方法
        参考钉钉官方文档: https://open.dingtalk.com/document/dingstart/robot-reply-and-send-messages
        
        Args:
            callback: 回调消息对象
            
        Returns:
            (status, message): 状态码和消息
        """
        # 初始化message_id，避免在异常处理中未定义
        message_id = None
        open_conversation_id = None
        incoming_message = None
        
        try:
            # 记录收到消息的详细信息（用于调试）
            # callback对象可能有不同的属性结构，尝试多种方式获取topic
            topic = None
            if hasattr(callback, 'topic'):
                topic = callback.topic
            elif hasattr(callback, 'headers'):
                # Headers可能是一个对象而不是字典，使用getattr获取属性
                headers = callback.headers
                if isinstance(headers, dict):
                    topic = headers.get('topic')
                else:
                    # 如果是对象，尝试获取topic属性
                    topic = getattr(headers, 'topic', None)
            
            self.logger.info(f"收到callback消息: topic={topic}, callback类型={type(callback)}")
            
            # 解析消息（使用SDK提供的方法）
            incoming_message = dingtalk_stream.ChatbotMessage.from_dict(callback.data)
            
            # 获取消息ID（用于去重）
            message_id = getattr(incoming_message, 'message_id', None)
            if message_id and message_id in self.processing_messages:
                self.logger.debug(f"消息 {message_id} 已处理，跳过")
                return dingtalk_stream.AckMessage.STATUS_OK, 'OK'
            
            if message_id:
                self.processing_messages.add(message_id)
            
            # 使用SDK提供的辅助方法提取文本内容（推荐方式）
            content = self.extract_text_from_incoming_message(incoming_message)
            
            # 如果content是列表，转换为字符串
            if isinstance(content, list):
                # 将列表中的元素连接成字符串
                content = ' '.join(str(item) for item in content if item)
            elif content is None:
                content = ''
            else:
                content = str(content)
            
            # 获取发送者ID
            user_id = getattr(incoming_message, 'sender_id', None)
            
            # 获取群会话ID（openConversationId）- 用于发送群聊消息
            # 尝试多种方式获取openConversationId
            # 方式1: 从incoming_message对象获取
            open_conversation_id = (getattr(incoming_message, 'conversation_id', None) or 
                                   getattr(incoming_message, 'openConversationId', None) or
                                   getattr(incoming_message, 'conversationId', None))
            # 方式2: 从callback.data中获取
            if not open_conversation_id and hasattr(callback, 'data') and isinstance(callback.data, dict):
                open_conversation_id = (callback.data.get('conversationId') or 
                                       callback.data.get('openConversationId') or
                                       callback.data.get('conversation_id'))
            # 方式3: 从原始消息数据中获取
            if not open_conversation_id and hasattr(callback, 'data'):
                try:
                    if isinstance(callback.data, dict):
                        # 尝试从嵌套结构中获取
                        if 'conversationId' in callback.data:
                            open_conversation_id = callback.data['conversationId']
                        elif 'openConversationId' in callback.data:
                            open_conversation_id = callback.data['openConversationId']
                except Exception as e:
                    self.logger.debug(f"从callback.data提取openConversationId失败: {e}")
            
            # 检查是否应回复：钉钉单聊(1)=直接发给机器人；群聊(2)=只有@机器人的消息才会推送，收到即需回复
            is_in_at_list = getattr(incoming_message, 'is_in_at_list', None)
            conversation_type = getattr(incoming_message, 'conversation_type', None)
            is_at_bot = (
                is_in_at_list is True
                or conversation_type == '1'   # 单聊：发给机器人的都回复
                or conversation_type == '2'   # 群聊：能收到就说明被@了（钉钉只推送@机器人的消息）
            )

            self.logger.info(f"收到消息: message_id={message_id}, user_id={user_id}, "
                           f"is_in_at_list={is_in_at_list}, conversation_type={conversation_type}, "
                           f"is_at_bot={is_at_bot}, openConversationId={open_conversation_id}, "
                           f"content={content[:100] if content else '(空)'}")
            
            if not is_at_bot:
                self.logger.debug(f"消息未@机器人或非单聊/群聊，跳过处理: message_id={message_id}")
                if message_id:
                    self.processing_messages.discard(message_id)
                return dingtalk_stream.AckMessage.STATUS_OK, 'OK'
            
            # 移除@机器人的部分（如果存在）
            if content:
                # 确保content是字符串
                content = str(content) if not isinstance(content, str) else content
                content = re.sub(r'@[^\s@]+', '', content).strip()
            # 调试：显式写文件，便于排查钉钉消息是否到达及内容
            _dingtalk_hexstrike_debug(f"钉钉消息 content_len={len(content or '')} preview={(content or '')[:150]}")
            
            self.logger.info(f"处理@机器人消息: user_id={user_id}, content={content[:100] if content else '(空)'}")
            
            # 如果消息内容为空，回复提示
            if not content:
                response_text = "👋 你好！我是SecOps智能体，可以帮你处理安全运营任务。\n\n你可以问我：\n- 查看最新漏洞\n- 采集资产信息\n- 创建任务\n等等..."
                # 直接使用SDK的reply_text方法
                self.reply_text(response_text, incoming_message)
                if message_id:
                    self.processing_messages.discard(message_id)
                return dingtalk_stream.AckMessage.STATUS_OK, 'OK'
            
            # 检查是否有AI配置（智能体功能）
            if not self.ai_config or not self.ai_config.qianwen_api_key:
                response_text = "❌ AI配置未启用，无法使用智能体功能。请在系统配置中启用AI配置。"
                # 直接使用SDK的reply_text方法
                self.reply_text(response_text, incoming_message)
                if message_id:
                    self.processing_messages.discard(message_id)
                return dingtalk_stream.AckMessage.STATUS_OK, 'OK'
            
            # 获取或初始化对话历史
            if user_id not in self.conversation_history:
                self.conversation_history[user_id] = []
            
            # 添加用户消息到历史
            self.conversation_history[user_id].append({
                'role': 'user',
                'content': content
            })
            
            # 钉钉兜底：若消息为「安全评估 + IP/域名」，直接调用 HexStrike，再回复（不依赖 agent.chat 是否选工具）
            # 归一化：全角数字转半角，便于匹配 IP
            content_normalized = (content or '').translate(str.maketrans('０１２３４５６７８９', '0123456789'))
            ip_match = re.search(r'(?:\d{1,3}\.){3}\d{1,3}', content_normalized)
            domain_match = re.search(
                r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}',
                content_normalized,
            )
            hexstrike_target = (ip_match.group(0) if ip_match else None) or (domain_match.group(0) if domain_match else None)
            security_keywords = [
                '安全评估', '渗透测试', '漏洞扫描', '全面评估', '安全扫描', '扫描一下',
                '做一次评估', '做一次扫描', '全面安全评估', '评估', '扫描', '全面',
            ]
            has_security_intent = any(kw in (content or '') for kw in security_keywords) or (
                hexstrike_target and any(kw in (content or '') for kw in ['资产', '服务器', '目标', '对'])
            )
            _dingtalk_hexstrike_debug(f"意图检测 has_security_intent={has_security_intent} hexstrike_target={hexstrike_target!r} HEXSTRIKE_ENABLED={getattr(django_settings, 'HEXSTRIKE_ENABLED', True)}")
            if has_security_intent and hexstrike_target and getattr(django_settings, 'HEXSTRIKE_ENABLED', True):
                _dingtalk_hexstrike_debug(f"HEXSTRIKE_DIRECT_CALL target={hexstrike_target}")
                self.logger.info("钉钉：检测到安全评估意图，直接调用 HexStrike: target=%s", hexstrike_target)
                try:
                    base_url = getattr(django_settings, 'HEXSTRIKE_SERVER_URL', 'http://localhost:8888')
                    timeout = getattr(django_settings, 'HEXSTRIKE_TIMEOUT', 300)
                    client = HexStrikeClient(base_url=base_url, timeout=timeout)
                    response = f"### 目标 {hexstrike_target} 安全评估\n\n"
                    # 1) AI 分析（可能无实际扫描，仅策略/摘要）
                    result = client.analyze_target(hexstrike_target, analysis_type='comprehensive')
                    if result.get('success') and result.get('data') is not None:
                        data = result['data']
                        if isinstance(data, dict) and data:
                            response += "**分析摘要**\n```\n" + json.dumps(data, ensure_ascii=False, indent=2) + "\n```\n\n"
                        elif data:
                            response += "**分析摘要**\n" + str(data) + "\n\n"
                    # 2) 显式执行 nmap 扫描，便于在 docker logs 中看到执行过程
                    nmap_res = client.run_command("nmap_scan", {"target": hexstrike_target})
                    if nmap_res.get('success') and nmap_res.get('data') is not None:
                        response += "**Nmap 端口扫描结果**\n```\n" + json.dumps(nmap_res['data'], ensure_ascii=False, indent=2) + "\n```\n\n"
                    elif not nmap_res.get('success'):
                        response += "**Nmap**：" + (nmap_res.get('message') or '未执行或失败') + "\n\n"
                    # 3) 显式执行 nuclei 漏洞扫描（目标为 http://IP 或 IP）
                    nuclei_res = client.run_command("nuclei_scan", {"target": hexstrike_target})
                    if nuclei_res.get('success') and nuclei_res.get('data') is not None:
                        response += "**Nuclei 漏洞扫描结果**\n```\n" + json.dumps(nuclei_res['data'], ensure_ascii=False, indent=2) + "\n```\n\n"
                    elif not nuclei_res.get('success'):
                        response += "**Nuclei**：" + (nuclei_res.get('message') or '未执行或失败') + "\n\n"
                    response += f"---\n✅ 评估完成。查看 HexStrike 执行过程：`docker logs hexstrike-ai 2>&1 | grep -E \"EXECUTING|FINAL RESULTS|{hexstrike_target}\"`"
                    self.conversation_history[user_id].append({'role': 'assistant', 'content': response})
                    if len(self.conversation_history[user_id]) > 40:
                        self.conversation_history[user_id] = self.conversation_history[user_id][-40:]
                    self.reply_text(response, incoming_message)
                    self.logger.info("钉钉：HexStrike 安全评估已回复, target=%s", hexstrike_target)
                    _dingtalk_hexstrike_debug("HexStrike 调用成功并已回复")
                except Exception as e:
                    self.logger.error("钉钉：HexStrike 调用异常: %s", e, exc_info=True)
                    _dingtalk_hexstrike_debug(f"HexStrike 调用异常: {e}")
                    self.reply_text(f"### ❌ HexStrike 调用异常: {str(e)}\n\n", incoming_message)
                if message_id:
                    self.processing_messages.discard(message_id)
                _dingtalk_hexstrike_debug("HexStrike 直接调用分支结束")
                return dingtalk_stream.AckMessage.STATUS_OK, 'OK'
            
            # 创建SecOps智能体实例并处理消息
            try:
                # 获取AI配置参数
                api_key = self.ai_config.qianwen_api_key
                api_base = self.ai_config.qianwen_api_base or 'https://dashscope.aliyuncs.com/compatible-mode/v1'
                model = self.ai_config.qianwen_model or 'qwen-plus'
                
                agent = SecOpsAgent(api_key, api_base, model)
                
                # 获取用户对象（用于插件执行时加载AI配置）
                # 钉钉场景下，使用配置关联的用户或默认用户
                user = None
                if self.config and hasattr(self.config, 'user'):
                    user = self.config.user
                elif self.ai_config and hasattr(self.ai_config, 'user'):
                    user = self.ai_config.user
                else:
                    # 如果没有关联用户，尝试查找默认用户或使用配置本身
                    # 这种情况下，TaskExecutor会使用配置来查找AI配置
                    pass
                
                # chat方法返回生成器，需要收集所有响应
                # 注意：process方法是同步的，所以直接调用同步方法
                response_parts = []
                for part in agent.chat(
                    user_message=content,
                    conversation_history=self.conversation_history.get(user_id, []),
                    user=user
                ):
                    response_parts.append(part)
                response = ''.join(response_parts)
                
                # 添加AI回复到历史
                self.conversation_history[user_id].append({
                    'role': 'assistant',
                    'content': response
                })
                
                # 限制历史记录长度（保留最近40条消息，约20轮对话）
                if len(self.conversation_history[user_id]) > 40:
                    self.conversation_history[user_id] = self.conversation_history[user_id][-40:]
                
                # 回复消息（直接使用SDK的reply_text方法，因为自定义API调用可能权限不足）
                self.reply_text(response, incoming_message)
                self.logger.info(f"已回复消息给用户 {user_id}: {response[:50] if len(response) > 50 else response}...")
                
            except Exception as e:
                self.logger.error(f"处理消息失败: {e}", exc_info=True)
                error_response = f"❌ 处理消息时发生错误: {str(e)}"
                # 直接使用SDK的reply_text方法
                self.reply_text(error_response, incoming_message)
            
            # 从处理中移除
            if message_id:
                self.processing_messages.discard(message_id)
            
            return dingtalk_stream.AckMessage.STATUS_OK, 'OK'
            
        except Exception as e:
            self.logger.error(f"处理钉钉Stream消息异常: {e}", exc_info=True)
            # 确保message_id已定义再尝试移除
            if hasattr(self, 'processing_messages'):
                if message_id:
                    self.processing_messages.discard(message_id)
            # 尝试发送错误消息（如果可能）
            try:
                if incoming_message and open_conversation_id:
                    error_response = f"❌ 处理消息时发生错误: {str(e)}"
                    self._send_group_message(open_conversation_id, error_response)
            except:
                pass  # 发送错误消息失败时不影响主流程
            return dingtalk_stream.AckMessage.STATUS_SYSTEM_EXCEPTION, str(e)
    


class DingTalkStreamService:
    """钉钉Stream推送服务"""
    
    def __init__(self, config_id: int):
        """
        初始化钉钉Stream推送服务
        
        Args:
            config_id: AliyunConfig的ID（包含钉钉和AI配置）
        """
        if not HAS_DINGTALK_STREAM_SDK:
            raise ImportError("钉钉Stream SDK未安装，请运行: pip install dingtalk-stream")
        
        self.config_id = config_id
        self.config = AliyunConfig.objects.get(id=config_id)
        self.client = None
        self.loop = None
        self.thread = None
        self.is_running = False
        
        # 检查配置
        if not self.config.dingtalk_client_id or not self.config.dingtalk_client_secret:
            raise ValueError("钉钉Client ID和Client Secret未配置")
        
        if not self.config.dingtalk_use_stream_push:
            raise ValueError("配置未启用Stream推送")
        
        logger.info(f"初始化钉钉Stream服务: config_id={config_id}, client_id={self.config.dingtalk_client_id}")
    
    def _create_client(self):
        """创建钉钉Stream客户端"""
        credential = dingtalk_stream.Credential(
            self.config.dingtalk_client_id,
            self.config.dingtalk_client_secret
        )
        
        client = dingtalk_stream.DingTalkStreamClient(credential)
        
        # 注册聊天机器人消息处理器
        handler = DingTalkStreamChatbotHandler(self.config_id, logger)
        
        # 注册两个topic：普通消息和代理消息（根据钉钉文档）
        chatbot_topic = dingtalk_stream.chatbot.ChatbotMessage.TOPIC
        delegate_topic = dingtalk_stream.chatbot.ChatbotMessage.DELEGATE_TOPIC
        
        logger.info(f"注册chatbot handler: TOPIC={chatbot_topic}, DELEGATE_TOPIC={delegate_topic}")
        
        client.register_callback_handler(chatbot_topic, handler)
        client.register_callback_handler(delegate_topic, handler)
        
        return client
    
    def _run_in_thread(self):
        """在线程中运行事件循环"""
        try:
            # 连接钉钉时清除代理，避免 SOCKS 代理导致 "python-socks required" 错误
            _proxy_keys = {'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'}
            for key in list(os.environ.keys()):
                if key in _proxy_keys:
                    try:
                        del os.environ[key]
                    except KeyError:
                        pass
            
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            self.client = self._create_client()
            logger.info(f"钉钉Stream客户端已创建，开始连接...")
            
            # 启动客户端（这会阻塞，直到连接关闭）
            self.loop.run_until_complete(self.client.start())
            
        except Exception as e:
            logger.error(f"钉钉Stream服务运行异常: {e}", exc_info=True)
            self.is_running = False
        finally:
            if self.loop:
                self.loop.close()
    
    def start(self):
        """启动服务"""
        if self.is_running:
            logger.warning(f"钉钉Stream服务 {self.config_id} 已在运行")
            return
        
        logger.info(f"启动钉钉Stream服务: config_id={self.config_id}")
        self.is_running = True
        
        # 在新线程中运行
        self.thread = threading.Thread(target=self._run_in_thread, daemon=True)
        self.thread.start()
        
        # 等待一小段时间确保连接建立
        import time
        time.sleep(2)
        
        logger.info(f"钉钉Stream服务 {self.config_id} 已启动")
    
    def stop(self):
        """停止服务"""
        if not self.is_running:
            return
        
        logger.info(f"停止钉钉Stream服务: config_id={self.config_id}")
        self.is_running = False
        
        if self.client and self.loop:
            try:
                # 关闭客户端连接
                if self.loop.is_running():
                    asyncio.run_coroutine_threadsafe(self.client.stop(), self.loop)
            except Exception as e:
                logger.error(f"停止钉钉Stream服务时出错: {e}", exc_info=True)
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        
        logger.info(f"钉钉Stream服务 {self.config_id} 已停止")


def start_service(config_id: int) -> DingTalkStreamService:
    """
    启动钉钉Stream推送服务
    
    Args:
        config_id: 配置ID
        
    Returns:
        DingTalkStreamService实例
    """
    # 如果服务已存在，先停止
    if config_id in _services:
        _services[config_id].stop()
    
    # 创建新服务
    service = DingTalkStreamService(config_id)
    service.start()
    _services[config_id] = service
    
    return service


def stop_service(config_id: int):
    """停止指定配置的服务"""
    if config_id in _services:
        _services[config_id].stop()
        del _services[config_id]


def stop_all_services():
    """停止所有服务"""
    for config_id in list(_services.keys()):
        stop_service(config_id)

