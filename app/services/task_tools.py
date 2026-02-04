"""
任务管理工具函数
供AI智能体调用，用于创建、修改和查询任务
"""
import logging
import re
from typing import Dict, Any, Optional, List
from django.utils import timezone
from app.models import Task, Plugin, AliyunConfig, Asset
from app.schedulers import register_task_schedule, unregister_task_schedule

logger = logging.getLogger(__name__)


def parse_cron_from_natural_language(text: str) -> Optional[str]:
    """
    从自然语言中解析cron表达式
    
    Args:
        text: 自然语言描述，如"每天0点"、"每周一"、"每小时"等
        
    Returns:
        str: cron表达式，如"0 0 * * *"，如果无法解析返回None
    """
    text_lower = text.lower()
    
    # 每天0点 / 每天凌晨 / 每天00:00
    if any(kw in text_lower for kw in ['每天0点', '每天凌晨', '每天00:00', '每天 0点', '每天 00:00']):
        return '0 0 * * *'
    
    # 每天特定时间
    hour_match = re.search(r'每天\s*(\d{1,2})\s*点', text)
    if hour_match:
        hour = int(hour_match.group(1))
        if 0 <= hour <= 23:
            return f'0 {hour} * * *'
    
    # 每N小时
    hour_interval_match = re.search(r'每\s*(\d+)\s*小时', text)
    if hour_interval_match:
        interval = int(hour_interval_match.group(1))
        if 1 <= interval <= 23:
            # 注意：cron表达式中，每N小时应该是 */N，不是 /N
            return f'0 */{interval} * * *'
    
    # 每周一 / 每周几
    weekday_map = {
        '周一': '1', '周二': '2', '周三': '3', '周四': '4',
        '周五': '5', '周六': '6', '周日': '0',
        '星期一': '1', '星期二': '2', '星期三': '3', '星期四': '4',
        '星期五': '5', '星期六': '6', '星期日': '0'
    }
    for weekday_text, weekday_num in weekday_map.items():
        if f'每周{weekday_text}' in text_lower or f'每{weekday_text}' in text_lower:
            return f'0 0 * * {weekday_num}'
    
    # 每小时
    if '每小时' in text_lower:
        return '0 * * * *'
    
    # 每N天
    day_interval_match = re.search(r'每\s*(\d+)\s*天', text)
    if day_interval_match:
        interval = int(day_interval_match.group(1))
        if 1 <= interval <= 31:
            # 每N天执行，使用日期字段
            return f'0 0 */{interval} * *'
    
    # 每月1号
    if '每月1号' in text_lower or '每月1日' in text_lower:
        return '0 0 1 * *'
    
    # 默认：每天0点
    if '每天' in text_lower and not any(kw in text_lower for kw in ['小时', '天', '周', '月']):
        return '0 0 * * *'
    
    return None


def get_plugin_by_name_or_keyword(name_or_keyword: str) -> Optional[Plugin]:
    """
    根据名称或关键词查找插件
    
    Args:
        name_or_keyword: 插件名称或关键词，如"漏洞采集"、"资产采集"等
        
    Returns:
        Plugin: 插件对象，如果未找到返回None
    """
    keyword_lower = name_or_keyword.lower()
    
    # 漏洞采集相关
    if any(kw in keyword_lower for kw in ['漏洞', 'cve', 'oss-security', 'collect_oss']):
        plugin = Plugin.objects.filter(name__icontains='oss-security').first()
        if plugin:
            return plugin
        plugin = Plugin.objects.filter(name__icontains='collect_oss').first()
        if plugin:
            return plugin
    
    # 资产采集相关
    if any(kw in keyword_lower for kw in ['资产', 'asset', 'aliyun_security', 'data_aliyun']):
        plugin = Plugin.objects.filter(name__icontains='aliyun_security').first()
        if plugin:
            return plugin
        plugin = Plugin.objects.filter(name__icontains='data_aliyun').first()
        if plugin:
            return plugin
    
    # 精确匹配
    plugin = Plugin.objects.filter(name=name_or_keyword, is_active=True).first()
    if plugin:
        return plugin
    
    # 模糊匹配
    plugin = Plugin.objects.filter(name__icontains=keyword_lower, is_active=True).first()
    if plugin:
        return plugin
    
    return None


