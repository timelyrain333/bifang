"""
钉钉机器人智能体服务
处理钉钉机器人的消息，并调用SecOps智能体执行任务
"""
import json
import logging
import re
import threading
from typing import Dict, Any, Optional
from django.conf import settings as django_settings
from django.db.models import Q
from app.models import AliyunConfig
from app.services.secops_agent import SecOpsAgent
from app.services.hexstrike_client import HexStrikeClient
from app.utils.dingtalk import send_dingtalk_message

logger = logging.getLogger(__name__)


class DingTalkAgent:
    """钉钉机器人智能体"""
    
    def __init__(self, config_id: int):
        """
        初始化钉钉机器人智能体
        
        Args:
            config_id: AliyunConfig的ID（包含钉钉和AI配置）
        """
        self.config = AliyunConfig.objects.get(id=config_id)
        self.conversation_history = {}  # 存储每个用户的对话历史 {user_id: [messages]}
    
    def handle_message(self, webhook_url: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理钉钉机器人接收到的消息
        
        Args:
            webhook_url: 钉钉webhook地址（用于发送回复）
            message_data: 钉钉消息数据
        
        Returns:
            Dict: 处理结果
        """
        try:
            # 解析消息内容
            msg_type = message_data.get('msgtype', '')
            
            if msg_type == 'text':
                # 文本消息
                text_content = message_data.get('text', {}).get('content', '').strip()
                
                # 移除@机器人的部分
                text_content = text_content.replace('@SecOps智能体', '').strip()
                
                if not text_content:
                    return {
                        'success': True,
                        'message': '收到空消息'
                    }
                
                # 获取发送者信息（如果有）
                sender_id = message_data.get('senderId', 'unknown')
                
                # 在新线程中处理消息并发送回复（避免超时）
                thread = threading.Thread(
                    target=self._process_and_reply,
                    args=(webhook_url, text_content, sender_id),
                    daemon=True
                )
                thread.start()
                
                # 立即返回确认
                return {
                    'success': True,
                    'message': '消息已接收，正在处理...'
                }
            else:
                return {
                    'success': False,
                    'message': f'不支持的消息类型: {msg_type}'
                }
                
        except Exception as e:
            logger.error(f"处理钉钉消息失败: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'处理失败: {str(e)}'
            }
    
    def _process_and_reply(self, webhook_url: str, user_message: str, sender_id: str):
        """
        处理消息并发送回复
        
        Args:
            webhook_url: 钉钉webhook地址
            user_message: 用户消息
            sender_id: 发送者ID
        """
        try:
            # 获取或初始化对话历史
            if sender_id not in self.conversation_history:
                self.conversation_history[sender_id] = []
            
            conversation_history = self.conversation_history[sender_id]
            
            # 检查AI配置
            if not self.config.qianwen_enabled or not self.config.qianwen_api_key:
                send_dingtalk_message(
                    webhook_url=webhook_url,
                    secret=self.config.dingtalk_secret if self.config.dingtalk_secret else None,
                    title='配置错误',
                    text='❌ 未找到可用的通义千问配置，请先在系统配置中配置通义千问API'
                )
                return
            
            # 钉钉 Webhook 兜底：若消息为「安全评估 + IP/域名」，直接调用 HexStrike 再回复
            ip_match = re.search(r'(?:\d{1,3}\.){3}\d{1,3}', user_message)
            domain_match = re.search(
                r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}',
                user_message,
            )
            hexstrike_target = (ip_match.group(0) if ip_match else None) or (domain_match.group(0) if domain_match else None)
            security_keywords = [
                '安全评估', '渗透测试', '漏洞扫描', '全面评估', '安全扫描', '扫描一下',
                '做一次评估', '做一次扫描', '全面安全评估', '评估', '扫描',
            ]
            has_security_intent = any(kw in user_message for kw in security_keywords) or (
                hexstrike_target and any(kw in user_message for kw in ['资产', '服务器', '目标', '对'])
            )
            if has_security_intent and hexstrike_target and getattr(django_settings, 'HEXSTRIKE_ENABLED', True):
                logger.info("钉钉 Webhook：检测到安全评估意图，直接调用 HexStrike: target=%s", hexstrike_target)
                try:
                    base_url = getattr(django_settings, 'HEXSTRIKE_SERVER_URL', 'http://localhost:8888')
                    timeout = getattr(django_settings, 'HEXSTRIKE_TIMEOUT', 300)
                    client = HexStrikeClient(base_url=base_url, timeout=timeout)
                    result = client.analyze_target(hexstrike_target, analysis_type='comprehensive')
                    if result.get('success') and result.get('data') is not None:
                        response = f"### ✅ 已对目标 {hexstrike_target} 完成安全分析\n\n"
                        data = result['data']
                        if isinstance(data, dict):
                            response += json.dumps(data, ensure_ascii=False, indent=2)
                        else:
                            response += str(data)
                    else:
                        response = f"### ❌ {result.get('message', 'HexStrike 分析失败，请确认 HexStrike 服务已启动。')}\n\n"
                    send_dingtalk_message(
                        webhook_url=webhook_url,
                        secret=self.config.dingtalk_secret if self.config.dingtalk_secret else None,
                        title='SecOps 安全评估',
                        text=response
                    )
                    conversation_history.append({"role": "user", "content": user_message})
                    conversation_history.append({"role": "assistant", "content": response})
                    if len(conversation_history) > 10:
                        conversation_history = conversation_history[-10:]
                    self.conversation_history[sender_id] = conversation_history
                    return
                except Exception as e:
                    logger.error("钉钉 Webhook：HexStrike 调用异常: %s", e, exc_info=True)
                    send_dingtalk_message(
                        webhook_url=webhook_url,
                        secret=self.config.dingtalk_secret if self.config.dingtalk_secret else None,
                        title='HexStrike 异常',
                        text=f"### ❌ HexStrike 调用异常: {str(e)}\n\n"
                    )
                    return
            
            # 创建智能体实例
            agent = SecOpsAgent(
                api_key=self.config.qianwen_api_key,
                api_base=self.config.qianwen_api_base or 'https://dashscope.aliyuncs.com/compatible-mode/v1',
                model=self.config.qianwen_model or 'qwen-plus'
            )
            
            # 收集所有响应内容
            full_response = ""
            response_chunks = []
            current_chunk = ""
            chunk_size = 3000  # 钉钉Markdown消息建议不超过4000字符，我们使用3000
            
            # 调用智能体（流式返回）
            for chunk in agent.chat(user_message, conversation_history, None):
                full_response += chunk
                current_chunk += chunk
                
                # 如果当前块达到一定大小，准备发送
                if len(current_chunk) >= chunk_size:
                    response_chunks.append(current_chunk)
                    current_chunk = ""
            
            # 添加最后一块
            if current_chunk:
                response_chunks.append(current_chunk)
            
            # 如果没有响应块，添加完整响应
            if not response_chunks and full_response:
                response_chunks.append(full_response)
            
            # 发送响应（分批发送，避免消息过长）
            if response_chunks:
                for idx, chunk in enumerate(response_chunks):
                    title = f"SecOps智能体回复"
                    if len(response_chunks) > 1:
                        title += f" ({idx + 1}/{len(response_chunks)})"
                    
                    # 格式化消息（Markdown）
                    text = f"**您的指令**: {user_message}\n\n---\n\n{chunk}"
                    
                    send_dingtalk_message(
                        webhook_url=webhook_url,
                        secret=self.config.dingtalk_secret if self.config.dingtalk_secret else None,
                        title=title,
                        text=text
                    )
            else:
                # 如果没有响应，发送错误消息
                send_dingtalk_message(
                    webhook_url=webhook_url,
                    secret=self.config.dingtalk_secret if self.config.dingtalk_secret else None,
                    title='处理完成',
                    text='✅ 指令已处理完成'
                )
            
            # 更新对话历史（只保留最近5轮对话）
            conversation_history.append({"role": "user", "content": user_message})
            conversation_history.append({"role": "assistant", "content": full_response})
            if len(conversation_history) > 10:  # 保留最近5轮（每轮2条消息）
                conversation_history = conversation_history[-10:]
            self.conversation_history[sender_id] = conversation_history
            
        except Exception as e:
            logger.error(f"处理并回复钉钉消息失败: {e}", exc_info=True)
            error_msg = f"❌ 处理失败: {str(e)}"
            send_dingtalk_message(
                webhook_url=webhook_url,
                secret=self.config.dingtalk_secret if self.config.dingtalk_secret else None,
                title='处理失败',
                text=error_msg
            )




