"""
数据库操作辅助类
"""
from django.db import transaction
from app.models import Asset
import logging

logger = logging.getLogger(__name__)


class DBHelper:
    """数据库操作辅助类"""
    
    @staticmethod
    @transaction.atomic
    def save_asset(asset_type, uuid, data, host_uuid=None, name=None, source='aliyun_security'):
        """
        保存资产数据
        
        Args:
            asset_type: 资产类型
            uuid: 资产UUID
            data: 资产详细数据
            host_uuid: 主机UUID
            name: 资产名称
            source: 数据来源
            
        Returns:
            Asset: 保存的资产对象
        """
        try:
            # 确保uuid和name不为None
            uuid = uuid or ''
            name = name or ''
            host_uuid = host_uuid or ''
            
            # 确保uuid长度不超过100字符（数据库限制）
            if len(uuid) > 100:
                logger.warning(f'UUID长度超过100字符，将被截断: {uuid[:100]}')
                uuid = uuid[:100]
            
            asset, created = Asset.objects.update_or_create(
                asset_type=asset_type,
                uuid=uuid,
                defaults={
                    'host_uuid': host_uuid,
                    'name': name,
                    'data': data,
                    'source': source,
                }
            )
            
            action = '创建' if created else '更新'
            logger.debug(f'{action}资产: {asset_type} - {uuid[:80]}...')
            
            return asset
        except Exception as e:
            logger.error(f'保存资产失败: asset_type={asset_type}, uuid={uuid[:80]}..., error={str(e)}')
            raise
    
    @staticmethod
    @transaction.atomic
    def batch_save_assets(assets_data):
        """
        批量保存资产数据
        
        Args:
            assets_data: 资产数据列表，每个元素为字典，包含asset_type, uuid, data等字段
            
        Returns:
            tuple: (成功数量, 失败数量)
        """
        success_count = 0
        fail_count = 0
        
        if not assets_data:
            logger.warning('批量保存资产数据为空')
            return 0, 0
        
        logger.info(f'开始批量保存 {len(assets_data)} 条资产数据')
        
        for idx, asset_data in enumerate(assets_data):
            try:
                # 验证必需字段
                if 'asset_type' not in asset_data or 'uuid' not in asset_data:
                    logger.error(f'资产数据缺少必需字段 (索引 {idx}): {list(asset_data.keys())}')
                    fail_count += 1
                    continue
                
                DBHelper.save_asset(**asset_data)
                success_count += 1
            except Exception as e:
                uuid_preview = asset_data.get("uuid", "unknown")[:60] if asset_data.get("uuid") else "unknown"
                logger.error(f'保存资产失败 (索引 {idx}): uuid={uuid_preview}..., asset_type={asset_data.get("asset_type")}, error={str(e)}')
                fail_count += 1
        
        logger.info(f'批量保存完成: 成功 {success_count} 条, 失败 {fail_count} 条')
        return success_count, fail_count
    
    @staticmethod
    @transaction.atomic
    def delete_assets_by_host(host_uuid: str, asset_type: str = None, source: str = 'aliyun_security'):
        """
        根据host_uuid删除资产数据（用于在执行任务前清理旧数据）
        
        Args:
            host_uuid: 主机UUID
            asset_type: 资产类型，如果为None则删除所有类型的资产（除了server）
            source: 数据来源，默认'aliyun_security'
            
        Returns:
            int: 删除的记录数
        """
        try:
            queryset = Asset.objects.filter(host_uuid=host_uuid, source=source)
            
            # 如果指定了资产类型，只删除该类型
            if asset_type:
                queryset = queryset.filter(asset_type=asset_type)
            else:
                # 如果不指定，删除除server外的所有类型（保留server作为基础数据）
                queryset = queryset.exclude(asset_type='server')
            
            count = queryset.count()
            if count > 0:
                queryset.delete()
                logger.info(f'删除 {host_uuid} 的旧资产数据: {asset_type or "所有类型"} {count} 条')
            
            return count
        except Exception as e:
            logger.error(f'删除资产数据失败: host_uuid={host_uuid}, asset_type={asset_type}, error={str(e)}')
            raise
