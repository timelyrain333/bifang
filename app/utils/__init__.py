"""
Utils package - 模块初始化
"""
# 导入 SSEManager 类
from app.utils.sse_manager import SSEManager

# 为了向后兼容，将 SSEManager 别名为 sse_manager
# 这样 `from .utils.sse_manager import sse_manager` 可以工作
sse_manager = SSEManager

__all__ = ['SSEManager', 'sse_manager']

