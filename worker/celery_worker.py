"""
Celery Worker启动脚本
用于在worker目录下启动Celery worker进程
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bifang.settings')

import django
django.setup()

from app.celery_app import app as celery_app

if __name__ == '__main__':
    celery_app.start()








