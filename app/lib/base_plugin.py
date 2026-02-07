"""
插件基类
所有插件都需要继承此类
"""
import logging
from abc import ABC, abstractmethod


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
    
    @abstractmethod
    def execute(self, *args, **kwargs):
        """
        执行插件逻辑
        
        Returns:
            dict: 执行结果
                - success: bool, 是否成功
                - message: str, 消息
                - data: dict, 返回数据
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