def list_assets(
    limit: int = 50,
    asset_type: Optional[str] = None,
    source: Optional[str] = None
) -> Dict[str, Any]:
    """
    查询资产列表，用于安全评估时选择目标。返回资产摘要（含可用于扫描的目标地址：IP/域名/主机名）。
    
    Args:
        limit: 返回数量限制，默认50
        asset_type: 资产类型筛选（可选），如 server, web_service, web_site 等
        source: 数据来源筛选（可选），如 aliyun_security, aws_inspector
        
    Returns:
        Dict: {'success': bool, 'message': str, 'assets': [{'id', 'name', 'asset_type', 'target', 'uuid'}, ...]}
    """
    try:
        qs = Asset.objects.all().order_by('-updated_at')
        if asset_type:
            qs = qs.filter(asset_type=asset_type)
        if source:
            qs = qs.filter(source=source)
        qs = qs[:limit]
        assets = []
        for a in qs:
            data = a.data or {}
            # 优先用 IP/域名/主机名 作为安全扫描目标
            target = (
                data.get('InternetIp') or data.get('IntranetIp') or
                data.get('PublicIp') or data.get('PrivateIpAddress') or
                data.get('Hostname') or data.get('InstanceId') or
                data.get('Domain') or data.get('Url') or
                a.name or a.uuid
            )
            if isinstance(target, list):
                target = target[0] if target else (a.name or a.uuid)
            assets.append({
                'id': a.id,
                'name': a.name or a.uuid,
                'asset_type': a.asset_type,
                'target': str(target) if target else (a.name or a.uuid),
                'uuid': a.uuid,
                'source': a.source,
            })
        return {
            'success': True,
            'message': f'共 {len(assets)} 条资产',
            'assets': assets,
            'total': len(assets),
        }
    except Exception as e:
        logger.exception(f"list_assets failed: {e}")
        return {'success': False, 'message': str(e), 'assets': [], 'total': 0}


def create_task(
    name: str,
    plugin_name_or_keyword: str,
    trigger_type: str = 'manual',
    cron_expression: Optional[str] = None,
    task_config: Optional[Dict[str, Any]] = None,
    aliyun_config_id: Optional[int] = None,
    is_active: bool = True,
    created_by: Optional[str] = None
) -> Dict[str, Any]:
    """
    创建任务
    
    Args:
        name: 任务名称
        plugin_name_or_keyword: 插件名称或关键词
        trigger_type: 触发类型 ('manual', 'cron', 'interval')
        cron_expression: Cron表达式（当trigger_type为'cron'时必需）
        task_config: 任务配置（JSON格式）
        aliyun_config_id: 阿里云配置ID（可选）
        is_active: 是否启用
        created_by: 创建者用户名
        
    Returns:
        Dict: 创建结果 {'success': bool, 'message': str, 'task_id': int}
    """
    try:
        # 查找插件
        plugin = get_plugin_by_name_or_keyword(plugin_name_or_keyword)
        if not plugin:
            return {
                'success': False,
                'message': f'未找到插件: {plugin_name_or_keyword}。可用插件：{", ".join([p.name for p in Plugin.objects.filter(is_active=True)])}'
            }
        
        # 验证cron表达式
        if trigger_type == 'cron':
            if not cron_expression:
                return {
                    'success': False,
                    'message': '定时任务必须提供cron表达式'
                }
            # 验证cron表达式格式（简单验证）
            parts = cron_expression.split()
            if len(parts) != 5:
                return {
                    'success': False,
                    'message': f'Cron表达式格式错误，应为5个字段：分钟 小时 日 月 周。例如: 0 0 * * *'
                }
        
        # 获取阿里云配置（如果指定）
        aliyun_config = None
        if aliyun_config_id:
            try:
                aliyun_config = AliyunConfig.objects.get(id=aliyun_config_id, is_active=True)
            except AliyunConfig.DoesNotExist:
                return {
                    'success': False,
                    'message': f'未找到阿里云配置 ID: {aliyun_config_id}'
                }
        
        # 创建任务
        task = Task.objects.create(
            name=name,
            plugin=plugin,
            aliyun_config=aliyun_config,
            status='pending',
            trigger_type=trigger_type,
            cron_expression=cron_expression,
            config=task_config or {},
            is_active=is_active,
            created_by=created_by or ''
        )
        
        logger.info(f"成功创建任务: {task.name} (ID: {task.id}), 插件: {plugin.name}, 触发类型: {trigger_type}")
        
        # 如果是定时任务，注册到Celery Beat调度器
        if trigger_type == 'cron' and cron_expression and is_active:
            try:
                register_task_schedule(task)
                logger.info(f"已注册定时任务到Celery Beat: {task.name} (ID: {task.id})")
            except Exception as e:
                logger.error(f"注册定时任务到Celery Beat失败: {task.name} (ID: {task.id}) - {str(e)}", exc_info=True)
        
        return {
            'success': True,
            'message': f'任务创建成功：{task.name} (ID: {task.id})',
            'task_id': task.id,
            'task_name': task.name,
            'plugin_name': plugin.name,
            'trigger_type': trigger_type,
            'cron_expression': cron_expression
        }
        
    except Exception as e:
        logger.error(f"创建任务失败: {e}", exc_info=True)
        return {
            'success': False,
            'message': f'创建任务失败: {str(e)}'
        }


