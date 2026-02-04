"""
飞书机器人智能体服务
处理飞书机器人的消息，并调用SecOps智能体执行任务

注意：
1. 飞书自定义机器人只能发送消息，不能接收消息
2. 要实现双向交互，需要使用飞书机器人应用（Bot），并配置事件订阅
3. 在飞书开放平台创建机器人应用后，需要：
   - 配置事件订阅，订阅"接收消息"事件
   - 设置请求地址为: https://your-domain.com/api/feishu/bot/
   - 确保配置中包含飞书webhook和通义千问AI配置
"""
import json
import logging
import threading
import re
from typing import Dict, Any, Optional
from django.db.models import Q
from app.models import AliyunConfig
from app.services.secops_agent import SecOpsAgent
from app.utils.feishu import send_feishu_message

logger = logging.getLogger(__name__)


class FeishuAgent:
    """飞书机器人智能体"""
    
    def __init__(self, config_id: int):
        """
        初始化飞书机器人智能体
        
        Args:
            config_id: AliyunConfig的ID（包含飞书和AI配置）
        """
        self.config = AliyunConfig.objects.get(id=config_id)
        self.conversation_history = {}  # 存储每个用户的对话历史 {user_id: [messages]}
    
    def handle_message(self, webhook_url: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理飞书机器人接收到的消息
        
        支持两种消息格式：
        1. 飞书机器人应用（Bot）的消息格式：包含 event 字段
        2. 自定义机器人的消息格式：直接包含消息内容
        
        Args:
            webhook_url: 飞书webhook地址（用于发送回复）
            message_data: 飞书消息数据
        
        Returns:
            Dict: 处理结果
        """
        try:
            logger.info(f"收到飞书消息: {json.dumps(message_data, ensure_ascii=False)[:1000]}")
            
            # 检查是否是飞书机器人应用的消息格式（包含schema和event）
            schema = message_data.get('schema', '')
            header = message_data.get('header', {})
            event_type = header.get('event_type', '')
            
            # 飞书机器人应用（Bot）的消息格式：通常包含 event 字段
            event = message_data.get('event', {})
            message = event.get('message', {}) if event else {}
            
            logger.info(f"消息格式检查: schema={schema}, event_type={event_type}, has_event={bool(event)}, has_message={bool(message)}")
            
            # 如果event为空，可能是自定义机器人的消息格式或其他格式
            if not event and not message:
                logger.warning("未找到event或message字段，尝试直接解析消息内容")
                # 尝试直接解析消息内容
                text_content = message_data.get('text', '') or message_data.get('content', '')
                if isinstance(text_content, dict):
                    text_content = text_content.get('text', '')
            else:
                # 机器人应用的消息格式
                msg_type = message.get('message_type', '')
                logger.info(f"消息类型: {msg_type}")
                
                # 获取消息内容
                if msg_type == 'text':
                    text_content = message.get('content', '')
                    logger.info(f"文本消息content类型: {type(text_content)}, 内容: {str(text_content)[:200]}")
                    # 飞书的content可能是JSON字符串
                    if isinstance(text_content, str):
                        try:
                            content_obj = json.loads(text_content)
                            text_content = content_obj.get('text', text_content)
                            logger.info(f"解析JSON后得到: {text_content[:200]}")
                        except json.JSONDecodeError:
                            # 如果不是JSON，直接使用
                            logger.info("content不是JSON格式，直接使用")
                            pass
                else:
                    # 尝试从其他地方获取文本
                    content = message.get('content', {})
                    logger.info(f"非文本消息，content类型: {type(content)}")
                    if isinstance(content, dict):
                        text_content = content.get('text', '')
                    elif isinstance(content, str):
                        try:
                            content_obj = json.loads(content)
                            text_content = content_obj.get('text', content)
                        except:
                            text_content = content
                    else:
                        text_content = ''
            
            # 确保text_content是字符串
            if not isinstance(text_content, str):
                text_content = str(text_content) if text_content else ''
            
            # 移除@机器人的部分（支持多种@格式）
            text_content = text_content.replace('@SecOps智能体', '').replace('@机器人', '').replace('@SecOps', '').strip()
            
            # 移除可能的HTML标签（如果存在）
            text_content = re.sub(r'<[^>]+>', '', text_content).strip()
            
            if not text_content:
                logger.warning("收到空消息或无法解析的消息内容")
                logger.warning(f"原始消息数据: {json.dumps(message_data, ensure_ascii=False)[:1000]}")
                # 发送提示消息给用户（如果可能）
                try:
                    send_feishu_message(
                        webhook_url=webhook_url,
                        secret=self.config.feishu_secret if self.config.feishu_secret else None,
                        title='消息解析失败',
                        text='❌ 无法解析您的消息内容。\n\n**重要提示**:\n1. 飞书自定义机器人只能发送消息，不能接收消息\n2. 要实现双向交互，请使用飞书机器人应用（Bot）\n3. 需要在飞书开放平台配置事件订阅，订阅"接收消息"事件\n4. 事件订阅地址应设置为: https://your-domain.com/api/feishu/bot/'
                    )
                except Exception as send_error:
                    logger.error(f"发送提示消息失败: {send_error}")
                return {
                    'success': True,
                    'message': '收到空消息'
                }
            
            # 获取发送者信息（如果有）
            sender = event.get('sender', {}) if event else {}
            sender_id = 'unknown'
            if sender:
                sender_id_obj = sender.get('sender_id', {})
                if isinstance(sender_id_obj, dict):
                    sender_id = sender_id_obj.get('open_id') or sender_id_obj.get('user_id') or sender.get('user_id') or 'unknown'
                else:
                    sender_id = sender.get('user_id') or sender.get('open_id') or 'unknown'
            
            logger.info(f"解析消息内容: {text_content[:100]}..., 发送者ID: {sender_id}")
            
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
                
        except Exception as e:
            logger.error(f"处理飞书消息失败: {e}", exc_info=True)
            logger.error(f"消息数据: {json.dumps(message_data, ensure_ascii=False)[:1000]}")
            return {
                'success': False,
                'message': f'处理失败: {str(e)}'
            }
    
    def _process_and_reply(self, webhook_url: str, user_message: str, sender_id: str):
        """
        处理消息并发送回复
        
        Args:
            webhook_url: 飞书webhook地址
            user_message: 用户消息
            sender_id: 发送者ID
        """
        try:
            logger.info(f"开始处理用户消息: {user_message[:100]}..., 发送者: {sender_id}, webhook: {webhook_url[:50]}...")
            
            # 获取或初始化对话历史
            if sender_id not in self.conversation_history:
                self.conversation_history[sender_id] = []
            
            conversation_history = self.conversation_history[sender_id]
            
            # 检查AI配置
            if not self.config.qianwen_enabled or not self.config.qianwen_api_key:
                logger.warning(f"配置 {self.config.id} 未启用AI或缺少API Key")
                error_msg = '❌ 未找到可用的通义千问配置，请先在系统配置中配置通义千问API'
                result = send_feishu_message(
                    webhook_url=webhook_url,
                    secret=self.config.feishu_secret if self.config.feishu_secret else None,
                    title='配置错误',
                    text=error_msg
                )
                logger.info(f"发送配置错误消息结果: {result}")
                return
            
            # 创建智能体实例
            logger.info(f"创建SecOps智能体实例，模型: {self.config.qianwen_model or 'qwen-plus'}")
            agent = SecOpsAgent(
                api_key=self.config.qianwen_api_key,
                api_base=self.config.qianwen_api_base or 'https://dashscope.aliyuncs.com/compatible-mode/v1',
                model=self.config.qianwen_model or 'qwen-plus'
            )
            
            # 收集所有响应内容
            full_response = ""
            response_chunks = []
            current_chunk = ""
            chunk_size = 3000  # 飞书消息建议不超过4000字符，我们使用3000
            
            logger.info(f"开始调用智能体处理消息...")
            # 调用智能体（流式返回）
            chunk_count = 0
            for chunk in agent.chat(user_message, conversation_history, None):
                chunk_count += 1
                full_response += chunk
                current_chunk += chunk
                
                # 如果当前块达到一定大小，准备发送
                if len(current_chunk) >= chunk_size:
                    response_chunks.append(current_chunk)
                    current_chunk = ""
            
            logger.info(f"智能体返回完成，共收到 {chunk_count} 个chunk，总长度: {len(full_response)}")
            
            # 添加最后一块
            if current_chunk:
                response_chunks.append(current_chunk)
            
            # 如果没有响应块，添加完整响应
            if not response_chunks and full_response:
                response_chunks.append(full_response)
            
            # 发送响应（分批发送，避免消息过长）
            if response_chunks:
                logger.info(f"准备发送 {len(response_chunks)} 条消息")
                for idx, chunk in enumerate(response_chunks):
                    title = f"SecOps智能体回复"
                    if len(response_chunks) > 1:
                        title += f" ({idx + 1}/{len(response_chunks)})"
                    
                    # 格式化消息（Markdown）
                    text = f"**您的指令**: {user_message}\n\n---\n\n{chunk}"
                    
                    logger.info(f"发送第 {idx + 1} 条消息，长度: {len(text)}")
                    result = send_feishu_message(
                        webhook_url=webhook_url,
                        secret=self.config.feishu_secret if self.config.feishu_secret else None,
                        title=title,
                        text=text
                    )
                    logger.info(f"第 {idx + 1} 条消息发送结果: {result}")
            else:
                # 如果没有响应，发送错误消息
                logger.warning("智能体未返回任何响应")
                result = send_feishu_message(
                    webhook_url=webhook_url,
                    secret=self.config.feishu_secret if self.config.feishu_secret else None,
                    title='处理完成',
                    text='✅ 指令已处理完成'
                )
                logger.info(f"发送完成消息结果: {result}")
            
            # 更新对话历史（只保留最近5轮对话）
            conversation_history.append({"role": "user", "content": user_message})
            conversation_history.append({"role": "assistant", "content": full_response})
            if len(conversation_history) > 10:  # 保留最近5轮（每轮2条消息）
                conversation_history = conversation_history[-10:]
            self.conversation_history[sender_id] = conversation_history
            
        except Exception as e:
            logger.error(f"处理并回复飞书消息失败: {e}", exc_info=True)
            error_msg = f"❌ 处理失败: {str(e)}"
            try:
                result = send_feishu_message(
                    webhook_url=webhook_url,
                    secret=self.config.feishu_secret if self.config.feishu_secret else None,
                    title='处理失败',
                    text=error_msg
                )
                logger.info(f"发送错误消息结果: {result}")
            except Exception as send_error:
                logger.error(f"发送错误消息也失败: {send_error}", exc_info=True)


