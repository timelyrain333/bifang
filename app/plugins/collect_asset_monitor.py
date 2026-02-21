"""
资产变化监测插件
监测云资产的资产变化，并通过钉钉推送通知
"""
import sys
import os
import logging
from datetime import datetime
from typing import Dict, List, Any, Set
from django.utils import timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from app.lib.base_plugin import BasePlugin
from app.utils.dingtalk import send_dingtalk_message

logger = logging.getLogger(__name__)


class Plugin(BasePlugin):
    """资产变化监测插件"""

    # 支持监测的资产类型
    SUPPORTED_ASSET_TYPES = [
        'ecs_instance',
        'ecs_image',
        'ecs_disk',
        'vpc',
        'vswitch',
        'slb',
        'rds',
    ]

    ASSET_TYPE_LABELS = {
        'ecs_instance': 'ECS云服务器',
        'ecs_image': '镜像',
        'ecs_disk': '磁盘',
        'vpc': 'VPC专有网络',
        'vswitch': '交换机',
        'slb': '负载均衡',
        'rds': '云数据库',
    }

    def __init__(self, config=None):
        super().__init__(config)

        # 配置参数
        asset_types_config = self.config.get('asset_types', 'ecs_instance')
        if isinstance(asset_types_config, str):
            self.asset_types = [t.strip() for t in asset_types_config.split(',') if t.strip()]
        else:
            self.asset_types = asset_types_config

        self.source = self.config.get('source', 'aliyun_ecs')
        self.enable_dingtalk = self.config.get('enable_dingtalk', True)
        self.notification_config_id = self.config.get('notification_config_id')

        # 自动同步配置（监测前自动调用数据采集插件同步数据）
        self.auto_sync = self.config.get('auto_sync', True)

        # 通知阈值配置
        self.max_changes_per_notification = self.config.get('max_changes_per_notification', 20)
        self.notify_on_add = self.config.get('notify_on_add', True)
        self.notify_on_delete = self.config.get('notify_on_delete', True)
        self.notify_on_modify = self.config.get('notify_on_modify', False)

    def execute(self, *args, **kwargs) -> Dict[str, Any]:
        """执行资产变化监测"""
        from django.apps import apps
        Asset = apps.get_model('app', 'Asset')
        AssetSnapshot = apps.get_model('app', 'AssetSnapshot')
        AssetChangeRecord = apps.get_model('app', 'AssetChangeRecord')

        result = {
            'success': True,
            'message': '资产变化监测完成',
            'data': {
                'monitored_types': [],
                'total_changes': 0,
                'notifications_sent': 0,
                'changes': {}
            }
        }

        try:
            self.log_info("=" * 60)
            self.log_info("开始执行资产变化监测")
            self.log_info(f"监测类型: {self.asset_types}")
            self.log_info(f"数据来源: {self.source}")
            self.log_info(f"钉钉通知: {'启用' if self.enable_dingtalk else '禁用'}")
            self.log_info("=" * 60)

            for asset_type in self.asset_types:
                if asset_type not in self.SUPPORTED_ASSET_TYPES:
                    self.log_warning(f"不支持的资产类型: {asset_type}")
                    continue

                type_name = self.ASSET_TYPE_LABELS.get(asset_type, asset_type)
                self.log_info(f"\n--- 开始监测 {type_name} ---")

                changes = self._monitor_asset_type(
                    asset_type=asset_type,
                    source=self.source,
                    Asset=Asset,
                    AssetSnapshot=AssetSnapshot,
                    AssetChangeRecord=AssetChangeRecord
                )

                result['data']['monitored_types'].append(asset_type)
                result['data']['changes'][asset_type] = changes
                result['data']['total_changes'] += changes.get('total', 0)

                # 发送钉钉通知
                if self.enable_dingtalk and changes.get('total', 0) > 0:
                    notification_sent = self._send_notification(asset_type, changes)
                    if notification_sent:
                        result['data']['notifications_sent'] += 1

            result['message'] = f"监测完成，共发现 {result['data']['total_changes']} 处变化"

        except Exception as e:
            self.log_error(f"执行失败: {str(e)}", exc_info=True)
            result['success'] = False
            result['message'] = f"执行失败: {str(e)}"

        return result

    def _sync_assets(self, asset_type: str, source: str):
        """同步资产数据 - 调用相应的数据采集插件"""
        # 资产类型到采集插件的映射
        ASSET_TYPE_TO_PLUGIN = {
            # ECS相关资源
            'ecs_instance': 'data_aliyun_ecs',
            'ecs_image': 'data_aliyun_ecs',
            'ecs_disk': 'data_aliyun_ecs',
            'ecs_snapshot': 'data_aliyun_ecs',
            'ecs_security_group': 'data_aliyun_ecs',
            'ecs_network_interface': 'data_aliyun_ecs',
            # VPC相关
            'vpc': 'data_aliyun_vpc',
            'vswitch': 'data_aliyun_vpc',
            # SLB
            'slb': 'data_aliyun_slb',
            # RDS
            'rds': 'data_aliyun_rds',
        }

        # AWS 资源映射
        if source.startswith('aws'):
            ASSET_TYPE_TO_PLUGIN = {
                'vpc': 'data_aws_vpc',
                'vswitch': 'data_aws_vpc',
                'slb': 'data_aws_elb',
                'rds': 'data_aws_rds',
            }

        plugin_name = ASSET_TYPE_TO_PLUGIN.get(asset_type)
        if not plugin_name:
            self.log_warning(f"未找到资产类型 {asset_type} 对应的采集插件，跳过同步")
            return

        try:
            # 动态导入采集插件
            plugin_module = __import__(
                f'app.plugins.{plugin_name}',
                fromlist=['Plugin']
            )

            # 获取阿里云配置
            from django.apps import apps
            AliyunConfig = apps.get_model('app', 'AliyunConfig')

            # 获取有效的配置（必须有 access_key_id）
            config_obj = None

            if self.notification_config_id:
                # 尝试使用指定的配置ID
                config_obj = AliyunConfig.objects.filter(
                    id=self.notification_config_id,
                    is_active=True
                ).exclude(access_key_id='').exclude(access_key_id__isnull=True).first()

            # 如果指定配置无效或未指定，回退到默认配置
            if not config_obj:
                # 优先使用 is_default=True 且有 AK 的配置
                config_obj = AliyunConfig.objects.filter(
                    is_active=True,
                    is_default=True
                ).exclude(access_key_id='').exclude(access_key_id__isnull=True).first()

            # 如果仍没有，使用第一个有 AK 的配置
            if not config_obj:
                config_obj = AliyunConfig.objects.filter(
                    is_active=True
                ).exclude(access_key_id='').exclude(access_key_id__isnull=True).first()

            if not config_obj:
                self.log_warning("未找到有效的云服务配置，跳过数据同步")
                return

            # 构建插件配置
            plugin_config = {
                'access_key_id': config_obj.access_key_id,
                'access_key_secret': config_obj.access_key_secret,
                'region_id': config_obj.region_id,
            }

            # 实例化并执行采集插件
            sync_plugin = plugin_module.Plugin(config=plugin_config)

            self.log_info(f"开始同步 {asset_type} 数据，调用插件: {plugin_name}")

            # 如果是 ECS 相关，只采集对应的资源类型
            if plugin_name == 'data_aliyun_ecs':
                result = sync_plugin.execute(resource_types=[asset_type])
            else:
                result = sync_plugin.execute()

            if result.get('success'):
                self.log_info(f"数据同步完成: {result.get('message')}")
            else:
                self.log_warning(f"数据同步失败: {result.get('message')}")

        except ImportError as e:
            self.log_warning(f"导入采集插件 {plugin_name} 失败: {str(e)}")
        except Exception as e:
            self.log_error(f"同步资产数据失败: {str(e)}", exc_info=True)

    def _monitor_asset_type(self, asset_type: str, source: str,
                            Asset, AssetSnapshot, AssetChangeRecord) -> Dict:
        """监测指定类型的资产变化"""
        changes = {
            'created': [],
            'deleted': [],
            'modified': [],
            'total': 0
        }

        try:
            # 0. 自动同步数据（如果启用）
            if self.auto_sync:
                self._sync_assets(asset_type, source)

            # 1. 获取当前资产列表
            current_assets = Asset.objects.filter(
                asset_type=asset_type,
                source=source
            ).values('uuid', 'name', 'data')

            current_uuids = set()
            current_details = {}

            for asset in current_assets:
                uuid = asset['uuid']
                current_uuids.add(uuid)
                current_details[uuid] = {
                    'name': asset['name'],
                    'key_fields': self._extract_key_fields(asset_type, asset['data'])
                }

            self.log_info(f"当前资产数量: {len(current_uuids)}")

            # 2. 获取上一次快照
            last_snapshot = AssetSnapshot.objects.filter(
                asset_type=asset_type,
                source=source
            ).order_by('-collected_at').first()

            # 3. 创建新快照
            new_snapshot = AssetSnapshot.objects.create(
                snapshot_id=AssetSnapshot.generate_snapshot_id(asset_type),
                asset_type=asset_type,
                source=source,
                asset_uuids=list(current_uuids),
                asset_count=len(current_uuids),
                asset_details=current_details
            )
            self.log_info(f"已创建快照: {new_snapshot.snapshot_id}")

            if not last_snapshot:
                self.log_info("首次采集，无历史快照可对比")
                new_snapshot.changes = {'is_first_snapshot': True}
                new_snapshot.save()
                return changes

            # 4. 对比变化
            previous_uuids = set(last_snapshot.asset_uuids)
            previous_details = last_snapshot.asset_details

            # 新增的资产
            created_uuids = current_uuids - previous_uuids
            for uuid in created_uuids:
                detail = current_details.get(uuid, {})
                changes['created'].append({
                    'uuid': uuid,
                    'name': detail.get('name', ''),
                    'detail': detail.get('key_fields', {})
                })
                self._create_change_record(
                    AssetChangeRecord, new_snapshot, 'created',
                    asset_type, uuid, detail.get('name', ''),
                    {}, detail.get('key_fields', {})
                )

            # 删除的资产
            deleted_uuids = previous_uuids - current_uuids
            for uuid in deleted_uuids:
                detail = previous_details.get(uuid, {})
                changes['deleted'].append({
                    'uuid': uuid,
                    'name': detail.get('name', ''),
                    'detail': detail.get('key_fields', {})
                })
                self._create_change_record(
                    AssetChangeRecord, new_snapshot, 'deleted',
                    asset_type, uuid, detail.get('name', ''),
                    detail.get('key_fields', {}), {}
                )

            # 检查属性变更（可选）
            if self.notify_on_modify:
                common_uuids = current_uuids & previous_uuids
                for uuid in common_uuids:
                    old_detail = previous_details.get(uuid, {}).get('key_fields', {})
                    new_detail = current_details.get(uuid, {}).get('key_fields', {})

                    if old_detail != new_detail:
                        changes['modified'].append({
                            'uuid': uuid,
                            'name': current_details.get(uuid, {}).get('name', ''),
                            'old': old_detail,
                            'new': new_detail
                        })
                        self._create_change_record(
                            AssetChangeRecord, new_snapshot, 'modified',
                            asset_type, uuid, current_details.get(uuid, {}).get('name', ''),
                            old_detail, new_detail
                        )

            # 更新快照的变化记录
            changes['total'] = len(changes['created']) + len(changes['deleted']) + len(changes['modified'])
            new_snapshot.changes = changes
            new_snapshot.save()

            self.log_info(f"检测结果: 新增 {len(changes['created'])}, "
                         f"删除 {len(changes['deleted'])}, "
                         f"变更 {len(changes['modified'])}")

        except Exception as e:
            self.log_error(f"监测资产类型 {asset_type} 失败: {str(e)}", exc_info=True)

        return changes

    def _extract_key_fields(self, asset_type: str, data: dict) -> dict:
        """提取关键字段用于对比"""
        key_fields = {}

        if asset_type == 'ecs_instance':
            key_fields = {
                'status': data.get('Status'),
                'instance_type': data.get('InstanceType'),
                'public_ip': data.get('PublicIpAddress', []),
                'inner_ip': data.get('InnerIpAddress', []),
                'zone_id': data.get('ZoneId'),
            }
        elif asset_type == 'vpc':
            key_fields = {
                'status': data.get('Status'),
                'cidr_block': data.get('CidrBlock'),
                'vswitch_count': len(data.get('VSwitchIds', {}).get('VSwitchId', [])),
            }
        elif asset_type == 'slb':
            key_fields = {
                'status': data.get('LoadBalancerStatus'),
                'address': data.get('Address'),
                'network_type': data.get('AddressType'),
            }
        elif asset_type == 'rds':
            key_fields = {
                'status': data.get('DBInstanceStatus'),
                'engine': data.get('Engine'),
                'engine_version': data.get('EngineVersion'),
            }
        else:
            # 默认提取一些通用字段
            key_fields = {
                'status': data.get('Status') or data.get('status'),
                'name': data.get('Name') or data.get('name'),
            }

        return key_fields

    def _create_change_record(self, AssetChangeRecord, snapshot, change_type,
                              asset_type, asset_uuid, asset_name, old_value, new_value):
        """创建变更记录"""
        try:
            AssetChangeRecord.objects.create(
                snapshot=snapshot,
                change_type=change_type,
                asset_type=asset_type,
                asset_uuid=asset_uuid,
                asset_name=asset_name,
                old_value=old_value,
                new_value=new_value
            )
        except Exception as e:
            self.log_warning(f"创建变更记录失败: {str(e)}")

    def _send_notification(self, asset_type: str, changes: Dict) -> bool:
        """发送钉钉通知"""
        try:
            from django.apps import apps
            AliyunConfig = apps.get_model('app', 'AliyunConfig')

            # 获取通知配置
            config = self._get_notification_config(AliyunConfig)
            if not config:
                self.log_warning("未找到钉钉配置，跳过通知")
                return False

            if not config.dingtalk_webhook:
                self.log_warning("钉钉Webhook未配置，跳过通知")
                return False

            # 构建消息
            title, text = self._format_notification_message(asset_type, changes)

            # 发送消息
            result = send_dingtalk_message(
                webhook_url=config.dingtalk_webhook,
                secret=config.dingtalk_secret if config.dingtalk_secret else None,
                title=title,
                text=text
            )

            if result.get('success'):
                self.log_info(f"钉钉通知发送成功: {title}")
                return True
            else:
                self.log_warning(f"钉钉通知发送失败: {result.get('message')}")
                return False

        except Exception as e:
            self.log_error(f"发送钉钉通知失败: {str(e)}", exc_info=True)
            return False

    def _get_notification_config(self, AliyunConfig):
        """获取通知配置"""
        config = None

        # 优先使用指定的配置ID
        if self.notification_config_id:
            try:
                config = AliyunConfig.objects.get(
                    id=self.notification_config_id,
                    dingtalk_enabled=True,
                    is_active=True
                )
                self.log_info(f"使用指定配置: {config.name}")
                return config
            except AliyunConfig.DoesNotExist:
                self.log_warning(f"指定的通知配置不存在: {self.notification_config_id}")

        # 查找默认配置
        config = AliyunConfig.objects.filter(
            dingtalk_enabled=True,
            is_active=True,
            is_default=True
        ).exclude(dingtalk_webhook='').first()

        if not config:
            config = AliyunConfig.objects.filter(
                dingtalk_enabled=True,
                is_active=True
            ).exclude(dingtalk_webhook='').first()

        if config:
            self.log_info(f"使用配置: {config.name}")

        return config

    def _format_notification_message(self, asset_type: str, changes: Dict) -> tuple:
        """格式化通知消息"""
        type_name = self.ASSET_TYPE_LABELS.get(asset_type, asset_type)
        title = f"资产变化监测: {type_name}"

        text_parts = [
            f"## {title}",
            "",
            f"**监测时间**: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}",
            ""
        ]

        # 新增资产
        if changes.get('created') and self.notify_on_add:
            text_parts.append(f"### 新增资产 ({len(changes['created'])}个)")
            for item in changes['created'][:self.max_changes_per_notification]:
                name = item.get('name') or item.get('uuid', '未知')
                text_parts.append(f"- **{name}**")
            if len(changes['created']) > self.max_changes_per_notification:
                text_parts.append(f"  - ... 等共 {len(changes['created'])} 个")
            text_parts.append("")

        # 删除资产
        if changes.get('deleted') and self.notify_on_delete:
            text_parts.append(f"### 删除资产 ({len(changes['deleted'])}个)")
            for item in changes['deleted'][:self.max_changes_per_notification]:
                name = item.get('name') or item.get('uuid', '未知')
                text_parts.append(f"- **{name}**")
            if len(changes['deleted']) > self.max_changes_per_notification:
                text_parts.append(f"  - ... 等共 {len(changes['deleted'])} 个")
            text_parts.append("")

        # 变更资产
        if changes.get('modified') and self.notify_on_modify:
            text_parts.append(f"### 属性变更 ({len(changes['modified'])}个)")
            for item in changes['modified'][:self.max_changes_per_notification]:
                name = item.get('name') or item.get('uuid', '未知')
                text_parts.append(f"- **{name}**")
            if len(changes['modified']) > self.max_changes_per_notification:
                text_parts.append(f"  - ... 等共 {len(changes['modified'])} 个")
            text_parts.append("")

        text_parts.append("---")
        text_parts.append("*来自毕方安全威胁感知系统*")

        return title, "\n".join(text_parts)


