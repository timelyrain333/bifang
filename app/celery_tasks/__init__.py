"""
Celery 异步任务
"""
from app.celery_tasks.hexstrike_tasks import full_hexstrike_scan

__all__ = ['full_hexstrike_scan']
