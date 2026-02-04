"""
飞书长连接服务
使用飞书SDK建立WebSocket长连接，接收事件订阅
"""
import logging
import threading
import time
from typing import Dict, Any, Optional
from django.db.models import Q
from app.models import AliyunConfig
from app.services.secops_agent import SecOpsAgent
from app.utils.feishu import send_feishu_message
from app.utils.feishu_sdk import send_feishu_message_to_chat, send_feishu_message_to_user

logger = logging.getLogger(__name__)

try:
    import lark_oapi as lark
    # P2ImMessageReceiveV1 类型用于类型注解，实际使用时通过事件处理器接收
    HAS_LARK_SDK = True
except ImportError as e:
    HAS_LARK_SDK = False
    logger.warning(f"飞书SDK未安装或导入失败: {e}，请运行: pip install lark-oapi")


class FeishuLongConnectionService:
    """飞书长连接服务"""
    
    def __init__(self, config_id: int):
        """
        初始化飞书长连接服务
        
        Args:
            config_id: AliyunConfig的ID（包含飞书和AI配置）
        """
        if not HAS_LARK_SDK:
            raise ImportError("飞书SDK未安装，请运行: pip install larksuite-oapi")
        
        self.config = AliyunConfig.objects.get(id=config_id)
        self.conversation_history = {}  # 存储每个用户的对话历史 {user_id: [messages]}
        self.ws_client = None
        self.is_running = False
        self.thread = None
        self.processing_messages = set()  # 正在处理的消息ID集合，用于去重
        
        # 检查配置
        if not self.config.feishu_app_id or not self.config.feishu_app_secret:
            raise ValueError("飞书App ID和App Secret未配置")
        
        # 获取关联的AI配置（优先使用关联的配置，如果没有则使用当前配置的AI设置）
        if self.config.qianwen_config:
            # 使用关联的AI配置
            self.ai_config = self.config.qianwen_config
            logger.info(f"使用关联的AI配置: {self.ai_config.name} (ID: {self.ai_config.id})")
        elif self.config.qianwen_enabled and self.config.qianwen_api_key:
            # 使用当前配置的AI设置
            self.ai_config = self.config
            logger.info(f"使用当前配置的AI设置: {self.config.name} (ID: {self.config.id})")
        else:
            # 没有可用的AI配置
            logger.warning(f"配置 {config_id} 未关联AI配置且未启用AI，智能体功能将不可用")
            self.ai_config = None
    
    def _create_ws_client(self):
        """创建飞书WebSocket客户端"""
        # 定义事件处理函数
        def do_p2_im_message_receive_v1(data) -> None:
            """处理接收消息v2.0事件"""
            try:
                logger.info(f"收到消息事件: {data}")
                # 调用消息处理方法
                self._handle_p2_message(data)
            except Exception as e:
                logger.error(f"处理消息事件失败: {e}", exc_info=True)
        
        # 创建事件处理器
        event_handler = lark.EventDispatcherHandler.builder("", "") \
            .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1) \
            .build()
        
        # 创建WebSocket客户端
        ws_client = lark.ws.Client(
            self.config.feishu_app_id,
            self.config.feishu_app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.DEBUG
        )
        
        return ws_client
    
    def _handle_p2_message(self, data):
        """
        处理接收到的消息事件（v2.0版本）
        
        Args:
            data: P2ImMessageReceiveV1事件数据
        """
        try:
            logger.info(f"收到飞书消息事件: {data}")
            
            # 获取事件数据
            event = data.event
            message = event.message
            
            # 获取消息类型
            message_type = message.message_type
            
            if message_type != "text":
                logger.warning(f"不支持的消息类型: {message_type}")
                return
            
            # 解析消息内容
            content = message.content
            if isinstance(content, str):
                try:
                    import json
                    content_obj = json.loads(content)
                    text_content = content_obj.get('text', content)
                except:
                    text_content = content
            elif isinstance(content, dict):
                text_content = content.get('text', '')
            else:
                text_content = str(content) if content else ''
            
            # 移除@机器人的部分（包括 @_user_1 这种格式）
            text_content = text_content.replace('@SecOps智能体', '').replace('@机器人', '').replace('@SecOps', '').strip()
            # 移除 @_user_1 格式的@（飞书SDK中的格式）
            import re
            text_content = re.sub(r'@_user_\d+\s*', '', text_content).strip()
            
            if not text_content:
                logger.warning("收到空消息")
                return
            
            # 获取发送者信息
            sender = event.sender
            sender_id = sender.sender_id.open_id if hasattr(sender.sender_id, 'open_id') else sender.sender_id.user_id if hasattr(sender.sender_id, 'user_id') else 'unknown'
            
            # 获取群聊ID（如果是在群聊中）
            chat_id = message.chat_id if hasattr(message, 'chat_id') else None
            
            logger.info(f"解析消息内容: {text_content[:100]}..., 发送者ID: {sender_id}, 群聊ID: {chat_id}")
            
            # 检查消息是否正在处理（去重）
            if message.message_id in self.processing_messages:
                logger.warning(f"消息 {message.message_id} 正在处理中，跳过重复处理")
                return
            
            # 标记消息为正在处理
            self.processing_messages.add(message.message_id)
            
            # 在新线程中处理消息并发送回复（避免阻塞）
            thread = threading.Thread(
                target=self._process_and_reply,
                args=(text_content, sender_id, message.message_id, chat_id),
                daemon=True
            )
            thread.start()
            
        except Exception as e:
            logger.error(f"处理飞书消息事件失败: {e}", exc_info=True)
    
    def _process_and_reply(self, user_message: str, sender_id: str, message_id: str, chat_id: str = None):
        """
        处理消息并发送回复
        
        Args:
            user_message: 用户消息
            sender_id: 发送者ID
            message_id: 消息ID
            chat_id: 群聊ID（如果是在群聊中）
        """
        try:
            logger.info(f"开始处理用户消息: {user_message[:100]}..., 发送者: {sender_id}, 消息ID: {message_id}")
            
            # 获取或初始化对话历史
            if sender_id not in self.conversation_history:
                self.conversation_history[sender_id] = []
            
            conversation_history = self.conversation_history[sender_id]
            
            # 检查AI配置（每次处理消息时重新从数据库加载，确保使用最新配置）
            # 重新加载配置，因为可能在运行时更新了关联的AI配置
            self.config.refresh_from_db()
            
            # 获取关联的AI配置（优先使用关联的配置，如果没有则使用当前配置的AI设置）
            if self.config.qianwen_config_id:
                # 使用关联的AI配置，需要重新从数据库加载
                try:
                    ai_config = AliyunConfig.objects.get(id=self.config.qianwen_config_id)
                    logger.info(f"使用关联的AI配置: {ai_config.name} (ID: {ai_config.id}), enabled={ai_config.qianwen_enabled}, has_key={bool(ai_config.qianwen_api_key)}")
                except AliyunConfig.DoesNotExist:
                    logger.warning(f"关联的AI配置 (ID: {self.config.qianwen_config_id}) 不存在")
                    ai_config = None
            elif self.config.qianwen_enabled and self.config.qianwen_api_key:
                # 使用当前配置的AI设置
                ai_config = self.config
                logger.info(f"使用当前配置的AI设置: {self.config.name} (ID: {self.config.id})")
            else:
                ai_config = None
                logger.warning(f"配置 {self.config.id} 未关联AI配置且未启用AI")
            
            if not ai_config or not ai_config.qianwen_enabled or not ai_config.qianwen_api_key:
                logger.warning(f"未找到可用的AI配置: ai_config={ai_config is not None}, enabled={ai_config.qianwen_enabled if ai_config else False}, has_key={bool(ai_config.qianwen_api_key) if ai_config else False}")
                # 优先使用SDK API发送消息，如果没有chat_id则使用webhook
                error_msg = '❌ 未找到可用的通义千问配置，请先在系统配置中配置通义千问API'
                if chat_id:
                    send_feishu_message_to_chat(
                        app_id=self.config.feishu_app_id,
                        app_secret=self.config.feishu_app_secret,
                        chat_id=chat_id,
                        title='配置错误',
                        text=error_msg
                    )
                elif self.config.feishu_webhook:
                    send_feishu_message(
                        webhook_url=self.config.feishu_webhook,
                        secret=self.config.feishu_secret if self.config.feishu_secret else None,
                        title='配置错误',
                        text=error_msg
                    )
                return
            
            # 创建智能体实例（使用找到的AI配置）
            logger.info(f"创建SecOps智能体实例，使用AI配置: {ai_config.name} (ID: {ai_config.id})，模型: {ai_config.qianwen_model or 'qwen-plus'}")
            agent = SecOpsAgent(
                api_key=ai_config.qianwen_api_key,
                api_base=ai_config.qianwen_api_base or 'https://dashscope.aliyuncs.com/compatible-mode/v1',
                model=ai_config.qianwen_model or 'qwen-plus'
            )
            
            # 收集所有响应内容
            full_response = ""
            response_chunks = []
            current_chunk = ""
            chunk_size = 3000  # 飞书消息建议不超过4000字符，我们使用3000
            
            # 先发送一个"正在处理"的提示消息，让用户知道系统正在工作
            processing_msg = "⏳ 正在处理您的请求，请稍候..."
            logger.info(f"准备发送处理中提示消息...")
            try:
                if chat_id:
                    result = send_feishu_message_to_chat(
                        app_id=self.config.feishu_app_id,
                        app_secret=self.config.feishu_app_secret,
                        chat_id=chat_id,
                        title='处理中',
                        text=processing_msg,
                        message_type="interactive"  # 使用交互式卡片，更醒目
                    )
                    logger.info(f"发送处理中提示消息结果: {result}")
                    if not result.get('success'):
                        logger.warning(f"发送处理中提示消息失败: {result.get('message')}")
                elif self.config.feishu_webhook:
                    result = send_feishu_message(
                        webhook_url=self.config.feishu_webhook,
                        secret=self.config.feishu_secret if self.config.feishu_secret else None,
                        title='处理中',
                        text=processing_msg
                    )
                    logger.info(f"发送处理中提示消息结果: {result}")
                    if not result.get('success'):
                        logger.warning(f"发送处理中提示消息失败: {result.get('message')}")
                else:
                    logger.warning("未配置chat_id或webhook，无法发送处理中提示消息")
            except Exception as e:
                logger.error(f"发送处理中提示消息失败: {e}", exc_info=True)
            
            logger.info(f"开始调用智能体处理消息...")
            
            # 调用智能体（流式返回）
            chunk_count = 0
            # 传入当前飞书配置所属用户，确保智能体创建的任务能正确写入created_by
            try:
                logger.debug(f"开始迭代智能体响应...")
                for chunk in agent.chat(user_message, conversation_history, self.config.user):
                    chunk_count += 1
                    full_response += chunk
                    current_chunk += chunk
                    
                    # 如果当前块达到一定大小，准备发送
                    if len(current_chunk) >= chunk_size:
                        response_chunks.append(current_chunk)
                        current_chunk = ""
                    
                    # 每100个chunk记录一次进度
                    if chunk_count % 100 == 0:
                        logger.info(f"已收到 {chunk_count} 个chunk，当前响应长度: {len(full_response)}")
                
                logger.info(f"智能体返回完成，共收到 {chunk_count} 个chunk，总长度: {len(full_response)}")
            except Exception as agent_error:
                logger.error(f"智能体处理消息时发生异常: {agent_error}", exc_info=True)
                # 如果智能体处理失败，至少返回错误信息
                if not full_response:
                    full_response = f"❌ 智能体处理失败: {str(agent_error)}\n\n请检查日志文件 logs/bifang.log 获取详细错误信息。"
                    response_chunks = [full_response]
                # 确保即使有部分响应也记录错误
                logger.error(f"智能体处理异常，已收到 {chunk_count} 个chunk，响应长度: {len(full_response)}")
            
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
                    
                    # 优先使用SDK API发送消息（企业自建应用）
                    if chat_id:
                        result = send_feishu_message_to_chat(
                            app_id=self.config.feishu_app_id,
                            app_secret=self.config.feishu_app_secret,
                            chat_id=chat_id,
                            title=title,
                            text=text,
                            message_type="interactive"
                        )
                    elif self.config.feishu_webhook:
                        # 如果没有chat_id，使用webhook（自定义机器人）
                        result = send_feishu_message(
                            webhook_url=self.config.feishu_webhook,
                            secret=self.config.feishu_secret if self.config.feishu_secret else None,
                            title=title,
                            text=text
                        )
                    else:
                        logger.warning("未配置群聊ID或Webhook，无法发送回复消息")
                        result = {'success': False, 'message': '未配置发送方式'}
                    
                    logger.info(f"第 {idx + 1} 条消息发送结果: {result}")
            else:
                # 如果没有响应，发送错误消息
                logger.warning("智能体未返回任何响应")
                if chat_id:
                    result = send_feishu_message_to_chat(
                        app_id=self.config.feishu_app_id,
                        app_secret=self.config.feishu_app_secret,
                        chat_id=chat_id,
                        title='处理完成',
                        text='✅ 指令已处理完成'
                    )
                elif self.config.feishu_webhook:
                    result = send_feishu_message(
                        webhook_url=self.config.feishu_webhook,
                        secret=self.config.feishu_secret if self.config.feishu_secret else None,
                        title='处理完成',
                        text='✅ 指令已处理完成'
                    )
                else:
                    result = {'success': False, 'message': '未配置发送方式'}
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
                if chat_id:
                    result = send_feishu_message_to_chat(
                        app_id=self.config.feishu_app_id,
                        app_secret=self.config.feishu_app_secret,
                        chat_id=chat_id,
                        title='处理失败',
                        text=error_msg
                    )
                elif self.config.feishu_webhook:
                    result = send_feishu_message(
                        webhook_url=self.config.feishu_webhook,
                        secret=self.config.feishu_secret if self.config.feishu_secret else None,
                        title='处理失败',
                        text=error_msg
                    )
                else:
                    logger.warning("未配置发送方式，无法发送错误消息")
            except Exception as send_error:
                logger.error(f"发送错误消息也失败: {send_error}", exc_info=True)
        finally:
            # 处理完成后，从正在处理的集合中移除（延迟5秒，避免重复消息）
            import time
            time.sleep(5)  # 等待5秒，确保消息处理完成
            if message_id in self.processing_messages:
                self.processing_messages.remove(message_id)
                logger.debug(f"消息 {message_id} 处理完成，已从处理队列中移除")
    
    def start(self):
        """启动长连接服务"""
        if self.is_running:
            logger.warning("长连接服务已在运行")
            return
        
        try:
            # 创建WebSocket客户端
            self.ws_client = self._create_ws_client()
            logger.info("已创建WebSocket客户端")
            
            # 在新线程中启动长连接
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            
            logger.info(f"飞书长连接服务已启动，配置ID: {self.config.id}")
            
        except Exception as e:
            logger.error(f"启动飞书长连接服务失败: {e}", exc_info=True)
            raise
    
    def _run(self):
        """运行长连接服务"""
        self.is_running = True
        try:
            # 启动WebSocket客户端（建立长连接）
            logger.info("正在建立飞书WebSocket长连接...")
            # start()方法会阻塞，直到连接建立
            self.ws_client.start()
            logger.info("飞书WebSocket长连接已建立")
            
        except Exception as e:
            logger.error(f"飞书长连接服务运行失败: {e}", exc_info=True)
            self.is_running = False
        finally:
            logger.info("飞书长连接服务已停止")
    
    def stop(self):
        """停止长连接服务"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.ws_client:
            try:
                # 停止WebSocket客户端
                if hasattr(self.ws_client, 'stop'):
                    self.ws_client.stop()
                elif hasattr(self.ws_client, 'close'):
                    self.ws_client.close()
            except Exception as e:
                logger.warning(f"停止WebSocket客户端失败: {e}")
        
        logger.info("飞书长连接服务已停止")
    
    def is_connected(self):
        """检查连接状态"""
        return self.is_running and self.ws_client is not None


# 全局服务实例管理
_services = {}
_service_lock = threading.Lock()


def get_or_create_service(config_id: int) -> FeishuLongConnectionService:
    """获取或创建长连接服务实例"""
    with _service_lock:
        if config_id not in _services:
            _services[config_id] = FeishuLongConnectionService(config_id)
        return _services[config_id]


def start_service(config_id: int):
    """启动指定配置的长连接服务"""
    service = get_or_create_service(config_id)
    if not service.is_running:
        service.start()
    return service


def stop_service(config_id: int):
    """停止指定配置的长连接服务"""
    with _service_lock:
        if config_id in _services:
            _services[config_id].stop()
            del _services[config_id]


def stop_all_services():
    """停止所有长连接服务"""
    with _service_lock:
        for config_id, service in list(_services.items()):
            service.stop()
        _services.clear()

