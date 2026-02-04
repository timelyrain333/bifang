"""
定时任务调度器
使用django-crontab或celery-beat进行定时任务调度
"""
import logging
import time
from datetime import timedelta

logger = logging.getLogger(__name__)

# 尝试导入celery相关模块
try:
    from celery.schedules import crontab, schedule
    try:
        from app.celery_app import app as celery_app
        # 检查celery_app是否可用
        if celery_app is None:
            raise ImportError("celery_app is None")
    except (ImportError, AttributeError):
        raise ImportError("无法导入celery_app")
    CELERY_AVAILABLE = True
except ImportError:
    # Celery未安装时，使用占位符
    CELERY_AVAILABLE = False
    celery_app = None
    crontab = None
    schedule = None
    logger.warning("Celery未安装，定时任务调度功能将不可用")

# 标记是否已经初始化过
_initialized = False


def setup_periodic_tasks(sender=None, **kwargs):
    """
    配置周期性任务
    从数据库中读取所有启用的定时任务并注册
    
    注意：这个函数可能在Django完全初始化之前被调用，所以需要确保Django已初始化
    """
    global _initialized
    
    # 如果Celery不可用，直接返回
    if not CELERY_AVAILABLE:
        logger.warning("Celery未安装，无法配置定时任务")
        _initialized = True
        return
    
    # 如果已经初始化过，跳过
    if _initialized:
        logger.debug("定时任务已经初始化过，跳过")
        return
    
    # 确保Django已初始化，最多重试10次，每次等待0.5秒
    import django
    max_retries = 10
    retry_count = 0
    
    while not django.apps.apps.ready and retry_count < max_retries:
        logger.info(f"Django尚未完全初始化，等待中... (重试 {retry_count + 1}/{max_retries})")
        time.sleep(0.5)
        retry_count += 1
        # 尝试手动初始化Django（如果可能）
        try:
            if not django.apps.apps.ready:
                django.setup()
        except Exception:
            pass
    
    if not django.apps.apps.ready:
        logger.error("Django初始化超时，定时任务可能无法正确加载。请检查Django配置。")
        # 即使Django未初始化，也尝试加载任务（可能会失败，但至少会记录错误）
    
    # 从数据库读取所有启用的定时任务并注册
    try:
        # 延迟导入Task模型，确保Django已初始化
        from app.models import Task
        
        logger.info("=" * 60)
        logger.info("开始初始化定时任务调度器...")
        
        # 清空现有的调度表（避免重复注册）
        celery_app.conf.beat_schedule.clear()
        logger.info("已清空现有调度表")
        
        # 额外清理：确保所有手动执行的任务都被移除（防止之前注册的手动任务残留）
        all_tasks = Task.objects.filter(is_active=True).exclude(cron_expression__isnull=True).exclude(cron_expression='')
        manual_tasks = all_tasks.filter(trigger_type='manual')
        if manual_tasks.exists():
            for manual_task in manual_tasks:
                unregister_task_schedule(manual_task.id)
            logger.info(f"已清理 {manual_tasks.count()} 个手动执行任务的调度配置")
        
        # 加载cron类型的任务
        cron_tasks = Task.objects.filter(is_active=True, trigger_type='cron').exclude(cron_expression__isnull=True).exclude(cron_expression='')
        cron_count = cron_tasks.count()
        logger.info(f"开始加载Cron定时任务，共找到 {cron_count} 个任务")
        
        registered_cron = 0
        for task in cron_tasks:
            try:
                register_task_schedule(task)
                registered_cron += 1
            except Exception as e:
                logger.error(f"注册Cron任务失败: {task.name} (ID: {task.id}) - {str(e)}", exc_info=True)
        
        # 加载interval类型的任务
        interval_tasks = Task.objects.filter(is_active=True, trigger_type='interval').exclude(cron_expression__isnull=True).exclude(cron_expression='')
        interval_count = interval_tasks.count()
        logger.info(f"开始加载Interval定时任务，共找到 {interval_count} 个任务")
        
        registered_interval = 0
        for task in interval_tasks:
            try:
                register_task_schedule(task)
                registered_interval += 1
            except Exception as e:
                logger.error(f"注册Interval任务失败: {task.name} (ID: {task.id}) - {str(e)}", exc_info=True)
        
        total_registered = len(celery_app.conf.beat_schedule)
        logger.info("=" * 60)
        logger.info(f"定时任务加载完成:")
        logger.info(f"  - Cron任务: 找到 {cron_count} 个，成功注册 {registered_cron} 个")
        logger.info(f"  - Interval任务: 找到 {interval_count} 个，成功注册 {registered_interval} 个")
        logger.info(f"  - 总计: 已注册 {total_registered} 个定时任务到Celery Beat")
        logger.info("=" * 60)
        
        # 打印所有已注册的任务详情（用于调试）
        if total_registered > 0:
            logger.info("已注册的任务详情:")
            for schedule_key, schedule_info in celery_app.conf.beat_schedule.items():
                task_id = schedule_key.replace('task_', '')
                logger.info(f"  - {schedule_key}: 任务ID={task_id}, 调度={schedule_info.get('schedule')}")
        
        _initialized = True
        
    except Exception as e:
        logger.error(f"初始化定时任务失败: {str(e)}", exc_info=True)
        # 即使失败也标记为已初始化，避免无限重试
        _initialized = True


