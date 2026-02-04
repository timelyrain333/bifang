# 任务卡住排查指南

## 问题描述

漏洞采集任务一直卡在执行中，无法正常结束。

## 可能的原因

1. **网络请求超时或失败**
   - 访问 oss-security 邮件列表的网络连接不稳定
   - 网络请求没有正确设置超时或异常处理

2. **AI解析超时**
   - 如果启用了AI解析功能，AI API调用可能超时（5分钟超时）
   - AI API服务不稳定

3. **Celery Worker问题**
   - Celery worker崩溃或重启，导致任务状态没有更新
   - Celery worker资源不足（CPU、内存）

4. **数据库连接问题**
   - 数据库连接中断，导致状态更新失败

5. **任务执行时间过长**
   - 任务执行超过Celery配置的超时时间（30分钟硬超时，25分钟软超时）
   - 任务被强制终止，但状态没有正确更新

6. **插件代码异常**
   - 插件执行过程中抛出未捕获的异常
   - 插件代码中存在死循环或无限等待

## 排查步骤

### 1. 使用诊断工具

运行诊断命令检查卡住的任务：

```bash
# 检查所有卡住的任务（默认超过30分钟）
python manage.py diagnose_stuck_tasks

# 检查特定任务
python manage.py diagnose_stuck_tasks --task-id <任务ID>

# 自定义时间阈值（例如：检查超过60分钟的任务）
python manage.py diagnose_stuck_tasks --minutes 60
```

诊断工具会检查：
- 卡住的执行记录
- Celery worker状态
- 数据库连接
- Redis连接（Celery broker）
- 任务配置

### 2. 检查Celery Worker日志

查看Celery worker的日志，查找错误信息：

```bash
# 如果使用systemd管理
journalctl -u celery-worker -f

# 如果使用supervisor
tail -f /var/log/supervisor/celery-worker.log

# 如果直接运行
tail -f celery-worker.log
```

### 3. 检查任务执行记录

查看数据库中的任务执行记录：

```python
from app.models import TaskExecution, Task
from django.utils import timezone
from datetime import timedelta

# 查找卡住的执行记录
cutoff = timezone.now() - timedelta(minutes=30)
stuck = TaskExecution.objects.filter(status='running', started_at__lt=cutoff)

for execution in stuck:
    print(f"执行ID: {execution.id}")
    print(f"任务: {execution.task.name}")
    print(f"开始时间: {execution.started_at}")
    print(f"执行时长: {timezone.now() - execution.started_at}")
    print(f"错误信息: {execution.error_message}")
    print(f"日志: {execution.logs[-500:]}")  # 最后500字符
    print("-" * 80)
```

### 4. 检查系统资源

检查系统资源使用情况：

```bash
# CPU和内存使用
top

# 磁盘空间
df -h

# 网络连接
netstat -an | grep ESTABLISHED
```

## 修复方法

### 方法1：使用修复命令

运行修复命令，将长时间处于running状态的执行记录标记为失败：

```bash
# 修复所有卡住的执行记录（默认超过30分钟）
python manage.py fix_stuck_executions

# 自定义时间阈值
python manage.py fix_stuck_executions --minutes 60

# 先查看将要修复的记录（不实际修改）
python manage.py fix_stuck_executions --dry-run
```

### 方法2：手动修复

如果需要手动修复，可以通过Django shell：

```python
from app.models import TaskExecution, Task
from django.utils import timezone
from datetime import timedelta

# 查找卡住的执行记录
cutoff = timezone.now() - timedelta(minutes=30)
stuck = TaskExecution.objects.filter(status='running', started_at__lt=cutoff)

for execution in stuck:
    # 标记执行记录为失败
    execution.status = 'failed'
    execution.finished_at = timezone.now()
    execution.error_message = '执行超时（超过30分钟未更新状态）'
    execution.save()
    
    # 如果任务状态也是running，更新为failed
    if execution.task.status == 'running':
        execution.task.status = 'failed'
        execution.task.save()
```

### 方法3：重启Celery Worker

如果Celery worker出现问题，重启worker：

```bash
# 停止worker
pkill -f 'celery.*worker'

# 启动worker（根据你的启动方式）
# 如果使用脚本
./start_celery.sh

# 如果使用systemd
systemctl restart celery-worker

# 如果使用supervisor
supervisorctl restart celery-worker
```

## 预防措施

### 1. 增强异常处理

代码已经增强了异常处理：
- 网络请求添加了超时和异常处理
- 插件执行添加了异常捕获
- 任务执行添加了状态更新保护

### 2. 监控任务执行

建议定期运行诊断命令，及时发现卡住的任务：

```bash
# 添加到crontab，每小时检查一次
0 * * * * cd /path/to/project && python manage.py diagnose_stuck_tasks --minutes 30
```

### 3. 设置合理的超时时间

根据任务类型设置合理的超时时间：
- Celery任务超时：30分钟（硬超时），25分钟（软超时）
- 网络请求超时：30秒
- AI解析超时：5分钟

### 4. 监控系统资源

确保系统有足够的资源：
- CPU使用率 < 80%
- 内存使用率 < 80%
- 磁盘空间充足

### 5. 检查网络连接

确保网络连接稳定：
- 能够正常访问 oss-security 邮件列表
- AI API服务正常（如果启用）

## 常见问题

### Q: 任务一直显示"执行中"，但实际已经完成

A: 可能是状态更新失败。运行修复命令或手动更新状态。

### Q: 任务执行时间很长，但最终能完成

A: 检查任务配置，可能需要：
- 减少采集范围（max_days参数）
- 检查网络连接速度
- 如果启用AI解析，检查AI API响应速度

### Q: Celery worker频繁崩溃

A: 检查：
- 系统资源是否充足
- Celery配置是否正确
- 是否有内存泄漏

### Q: 网络请求经常超时

A: 检查：
- 网络连接是否稳定
- 是否可以正常访问目标网站
- 考虑增加重试机制

## 相关文件

- 诊断工具：`app/management/commands/diagnose_stuck_tasks.py`
- 修复工具：`app/management/commands/fix_stuck_executions.py`
- 任务执行：`app/tasks.py`
- 漏洞采集插件：`app/plugins/collect_oss_security.py`

## 更新日志

- 2026-01-23: 添加诊断工具和增强异常处理
- 改进了网络请求的异常处理
- 增强了任务执行的错误处理和状态更新保护
