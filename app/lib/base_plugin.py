"""
插件基类
所有插件都需要继承此类
"""
import logging
from io import StringIO
from abc import ABC, abstractmethod
from datetime import datetime


class BasePlugin(ABC):
    """插件基类"""

    def __init__(self, config=None):
        """
        初始化插件

        Args:
            config: 插件配置字典
        """
        self.config = config or {}
        self.logger = logging.getLogger(self.__class__.__name__)
        # 创建日志缓冲区
        self.log_buffer = StringIO()
        self._log_handler = None
        self._setup_log_handler()

    def _setup_log_handler(self):
        """设置日志处理器，将日志同时输出到缓冲区"""
        # 创建一个自定义的日志处理器，将日志写入缓冲区
        class BufferHandler(logging.Handler):
            def __init__(self, buffer):
                super().__init__()
                self.buffer = buffer

            def emit(self, record):
                try:
                    # 格式化日志消息
                    timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
                    level = record.levelname
                    message = self.format(record)
                    log_line = f"[{timestamp}] [{level}] {message}\n"
                    self.buffer.write(log_line)
                except Exception:
                    pass

        # 创建并添加处理器
        self._log_handler = BufferHandler(self.log_buffer)
        self._log_handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(self._log_handler)

    def _get_logs(self):
        """获取缓冲区中的日志内容"""
        return self.log_buffer.getvalue()

    @abstractmethod
    def execute(self, *args, **kwargs):
        """
        执行插件逻辑

        Returns:
            dict: 执行结果
                - success: bool, 是否成功
                - message: str, 消息
                - data: dict, 返回数据
                - logs: str, 日志内容（可选）
        """
        pass

    def validate_config(self, required_keys):
        """
        验证配置是否包含必需的键

        Args:
            required_keys: list, 必需的配置键列表

        Returns:
            bool: 验证是否通过

        Raises:
            ValueError: 配置验证失败
        """
        missing_keys = [key for key in required_keys if key not in self.config]
        if missing_keys:
            raise ValueError(f"缺少必需的配置项: {', '.join(missing_keys)}")
        return True

    def log_info(self, message):
        """记录信息日志"""
        self.logger.info(message)

    def log_error(self, message, exc_info=False):
        """记录错误日志"""
        self.logger.error(message, exc_info=exc_info)

    def log_warning(self, message):
        """记录警告日志"""
        self.logger.warning(message)








