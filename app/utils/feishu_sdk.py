"""
飞书SDK消息发送工具
使用飞书SDK API发送消息（企业自建应用，不需要webhook）
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

try:
    import lark_oapi as lark
    HAS_LARK_SDK = True
except ImportError:
    HAS_LARK_SDK = False
    logger.warning("飞书SDK未安装，请运行: pip install lark-oapi")


def send_feishu_message_by_api(
    app_id: str,
    app_secret: str,
    receive_id: str,
    receive_id_type: str = "open_id",
    title: str = "",
    text: str = "",
    message_type: str = "text"
) -> dict:
    """
    使用飞书SDK API发送消息（企业自建应用，不需要webhook）
    
    Args:
        app_id: 飞书App ID
        app_secret: 飞书App Secret
        receive_id: 接收者ID（open_id或chat_id）
        receive_id_type: 接收者ID类型，"open_id"（用户）或"chat_id"（群聊）
        title: 消息标题
        text: 消息内容
        message_type: 消息类型，"text" 或 "interactive"，默认 "text"
    
    Returns:
        dict: {'success': bool, 'message': str, 'data': dict}
    """
    if not HAS_LARK_SDK:
        return {
            'success': False,
            'message': '飞书SDK未安装',
            'data': {}
        }
    
    try:
        # 创建客户端
        client = lark.Client.builder() \
            .app_id(app_id) \
            .app_secret(app_secret) \
            .build()
        
        # 构建消息内容
        import json
        if message_type == "interactive":
            # 交互式卡片消息
            content_dict = {
                "config": {
                    "wide_screen_mode": True
                },
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": title or "消息通知"
                    },
                    "template": "blue"
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": text
                        }
                    }
                ]
            }
            content = json.dumps(content_dict)
        else:
            # 文本消息 - 需要JSON格式
            content_dict = {"text": text}
            content = json.dumps(content_dict)
        
        # 发送消息
        # 构建请求体
        request_body = lark.im.v1.CreateMessageRequestBody.builder() \
            .receive_id(receive_id) \
            .msg_type(message_type) \
            .content(content) \
            .build()
        
        # 构建请求
        request = lark.im.v1.CreateMessageRequest.builder() \
            .receive_id_type(receive_id_type) \
            .request_body(request_body) \
            .build()
        
        # 发送消息
        resp = client.im.v1.message.create(request)
        
        if resp.success():
            message_id = resp.data.message_id if hasattr(resp.data, 'message_id') else None
            logger.info(f"飞书消息发送成功，消息ID: {message_id}")
            return {
                'success': True,
                'message': '消息发送成功',
                'data': {
                    'message_id': message_id
                }
            }
        else:
            error_msg = f"飞书API返回错误: code={resp.code}, msg={resp.msg}"
            logger.error(error_msg)
            return {
                'success': False,
                'message': error_msg,
                'data': {}
            }
            
    except Exception as e:
        logger.error(f"发送飞书消息失败: {e}", exc_info=True)
        return {
            'success': False,
            'message': f'发送失败: {str(e)}',
            'data': {}
        }


def send_feishu_message_to_chat(
    app_id: str,
    app_secret: str,
    chat_id: str,
    title: str = "",
    text: str = "",
    message_type: str = "text"
) -> dict:
    """
    发送消息到飞书群聊
    
    Args:
        app_id: 飞书App ID
        app_secret: 飞书App Secret
        chat_id: 群聊ID（chat_id）
        title: 消息标题
        text: 消息内容
        message_type: 消息类型，"text" 或 "interactive"
    
    Returns:
        dict: {'success': bool, 'message': str, 'data': dict}
    """
    return send_feishu_message_by_api(
        app_id=app_id,
        app_secret=app_secret,
        receive_id=chat_id,
        receive_id_type="chat_id",
        title=title,
        text=text,
        message_type=message_type
    )


def send_feishu_message_to_user(
    app_id: str,
    app_secret: str,
    open_id: str,
    title: str = "",
    text: str = "",
    message_type: str = "text"
) -> dict:
    """
    发送消息到飞书用户
    
    Args:
        app_id: 飞书App ID
        app_secret: 飞书App Secret
        open_id: 用户Open ID
        title: 消息标题
        text: 消息内容
        message_type: 消息类型，"text" 或 "interactive"
    
    Returns:
        dict: {'success': bool, 'message': str, 'data': dict}
    """
    return send_feishu_message_by_api(
        app_id=app_id,
        app_secret=app_secret,
        receive_id=open_id,
        receive_id_type="open_id",
        title=title,
        text=text,
        message_type=message_type
    )

