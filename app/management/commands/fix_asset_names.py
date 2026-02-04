"""
修复资产数据中的名称字段，将名称和版本号分开
确保name字段只包含软件/组件名称，版本号存储在data字段中
"""
import re
from django.core.management.base import BaseCommand
from app.models import Asset


class Command(BaseCommand):
    help = '修复资产数据中的名称字段，将名称和版本号分开'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='仅显示将要修复的记录，不实际修改'
        )
        parser.add_argument(
            '--asset-type',
            type=str,
            help='只修复指定的资产类型（如：software）'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        asset_type = options.get('asset_type')
        
        # 查找需要修复的资产（主要是software类型）
        assets = Asset.objects.filter(asset_type='software')
        if asset_type:
            assets = assets.filter(asset_type=asset_type)
        
        fixed_count = 0
        skipped_count = 0
        error_count = 0
        
        self.stdout.write('开始扫描资产数据...')
        self.stdout.write('-' * 80)
        
        for asset in assets:
            try:
                # 检查名称是否包含版本号
                if not asset.name:
                    skipped_count += 1
                    continue
                
                # 检查名称是否包含版本号模式（如 "docker-ce 26.1.4"）
                version_pattern = r'\s+\d+\.\d+(?:\.\d+)?(?:\.[a-zA-Z0-9]+)?(?:\s|$)'
                if not re.search(version_pattern, asset.name):
                    skipped_count += 1
                    continue
                
                # 尝试从名称中分离出软件名称和版本号
                parts = asset.name.split()
                if len(parts) < 2:
                    skipped_count += 1
                    continue
                
                # 检查最后一部分是否是版本号
                last_part = parts[-1]
                if re.match(r'^\d+\.\d+(?:\.\d+)?(?:\.[a-zA-Z0-9]+)?$', last_part):
                    # 最后一部分是版本号，提取软件名称
                    new_name = ' '.join(parts[:-1])
                    version = last_part
                    
                    # 更新资产数据
                    asset_data = asset.data if isinstance(asset.data, dict) else {}
                    
                    # 确保data中有Version字段
                    if 'Version' not in asset_data and 'version' not in asset_data:
                        asset_data['Version'] = version
                    
                    self.stdout.write(f'\n资产UUID: {asset.uuid}')
                    self.stdout.write(f'  原名称: {asset.name}')
                    self.stdout.write(f'  新名称: {new_name}')
                    self.stdout.write(f'  版本号: {version}')
                    
                    if not dry_run:
                        asset.name = new_name
                        asset.data = asset_data
                        asset.save(update_fields=['name', 'data'])
                        self.stdout.write(self.style.SUCCESS('  ✓ 已修复'))
                    else:
                        self.stdout.write(self.style.WARNING('  [DRY RUN] 将修复'))
                    
                    fixed_count += 1
                else:
                    skipped_count += 1
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'\n修复资产 {asset.uuid} 时出错: {str(e)}'))
                error_count += 1
        
        self.stdout.write('-' * 80)
        self.stdout.write(f'\n修复完成:')
        self.stdout.write(f'  修复: {fixed_count} 条')
        self.stdout.write(f'  跳过: {skipped_count} 条')
        self.stdout.write(f'  错误: {error_count} 条')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n这是模拟运行，没有实际修改数据。去掉 --dry-run 参数执行实际修复。'))

