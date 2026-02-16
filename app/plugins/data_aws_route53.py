"""
AWS Route53 DNS资源数据导入插件
支持导入: 托管区域(域名)、解析记录
"""
import sys
import os
import logging
import io
import json
from typing import Dict, List, Any

# 添加项目根目录到路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from app.lib.base_plugin import BasePlugin
from app.lib.db_helper import DBHelper


def _check_boto3():
    """检查boto3是否可用"""
    try:
        import boto3
        from botocore.exceptions import ClientError, BotoCoreError
        return True, boto3, ClientError, BotoCoreError
    except ImportError as e:
        logging.warning(f"boto3未安装: {e}，请使用: pip install boto3")
        return False, None, None, None


class Plugin(BasePlugin):
    """AWS Route53 DNS资源数据导入插件"""

    # 支持的资源类型
    RESOURCE_TYPES = [
        'dns_hosted_zone',  # 托管区域
        'dns_record',       # 解析记录
    ]

    # 资源类型显示名称
    RESOURCE_TYPE_LABELS = {
        'dns_hosted_zone': '托管区域',
        'dns_record': '解析记录',
    }

    def __init__(self, config=None):
        """初始化插件"""
        super().__init__(config)
        self.db_helper = DBHelper()

        # 创建日志缓冲区
        self.log_buffer = io.StringIO()
        self.log_handler = logging.StreamHandler(self.log_buffer)
        self.log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.log_handler.setLevel(logging.DEBUG)
        self.logger.addHandler(self.log_handler)
        self.logger.setLevel(logging.DEBUG)

        # 检查boto3
        boto3_available, boto3_module, ClientError, BotoCoreError = _check_boto3()
        if not boto3_available:
            raise ImportError("boto3未安装，请使用: pip install boto3")

        self.boto3 = boto3_module
        self.ClientError = ClientError
        self.BotoCoreError = BotoCoreError

        # 初始化客户端
        self.route53_client = None

        # 缓存托管区域列表
        self._hosted_zones = []

    def init_client(self):
        """初始化AWS Route53客户端"""
        if not self.config.get('access_key_id') or not self.config.get('secret_access_key'):
            raise Exception("缺少AWS认证配置: access_key_id 和 secret_access_key")

        # Route53是全局服务，但客户端仍需要指定区域
        region = self.config.get('region', 'us-east-1')
        ak = (self.config['access_key_id'] or '').strip()
        sk = (self.config['secret_access_key'] or '').strip()

        session_kwargs = {
            'aws_access_key_id': ak,
            'aws_secret_access_key': sk,
            'region_name': region,
        }

        session_token = self.config.get('session_token')
        if session_token and isinstance(session_token, str) and session_token.strip():
            session_kwargs['aws_session_token'] = session_token.strip()

        self.log_info(f"使用凭证: AK 前缀 {ak[:4] if len(ak) >= 4 else ak}***, 区域 {region}")

        try:
            session = self.boto3.Session(**session_kwargs)
            self.route53_client = session.client('route53')
        except Exception as e:
            self.log_error(f"创建AWS Route53客户端失败: {str(e)}")
            raise

        self.log_info(f"AWS Route53客户端初始化成功")

    def execute(self, *args, **kwargs):
        """执行插件，导入所有类型的Route53资源"""
        try:
            self.log_info("开始执行AWS Route53 DNS资源数据导入...")

            # 初始化客户端
            self.init_client()

            # 确定要导入的资源类型
            resource_types = kwargs.get('resource_types', self.RESOURCE_TYPES)
            if isinstance(resource_types, str):
                resource_types = [resource_types]

            total_imported = 0

            # 先导入托管区域
            if 'dns_hosted_zone' in resource_types:
                self.log_info("开始导入 托管区域...")
                try:
                    count = self.import_hosted_zones()
                    total_imported += count
                    self.log_info(f"托管区域 导入完成，共导入 {count} 条记录")
                except Exception as e:
                    self.log_error(f"导入 托管区域 失败: {str(e)}")

            # 导入解析记录
            if 'dns_record' in resource_types:
                self.log_info("开始导入 解析记录...")
                try:
                    count = self.import_records()
                    total_imported += count
                    self.log_info(f"解析记录 导入完成，共导入 {count} 条记录")
                except Exception as e:
                    self.log_error(f"导入 解析记录 失败: {str(e)}")

            self.log_info(f"AWS Route53 DNS资源数据导入完成！共导入 {total_imported} 条记录")

            return {
                'success': True,
                'message': f'成功导入 {total_imported} 条Route53资源记录',
                'data': {
                    'total_imported': total_imported,
                    'resource_types': resource_types
                }
            }

        except Exception as e:
            error_msg = f"执行插件失败: {str(e)}"
            self.log_error(error_msg)
            return {
                'success': False,
                'message': error_msg,
                'data': {}
            }

    def get_tags_dict(self, tags):
        """将AWS标签列表转换为字典"""
        if not tags:
            return {}
        return {tag['Key']: tag['Value'] for tag in tags}

    def import_hosted_zones(self):
        """导入托管区域"""
        total_count = 0
        self._hosted_zones = []  # 清空缓存

        try:
            paginator = self.route53_client.get_paginator('list_hosted_zones')

            for page in paginator.paginate():
                hosted_zones = page.get('HostedZones', [])

                for zone in hosted_zones:
                    try:
                        zone_id = zone.get('Id', '').replace('/hostedzone/', '')
                        zone_name = zone.get('Name', '').rstrip('.')

                        # 获取标签
                        tags = {}
                        try:
                            tags_response = self.route53_client.list_tags_for_resource(
                                ResourceType='hostedzone',
                                ResourceId=zone_id
                            )
                            tags = self.get_tags_dict(tags_response.get('ResourceTagSet', {}).get('Tags', []))
                        except Exception:
                            pass

                        # 获取名称服务器
                        name_servers = []
                        try:
                            ns_response = self.route53_client.get_hosted_zone(Id=zone.get('Id'))
                            name_servers = ns_response.get('DelegationSet', {}).get('NameServers', [])
                        except Exception:
                            pass

                        asset_data = {
                            'HostedZoneId': zone_id,
                            'HostedZoneArn': zone.get('Id'),
                            'DomainName': zone_name,
                            'Name': zone_name,
                            'Status': zone.get('Config', {}).get('Comment') or 'Active',
                            'CallerReference': zone.get('CallerReference'),
                            'Config': zone.get('Config', {}),
                            'ResourceRecordSetCount': zone.get('ResourceRecordSetCount', 0),
                            'DnsServers': name_servers,
                            'DnsServersStr': ', '.join(name_servers),
                            'PrivateZone': zone.get('Config', {}).get('PrivateZone', False),
                            'Tags': tags,
                        }

                        self.db_helper.save_asset(
                            asset_type='dns_hosted_zone',
                            uuid=zone_id,
                            name=zone_name,
                            source='aws_route53',
                            data=asset_data,
                            host_uuid=None
                        )

                        # 缓存托管区域信息
                        self._hosted_zones.append({
                            'Id': zone.get('Id'),
                            'ZoneId': zone_id,
                            'Name': zone_name,
                        })

                        total_count += 1

                    except Exception as e:
                        self.log_error(f"保存托管区域 {zone.get('Name')} 失败: {str(e)}")
                        continue

        except Exception as e:
            self.log_error(f"获取托管区域列表失败: {str(e)}")
            raise

        return total_count

    def import_records(self):
        """导入解析记录"""
        # 如果没有缓存托管区域，先获取
        if not self._hosted_zones:
            self._fetch_all_hosted_zones()

        total_count = 0

        for zone_info in self._hosted_zones:
            zone_id = zone_info['Id']
            zone_name = zone_info['Name']

            try:
                paginator = self.route53_client.get_paginator('list_resource_record_sets')

                for page in paginator.paginate(HostedZoneId=zone_id):
                    record_sets = page.get('ResourceRecordSets', [])

                    for record in record_sets:
                        try:
                            # 跳过NS和SOA记录（这些是系统记录）
                            # if record.get('Type') in ['NS', 'SOA']:
                            #     continue

                            record_name = record.get('Name', '').rstrip('.')
                            rr = record_name.replace(zone_name, '').rstrip('.') if record_name.endswith(zone_name) else record_name
                            if rr == '':
                                rr = '@'

                            # 获取记录值
                            values = []
                            for r in record.get('ResourceRecords', []):
                                values.append(r.get('Value', ''))

                            # 处理Alias目标
                            alias_target = record.get('AliasTarget', {})
                            if alias_target:
                                values.append(f"ALIAS: {alias_target.get('DNSName', '')}")

                            asset_data = {
                                'RecordName': record_name,
                                'RR': rr,
                                'Type': record.get('Type'),
                                'TTL': record.get('TTL'),
                                'Values': values,
                                'Value': ', '.join(values),
                                'Status': '启用',
                                'HostedZoneId': zone_info['ZoneId'],
                                'DomainName': zone_name,
                                'FullRecord': record_name,
                                'AliasTarget': alias_target if alias_target else None,
                                'HealthCheckId': record.get('HealthCheckId'),
                                'TrafficPolicyInstanceId': record.get('TrafficPolicyInstanceId'),
                                'SetIdentifier': record.get('SetIdentifier'),
                                'Weight': record.get('Weight'),
                                'Region': record.get('Region'),
                                'Failover': record.get('Failover'),
                                'MultiValueAnswer': record.get('MultiValueAnswer'),
                            }

                            # 生成唯一UUID
                            uuid_parts = [zone_info['ZoneId'], record_name, record.get('Type')]
                            if record.get('SetIdentifier'):
                                uuid_parts.append(record.get('SetIdentifier'))
                            uuid = '_'.join(uuid_parts)

                            self.db_helper.save_asset(
                                asset_type='dns_record',
                                uuid=uuid,
                                name=record_name,
                                source='aws_route53',
                                data=asset_data,
                                host_uuid=zone_info['ZoneId']  # 关联到托管区域
                            )

                            total_count += 1

                        except Exception as e:
                            self.log_error(f"保存解析记录 {record.get('Name')} 失败: {str(e)}")
                            continue

            except Exception as e:
                self.log_error(f"获取托管区域 {zone_name} 的解析记录失败: {str(e)}")
                continue

        return total_count

    def _fetch_all_hosted_zones(self):
        """获取所有托管区域列表"""
        try:
            paginator = self.route53_client.get_paginator('list_hosted_zones')

            for page in paginator.paginate():
                hosted_zones = page.get('HostedZones', [])

                for zone in hosted_zones:
                    zone_id = zone.get('Id', '').replace('/hostedzone/', '')
                    zone_name = zone.get('Name', '').rstrip('.')
                    self._hosted_zones.append({
                        'Id': zone.get('Id'),
                        'ZoneId': zone_id,
                        'Name': zone_name,
                    })

        except Exception as e:
            self.log_error(f"获取托管区域列表失败: {str(e)}")
            raise