# 插件元信息
PLUGIN_INFO = {
    'name': 'collect_asset_monitor',
    'type': 'collect',
    'description': '资产变化监测插件，检测云资产的变化（新增/删除）并通过钉钉推送通知。支持自动同步数据后再监测。',
    'version': '1.1.0',
    'author': 'Bifang',
    'config_schema': {
        'type': 'object',
        'properties': {
            'asset_types': {
                'type': 'string',
                'description': '要监测的资产类型，多个用逗号分隔（ecs_instance, vpc, slb, rds）',
                'default': 'ecs_instance'
            },
            'source': {
                'type': 'string',
                'description': '数据来源',
                'default': 'aliyun_ecs'
            },
            'auto_sync': {
                'type': 'boolean',
                'description': '监测前是否自动同步云上最新数据（推荐开启）',
                'default': True
            },
            'enable_dingtalk': {
                'type': 'boolean',
                'description': '是否启用钉钉通知',
                'default': True
            },
            'notify_on_add': {
                'type': 'boolean',
                'description': '新增资产时是否通知',
                'default': True
            },
            'notify_on_delete': {
                'type': 'boolean',
                'description': '删除资产时是否通知',
                'default': True
            },
            'notify_on_modify': {
                'type': 'boolean',
                'description': '属性变更时是否通知',
                'default': False
            },
            'max_changes_per_notification': {
                'type': 'integer',
                'description': '每次通知最多显示的变化数量',
                'default': 20
            },
            'notification_config_id': {
                'type': 'integer',
                'description': '通知配置ID（AliyunConfig的ID）'
            }
        }
    }
}
