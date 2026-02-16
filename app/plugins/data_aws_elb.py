"""
AWS 负载均衡(ELB)数据导入插件
支持导入: ALB/NLB/GLB负载均衡器、目标组、监听器、目标
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
    """AWS 负载均衡(ELB)数据导入插件"""

    # 支持的资源类型
    RESOURCE_TYPES = [
        'load_balancer',    # 负载均衡器 (ALB/NLB/GLB)
        'target_group',     # 目标组
        'listener',         # 监听器
        'target',           # 目标
    ]

    # 资源类型显示名称
    RESOURCE_TYPE_LABELS = {
        'load_balancer': '负载均衡器',
        'target_group': '目标组',
        'listener': '监听器',
        'target': '目标',
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
        self.elbv2_client = None

    def init_client(self):
        """初始化AWS ELB客户端"""
        if not self.config.get('access_key_id') or not self.config.get('secret_access_key'):
            raise Exception("缺少AWS认证配置: access_key_id 和 secret_access_key")

        region = self.config.get('region', 'ap-northeast-1')
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
            self.elbv2_client = session.client('elbv2')
        except Exception as e:
            self.log_error(f"创建AWS ELB客户端失败: {str(e)}")
            raise

        self.log_info(f"AWS ELB客户端初始化成功，区域: {region}")

    def execute(self, *args, **kwargs):
        """执行插件，导入所有类型的负载均衡资源"""
        try:
            self.log_info("开始执行AWS负载均衡数据导入...")

            # 初始化客户端
            self.init_client()

            # 确定要导入的资源类型
            resource_types = kwargs.get('resource_types', self.RESOURCE_TYPES)
            if isinstance(resource_types, str):
                resource_types = [resource_types]

            total_imported = 0

            for resource_type in resource_types:
                if resource_type not in self.RESOURCE_TYPES:
                    self.log_warning(f"不支持的资源类型: {resource_type}，跳过")
                    continue

                self.log_info(f"开始导入 {self.RESOURCE_TYPE_LABELS.get(resource_type, resource_type)}...")

                try:
                    count = self.import_resource_type(resource_type)
                    total_imported += count
                    self.log_info(f"{self.RESOURCE_TYPE_LABELS.get(resource_type, resource_type)} 导入完成，共导入 {count} 条记录")
                except Exception as e:
                    self.log_error(f"导入 {resource_type} 失败: {str(e)}")
                    continue

            self.log_info(f"AWS负载均衡数据导入完成！共导入 {total_imported} 条记录")

            return {
                'success': True,
                'message': f'成功导入 {total_imported} 条负载均衡资源记录',
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

    def import_resource_type(self, resource_type):
        """导入指定类型的资源"""
        import_method_map = {
            'load_balancer': self.import_load_balancers,
            'target_group': self.import_target_groups,
            'listener': self.import_listeners,
            'target': self.import_targets,
        }

        method = import_method_map.get(resource_type)
        if not method:
            raise Exception(f"未实现的资源类型: {resource_type}")

        return method()

    def get_tags_dict(self, tags):
        """将AWS标签列表转换为字典"""
        if not tags:
            return {}
        return {tag['Key']: tag['Value'] for tag in tags}

    def get_tag_name(self, tags):
        """从标签中获取Name"""
        if not tags:
            return None
        for tag in tags:
            if tag['Key'] == 'Name':
                return tag['Value']
        return None

    def import_load_balancers(self):
        """导入负载均衡器"""
        total_count = 0

        try:
            paginator = self.elbv2_client.get_paginator('describe_load_balancers')

            for page in paginator.paginate():
                load_balancers = page.get('LoadBalancers', [])

                for lb in load_balancers:
                    try:
                        tags = []
                        try:
                            tags_response = self.elbv2_client.describe_tags(
                                ResourceArns=[lb.get('LoadBalancerArn')]
                            )
                            tag_descriptions = tags_response.get('TagDescriptions', [])
                            if tag_descriptions:
                                tags = tag_descriptions[0].get('Tags', [])
                        except Exception:
                            pass

                        tags_dict = self.get_tags_dict(tags)
                        name = self.get_tag_name(tags) or lb.get('LoadBalancerName')

                        # 获取可用区信息
                        availability_zones = lb.get('AvailabilityZones', [])
                        az_names = [az.get('ZoneName') for az in availability_zones]

                        asset_data = {
                            'LoadBalancerArn': lb.get('LoadBalancerArn'),
                            'LoadBalancerName': lb.get('LoadBalancerName'),
                            'DNSName': lb.get('DNSName'),
                            'CanonicalHostedZoneId': lb.get('CanonicalHostedZoneId'),
                            'CreatedTime': lb.get('CreatedTime').isoformat() if lb.get('CreatedTime') else None,
                            'Scheme': lb.get('Scheme'),
                            'VpcId': lb.get('VpcId'),
                            'State': lb.get('State', {}).get('Code', 'unknown'),
                            'Status': lb.get('State', {}).get('Code', 'unknown').title(),
                            'Type': lb.get('Type'),  # application, network, gateway
                            'IpAddressType': lb.get('IpAddressType'),
                            'AvailabilityZones': az_names,
                            'RegionId': self.elbv2_client.meta.region_name,
                            'Tags': tags_dict,
                        }

                        self.db_helper.save_asset(
                            asset_type='load_balancer',
                            uuid=lb.get('LoadBalancerArn'),
                            name=name,
                            source='aws_elb',
                            data=asset_data,
                            host_uuid=lb.get('VpcId')
                        )

                        total_count += 1

                    except Exception as e:
                        self.log_error(f"保存负载均衡器 {lb.get('LoadBalancerName')} 失败: {str(e)}")
                        continue

        except Exception as e:
            self.log_error(f"获取负载均衡器列表失败: {str(e)}")
            raise

        return total_count

    def import_target_groups(self):
        """导入目标组"""
        total_count = 0

        try:
            paginator = self.elbv2_client.get_paginator('describe_target_groups')

            for page in paginator.paginate():
                target_groups = page.get('TargetGroups', [])

                for tg in target_groups:
                    try:
                        tags = []
                        try:
                            tags_response = self.elbv2_client.describe_tags(
                                ResourceArns=[tg.get('TargetGroupArn')]
                            )
                            tag_descriptions = tags_response.get('TagDescriptions', [])
                            if tag_descriptions:
                                tags = tag_descriptions[0].get('Tags', [])
                        except Exception:
                            pass

                        tags_dict = self.get_tags_dict(tags)
                        name = self.get_tag_name(tags) or tg.get('TargetGroupName')

                        asset_data = {
                            'TargetGroupArn': tg.get('TargetGroupArn'),
                            'TargetGroupName': tg.get('TargetGroupName'),
                            'Protocol': tg.get('Protocol'),
                            'Port': tg.get('Port'),
                            'VpcId': tg.get('VpcId'),
                            'HealthCheckProtocol': tg.get('HealthCheckProtocol'),
                            'HealthCheckPort': tg.get('HealthCheckPort'),
                            'HealthCheckEnabled': tg.get('HealthCheckEnabled'),
                            'HealthCheckIntervalSeconds': tg.get('HealthCheckIntervalSeconds'),
                            'HealthCheckTimeoutSeconds': tg.get('HealthCheckTimeoutSeconds'),
                            'HealthyThresholdCount': tg.get('HealthyThresholdCount'),
                            'UnhealthyThresholdCount': tg.get('UnhealthyThresholdCount'),
                            'HealthCheckPath': tg.get('HealthCheckPath'),
                            'Matcher': tg.get('Matcher'),
                            'LoadBalancerArns': tg.get('LoadBalancerArns', []),
                            'TargetType': tg.get('TargetType'),  # instance, ip, lambda, alb
                            'ProtocolVersion': tg.get('ProtocolVersion'),
                            'RegionId': self.elbv2_client.meta.region_name,
                            'Tags': tags_dict,
                        }

                        self.db_helper.save_asset(
                            asset_type='target_group',
                            uuid=tg.get('TargetGroupArn'),
                            name=name,
                            source='aws_elb',
                            data=asset_data,
                            host_uuid=tg.get('VpcId')
                        )

                        total_count += 1

                    except Exception as e:
                        self.log_error(f"保存目标组 {tg.get('TargetGroupName')} 失败: {str(e)}")
                        continue

        except Exception as e:
            self.log_error(f"获取目标组列表失败: {str(e)}")
            raise

        return total_count

    def import_listeners(self):
        """导入监听器"""
        total_count = 0

        try:
            # 先获取所有负载均衡器
            lb_paginator = self.elbv2_client.get_paginator('describe_load_balancers')

            for lb_page in lb_paginator.paginate():
                load_balancers = lb_page.get('LoadBalancers', [])

                for lb in load_balancers:
                    try:
                        # 获取该LB的所有监听器
                        listener_paginator = self.elbv2_client.get_paginator('describe_listeners')

                        for listener_page in listener_paginator.paginate(LoadBalancerArn=lb.get('LoadBalancerArn')):
                            listeners = listener_page.get('Listeners', [])

                            for listener in listeners:
                                try:
                                    asset_data = {
                                        'ListenerArn': listener.get('ListenerArn'),
                                        'LoadBalancerArn': listener.get('LoadBalancerArn'),
                                        'Port': listener.get('Port'),
                                        'Protocol': listener.get('Protocol'),
                                        'SslPolicy': listener.get('SslPolicy'),
                                        'Certificates': listener.get('Certificates', []),
                                        'DefaultActions': listener.get('DefaultActions', []),
                                        'AlpnPolicy': listener.get('AlpnPolicy', []),
                                        'LoadBalancerName': lb.get('LoadBalancerName'),
                                        'RegionId': self.elbv2_client.meta.region_name,
                                    }

                                    self.db_helper.save_asset(
                                        asset_type='listener',
                                        uuid=listener.get('ListenerArn'),
                                        name=f"{listener.get('Protocol')}:{listener.get('Port')}",
                                        source='aws_elb',
                                        data=asset_data,
                                        host_uuid=lb.get('LoadBalancerArn')
                                    )

                                    total_count += 1

                                except Exception as e:
                                    self.log_error(f"保存监听器 {listener.get('ListenerArn')} 失败: {str(e)}")
                                    continue

                    except Exception as e:
                        self.log_error(f"获取LB {lb.get('LoadBalancerName')} 的监听器失败: {str(e)}")
                        continue

        except Exception as e:
            self.log_error(f"获取监听器列表失败: {str(e)}")
            raise

        return total_count

    def import_targets(self):
        """导入目标（目标组中的实例）"""
        total_count = 0

        try:
            # 获取所有目标组
            tg_paginator = self.elbv2_client.get_paginator('describe_target_groups')

            for tg_page in tg_paginator.paginate():
                target_groups = tg_page.get('TargetGroups', [])

                for tg in target_groups:
                    try:
                        # 获取目标组的健康状态
                        health_response = self.elbv2_client.describe_target_health(
                            TargetGroupArn=tg.get('TargetGroupArn')
                        )

                        target_health_descriptions = health_response.get('TargetHealthDescriptions', [])

                        for thd in target_health_descriptions:
                            try:
                                target = thd.get('Target', {})
                                health = thd.get('TargetHealth', {})

                                asset_data = {
                                    'TargetId': target.get('Id'),
                                    'TargetPort': target.get('Port'),
                                    'TargetAvailabilityZone': target.get('AvailabilityZone'),
                                    'HealthCheckPort': thd.get('HealthCheckPort'),
                                    'HealthStatus': health.get('State', 'unknown'),
                                    'Status': health.get('State', 'unknown').title(),
                                    'HealthCheckDescription': health.get('Description'),
                                    'HealthCheckReason': health.get('Reason'),
                                    'TargetGroupArn': tg.get('TargetGroupArn'),
                                    'TargetGroupName': tg.get('TargetGroupName'),
                                    'RegionId': self.elbv2_client.meta.region_name,
                                }

                                target_uuid = f"{tg.get('TargetGroupArn')}:{target.get('Id')}:{target.get('Port')}"

                                self.db_helper.save_asset(
                                    asset_type='target',
                                    uuid=target_uuid,
                                    name=target.get('Id'),
                                    source='aws_elb',
                                    data=asset_data,
                                    host_uuid=tg.get('TargetGroupArn')
                                )

                                total_count += 1

                            except Exception as e:
                                self.log_error(f"保存目标 {target.get('Id')} 失败: {str(e)}")
                                continue

                    except Exception as e:
                        self.log_error(f"获取目标组 {tg.get('TargetGroupName')} 的目标失败: {str(e)}")
                        continue

        except Exception as e:
            self.log_error(f"获取目标列表失败: {str(e)}")
            raise

        return total_count