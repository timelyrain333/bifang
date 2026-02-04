"""
诊断卡住的任务
检查任务执行状态、Celery worker状态、数据库连接等
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from app.models import TaskExecution, Task
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '诊断卡住的任务，检查可能的原因'

    def add_arguments(self, parser):
        parser.add_argument(
            '--minutes',
            type=int,
            default=30,
            help='检查超过多少分钟的running状态记录（默认30分钟）'
        )
        parser.add_argument(
            '--task-id',
            type=int,
            default=None,
            help='指定任务ID进行诊断'
        )

    def handle(self, *args, **options):
        minutes = options['minutes']
        task_id = options.get('task_id')
        
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('任务卡住诊断工具'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write('')
        
        # 1. 检查卡住的执行记录
        cutoff_time = timezone.now() - timedelta(minutes=minutes)
        if task_id:
            stuck_executions = TaskExecution.objects.filter(
                task_id=task_id,
                status='running',
                started_at__lt=cutoff_time
            )
        else:
            stuck_executions = TaskExecution.objects.filter(
                status='running',
                started_at__lt=cutoff_time
            )
        
        count = stuck_executions.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS(f'✓ 没有找到超过{minutes}分钟仍为running状态的执行记录'))
        else:
            self.stdout.write(self.style.WARNING(f'⚠ 找到 {count} 条卡住的执行记录（超过{minutes}分钟）：'))
            self.stdout.write('-' * 80)
            
            for execution in stuck_executions:
                duration = timezone.now() - execution.started_at
                duration_minutes = duration.total_seconds() / 60
                
                self.stdout.write(f'\n执行记录ID: {execution.id}')
                self.stdout.write(f'任务: {execution.task.name} (ID: {execution.task.id})')
                self.stdout.write(f'插件: {execution.task.plugin.name}')
                self.stdout.write(f'开始时间: {execution.started_at}')
                self.stdout.write(f'执行时长: {duration_minutes:.2f} 分钟')
                self.stdout.write(f'任务状态: {execution.task.status}')
                
                # 检查执行记录的最后更新时间
                if hasattr(execution, 'updated_at'):
                    self.stdout.write(f'最后更新: {execution.updated_at}')
                
                # 检查是否有错误信息
                if execution.error_message:
                    self.stdout.write(self.style.ERROR(f'错误信息: {execution.error_message[:200]}'))
                
                # 检查日志
                if execution.logs:
                    log_lines = execution.logs.split('\n')
                    last_logs = '\n'.join(log_lines[-5:])  # 最后5行日志
                    self.stdout.write(f'最后日志:\n{last_logs}')
        
        self.stdout.write('')
        self.stdout.write('-' * 80)
        
        # 2. 检查Celery worker状态
        self.stdout.write('\n检查Celery Worker状态...')
        try:
            from celery import current_app
            inspect = current_app.control.inspect()
            
            # 检查活跃的worker
            active_workers = inspect.active()
            if active_workers:
                self.stdout.write(self.style.SUCCESS(f'✓ 找到 {len(active_workers)} 个活跃的Celery worker'))
                for worker_name, tasks in active_workers.items():
                    self.stdout.write(f'  Worker: {worker_name}')
                    if tasks:
                        for task in tasks:
                            task_name = task.get('name', 'unknown')
                            task_id = task.get('id', 'unknown')
                            self.stdout.write(f'    正在执行: {task_name} (ID: {task_id})')
                    else:
                        self.stdout.write(f'    当前无任务执行')
            else:
                self.stdout.write(self.style.WARNING('⚠ 没有找到活跃的Celery worker'))
            
            # 检查注册的任务
            registered = inspect.registered()
            if registered:
                self.stdout.write(f'\n✓ 已注册的任务数量: {sum(len(tasks) for tasks in registered.values())}')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ 检查Celery worker状态失败: {str(e)}'))
            self.stdout.write('  可能原因: Celery未运行或Redis连接失败')
        
        self.stdout.write('')
        self.stdout.write('-' * 80)
        
        # 3. 检查数据库连接
        self.stdout.write('\n检查数据库连接...')
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                if result:
                    self.stdout.write(self.style.SUCCESS('✓ 数据库连接正常'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ 数据库连接失败: {str(e)}'))
        
        self.stdout.write('')
        self.stdout.write('-' * 80)
        
        # 4. 检查Redis连接（Celery broker）
        self.stdout.write('\n检查Redis连接（Celery Broker）...')
        try:
            import redis
            from django.conf import settings
            broker_url = getattr(settings, 'CELERY_BROKER_URL', 'redis://localhost:6379/0')
            
            # 解析Redis URL
            if broker_url.startswith('redis://'):
                import urllib.parse
                parsed = urllib.parse.urlparse(broker_url)
                host = parsed.hostname or 'localhost'
                port = parsed.port or 6379
                db = int(parsed.path.lstrip('/')) if parsed.path else 0
                
                r = redis.Redis(host=host, port=port, db=db, socket_connect_timeout=5)
                r.ping()
                self.stdout.write(self.style.SUCCESS(f'✓ Redis连接正常 ({host}:{port}/{db})'))
            else:
                self.stdout.write(self.style.WARNING(f'⚠ 使用非Redis broker: {broker_url}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Redis连接失败: {str(e)}'))
            self.stdout.write('  可能原因: Redis未运行或配置错误')
        
        self.stdout.write('')
        self.stdout.write('-' * 80)
        
        # 5. 检查任务配置
        if task_id:
            self.stdout.write(f'\n检查任务配置 (ID: {task_id})...')
            try:
                task = Task.objects.get(id=task_id)
                self.stdout.write(f'任务名称: {task.name}')
                self.stdout.write(f'插件: {task.plugin.name}')
                self.stdout.write(f'触发类型: {task.trigger_type}')
                self.stdout.write(f'是否启用: {task.is_active}')
                self.stdout.write(f'任务状态: {task.status}')
                self.stdout.write(f'最后执行时间: {task.last_run_time}')
                
                # 检查任务配置
                if task.config:
                    self.stdout.write(f'任务配置: {task.config}')
                
            except Task.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'✗ 任务不存在: {task_id}'))
        
        self.stdout.write('')
        self.stdout.write('=' * 80)
        
        # 6. 建议
        self.stdout.write('\n建议：')
        if count > 0:
            self.stdout.write('1. 运行以下命令修复卡住的执行记录:')
            self.stdout.write(self.style.WARNING('   python manage.py fix_stuck_executions'))
            self.stdout.write('')
            self.stdout.write('2. 检查Celery worker日志，查看是否有错误或异常')
            self.stdout.write('')
            self.stdout.write('3. 检查网络连接，特别是访问oss-security邮件列表的网络')
            self.stdout.write('')
            self.stdout.write('4. 如果启用了AI解析，检查AI API是否正常响应')
            self.stdout.write('')
            self.stdout.write('5. 检查系统资源（CPU、内存、磁盘空间）')
        else:
            self.stdout.write('✓ 当前没有发现卡住的任务')
        
        self.stdout.write('')
        self.stdout.write('=' * 80)
