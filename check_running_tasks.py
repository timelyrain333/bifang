#!/usr/bin/env python3
"""检查正在执行的任务"""
import os
import sys
import django

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bifang.settings')
django.setup()

from app.models import TaskExecution, Task
from django.utils import timezone
from datetime import timedelta

print("=" * 80)
print("任务执行状态诊断")
print("=" * 80)

now = timezone.now()

# 1. 检查所有正在执行的任务
print("\n1. 正在执行的任务 (Task.status = 'running'):")
print("-" * 80)
running_tasks = Task.objects.filter(status='running')
if running_tasks.exists():
    for task in running_tasks:
        print(f"  任务ID: {task.id}")
        print(f"  任务名称: {task.name}")
        print(f"  插件: {task.plugin.name}")
        print(f"  最后运行时间: {task.last_run_time}")
        print()
else:
    print("  ✓ 没有正在执行的任务")

# 2. 检查所有正在执行的执行记录
print("\n2. 正在执行的执行记录 (TaskExecution.status = 'running'):")
print("-" * 80)
running_executions = TaskExecution.objects.filter(status='running').order_by('-started_at')
if running_executions.exists():
    for execution in running_executions:
        duration = (now - execution.started_at).total_seconds()
        duration_minutes = duration / 60
        duration_hours = duration / 3600
        
        print(f"  执行记录ID: {execution.id}")
        print(f"  任务: {execution.task.name} (ID: {execution.task.id})")
        print(f"  开始时间: {execution.started_at}")
        print(f"  执行时长: {duration_minutes:.2f} 分钟 ({duration_hours:.2f} 小时)")
        
        # 检查是否超过30分钟
        if duration_minutes > 30:
            print(f"  ⚠️  警告: 已执行超过30分钟，可能已卡住！")
        
        # 检查任务状态是否一致
        if execution.task.status != 'running':
            print(f"  ⚠️  警告: 任务状态为 '{execution.task.status}'，与执行记录状态不一致！")
        
        print()
else:
    print("  ✓ 没有正在执行的执行记录")

# 3. 检查最近1小时的执行记录
print("\n3. 最近1小时的执行记录:")
print("-" * 80)
one_hour_ago = now - timedelta(hours=1)
recent_executions = TaskExecution.objects.filter(
    started_at__gte=one_hour_ago
).order_by('-started_at')[:10]

if recent_executions.exists():
    for execution in recent_executions:
        duration_str = ""
        if execution.finished_at:
            duration = (execution.finished_at - execution.started_at).total_seconds() / 60
            duration_str = f" (耗时: {duration:.2f} 分钟)"
        else:
            duration = (now - execution.started_at).total_seconds() / 60
            duration_str = f" (已运行: {duration:.2f} 分钟)"
        
        print(f"  [{execution.status.upper()}] {execution.task.name} - {execution.started_at}{duration_str}")
        if execution.error_message:
            print(f"    错误: {execution.error_message[:100]}")
else:
    print("  最近1小时内没有执行记录")

# 4. 检查可能卡住的任务（超过30分钟）
print("\n4. 可能卡住的任务（超过30分钟）:")
print("-" * 80)
cutoff_time = now - timedelta(minutes=30)
stuck_executions = TaskExecution.objects.filter(
    status='running',
    started_at__lt=cutoff_time
)

if stuck_executions.exists():
    print(f"  找到 {stuck_executions.count()} 个可能卡住的任务:")
    for execution in stuck_executions:
        duration = (now - execution.started_at).total_seconds() / 60
        print(f"    - 任务: {execution.task.name} (执行ID: {execution.id})")
        print(f"      已运行: {duration:.2f} 分钟")
        print(f"      开始时间: {execution.started_at}")
else:
    print("  ✓ 没有发现卡住的任务")

# 5. 检查Celery Worker进程
print("\n5. Celery Worker 进程检查:")
print("-" * 80)
import subprocess
try:
    result = subprocess.run(
        ['ps', 'aux'], 
        capture_output=True, 
        text=True, 
        timeout=5
    )
    celery_processes = [line for line in result.stdout.split('\n') if 'celery' in line.lower() and 'worker' in line.lower()]
    if celery_processes:
        print("  找到 Celery Worker 进程:")
        for proc in celery_processes[:3]:  # 只显示前3个
            print(f"    {proc[:100]}")
    else:
        print("  ⚠️  未找到 Celery Worker 进程，任务可能无法执行")
except Exception as e:
    print(f"  ⚠️  无法检查进程: {e}")

print("\n" + "=" * 80)
print("诊断完成")
print("=" * 80)
print("\n建议:")
print("1. 如果有卡住的任务，运行: python manage.py fix_stuck_executions")
print("2. 检查 Celery Worker 日志: tail -f logs/celery_worker.log")
print("3. 检查 Django 日志: tail -f logs/django.log")


