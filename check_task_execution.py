#!/usr/bin/env python
"""检查任务执行情况"""
import os
import sys
import django

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bifang.settings')
django.setup()

from app.models import TaskExecution
from django.utils import timezone
from datetime import timedelta

now = timezone.now()
one_hour_ago = now - timedelta(hours=1)

# 检查是否有running状态的执行记录
running = TaskExecution.objects.filter(task_id=9, status='running', started_at__gte=one_hour_ago)
print(f'正在执行中的任务数量: {running.count()}')
for e in running:
    duration = (now - e.started_at).total_seconds() / 60
    print(f'  执行ID {e.id}: 已运行 {duration:.1f} 分钟')

executions = list(TaskExecution.objects.filter(
    task_id=9,
    started_at__gte=one_hour_ago
).order_by('started_at'))

print(f'\n过去1小时内的执行记录数量: {len(executions)}')
print(f'\n执行时间间隔分析:')
prev_time = None
for e in executions:
    e_time_local = timezone.localtime(e.started_at)
    if prev_time:
        gap = (e.started_at - prev_time).total_seconds() / 60
        print(f'  {e_time_local.strftime("%H:%M:%S")} - 间隔: {gap:.1f}分钟, 状态: {e.status}')
    else:
        print(f'  {e_time_local.strftime("%H:%M:%S")} - 首次, 状态: {e.status}')
    prev_time = e.started_at

print(f'\n当前时间: {timezone.localtime(now).strftime("%Y-%m-%d %H:%M:%S")}')
if executions:
    last_exec = executions[-1]
    last_time_local = timezone.localtime(last_exec.started_at)
    minutes_ago = (now - last_exec.started_at).total_seconds() / 60
    print(f'最后一次执行: {last_time_local.strftime("%Y-%m-%d %H:%M:%S")} (距今 {minutes_ago:.1f} 分钟)')
    print(f'期望的下次执行时间: {(last_exec.started_at + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")} UTC')
