"""
Celery任务定义
"""
import os
import sys
import importlib.util
import logging
from django.utils import timezone
from django.conf import settings
from app.models import Task, TaskExecution, Plugin, AliyunConfig
from app.lib.db_helper import DBHelper

logger = logging.getLogger(__name__)


def send_task_status_update(task, status=None, execution=None, executor_user_id=None):
    """
    发送任务状态更新到SSE
    
    Args:
        task: Task对象
        status: 任务状态（如果为None，使用task.status）
        execution: TaskExecution对象（可选，用于获取执行用户）
        executor_user_id: 执行用户的ID（可选，用于手动执行时传递执行用户）
    """
    try:
        from app.utils.sse_manager import sse_manager
        from django.contrib.auth.models import User
        
        # 准备任务数据
        task_data = {
            'id': task.id,
            'name': task.name,
            'status': status or task.status,
            'last_run_time': task.last_run_time.isoformat() if task.last_run_time else None,
        }
        
        # 收集需要发送消息的用户ID列表
        user_ids = set()
        
        # 1. 向任务创建者发送
        if task.created_by:
            try:
                creator = User.objects.filter(username=task.created_by).first()
                if creator:
                    user_ids.add(creator.id)
            except Exception as e:
                logger.warning(f'获取任务创建者ID失败: {e}')
        
        # 2. 如果有执行用户ID（手动执行时传递），也向执行用户发送
        if executor_user_id:
            user_ids.add(executor_user_id)
            logger.info(f'将向执行用户发送消息: user_id={executor_user_id}')
        
        # 向所有相关用户发送消息
        for user_id in user_ids:
            try:
                sse_manager.send_task_update(user_id, task.id, task_data)
                logger.info(f'已发送任务状态更新SSE消息: task_id={task.id}, user_id={user_id}, status={task_data["status"]}, task_data={task_data}')
            except Exception as e:
                logger.warning(f'向用户 {user_id} 发送SSE消息失败: {e}', exc_info=True)
        
        if not user_ids:
            logger.warning(f'任务 {task.id} 没有找到相关用户，无法发送SSE消息。任务创建者: {task.created_by}, 执行用户ID: {executor_user_id}')
            
    except Exception as e:
        # SSE发送失败不应该影响任务执行
        logger.warning(f'发送任务状态更新SSE消息失败: {e}', exc_info=True)

# 可选：如果celery未安装，使用装饰器占位符
try:
    from celery import shared_task
    # 如果celery可用，使用装饰器
    @shared_task(bind=True, max_retries=3)
    def execute_task_async_wrapper(self, task_id, execution_id):
        return execute_task_async(task_id, execution_id, self)
    
    @shared_task(bind=True, max_retries=3)
    def execute_scheduled_task(self, task_id):
        """
        执行定时任务的包装函数
        自动创建TaskExecution并调用execute_task_async
        
        Args:
            task_id: 任务ID
        """
        try:
            task = Task.objects.get(id=task_id)
            
            # 检查任务的触发类型，如果是手动执行，则跳过
            if task.trigger_type == 'manual':
                logger.warning(f"任务 {task.name} (ID: {task_id}) 已改为手动执行，跳过定时执行。请重启Celery Beat以完全移除该任务的调度。")
                return {
                    'success': False,
                    'message': '任务已改为手动执行，跳过定时执行',
                    'skipped': True
                }
            
            # 检查任务是否启用
            if not task.is_active:
                logger.warning(f"任务 {task.name} (ID: {task_id}) 未启用，跳过执行")
                return {
                    'success': False,
                    'message': '任务未启用，跳过执行',
                    'skipped': True
                }
            
            # 创建执行记录
            execution = TaskExecution.objects.create(
                task=task,
                status='running'
            )
            # 调用执行函数
            return execute_task_async(task_id, execution.id, self)
        except Task.DoesNotExist:
            logger.error(f"任务不存在: {task_id}")
            raise
        except Exception as e:
            logger.error(f"执行定时任务失败: {task_id} - {str(e)}", exc_info=True)
            raise
except ImportError:
    # Celery未安装时的占位符
    execute_task_async_wrapper = None
    execute_scheduled_task = None


