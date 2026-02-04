"""
Celery应用配置
"""
import os
import logging

logger = logging.getLogger(__name__)

# 尝试导入Celery
try:
    from celery import Celery
    from django.conf import settings
    
    # 设置Django settings模块
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bifang.settings')
    
    app = Celery('bifang')
    CELERY_AVAILABLE = True
except ImportError:
    # Celery未安装时，使用占位符
    CELERY_AVAILABLE = False
    app = None
    logger.warning("Celery未安装，Celery相关功能将不可用")

if CELERY_AVAILABLE:
    # 从Django settings中加载Celery配置
    app.config_from_object('django.conf:settings', namespace='CELERY')
    
    # 自动发现任务
    app.autodiscover_tasks()
    
    # 导入schedulers模块，确保setup_periodic_tasks被注册
    # 注意：这里只是导入模块，实际的setup_periodic_tasks会在Django初始化后通过信号触发
    try:
        import django
        # 确保Django已初始化
        if not django.apps.apps.ready:
            django.setup()
        from app import schedulers  # noqa: F401
        # 确保信号处理器已注册
        logger.info("Celery应用已初始化，定时任务调度器已加载")
    except (ImportError, Exception) as e:
        # 如果Django还没初始化，会在autodiscover_tasks时自动初始化
        logger.warning(f"初始化Django时出错（可能正常）: {str(e)}")
        # 仍然导入schedulers，让信号处理器注册
        try:
            from app import schedulers  # noqa: F401
        except Exception:
            pass
    
    @app.task(bind=True)
    def debug_task(self):
        print(f'Request: {self.request!r}')
else:
    # Celery未安装时的占位符
    def debug_task(self):
        logger.warning("Celery未安装，debug_task不可用")




