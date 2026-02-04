"""
管理命令：加载插件到数据库
"""
from django.core.management.base import BaseCommand
from app.models import Plugin
import os
from pathlib import Path


class Command(BaseCommand):
    help = '加载插件到数据库'

    def handle(self, *args, **options):
        # 插件目录在 app/plugins
        # __file__ 是 app/management/commands/load_plugins.py
        # parent.parent.parent 是 app 目录
        # 然后进入 plugins
        base_dir = Path(__file__).resolve().parent.parent.parent
        plugins_dir = base_dir / 'plugins'
        
        if not plugins_dir.exists():
            self.stdout.write(self.style.ERROR(f'插件目录不存在: {plugins_dir}'))
            return
        
        loaded_count = 0
        
        for plugin_file in plugins_dir.glob('*.py'):
            if plugin_file.name == '__init__.py':
                continue
            
            try:
                # 读取插件文件，提取插件信息
                with open(plugin_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 简单的插件类型检测
                plugin_type = 'data'
                if plugin_file.name.startswith('data_'):
                    plugin_type = 'data'
                elif plugin_file.name.startswith('collect_'):
                    plugin_type = 'collect'
                elif plugin_file.name.startswith('risk_'):
                    plugin_type = 'risk'
                elif plugin_file.name.startswith('dump_'):
                    plugin_type = 'dump'
                elif plugin_file.name.startswith('alarm_'):
                    plugin_type = 'alarm'
                
                # 尝试从文件中提取PLUGIN_INFO
                plugin_name = plugin_file.stem
                description = f'{plugin_type}类型插件: {plugin_name}'
                
                # 如果文件中有PLUGIN_INFO，提取更详细的信息
                if 'PLUGIN_INFO' in content:
                    try:
                        # 尝试执行文件来获取PLUGIN_INFO（安全的方式）
                        import re
                        # 使用正则表达式提取PLUGIN_INFO字典
                        match = re.search(r'PLUGIN_INFO\s*=\s*\{([^}]+)\}', content, re.DOTALL)
                        if match:
                            # 提取description字段
                            desc_match = re.search(r"'description':\s*['\"]([^'\"]+)['\"]", match.group(0))
                            if desc_match:
                                description = desc_match.group(1)
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f'解析PLUGIN_INFO失败 {plugin_file.name}: {str(e)}'))
                
                plugin, created = Plugin.objects.update_or_create(
                    name=plugin_name,
                    defaults={
                        'plugin_type': plugin_type,
                        'description': description,
                        'file_path': f'app/plugins/{plugin_file.name}',
                        'is_active': True,
                    }
                )
                
                if created:
                    self.stdout.write(self.style.SUCCESS(f'已加载插件: {plugin_name}'))
                    loaded_count += 1
                else:
                    self.stdout.write(f'插件已存在: {plugin_name}')
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'加载插件失败 {plugin_file.name}: {str(e)}'))
        
        self.stdout.write(self.style.SUCCESS(f'\n共加载 {loaded_count} 个插件'))