def execute_task_async(task_id, execution_id, bind_obj=None):
    """
    异步执行任务
    
    Args:
        task_id: 任务ID
        execution_id: 执行记录ID
    """
    execution = None
    task = None
    try:
        task = Task.objects.get(id=task_id)
        execution = TaskExecution.objects.get(id=execution_id)
        
        # 更新任务状态为运行中
        task.status = 'running'
        task.save()
        
        # 获取执行用户ID（从execution.result中读取，如果是手动执行的话）
        executor_user_id = None
        if execution and execution.result:
            if isinstance(execution.result, dict):
                executor_user_id = execution.result.get('executor_user_id')
                logger.info(f'任务开始时读取执行用户ID: task_id={task.id}, execution_id={execution.id}, executor_user_id={executor_user_id}')
        
        # 发送状态更新通知
        send_task_status_update(task, 'running', execution, executor_user_id)
        
        # 加载插件
        plugin_module = load_plugin_module(task.plugin.file_path)
        if not plugin_module:
            raise ValueError(f'无法加载插件: {task.plugin.file_path}')
        
        # 获取插件类
        plugin_class = getattr(plugin_module, 'Plugin', None)
        if not plugin_class:
            raise ValueError('插件模块中未找到Plugin类')
        
        # 准备插件配置；阿里云与 AWS 配置相互独立，仅对对应云类型的插件合并
        plugin_config = task.config.copy() if task.config else {}
        
        # 仅当插件为阿里云相关时，才从阿里云配置中获取认证信息（避免与 AWS 配置耦合）
        is_aliyun_plugin = task.plugin and 'aliyun' in (task.plugin.name or '').lower()
        need_aliyun_config = is_aliyun_plugin and not all(
            k in plugin_config for k in ['access_key_id', 'access_key_secret', 'region_id']
        )
        if need_aliyun_config:
            # 获取阿里云配置
            aliyun_config = None
            
            # 优先使用任务指定的配置
            if task.aliyun_config and task.aliyun_config.is_active:
                aliyun_config = task.aliyun_config
                logger.info(f'使用任务指定的阿里云配置: {aliyun_config.name}')
            
            # 如果没有指定或配置无效，尝试从任务关联的配置中获取
            if not aliyun_config and task.aliyun_config and task.aliyun_config.is_active:
                aliyun_config = task.aliyun_config
                logger.info(f'使用任务关联的阿里云配置: {aliyun_config.name}')
            
            # 如果还是没有，尝试使用默认配置
            if not aliyun_config:
                try:
                    # 根据任务创建者查找用户
                    from django.contrib.auth.models import User
                    user = None
                    
                    if task.created_by:
                        user = User.objects.filter(username=task.created_by).first()
                    
                    if user:
                        aliyun_config = AliyunConfig.objects.filter(
                            user=user,
                            is_default=True,
                            is_active=True
                        ).first()
                        if aliyun_config:
                            logger.info(f'使用用户默认阿里云配置: {aliyun_config.name}')
                except Exception as e:
                    logger.error(f'获取默认阿里云配置失败: {str(e)}')
            
            # 如果找到配置，合并到插件配置中
            if aliyun_config:
                plugin_config['access_key_id'] = plugin_config.get('access_key_id') or aliyun_config.access_key_id
                plugin_config['access_key_secret'] = plugin_config.get('access_key_secret') or aliyun_config.access_key_secret
                plugin_config['region_id'] = plugin_config.get('region_id') or aliyun_config.region_id
                plugin_config['api_endpoint'] = plugin_config.get('api_endpoint') or aliyun_config.api_endpoint
                logger.info(f'已从阿里云配置"{aliyun_config.name}"中获取认证信息')
                
                # 如果阿里云配置中包含通义千问配置，使用它
                if aliyun_config.qianwen_enabled and aliyun_config.qianwen_api_key:
                    plugin_config['use_ai_parsing'] = True
                    plugin_config['ai_config'] = {
                        'api_key': aliyun_config.qianwen_api_key,
                        'api_base': aliyun_config.qianwen_api_base or 'https://dashscope.aliyuncs.com/compatible-mode/v1',
                        'model': aliyun_config.qianwen_model or 'qwen-plus',
                        'enabled': aliyun_config.qianwen_enabled
                    }
                    logger.info(f'已启用AI解析功能，使用模型: {plugin_config["ai_config"]["model"]}')
                
                # 如果是告警插件，并且阿里云配置中包含钉钉/飞书配置，自动传递通知配置ID
                # 检查插件类型是否为告警类型
                if task.plugin and task.plugin.plugin_type == 'alarm':
                    # 检查配置是否包含通知功能（钉钉或飞书）
                    # 钉钉：优先检查Stream模式（Client ID + Client Secret），其次检查Webhook
                    has_dingtalk = (
                        (aliyun_config.dingtalk_enabled and 
                         aliyun_config.dingtalk_use_stream_push and
                         aliyun_config.dingtalk_client_id and 
                         aliyun_config.dingtalk_client_secret) or
                        (aliyun_config.dingtalk_enabled and aliyun_config.dingtalk_webhook)
                    )
                    has_feishu = (
                        aliyun_config.feishu_enabled and aliyun_config.feishu_webhook
                    )
                    has_notification = has_dingtalk or has_feishu
                    
                    if has_notification:
                        # 如果没有手动指定通知配置ID，使用当前阿里云配置的ID
                        if 'notification_config_id' not in plugin_config or not plugin_config.get('notification_config_id'):
                            plugin_config['notification_config_id'] = aliyun_config.id
                            logger.info(f'已为告警插件设置通知配置ID: {aliyun_config.id} ({aliyun_config.name})')
            else:
                logger.warning('未找到可用的阿里云配置')
        
        # 仅当插件为 AWS 相关时，才从 AWS 配置中获取认证信息（与阿里云配置独立）
        is_aws_plugin = task.plugin and 'aws' in (task.plugin.name or '').lower()
        need_aws_config = is_aws_plugin and not all(
            k in plugin_config for k in ['access_key_id', 'secret_access_key', 'region']
        )
        if need_aws_config:
            # 获取AWS配置
            aws_config = None
            from app.models import AWSConfig
            
            # 优先使用任务指定的配置
            if task.aws_config and task.aws_config.is_active:
                aws_config = task.aws_config
                logger.info(f'使用任务指定的AWS配置: {aws_config.name}')
            
            # 如果还是没有，尝试使用默认配置
            if not aws_config:
                try:
                    from django.contrib.auth.models import User
                    user = None
                    
                    if task.created_by:
                        user = User.objects.filter(username=task.created_by).first()
                    
                    if user:
                        aws_config = AWSConfig.objects.filter(
                            user=user,
                            is_default=True,
                            is_active=True
                        ).first()
                        if aws_config:
                            logger.info(f'使用用户默认AWS配置: {aws_config.name}')
                except Exception as e:
                    logger.error(f'获取默认AWS配置失败: {str(e)}')
            
            # 如果找到配置，合并到插件配置中
            if aws_config:
                plugin_config['access_key_id'] = aws_config.access_key_id
                plugin_config['secret_access_key'] = aws_config.secret_access_key
                plugin_config['region'] = aws_config.region or plugin_config.get('region') or 'ap-northeast-1'
                if aws_config.session_token:
                    plugin_config['session_token'] = aws_config.session_token
                else:
                    plugin_config.pop('session_token', None)
                logger.info(f'已从AWS配置"{aws_config.name}"中获取认证信息')
            else:
                logger.warning('未找到可用的AWS配置')
        
        # 单独查找通义千问AI配置（所有插件类型都可以使用，特别是漏洞采集插件）
        # 如果没有从阿里云配置中找到AI配置，则单独查找
        if not plugin_config.get('use_ai_parsing'):
            try:
                from django.contrib.auth.models import User
                from django.db.models import Q
                user = None
                
                if task.created_by:
                    user = User.objects.filter(username=task.created_by).first()
                
                if user:
                    # 查找独立的通义千问配置或包含通义千问的配置
                    qianwen_config = AliyunConfig.objects.filter(
                        user=user,
                        is_active=True
                    ).filter(
                        Q(config_type='qianwen') | Q(config_type='both')
                    ).filter(
                        qianwen_enabled=True
                    ).exclude(
                        qianwen_api_key=''
                    ).first()
                    
                    if qianwen_config and qianwen_config.qianwen_api_key:
                        plugin_config['use_ai_parsing'] = True
                        plugin_config['ai_config'] = {
                            'api_key': qianwen_config.qianwen_api_key,
                            'api_base': qianwen_config.qianwen_api_base or 'https://dashscope.aliyuncs.com/compatible-mode/v1',
                            'model': qianwen_config.qianwen_model or 'qwen-plus',
                            'enabled': qianwen_config.qianwen_enabled
                        }
                        logger.info(f'已从独立通义千问配置"{qianwen_config.name}"中启用AI解析功能，使用模型: {plugin_config["ai_config"]["model"]}')
            except Exception as e:
                logger.error(f'获取通义千问AI配置失败: {str(e)}', exc_info=True)
        
        # 记录AI解析配置状态
        if plugin_config.get('use_ai_parsing'):
            logger.info('✅ AI解析功能已启用，漏洞采集插件将使用AI模型解析漏洞详情')
        else:
            logger.info('ℹ️ AI解析功能未启用，将使用规则解析')
        
        # 实例化插件
        plugin_instance = plugin_class(config=plugin_config)
        
        # 执行插件（添加超时保护）
        try:
            # 使用信号量或超时机制来防止插件执行时间过长
            # 注意：Celery已经有软超时和硬超时配置，这里主要是记录日志
            logger.info(f'开始执行插件: {task.plugin.name} (任务ID: {task.id}, 执行ID: {execution.id})')
            result = plugin_instance.execute()

            # 获取插件日志
            if hasattr(plugin_instance, '_get_logs'):
                try:
                    logs = plugin_instance._get_logs()
                    if not isinstance(result, dict):
                        result = {'success': True, 'message': '执行完成', 'data': result}
                    result['logs'] = logs
                    logger.info(f'已捕获插件日志: {len(logs)} 字符')
                except Exception as log_error:
                    logger.warning(f'获取插件日志失败: {str(log_error)}')

            logger.info(f'插件执行完成: {task.plugin.name} (任务ID: {task.id}, 执行ID: {execution.id})')
        except Exception as plugin_error:
            # 插件执行异常，记录详细错误信息
            error_msg = f'插件执行异常: {str(plugin_error)}'
            logger.error(f'{error_msg} (任务ID: {task.id}, 执行ID: {execution.id})', exc_info=True)

            # 尝试获取日志
            logs = ''
            if hasattr(plugin_instance, '_get_logs'):
                try:
                    logs = plugin_instance._get_logs()
                    logger.info(f'已捕获异常插件日志: {len(logs)} 字符')
                except Exception as log_error:
                    logger.warning(f'获取异常插件日志失败: {str(log_error)}')

            # 构造失败结果
            result = {
                'success': False,
                'message': error_msg,
                'data': {},
                'logs': logs
            }
        
        # 更新执行记录
        # 先保存执行用户ID（如果存在）- 需要在更新result之前读取
        executor_user_id = None
        if execution.result and isinstance(execution.result, dict):
            executor_user_id = execution.result.get('executor_user_id')
            logger.info(f'从执行记录中读取执行用户ID: task_id={task.id}, execution_id={execution.id}, executor_user_id={executor_user_id}')
        
        # 确保result是字典类型
        if not isinstance(result, dict):
            logger.warning(f'插件返回结果不是字典类型: {type(result)}, 任务ID: {task.id}')
            result = {
                'success': False,
                'message': f'插件返回结果格式错误: {type(result)}',
                'data': {},
                'logs': ''
            }
        
        try:
            execution.status = 'success' if result.get('success') else 'failed'
            execution.finished_at = timezone.now()
            # 合并结果，保留执行用户ID
            if executor_user_id:
                result['executor_user_id'] = executor_user_id
            execution.result = result
            if not result.get('success'):
                execution.error_message = result.get('message', '执行失败')
            execution.logs = result.get('logs', '')
            execution.save()
            logger.info(f'执行记录已更新: 任务ID={task.id}, 执行ID={execution.id}, 状态={execution.status}')
        except Exception as save_error:
            logger.error(f'保存执行记录失败: {str(save_error)} (任务ID: {task.id}, 执行ID: {execution.id})', exc_info=True)
            # 即使保存失败，也尝试更新任务状态
        
        # 更新任务状态
        try:
            task.status = 'success' if result.get('success') else 'failed'
            task.last_run_time = timezone.now()
            task.save()
            logger.info(f'任务状态已更新: 任务ID={task.id}, 状态={task.status}')
        except Exception as task_save_error:
            logger.error(f'保存任务状态失败: {str(task_save_error)} (任务ID: {task.id})', exc_info=True)
        
        # 发送状态更新通知（传递执行用户ID）
        try:
            logger.info(f'准备发送任务状态更新: task_id={task.id}, status={task.status}, executor_user_id={executor_user_id}')
            send_task_status_update(task, executor_user_id=executor_user_id)
        except Exception as sse_error:
            # SSE发送失败不应该影响任务执行结果
            logger.warning(f'发送SSE通知失败: {str(sse_error)} (任务ID: {task.id})', exc_info=True)
        
        return result
        
    except Exception as e:
        error_type = type(e).__name__
        # Celery 软超时（25 分钟）会抛出 SoftTimeLimitExceeded，明确提示
        try:
            from celery.exceptions import SoftTimeLimitExceeded
            if isinstance(e, SoftTimeLimitExceeded):
                error_msg = '任务执行超时（超过 Celery 软超时 25 分钟）。可减小 CNVD 任务的 max_pages/max_days 或增加 CELERY_TASK_SOFT_TIME_LIMIT。'
                logger.warning(f'任务被 Celery 软超时终止: 任务ID={task.id if task else "unknown"}, 执行ID={execution.id if execution else "unknown"}')
            else:
                error_msg = str(e)
        except ImportError:
            error_msg = str(e)
        logger.error(f'任务执行异常: {error_type}: {error_msg} (任务ID: {task.id if task else "unknown"}, 执行ID: {execution.id if execution else "unknown"})', exc_info=True)
        
        # 更新执行记录（确保即使异常也能更新状态）
        try:
            if execution:
                execution.status = 'failed'
                execution.finished_at = timezone.now()
                # 限制错误信息长度，避免数据库字段溢出
                error_message = f'{error_type}: {error_msg}'
                if len(error_message) > 2000:
                    error_message = error_message[:1997] + '...'
                execution.error_message = error_message
                try:
                    execution.save()
                    logger.info(f'执行记录已标记为失败: 执行ID={execution.id}')
                except Exception as save_ex:
                    logger.error(f'保存执行记录失败: {str(save_ex)} (执行ID: {execution.id})', exc_info=True)
            
            if task:
                task.status = 'failed'
                try:
                    task.save()
                    logger.info(f'任务已标记为失败: 任务ID={task.id}')
                except Exception as task_save_ex:
                    logger.error(f'保存任务状态失败: {str(task_save_ex)} (任务ID: {task.id})', exc_info=True)
                
                # 获取执行用户ID（从execution.result中读取，如果是手动执行的话）
                executor_user_id = None
                if execution and execution.result:
                    if isinstance(execution.result, dict):
                        executor_user_id = execution.result.get('executor_user_id')
                        logger.info(f'异常处理中读取执行用户ID: task_id={task.id}, execution_id={execution.id}, executor_user_id={executor_user_id}')
                
                # 发送状态更新通知
                try:
                    logger.info(f'准备发送任务失败状态更新: task_id={task.id}, executor_user_id={executor_user_id}')
                    send_task_status_update(task, 'failed', execution, executor_user_id)
                except Exception as sse_ex:
                    logger.warning(f'发送SSE通知失败: {str(sse_ex)} (任务ID: {task.id})', exc_info=True)
        except Exception as update_error:
            logger.error(f'更新执行记录失败: {str(update_error)}', exc_info=True)
        
        # 重试（如果有bind_obj且celery可用）
        # 注意：对于某些严重错误（如数据库连接失败），不应该重试
        should_retry = True
        if error_type in ['OperationalError', 'DatabaseError', 'ConnectionError']:
            # 数据库连接错误，不重试
            should_retry = False
            logger.warning(f'检测到数据库连接错误，不进行重试: {error_type}')
        
        if should_retry and bind_obj and hasattr(bind_obj, 'retry'):
            try:
                # 检查重试次数
                retry_count = getattr(bind_obj.request, 'retries', 0)
                max_retries = getattr(bind_obj, 'max_retries', 3)
                if retry_count < max_retries:
                    logger.info(f'准备重试任务 (第{retry_count + 1}次): 任务ID={task.id if task else "unknown"}')
                    raise bind_obj.retry(exc=e, countdown=60)
                else:
                    logger.warning(f'已达到最大重试次数 ({max_retries})，不再重试: 任务ID={task.id if task else "unknown"}')
            except Exception as retry_error:
                logger.error(f'重试任务失败: {str(retry_error)}', exc_info=True)
        
        # 重新抛出异常，让Celery知道任务失败
        raise


def load_plugin_module(file_path):
    """
    加载插件模块
    
    Args:
        file_path: 插件文件路径，相对于app/plugins目录或完整路径
        
    Returns:
        module: 插件模块
    """
    try:
        # 构建完整路径
        if os.path.isabs(file_path):
            full_path = file_path
        elif file_path.startswith('app/plugins/'):
            full_path = os.path.join(settings.BASE_DIR, file_path)
        else:
            full_path = os.path.join(settings.BASE_DIR, 'app', 'plugins', file_path)
        
        if not os.path.exists(full_path):
            logger.error(f'插件文件不存在: {full_path}')
            return None
        
        # 生成唯一的模块名
        module_name = f"plugin_{os.path.basename(full_path).replace('.py', '')}"
        
        # 动态导入模块
        spec = importlib.util.spec_from_file_location(module_name, full_path)
        if spec is None or spec.loader is None:
            logger.error(f'无法创建模块规范: {full_path}')
            return None
        
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        
        return module
        
    except Exception as e:
        logger.error(f'加载插件模块失败: {str(e)}', exc_info=True)
        return None