def reload_all_tasks():
    """
    重新加载所有定时任务
    用于在任务创建或更新后手动触发重新加载
    
    Returns:
        dict: 加载结果统计
    """
    global _initialized
    
    if not CELERY_AVAILABLE:
        logger.warning("Celery未安装，无法重新加载定时任务")
        return {
            'total_tasks': 0,
            'schedules': {}
        }
    
    _initialized = False  # 重置初始化标记，允许重新初始化
    
    logger.info("手动触发重新加载所有定时任务...")
    setup_periodic_tasks(sender=None)
    
    return {
        'total_tasks': len(celery_app.conf.beat_schedule),
        'schedules': dict(celery_app.conf.beat_schedule)
    }


def unregister_task_schedule(task_id: int):
    """
    从Celery Beat调度器中取消注册任务
    
    Args:
        task_id: 任务ID
    """
    if not CELERY_AVAILABLE:
        logger.debug(f"Celery未安装，无法取消注册任务: task_{task_id}")
        return
    
    schedule_key = f'task_{task_id}'
    if schedule_key in celery_app.conf.beat_schedule:
        del celery_app.conf.beat_schedule[schedule_key]
        logger.info(f"已取消注册定时任务: task_{task_id}")
    else:
        logger.debug(f"任务未在调度表中: task_{task_id}")


