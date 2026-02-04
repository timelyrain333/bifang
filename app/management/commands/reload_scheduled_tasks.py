"""
重新加载所有定时任务到Celery Beat调度器

使用方法:
    python manage.py reload_scheduled_tasks
"""
from django.core.management.base import BaseCommand
from app.schedulers import reload_all_tasks
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '重新加载所有定时任务到Celery Beat调度器'

    def handle(self, *args, **options):
        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS("开始重新加载定时任务..."))
        self.stdout.write("=" * 60)
        
        try:
            result = reload_all_tasks()
            
            self.stdout.write(self.style.SUCCESS(f"\n✅ 重新加载完成！"))
            self.stdout.write(f"   已注册 {result['total_tasks']} 个定时任务")
            
            if result['total_tasks'] > 0:
                self.stdout.write("\n已注册的任务:")
                for schedule_key, schedule_info in result['schedules'].items():
                    task_id = schedule_key.replace('task_', '')
                    schedule = schedule_info.get('schedule', 'N/A')
                    self.stdout.write(f"  - {schedule_key}: 任务ID={task_id}, 调度={schedule}")
            
            self.stdout.write("\n" + "=" * 60)
            self.stdout.write(self.style.WARNING("⚠️  注意: 如果Celery Beat正在运行，需要重启Celery Beat才能使新任务生效"))
            self.stdout.write("   重启命令: pkill -f 'celery.*beat' && celery -A app.celery_app beat -l info")
            self.stdout.write("=" * 60)
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ 重新加载失败: {str(e)}"))
            logger.error(f"重新加载定时任务失败: {str(e)}", exc_info=True)
            raise
