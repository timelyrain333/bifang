"""
检查定时任务配置和注册状态
"""
from django.core.management.base import BaseCommand
from app.models import Task
from app.celery_app import app as celery_app
from app.schedulers import register_task_schedule


class Command(BaseCommand):
    help = '检查定时任务配置和注册状态'

    def add_arguments(self, parser):
        parser.add_argument(
            '--task-id',
            type=int,
            help='检查指定任务ID'
        )
        parser.add_argument(
            '--fix',
            action='store_true',
            help='自动修复Cron表达式格式问题并重新注册'
        )

    def handle(self, *args, **options):
        task_id = options.get('task_id')
        fix = options.get('fix', False)
        
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('定时任务检查工具'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write('')
        
        # 查询任务
        if task_id:
            tasks = Task.objects.filter(id=task_id)
        else:
            tasks = Task.objects.filter(
                is_active=True,
                trigger_type__in=['cron', 'interval']
            ).exclude(cron_expression__isnull=True).exclude(cron_expression='')
        
        if not tasks.exists():
            self.stdout.write(self.style.WARNING('未找到符合条件的定时任务'))
            return
        
        self.stdout.write(f'找到 {tasks.count()} 个定时任务：')
        self.stdout.write('')
        
        # 检查Celery Beat中已注册的任务
        beat_schedule = celery_app.conf.beat_schedule or {}
        registered_task_ids = set()
        for key in beat_schedule.keys():
            if key.startswith('task_'):
                try:
                    registered_task_ids.add(int(key.replace('task_', '')))
                except ValueError:
                    pass
        
        for task in tasks:
            self.stdout.write('-' * 80)
            self.stdout.write(f'任务ID: {task.id}')
            self.stdout.write(f'任务名称: {task.name}')
            self.stdout.write(f'触发类型: {task.trigger_type}')
            self.stdout.write(f'Cron表达式: {task.cron_expression}')
            self.stdout.write(f'是否启用: {task.is_active}')
            self.stdout.write(f'最后执行时间: {task.last_run_time or "从未执行"}')
            self.stdout.write(f'下次执行时间: {task.next_run_time or "未设置"}')
            
            # 检查Cron表达式格式
            cron_expr = task.cron_expression.strip()
            has_space = ' ' in cron_expr
            parts = cron_expr.split()
            
            if task.trigger_type == 'cron':
                if not has_space:
                    self.stdout.write(self.style.ERROR(f'  ❌ Cron表达式缺少空格分隔符: "{cron_expr}"'))
                    self.stdout.write(self.style.WARNING(f'  正确格式应为: "*/5 * * * *" (每5分钟)'))
                    if fix:
                        # 尝试自动修复
                        import re
                        match = re.match(r'^(\S+?)(\*+)$', cron_expr)
                        if match and len(match.group(2)) == 4:
                            fixed_expr = f"{match.group(1)} * * * *"
                            task.cron_expression = fixed_expr
                            task.save()
                            self.stdout.write(self.style.SUCCESS(f'  ✓ 已自动修复为: "{fixed_expr}"'))
                elif len(parts) != 5:
                    self.stdout.write(self.style.ERROR(f'  ❌ Cron表达式字段数量错误: 期望5个字段，实际{len(parts)}个'))
                    self.stdout.write(self.style.WARNING(f'  分割结果: {parts}'))
                else:
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Cron表达式格式正确'))
                    self.stdout.write(f'    解析: minute={parts[0]}, hour={parts[1]}, day={parts[2]}, month={parts[3]}, week={parts[4]}')
            
            elif task.trigger_type == 'interval':
                try:
                    interval_seconds = int(cron_expr)
                    interval_minutes = interval_seconds // 60
                    self.stdout.write(self.style.SUCCESS(f'  ✓ 间隔时间: {interval_seconds}秒 ({interval_minutes}分钟)'))
                except ValueError:
                    self.stdout.write(self.style.ERROR(f'  ❌ 间隔时间格式错误: "{cron_expr}"，应为数字（秒）'))
            
            # 检查是否已注册到Celery Beat
            if task.id in registered_task_ids:
                self.stdout.write(self.style.SUCCESS(f'  ✓ 已注册到Celery Beat'))
                schedule_info = beat_schedule.get(f'task_{task.id}', {})
                self.stdout.write(f'    调度信息: {schedule_info}')
            else:
                self.stdout.write(self.style.WARNING(f'  ⚠️  未注册到Celery Beat'))
                if fix:
                    try:
                        register_task_schedule(task)
                        self.stdout.write(self.style.SUCCESS(f'  ✓ 已重新注册到Celery Beat'))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'  ❌ 注册失败: {str(e)}'))
            
            self.stdout.write('')
        
        self.stdout.write('-' * 80)
        self.stdout.write(f'Celery Beat中已注册的任务总数: {len(registered_task_ids)}')
        self.stdout.write('')
        
        if fix:
            self.stdout.write(self.style.SUCCESS('提示: 已尝试修复问题，请重启Celery Beat服务使更改生效'))
        else:
            self.stdout.write(self.style.WARNING('提示: 使用 --fix 参数可以自动修复格式问题并重新注册任务'))
            self.stdout.write(self.style.WARNING('提示: 修复后需要重启Celery Beat服务: celery -A app.celery_app beat -l info'))
