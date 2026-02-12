"""
修复卡住的执行记录
将长时间处于running状态且没有更新的执行记录标记为失败
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from app.models import TaskExecution, Task


class Command(BaseCommand):
    help = '修复卡住的执行记录（将长时间处于running状态的记录标记为失败）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--minutes',
            type=int,
            default=30,
            help='超过多少分钟的running状态记录将被标记为失败（默认30分钟）'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='仅显示将要修复的记录，不实际修改'
        )

    def handle(self, *args, **options):
        minutes = options['minutes']
        dry_run = options['dry_run']
        
        # 查找超过指定时间仍为running状态的执行记录
        cutoff_time = timezone.now() - timedelta(minutes=minutes)
        stuck_executions = TaskExecution.objects.filter(
            status='running',
            started_at__lt=cutoff_time
        )
        
        count = stuck_executions.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS(f'没有找到超过{minutes}分钟仍为running状态的执行记录'))
            return
        
        self.stdout.write(f'找到 {count} 条卡住的执行记录（超过{minutes}分钟）：')
        self.stdout.write('-' * 80)
        
        for execution in stuck_executions:
            duration = timezone.now() - execution.started_at
            duration_minutes = duration.total_seconds() / 60
            
            self.stdout.write(f'\n执行记录ID: {execution.id}')
            self.stdout.write(f'任务: {execution.task.name} (ID: {execution.task.id})')
            self.stdout.write(f'开始时间: {execution.started_at}')
            self.stdout.write(f'执行时长: {duration_minutes:.2f} 分钟')
            
            if not dry_run:
                # 更新执行记录状态
                execution.status = 'failed'
                execution.finished_at = timezone.now()
                execution.error_message = f'执行超时（超过{minutes}分钟未更新状态）'
                execution.save()
                
                # 更新任务状态（如果任务状态也是running）
                if execution.task.status == 'running':
                    execution.task.status = 'failed'
                    execution.task.save()
                
                self.stdout.write(self.style.SUCCESS('  ✓ 已标记为失败'))
            else:
                self.stdout.write(self.style.WARNING('  [DRY RUN] 将标记为失败'))
        
        self.stdout.write('-' * 80)
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f'\n[DRY RUN模式] 实际未修改任何记录'))
            self.stdout.write(f'要实际修复，请运行: python manage.py fix_stuck_executions')
        else:
            self.stdout.write(self.style.SUCCESS(f'\n成功修复 {count} 条执行记录'))