def list_tasks(
    plugin_name: Optional[str] = None,
    trigger_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    created_by: Optional[str] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """
    查询任务列表
    
    Args:
        plugin_name: 插件名称（可选）
        trigger_type: 触发类型（可选）
        is_active: 是否启用（可选）
        created_by: 创建者（可选）
        limit: 返回数量限制
        
    Returns:
        Dict: 任务列表
    """
    try:
        queryset = Task.objects.all()
        
        if plugin_name:
            plugin = get_plugin_by_name_or_keyword(plugin_name)
            if plugin:
                queryset = queryset.filter(plugin=plugin)
        
        if trigger_type:
            queryset = queryset.filter(trigger_type=trigger_type)
        
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)
        
        if created_by:
            queryset = queryset.filter(created_by=created_by)
        
        tasks = queryset.order_by('-created_at')[:limit]
        
        task_list = []
        for task in tasks:
            task_list.append({
                'id': task.id,
                'name': task.name,
                'plugin_name': task.plugin.name,
                'trigger_type': task.trigger_type,
                'cron_expression': task.cron_expression,
                'is_active': task.is_active,
                'status': task.status,
                'created_at': task.created_at.strftime('%Y-%m-%d %H:%M:%S') if task.created_at else None
            })
        
        return {
            'success': True,
            'count': len(task_list),
            'tasks': task_list
        }
        
    except Exception as e:
        logger.error(f"查询任务列表失败: {e}", exc_info=True)
        return {
            'success': False,
            'message': f'查询任务列表失败: {str(e)}',
            'tasks': []
        }


def update_task(
    task_id: int,
    name: Optional[str] = None,
    trigger_type: Optional[str] = None,
    cron_expression: Optional[str] = None,
    task_config: Optional[Dict[str, Any]] = None,
    is_active: Optional[bool] = None,
    user=None
) -> Dict[str, Any]:
    """
    更新任务
    
    Args:
        task_id: 任务ID
        name: 任务名称（可选）
        trigger_type: 触发类型（可选）
        cron_expression: Cron表达式（可选）
        task_config: 任务配置（可选）
        is_active: 是否启用（可选）
        user: 用户对象（用于权限检查）
        
    Returns:
        Dict: 更新结果
    """
    try:
        # 验证task_id类型和范围
        if not isinstance(task_id, int):
            try:
                task_id = int(task_id)
            except (ValueError, TypeError):
                return {
                    'success': False,
                    'message': f'无效的任务ID: {task_id}'
                }
        
        if task_id <= 0:
            return {
                'success': False,
                'message': f'无效的任务ID: {task_id}'
            }
        
        task = Task.objects.get(id=task_id)
        
        # 权限检查：只有任务创建者或超级管理员可以修改任务
        if user:
            is_superuser = False
            username = None
            
            if hasattr(user, 'is_superuser'):
                is_superuser = user.is_superuser
            elif hasattr(user, 'username'):
                username = user.username
            elif isinstance(user, str):
                username = user
                # 检查是否为超级用户（需要从数据库查询）
                try:
                    from django.contrib.auth.models import User
                    user_obj = User.objects.get(username=username)
                    is_superuser = user_obj.is_superuser
                except:
                    pass
            
            # 如果不是超级管理员，检查是否为任务创建者
            if not is_superuser:
                if username and task.created_by != username:
                    return {
                        'success': False,
                        'message': '无权修改此任务，只有任务创建者或管理员可以修改'
                    }
                elif not username:
                    return {
                        'success': False,
                        'message': '无法验证用户身份'
                    }
        
        old_trigger_type = task.trigger_type
        old_cron_expression = task.cron_expression
        old_is_active = task.is_active
        
        if name is not None:
            task.name = name
        if trigger_type is not None:
            task.trigger_type = trigger_type
        if cron_expression is not None:
            task.cron_expression = cron_expression
        if task_config is not None:
            task.config = task_config
        if is_active is not None:
            task.is_active = is_active
        
        task.save()
        
        # 如果定时任务相关属性发生变化，需要重新注册或取消注册
        trigger_changed = (trigger_type is not None and trigger_type != old_trigger_type) or \
                         (cron_expression is not None and cron_expression != old_cron_expression) or \
                         (is_active is not None and is_active != old_is_active)
        
        if trigger_changed:
            # 先取消注册旧的
            unregister_task_schedule(task.id)
            # 如果是定时任务且启用，重新注册
            if task.trigger_type == 'cron' and task.cron_expression and task.is_active:
                try:
                    register_task_schedule(task)
                    logger.info(f"已重新注册定时任务到Celery Beat: {task.name} (ID: {task.id})")
                except Exception as e:
                    logger.error(f"重新注册定时任务到Celery Beat失败: {task.name} (ID: {task.id}) - {str(e)}", exc_info=True)
        
        logger.info(f"成功更新任务: {task.name} (ID: {task.id})")
        
        return {
            'success': True,
            'message': f'任务更新成功：{task.name} (ID: {task.id})',
            'task_id': task.id
        }
        
    except Task.DoesNotExist:
        return {
            'success': False,
            'message': f'未找到任务 ID: {task_id}'
        }
    except Exception as e:
        logger.error(f"更新任务失败: {e}", exc_info=True)
        return {
            'success': False,
            'message': f'更新任务失败: {str(e)}'
        }

