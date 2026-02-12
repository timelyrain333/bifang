"""
SSE (Server-Sent Events) 管理器
用于实时推送 Agent 执行进度和中间结果
"""
import json
import logging
import redis
from typing import Dict, Any, Optional
from django.conf import settings

logger = logging.getLogger(__name__)


class SSEManager:
    """
    SSE 消息管理器

    功能：
    1. 发布进度更新到 Redis 频道
    2. 支持实时推送 Agent 思考过程
    3. 支持推送工具执行中间结果
    """

    def __init__(self, channel: str):
        """
        初始化 SSE 管理器

        Args:
            channel: 频道名称（如 "user_123", "task_456"）
        """
        self.channel = channel
        self._redis_client = None

    @property
    def redis_client(self):
        """延迟获取 Redis 客户端"""
        if self._redis_client is None:
            try:
                redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
                self._redis_client = redis.from_url(
                    redis_url,
                    decode_responses=True
                )
            except Exception as e:
                logger.error(f"连接 Redis 失败: {e}")
                self._redis_client = None
        return self._redis_client

    def publish(self, data: Dict[str, Any]) -> bool:
        """
        发布消息到 Redis 频道

        Args:
            data: 要发送的数据字典

        Returns:
            bool: 是否发送成功
        """
        if not self.redis_client:
            logger.warning("Redis 客户端未初始化，无法发送 SSE 消息")
            return False

        try:
            message = json.dumps(data, ensure_ascii=False)
            self.redis_client.publish(self.channel, message)
            logger.debug(f"SSE 发送消息到频道 {self.channel}: {message[:100]}")
            return True
        except Exception as e:
            logger.error(f"SSE 发送消息失败: {e}")
            return False

    # ========== 便捷方法 ==========

    def send_progress(self, stage: str, progress: int, message: str) -> bool:
        """发送进度更新"""
        return self.publish({
            "type": "progress",
            "stage": stage,
            "progress": progress,
            "message": message
        })

    def send_tool_start(self, tool_name: str, arguments: Dict = None) -> bool:
        """发送工具开始执行事件"""
        return self.publish({
            "type": "tool_start",
            "tool": tool_name,
            "arguments": arguments or {}
        })

    def send_tool_end(self, tool_name: str, result: Any = None) -> bool:
        """发送工具执行完成事件"""
        return self.publish({
            "type": "tool_end",
            "tool": tool_name,
            "result": str(result) if result else None
        })

    def send_tool_stream(self, tool_name: str, chunk: str) -> bool:
        """发送工具执行流式输出"""
        return self.publish({
            "type": "tool_stream",
            "tool": tool_name,
            "chunk": chunk
        })

    def send_agent_thinking(self, thought: str) -> bool:
        """发送 Agent 思考过程"""
        return self.publish({
            "type": "thinking",
            "content": thought
        })

    def send_error(self, error: str, stage: str = None) -> bool:
        """发送错误消息"""
        data = {"type": "error", "error": error}
        if stage:
            data["stage"] = stage
        return self.publish(data)

    def send_complete(self, result: Dict = None) -> bool:
        """发送完成消息"""
        return self.publish({
            "type": "complete",
            "result": result or {}
        })


class SSEProgress:
    """
    SSE 进度上下文管理器

    用法：
        with SSEProgress("user_123") as progress:
            progress.update("scanning", 50, "正在扫描端口...")
            # ... 执行操作
            progress.update("done", 100, "扫描完成")
    """

    def __init__(self, channel: str):
        self.manager = SSEManager(channel)
        self._stage = None
        self._progress = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.manager.send_error(str(exc_val), self._stage)
        else:
            self.manager.send_complete()

    def update(self, stage: str, progress: int, message: str):
        """更新进度"""
        self._stage = stage
        self._progress = progress
        self.manager.send_progress(stage, progress, message)

    def tool_start(self, tool_name: str, **kwargs):
        """标记工具开始"""
        self.manager.send_tool_start(tool_name, kwargs)

    def tool_end(self, tool_name: str, **kwargs):
        """标记工具结束"""
        self.manager.send_tool_end(tool_name, kwargs.get("result"))

    def tool_stream(self, tool_name: str, chunk: str):
        """流式输出工具结果"""
        self.manager.send_tool_stream(tool_name, chunk)

    def thinking(self, thought: str):
        """发送思考过程"""
        self.manager.send_agent_thinking(thought)


# 向后兼容：导出 sse_manager 作为 SSEManager 的别名
# 这样 `from .utils.sse_manager import sse_manager` 可以工作
sse_manager = SSEManager