def register_task_schedule(task):
    """
    注册任务到Celery Beat调度器
    
    Args:
        task: Task对象
    
    Returns:
        bool: 是否成功注册
    """
    if not CELERY_AVAILABLE:
        logger.debug(f"Celery未安装，无法注册任务: {task.name} (ID: {task.id})")
        return False
    
    # 确保Django已初始化
    import django
    if not django.apps.apps.ready:
        try:
            django.setup()
        except Exception:
            pass
    
    # 延迟导入Task模型，避免在Django未初始化时出错
    from app.models import Task
    
    # 如果是手动执行任务，直接取消注册并返回
    if task.trigger_type == 'manual':
        unregister_task_schedule(task.id)
        logger.debug(f"任务为手动执行类型，已取消注册: {task.name} (ID: {task.id})")
        return False
    
    if not task.is_active:
        # 如果任务未启用，取消注册
        unregister_task_schedule(task.id)
        logger.debug(f"任务未启用，已取消注册: {task.name} (ID: {task.id})")
        return False
    
    if not task.cron_expression:
        # 如果没有cron表达式，取消注册
        unregister_task_schedule(task.id)
        logger.debug(f"任务缺少Cron表达式，已取消注册: {task.name} (ID: {task.id})")
        return False
    
    try:
        # 处理interval类型（间隔执行）
        if task.trigger_type == 'interval':
            # cron_expression字段存储间隔秒数（如：300 表示5分钟）
            try:
                interval_seconds = int(task.cron_expression.strip())
                if interval_seconds <= 0:
                    raise ValueError("间隔时间必须大于0")
                
                beat_schedule = schedule(timedelta(seconds=interval_seconds))
                
                celery_app.conf.beat_schedule[f'task_{task.id}'] = {
                    'task': 'app.tasks.execute_scheduled_task',
                    'schedule': beat_schedule,
                    'args': (task.id,),
                }
                
                logger.info(f"✅ 成功注册间隔任务: {task.name} (ID: {task.id}), 间隔: {interval_seconds}秒 ({interval_seconds//60}分钟)")
                return True
                
            except ValueError as e:
                logger.error(f"❌ 注册间隔任务失败: {task.name} (ID: {task.id}) - 间隔时间格式错误: {str(e)}")
                unregister_task_schedule(task.id)
                return False
        
        # 处理cron类型（定时执行）
        if task.trigger_type != 'cron':
            unregister_task_schedule(task.id)
            logger.warning(f"任务触发类型不是cron或interval: {task.name} (ID: {task.id}), trigger_type={task.trigger_type}")
            return False
        
        # 解析cron表达式 (格式: minute hour day month day_of_week)
        # 例如: "0 0 * * *" 表示每天0点执行
        # 例如: "*/5 * * * *" 表示每5分钟执行一次
        
        # 清理和规范化Cron表达式
        cron_expr = task.cron_expression.strip()
        
        # 修复常见的格式问题：处理 "* /5" 这种情况，应该合并为 "*/5"
        import re
        # 修复 "* /数字" 或 "* / *" 这种情况
        cron_expr = re.sub(r'\*\s+/(\d+)', r'*/\1', cron_expr)
        cron_expr = re.sub(r'\*\s+/\s*\*', r'*', cron_expr)
        
        # 尝试修复缺少空格的情况：例如: "*/5****" -> "*/5 * * * *"
        if ' ' not in cron_expr and len(cron_expr) > 5:
            # 尝试智能分割：假设格式是 "*/5****" 或类似
            match = re.match(r'^(\S+?)(\*+)$', cron_expr)
            if match:
                first_part = match.group(1)  # 例如 "*/5"
                stars = match.group(2)  # 例如 "****"
                # 如果stars有4个*，说明格式可能是 "*/5****"
                if len(stars) == 4:
                    cron_expr = f"{first_part} * * * *"
                    logger.warning(f"自动修复Cron表达式格式: {task.cron_expression} -> {cron_expr}")
                elif len(stars) >= 4:
                    # 如果超过4个*，只取前4个
                    cron_expr = f"{first_part} * * * *"
                    logger.warning(f"自动修复Cron表达式格式: {task.cron_expression} -> {cron_expr}")
        
        parts = cron_expr.split()
        if len(parts) != 5:
            error_msg = f"Cron表达式格式错误，应为5个字段（用空格分隔）：分钟 小时 日 月 周。当前值: '{task.cron_expression}'，分割后得到 {len(parts)} 个字段: {parts}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        minute, hour, day, month, day_of_week = parts
        
        # 验证每个字段的格式
        valid_chars = set('0123456789*/- ,')
        for i, part in enumerate([minute, hour, day, month, day_of_week]):
            if not all(c in valid_chars for c in part):
                raise ValueError(f"Cron表达式第{i+1}个字段包含无效字符: {part}")
        
        # 使用crontab，支持 */5 这种格式
        beat_schedule = crontab(
            minute=minute,
            hour=hour,
            day_of_month=day,
            month_of_year=month,
            day_of_week=day_of_week,
        )
        
        # 使用包装函数，自动创建TaskExecution
        celery_app.conf.beat_schedule[f'task_{task.id}'] = {
            'task': 'app.tasks.execute_scheduled_task',
            'schedule': beat_schedule,
            'args': (task.id,),
        }
        
        logger.info(f"✅ 成功注册定时任务: {task.name} (ID: {task.id}), Cron: {task.cron_expression} -> 解析为: minute={minute}, hour={hour}, day={day}, month={month}, day_of_week={day_of_week}")
        return True
        
    except Exception as e:
        logger.error(f"❌ 注册定时任务失败: {task.name} (ID: {task.id}) - {str(e)}", exc_info=True)
        unregister_task_schedule(task.id)
        return False


