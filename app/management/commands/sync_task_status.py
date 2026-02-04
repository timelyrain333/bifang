"""
同步任务状态和执行记录状态
如果任务状态为running但最新的执行记录不是running，则同步状态
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from app.models import Task, TaskExecution


class Command(BaseCommand):
    help = '同步任务状态和执行记录状态'

    def add_arguments(self, parser):
        parser.add_argument(
            '--task-id',
            type=int,
            default=None,
            help='指定任务ID进行同步'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='仅显示将要同步的记录，不实际修改'
        )

    def handle(self, *args, **options):
        task_id = options.get('task_id')
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('任务状态同步工具'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write('')
        
        # 查找状态为running的任务
        if task_id:
            tasks = Task.objects.filter(id=task_id, status='running')
        else:
            tasks = Task.objects.filter(status='running')
        
        count = tasks.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('✓ 没有找到状态为running的任务'))
            return
        
        self.stdout.write(f'找到 {count} 个状态为running的任务：')
        self.stdout.write('-' * 80)
        
        synced_count = 0
        for task in tasks:
            # 获取最新的执行记录
            latest_execution = TaskExecution.objects.filter(task=task).order_by('-started_at').first()
            
            if not latest_execution:
                self.stdout.write(f'\n任务ID: {task.id}, 名称: {task.name}')
                self.stdout.write(f'  没有执行记录')
                continue
            
            # 如果最新执行记录不是running，同步任务状态
            if latest_execution.status != 'running':
                self.stdout.write(f'\n任务ID: {task.id}, 名称: {task.name}')
                self.stdout.write(f'  任务状态: {task.status}')
                self.stdout.write(f'  最新执行记录状态: {latest_execution.status}')
                self.stdout.write(f'  最新执行记录ID: {latest_execution.id}')
                self.stdout.write(f'  执行开始时间: {latest_execution.started_at}')
                self.stdout.write(f'  执行结束时间: {latest_execution.finished_at}')
                
                if not dry_run:
                    # 同步任务状态
                    task.status = latest_execution.status
                    task.save()
                    self.stdout.write(self.style.SUCCESS(f'  ✓ 已同步任务状态为: {latest_execution.status}'))
                    synced_count += 1
                else:
                    self.stdout.write(self.style.WARNING(f'  [DRY RUN] 将同步任务状态为: {latest_execution.status}'))
        
        self.stdout.write('-' * 80)
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f'\n[DRY RUN模式] 实际未修改任何记录'))
            self.stdout.write(f'要实际同步，请运行: python manage.py sync_task_status')
        else:
            self.stdout.write(self.style.SUCCESS(f'\n成功同步 {synced_count} 个任务状态'))
        
        self.stdout.write('=' * 80)
