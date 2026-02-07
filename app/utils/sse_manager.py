"""
SSE消息管理器
用于管理任务状态更新的实时推送
"""
import json
import logging
from typing import Dict, Any, Optional
from collections import defaultdict
from queue import Queue
import threading

logger = logging.getLogger(__name__)


class SSEManager:
    """SSE消息管理器，使用内存队列存储消息"""
    
    def __init__(self):
        # 为每个用户维护一个消息队列
        # 格式: {user_id: Queue}
        self._queues: Dict[int, Queue] = defaultdict(Queue)
        self._lock = threading.Lock()
    
    def send_task_update(self, user_id: int, task_id: int, task_data: Dict[str, Any]):
        """
        发送任务状态更新
        
        Args:
            user_id: 用户ID
            task_id: 任务ID
            task_data: 任务数据（包含status等字段）
        """
        try:
            message = {
                'type': 'task_update',
                'task_id': task_id,
                'data': task_data
            }
            
            message_json = json.dumps(message, ensure_ascii=False)
            
            with self._lock:
                queue = self._queues[user_id]
                queue.put(message_json)
                queue_size = queue.qsize()
            
            logger.info(f'已发送任务更新消息到队列: user_id={user_id}, task_id={task_id}, status={task_data.get("status")}, 队列大小={queue_size}')
        except Exception as e:
            logger.error(f'发送任务更新消息失败: {e}', exc_info=True)
    
    def get_message(self, user_id: int, timeout: float = 30.0) -> Optional[str]:
        """
        获取用户的消息（阻塞等待）
        
        Args:
            user_id: 用户ID
            timeout: 超时时间（秒）
            
        Returns:
            消息JSON字符串，如果超时返回心跳消息
        """
        try:
            with self._lock:
                queue = self._queues[user_id]
            
            # 先检查队列大小
            queue_size = queue.qsize()
            if queue_size > 0:
                logger.info(f'队列中有 {queue_size} 条消息等待处理: user_id={user_id}')
            
            # 先尝试非阻塞获取，如果有消息立即返回
            try:
                message = queue.get_nowait()
                logger.info(f'从队列立即获取消息: user_id={user_id}, message={message[:200] if message else None}, 剩余队列大小={queue.qsize()}')
                return message
            except:
                # 队列为空，使用超时等待
                try:
                    message = queue.get(timeout=timeout)
                    logger.info(f'从队列超时获取消息: user_id={user_id}, message={message[:200] if message else None}')
                    return message
                except:
                    # 超时，返回心跳消息
                    logger.debug(f'队列超时，返回心跳: user_id={user_id}, 队列大小={queue.qsize()}')
                    return json.dumps({'type': 'heartbeat'}, ensure_ascii=False)
        except Exception as e:
            logger.error(f'获取消息失败: {e}', exc_info=True)
            return json.dumps({'type': 'heartbeat'}, ensure_ascii=False)
    
    def clear_queue(self, user_id: int):
        """清空用户的消息队列"""
        try:
            with self._lock:
                if user_id in self._queues:
                    queue = self._queues[user_id]
                    while not queue.empty():
                        try:
                            queue.get_nowait()
                        except:
                            break
        except Exception as e:
            logger.error(f'清空队列失败: {e}', exc_info=True)


# 全局SSE管理器实例
sse_manager = SSEManager()