def restart_celery_beat():
    """
    重启Celery Beat进程，使调度配置生效
    
    Returns:
        bool: 是否成功重启
    """
    import subprocess
    import os
    import signal
    import time
    
    try:
        # 获取项目根目录
        import django
        from django.conf import settings
        project_root = settings.BASE_DIR
        
        # 检查Celery Beat是否在运行
        try:
            result = subprocess.run(
                ['pgrep', '-f', 'celery.*beat'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                # 找到运行中的进程
                pids = result.stdout.strip().split('\n')
                pids = [pid.strip() for pid in pids if pid.strip()]
                
                if pids:
                    logger.info(f"发现运行中的Celery Beat进程: {', '.join(pids)}")
                    
                    # 停止所有Celery Beat进程
                    for pid in pids:
                        try:
                            os.kill(int(pid), signal.SIGTERM)
                            logger.info(f"已发送停止信号到进程 {pid}")
                        except (ValueError, ProcessLookupError, PermissionError) as e:
                            logger.warning(f"停止进程 {pid} 失败: {str(e)}")
                    
                    # 等待进程停止
                    time.sleep(2)
                    
                    # 再次检查，如果还在运行，强制杀死
                    result = subprocess.run(
                        ['pgrep', '-f', 'celery.*beat'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        pids = result.stdout.strip().split('\n')
                        pids = [pid.strip() for pid in pids if pid.strip()]
                        for pid in pids:
                            try:
                                os.kill(int(pid), signal.SIGKILL)
                                logger.warning(f"强制停止进程 {pid}")
                            except (ValueError, ProcessLookupError, PermissionError):
                                pass
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"检查Celery Beat进程时出错: {str(e)}，尝试使用pkill")
        
        # 使用pkill作为备用方案
        try:
            subprocess.run(['pkill', '-f', 'celery.*beat'], 
                         capture_output=True, timeout=5)
            time.sleep(1)  # 等待进程完全停止
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        # 检查虚拟环境
        venv_celery = os.path.join(project_root, 'venv', 'bin', 'celery')
        if os.path.exists(venv_celery):
            celery_cmd = venv_celery
        else:
            # 尝试使用系统命令
            celery_cmd = 'celery'
            logger.warning("未找到虚拟环境中的celery，尝试使用系统命令")
        
        # 创建日志目录
        logs_dir = os.path.join(project_root, 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        
        # 启动Celery Beat（后台运行）
        log_file = os.path.join(logs_dir, 'celery_beat.log')
        beat_cmd = [
            celery_cmd,
            '-A', 'app.celery_app',
            'beat',
            '-l', 'info',
            '--logfile', log_file,
            '--detach'
        ]
        
        logger.info(f"正在启动Celery Beat: {' '.join(beat_cmd)}")
        result = subprocess.run(
            beat_cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            # 等待一下，然后检查是否成功启动
            time.sleep(2)
            check_result = subprocess.run(
                ['pgrep', '-f', 'celery.*beat'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if check_result.returncode == 0:
                logger.info("✅ Celery Beat已成功重启")
                return True
            else:
                logger.warning("⚠️  Celery Beat可能未成功启动，请检查日志")
                return False
        else:
            error_msg = result.stderr if result.stderr else result.stdout
            logger.error(f"❌ 启动Celery Beat失败: {error_msg}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("启动Celery Beat超时")
        return False
    except Exception as e:
        logger.error(f"重启Celery Beat时出错: {str(e)}", exc_info=True)
        return False




