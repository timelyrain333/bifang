from django.apps import AppConfig


class AppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'
    verbose_name = 'Bifang Application'
    
    def ready(self):
        """Django应用就绪时调用"""
        # 导入schedulers模块，确保setup_periodic_tasks被注册
        try:
            from app import schedulers
            # 调用setup_periodic_tasks来加载定时任务
            schedulers.setup_periodic_tasks()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"初始化定时任务失败: {str(e)}")




