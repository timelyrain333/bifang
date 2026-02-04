"""
任务执行器
支持同步执行插件任务，并流式返回执行结果
"""
import logging
import sys
import os
import importlib.util
import io
import threading
from typing import Dict, Any, Generator, Optional
from django.conf import settings
from app.models import Task, Plugin, AliyunConfig
from django.db.models import Q

logger = logging.getLogger(__name__)


class TaskExecutor:
    """任务执行器"""
    
    @staticmethod
    def execute_plugin_by_name(plugin_name: str, config: Optional[Dict] = None, user=None) -> Dict[str, Any]:
        """
        根据插件名称执行插件
        
        Args:
            plugin_name: 插件名称
            config: 插件配置
            user: 用户对象
            
        Returns:
            Dict: 执行结果
        """
        try:
            plugin = Plugin.objects.filter(name=plugin_name, is_active=True).first()
            if not plugin:
                return {
                    'success': False,
                    'message': f'插件 {plugin_name} 不存在或未启用'
                }
            
            # 加载插件模块
            plugin_class = TaskExecutor._load_plugin_class(plugin.file_path)
            if not plugin_class:
                return {
                    'success': False,
                    'message': f'加载插件 {plugin_name} 失败'
                }
            
            # 合并配置
            plugin_config = config or {}
            
            # 获取用户配置
            if user:
                # 查找阿里云配置
                aliyun_config = AliyunConfig.objects.filter(
                    user=user,
                    is_active=True
                ).filter(
                    Q(config_type='aliyun') | Q(config_type='both')
                ).first()
                
                if aliyun_config:
                    # 合并阿里云配置
                    plugin_config['access_key_id'] = plugin_config.get('access_key_id') or aliyun_config.access_key_id
                    plugin_config['access_key_secret'] = plugin_config.get('access_key_secret') or aliyun_config.access_key_secret
                    plugin_config['region_id'] = plugin_config.get('region_id') or aliyun_config.region_id
                    plugin_config['api_endpoint'] = plugin_config.get('api_endpoint') or aliyun_config.api_endpoint
                    
                    # 合并AI配置
                    if aliyun_config.qianwen_enabled and aliyun_config.qianwen_api_key:
                        plugin_config['use_ai_parsing'] = True
                        plugin_config['ai_config'] = {
                            'api_key': aliyun_config.qianwen_api_key,
                            'api_base': aliyun_config.qianwen_api_base or 'https://dashscope.aliyuncs.com/compatible-mode/v1',
                            'model': aliyun_config.qianwen_model or 'qwen-plus',
                            'enabled': aliyun_config.qianwen_enabled
                        }
                
                # 查找通义千问配置（如果还没有）
                if not plugin_config.get('use_ai_parsing'):
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
            
            # 实例化并执行插件
            plugin_instance = plugin_class(config=plugin_config)
            result = plugin_instance.execute()
            
            # 获取插件日志
            if hasattr(plugin_instance, 'log_buffer'):
                logs = plugin_instance.log_buffer.getvalue()
                if logs:
                    result['logs'] = logs
            
            return result
            
        except Exception as e:
            logger.error(f"执行插件失败: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'执行失败: {str(e)}'
            }
    
    @staticmethod
    def execute_task(task_id: int) -> Dict[str, Any]:
        """
        执行任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            Dict: 执行结果
        """
        try:
            task = Task.objects.get(id=task_id)
            
            # 直接调用同步执行函数
            from app.tasks import execute_task_async
            result = execute_task_async(task.id, None)
            
            return result
            
        except Task.DoesNotExist:
            return {
                'success': False,
                'message': f'任务 {task_id} 不存在'
            }
        except Exception as e:
            logger.error(f"执行任务失败: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'执行失败: {str(e)}'
            }
    
    @staticmethod
    def _load_plugin_class(file_path: str):
        """
        加载插件类
        
        Args:
            file_path: 插件文件路径
            
        Returns:
            Plugin类
        """
        try:
            # 转换为绝对路径
            if not os.path.isabs(file_path):
                base_dir = settings.BASE_DIR
                file_path = os.path.join(base_dir, file_path)
            
            spec = importlib.util.spec_from_file_location("plugin_module", file_path)
            if spec is None or spec.loader is None:
                logger.error(f"无法加载插件文件: {file_path}")
                return None
            
            module = importlib.util.module_from_spec(spec)
            sys.modules["plugin_module"] = module
            spec.loader.exec_module(module)
            
            plugin_class = getattr(module, 'Plugin', None)
            if not plugin_class:
                logger.error(f"插件文件中未找到Plugin类: {file_path}")
                return None
            
            return plugin_class
            
        except Exception as e:
            logger.error(f"加载插件类失败: {e}", exc_info=True)
            return None
    
    @staticmethod
    def execute_plugin_stream(plugin_name: str, config: Optional[Dict] = None, user=None) -> Generator[str, None, None]:
        """
        流式执行插件，实时yield执行日志
        
        Args:
            plugin_name: 插件名称
            config: 插件配置
            user: 用户对象
            
        Yields:
            str: 执行日志片段
        """
        # 不输出开始执行信息，只输出最终结果
        
        try:
            plugin = Plugin.objects.filter(name=plugin_name, is_active=True).first()
            if not plugin:
                yield f"❌ 插件 {plugin_name} 不存在或未启用\n"
                return
            
            # 加载插件模块
            plugin_class = TaskExecutor._load_plugin_class(plugin.file_path)
            if not plugin_class:
                yield f"❌ 加载插件 {plugin_name} 失败\n"
                return
            
            # 合并配置
            plugin_config = config or {}
            
            # 获取用户配置（同execute_plugin_by_name）
            if user:
                aliyun_config = AliyunConfig.objects.filter(
                    user=user,
                    is_active=True
                ).filter(
                    Q(config_type='aliyun') | Q(config_type='both')
                ).first()
                
                if aliyun_config:
                    plugin_config['access_key_id'] = plugin_config.get('access_key_id') or aliyun_config.access_key_id
                    plugin_config['access_key_secret'] = plugin_config.get('access_key_secret') or aliyun_config.access_key_secret
                    plugin_config['region_id'] = plugin_config.get('region_id') or aliyun_config.region_id
                    plugin_config['api_endpoint'] = plugin_config.get('api_endpoint') or aliyun_config.api_endpoint
                    
                    if aliyun_config.qianwen_enabled and aliyun_config.qianwen_api_key:
                        plugin_config['use_ai_parsing'] = True
                        plugin_config['ai_config'] = {
                            'api_key': aliyun_config.qianwen_api_key,
                            'api_base': aliyun_config.qianwen_api_base or 'https://dashscope.aliyuncs.com/compatible-mode/v1',
                            'model': aliyun_config.qianwen_model or 'qwen-plus',
                            'enabled': aliyun_config.qianwen_enabled
                        }
                        logger.info(f'已从阿里云配置"{aliyun_config.name}"中启用AI解析功能，使用模型: {plugin_config["ai_config"]["model"]}')
                
                if not plugin_config.get('use_ai_parsing'):
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
                        logger.info(f'已从通义千问配置"{qianwen_config.name}"中启用AI解析功能，使用模型: {plugin_config["ai_config"]["model"]}')
            
            # 如果用户为None或没有找到AI配置，尝试查找所有启用的通义千问配置（用于钉钉等场景）
            if not plugin_config.get('use_ai_parsing'):
                qianwen_config = AliyunConfig.objects.filter(
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
                    logger.info(f'已从全局通义千问配置"{qianwen_config.name}"中启用AI解析功能，使用模型: {plugin_config["ai_config"]["model"]}')
            
            # 记录AI解析配置状态
            if plugin_config.get('use_ai_parsing'):
                logger.info('✅ AI解析功能已启用，漏洞采集插件将使用AI模型解析漏洞详情')
            else:
                logger.info('ℹ️ AI解析功能未启用，将使用规则解析')
            
            # 实例化插件
            plugin_instance = plugin_class(config=plugin_config)
            
            # 创建日志捕获器
            log_buffer = io.StringIO()
            log_handler = logging.StreamHandler(log_buffer)
            log_handler.setLevel(logging.INFO)
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            log_handler.setFormatter(formatter)
            
            # 如果插件有logger，添加handler
            if hasattr(plugin_instance, 'logger'):
                plugin_instance.logger.addHandler(log_handler)
            
            # 在后台线程中执行插件（不输出日志，日志保留在log文件中）
            result_container = {'result': None, 'error': None}
            
            def execute_in_thread():
                try:
                    result_container['result'] = plugin_instance.execute()
                except Exception as e:
                    result_container['error'] = str(e)
            
            thread = threading.Thread(target=execute_in_thread, daemon=True)
            thread.start()
            
            # 等待线程完成（不输出日志）
            thread.join()
            
            # 只输出执行结果摘要（不输出详细日志）
            if result_container['error']:
                yield f"### ❌ 执行失败\n\n"
                yield f"{result_container['error']}\n"
            elif result_container['result']:
                result = result_container['result']
                if result.get('success'):
                    # 只输出关键结果信息
                    data = result.get('data', {})
                    collected = data.get('collected', 0)
                    updated = data.get('updated', 0)
                    skipped = data.get('skipped', 0)
                    errors = data.get('errors', 0)
                    
                    # 简洁的结果摘要
                    if collected > 0 or updated > 0:
                        yield f"✅ 采集完成：新增 {collected} 条，更新 {updated} 条"
                        if skipped > 0:
                            yield f"，跳过 {skipped} 条"
                        if errors > 0:
                            yield f"，错误 {errors} 条"
                        yield "\n"
                    else:
                        yield f"✅ {result.get('message', '执行完成')}\n"
                else:
                    yield f"### ❌ 执行失败\n\n"
                    yield f"{result.get('message', '')}\n"
            
        except Exception as e:
            logger.error(f"流式执行插件失败: {e}", exc_info=True)
            yield f"\n### ❌ 执行失败\n\n"
            yield f"{str(e)}\n"
        
        # 不输出分割线
