# 加载Celery应用（如果可用）
try:
    from app.celery_app import app as celery_app
    __all__ = ('celery_app',)
except ImportError:
    # Celery未安装时跳过
    pass
