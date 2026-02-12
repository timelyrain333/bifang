"""
钉钉AI卡片流式更新服务
实现打字机效果的流式AI卡片回复

参考文档：
- 打字机效果流式AI卡片: https://open.dingtalk.com/document/dingstart/typewriter-effect-streaming-ai-card
- AI卡片流式更新: https://open.dingtalk.com/document/development/api-streamingupdate
- 创建并投放卡片: https://open.dingtalk.com/document/development/create-and-deliver-cards
"""
import json
import logging
import time
import uuid
import threading
import requests
from typing import Dict, Any, Optional, Generator

logger = logging.getLogger(__name__)


class DingTalkAICardStreamer:
    """钉钉AI卡片流式更新器"""

    def __init__(self, client_id: str, client_secret: str, access_token: str = None):
        """
        初始化AI卡片流式更新器

        Args:
            client_id: 钉钉应用的Client ID (AppKey)
            client_secret: 钉钉应用的Client Secret (AppSecret)
            access_token: 可选的access_token，如果不提供将自动获取
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self._access_token = access_token
        self._token_expires_at = 0
        self.api_base = "https://api.dingtalk.com/v1.0"

    def get_access_token(self) -> str:
        """
        获取AccessToken

        Returns:
            str: AccessToken
        """
        # 检查缓存是否有效（提前5分钟刷新）
        if self._access_token and time.time() < self._token_expires_at - 300:
            return self._access_token

        # 获取新的AccessToken
        try:
            # 使用钉钉官方的获取AccessToken接口（企业内部应用）
            url = "https://oapi.dingtalk.com/gettoken"
            params = {
                'appkey': self.client_id,
                'appsecret': self.client_secret
            }
            response = requests.get(url, params=params, timeout=10)
            result = response.json()

            if result.get('errcode') == 0 and result.get('access_token'):
                self._access_token = result['access_token']
                # AccessToken有效期通常为2小时（7200秒）
                self._token_expires_at = time.time() + 7200
                logger.info("成功获取AccessToken")
                return self._access_token
            else:
                logger.error(f"获取AccessToken失败: {result}")
                raise Exception(f"获取AccessToken失败: {result}")
        except Exception as e:
            logger.error(f"获取AccessToken异常: {e}", exc_info=True)
            raise

    def send_ai_card(
        self,
        card_template_id: str,
        open_conversation_id: str,
        card_data: Dict[str, Any],
        user_id: str = None,
        conversation_type: str = "2"
    ) -> Dict[str, Any]:
        """
        发送AI卡片到群聊或单聊

        Args:
            card_template_id: 卡片模板ID（在钉钉开发者后台创建）
            open_conversation_id: 群会话ID（群聊）或用户ID（单聊）
            card_data: 卡片数据（JSON对象）
            user_id: 用户ID（单聊时需要）
            conversation_type: 会话类型，"1"=单聊，"2"=群聊

        Returns:
            Dict: 包含processQueryKey的响应数据
        """
        try:
            access_token = self.get_access_token()

            # 生成唯一的cardBizId
            card_biz_id = str(uuid.uuid4())

            # 使用正确的API路径：发送互动卡片
            url = f"{self.api_base}/im/chat/sendInteractiveCard"
            headers = {
                'Content-Type': 'application/json',
                'x-acs-dingtalk-access-token': access_token
            }

            # 构建请求体（参考钉钉官方文档格式）
            payload = {
                "robotCode": self.client_id,
                "openConversationId": open_conversation_id,
                "cardTemplateId": card_template_id,
                "cardData": card_data,
                "callbackType": "STREAM",
                "conversationId": open_conversation_id
            }

            response = requests.post(url, headers=headers, json=payload, timeout=10)
            result = response.json()

            logger.info(f"发送AI卡片响应: status={response.status_code}, result={result}")

            if result.get('processQueryKey') or response.status_code == 200:
                return {
                    'success': True,
                    'cardBizId': card_biz_id,
                    'processQueryKey': result.get('processQueryKey'),
                    'data': result
                }
            else:
                error_msg = result.get('message', '未知错误')
                logger.error(f"发送AI卡片失败: {error_msg}, 完整响应: {result}")
                return {
                    'success': False,
                    'message': error_msg,
                    'data': result
                }

        except Exception as e:
            logger.error(f"发送AI卡片异常: {e}", exc_info=True)
            return {
                'success': False,
                'message': str(e)
            }

    def update_ai_card(
        self,
        card_biz_id: str,
        card_data: Dict[str, Any],
        process_query_key: str = None
    ) -> bool:
        """
        更新AI卡片内容

        Args:
            card_biz_id: 卡片业务ID（发送卡片时返回的）
            card_data: 更新的卡片数据
            process_query_key: 进程查询键（可选，如果使用流式更新接口）

        Returns:
            bool: 是否更新成功
        """
        try:
            access_token = self.get_access_token()

            url = f"{self.api_base}/im/robot/interactiveCard/update"
            headers = {
                'Content-Type': 'application/json',
                'x-acs-dingtalk-access-token': access_token
            }

            payload = {
                "cardBizId": card_biz_id,
                "cardData": json.dumps(card_data)
            }

            # 如果提供了processQueryKey，使用AI流式更新接口
            if process_query_key:
                payload["processQueryKey"] = process_query_key

            response = requests.post(url, headers=headers, json=payload, timeout=10)
            result = response.json()

            # 检查响应
            if result.get('errcode', -1) == 0 or response.status_code == 200:
                logger.debug(f"更新AI卡片成功: cardBizId={card_biz_id}")
                return True
            else:
                logger.warning(f"更新AI卡片失败: {result}")
                return False

        except Exception as e:
            logger.error(f"更新AI卡片异常: {e}", exc_info=True)
            return False

    def stream_reply(
        self,
        card_template_id: str,
        open_conversation_id: str,
        text_stream: Generator[str, None, None],
        user_id: str = None,
        conversation_type: str = "2",
        update_interval: float = 0.1
    ) -> bool:
        """
        使用流式文本回复（打字机效果）

        Args:
            card_template_id: 卡片模板ID
            open_conversation_id: 群会话ID
            text_stream: 文本生成器（返回文本片段）
            user_id: 用户ID（单聊时需要）
            conversation_type: 会话类型
            update_interval: 更新间隔（秒）

        Returns:
            bool: 是否成功
        """
        try:
            # 首先发送空卡片
            initial_card_data = {
                "content": {
                    "title": "SecOps智能体",
                    "text": "思考中..."
                }
            }

            result = self.send_ai_card(
                card_template_id=card_template_id,
                open_conversation_id=open_conversation_id,
                card_data=initial_card_data,
                user_id=user_id,
                conversation_type=conversation_type
            )

            if not result.get('success'):
                logger.error(f"发送初始卡片失败: {result.get('message')}")
                return False

            card_biz_id = result['cardBizId']
            process_query_key = result.get('processQueryKey')

            # 流式更新卡片
            full_text = ""
            for chunk in text_stream:
                full_text += chunk
                time.sleep(update_interval)

                # 更新卡片
                card_data = {
                    "content": {
                        "title": "SecOps智能体",
                        "text": full_text
                    }
                }

                self.update_ai_card(
                    card_biz_id=card_biz_id,
                    card_data=card_data,
                    process_query_key=process_query_key
                )

            logger.info(f"流式回复完成: {len(full_text)} 字符")
            return True

        except Exception as e:
            logger.error(f"流式回复异常: {e}", exc_info=True)
            return False


def create_ai_card_template() -> Dict[str, Any]:
    """
    创建一个简单的AI卡片模板数据结构

    这是一个示例模板，实际使用时需要在钉钉开发者后台创建卡片模板

    Returns:
        Dict: 卡片数据结构
    """
    return {
        "config": {
            "autoLayout": True,
            "enableForward": True
        },
        "header": {
            "title": {
                "type": "text",
                "text": "SecOps智能体"
            },
            "logo": "@lALPDfJ6V_FPDmvNAfTNAfQ"
        },
        "contents": [
            {
                "type": "markdown",
                "text": "%s",
                "id": "content_markdown"
            }
        ]
    }


def format_markdown_for_card(text: str) -> str:
    """
    格式化文本为Markdown格式（适用于AI卡片）

    Args:
        text: 原始文本

    Returns:
        str: Markdown格式文本
    """
    # 如果已经是Markdown格式，直接返回
    if text.startswith('#') or '##' in text or '**' in text:
        return text

    # 否则，简单包装成段落
    return f"{text}"
