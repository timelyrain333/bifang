"""
AWS VPC网络资源数据导入插件
支持导入: VPC实例、子网(Subnet)、路由表、NAT网关、Internet网关、VPC对等连接
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
    """AWS VPC网络资源数据导入插件"""

    # 支持的资源类型
    RESOURCE_TYPES = [
        'vpc',                  # VPC实例
        'subnet',               # 子网
        'route_table',          # 路由表
        'nat_gateway',          # NAT网关
        'internet_gateway',     # Internet网关
        'vpc_peer_connection',  # VPC对等连接
    ]

    # 资源类型显示名称
    RESOURCE_TYPE_LABELS = {
        'vpc': 'VPC实例',
        'subnet': '子网',
        'route_table': '路由表',
        'nat_gateway': 'NAT网关',
        'internet_gateway': 'Internet网关',
        'vpc_peer_connection': 'VPC对等连接',
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
        self.ec2_client = None

    def init_client(self):
        """初始化AWS EC2客户端"""
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
            self.ec2_client = session.client('ec2')
        except Exception as e:
            self.log_error(f"创建AWS EC2客户端失败: {str(e)}")
            raise

        self.log_info(f"AWS EC2客户端初始化成功，区域: {region}")

    def execute(self, *args, **kwargs):
        """执行插件，导入所有类型的VPC资源"""
        try:
            self.log_info("开始执行AWS VPC资源数据导入...")

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

            self.log_info(f"AWS VPC资源数据导入完成！共导入 {total_imported} 条记录")

            return {
                'success': True,
                'message': f'成功导入 {total_imported} 条VPC资源记录',
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
            'vpc': self.import_vpcs,
            'subnet': self.import_subnets,
            'route_table': self.import_route_tables,
            'nat_gateway': self.import_nat_gateways,
            'internet_gateway': self.import_internet_gateways,
            'vpc_peer_connection': self.import_vpc_peering_connections,
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

    def import_vpcs(self):
        """导入VPC实例"""
        total_count = 0

        try:
            paginator = self.ec2_client.get_paginator('describe_vpcs')

            for page in paginator.paginate():
                vpcs = page.get('Vpcs', [])

                for vpc in vpcs:
                    try:
                        tags = self.get_tags_dict(vpc.get('Tags', []))
                        name = self.get_tag_name(vpc.get('Tags', [])) or vpc.get('VpcId')

                        # 获取CIDR块
                        cidr_blocks = vpc.get('CidrBlockAssociationSet', [])
                        primary_cidr = vpc.get('CidrBlock', '')

                        asset_data = {
                            'VpcId': vpc.get('VpcId'),
                            'VpcName': name,
                            'Status': vpc.get('State', 'unknown').title(),
                            'CidrBlock': primary_cidr,
                            'CidrBlockAssociations': [cb.get('CidrBlock') for cb in cidr_blocks],
                            'RegionId': self.ec2_client.meta.region_name,
                            'IsDefault': vpc.get('IsDefault', False),
                            'InstanceTenancy': vpc.get('InstanceTenancy'),
                            'OwnerId': vpc.get('OwnerId'),
                            'Ipv6CidrBlocks': vpc.get('Ipv6CidrBlockAssociationSet', []),
                            'Tags': tags,
                            'DhcpOptionsId': vpc.get('DhcpOptionsId'),
                        }

                        self.db_helper.save_asset(
                            asset_type='vpc',
                            uuid=vpc.get('VpcId'),
                            name=name,
                            source='aws_vpc',
                            data=asset_data,
                            host_uuid=None
                        )

                        total_count += 1

                    except Exception as e:
                        self.log_error(f"保存VPC {vpc.get('VpcId')} 失败: {str(e)}")
                        continue

        except Exception as e:
            self.log_error(f"获取VPC列表失败: {str(e)}")
            raise

        return total_count

    def import_subnets(self):
        """导入子网"""
        total_count = 0

        try:
            paginator = self.ec2_client.get_paginator('describe_subnets')

            for page in paginator.paginate():
                subnets = page.get('Subnets', [])

                for subnet in subnets:
                    try:
                        tags = self.get_tags_dict(subnet.get('Tags', []))
                        name = self.get_tag_name(subnet.get('Tags', [])) or subnet.get('SubnetId')

                        asset_data = {
                            'SubnetId': subnet.get('SubnetId'),
                            'SubnetName': name,
                            'Status': subnet.get('State', 'unknown').title(),
                            'CidrBlock': subnet.get('CidrBlock'),
                            'VpcId': subnet.get('VpcId'),
                            'AvailabilityZone': subnet.get('AvailabilityZone'),
                            'AvailabilityZoneId': subnet.get('AvailabilityZoneId'),
                            'RegionId': self.ec2_client.meta.region_name,
                            'AvailableIpAddressCount': subnet.get('AvailableIpAddressCount'),
                            'DefaultForAz': subnet.get('DefaultForAz', False),
                            'MapPublicIpOnLaunch': subnet.get('MapPublicIpOnLaunch', False),
                            'Ipv6CidrBlock': subnet.get('Ipv6CidrBlockAssociationSet', [{}])[0].get('Ipv6CidrBlock') if subnet.get('Ipv6CidrBlockAssociationSet') else None,
                            'OwnerId': subnet.get('OwnerId'),
                            'Tags': tags,
                        }

                        self.db_helper.save_asset(
                            asset_type='subnet',
                            uuid=subnet.get('SubnetId'),
                            name=name,
                            source='aws_vpc',
                            data=asset_data,
                            host_uuid=subnet.get('VpcId')
                        )

                        total_count += 1

                    except Exception as e:
                        self.log_error(f"保存子网 {subnet.get('SubnetId')} 失败: {str(e)}")
                        continue

        except Exception as e:
            self.log_error(f"获取子网列表失败: {str(e)}")
            raise

        return total_count

    def import_route_tables(self):
        """导入路由表"""
        total_count = 0

        try:
            paginator = self.ec2_client.get_paginator('describe_route_tables')

            for page in paginator.paginate():
                route_tables = page.get('RouteTables', [])

                for rt in route_tables:
                    try:
                        tags = self.get_tags_dict(rt.get('Tags', []))
                        name = self.get_tag_name(rt.get('Tags', [])) or rt.get('RouteTableId')

                        # 获取路由条目
                        routes = []
                        for route in rt.get('Routes', []):
                            routes.append({
                                'DestinationCidrBlock': route.get('DestinationCidrBlock'),
                                'DestinationIpv6CidrBlock': route.get('DestinationIpv6CidrBlock'),
                                'GatewayId': route.get('GatewayId'),
                                'InstanceId': route.get('InstanceId'),
                                'NatGatewayId': route.get('NatGatewayId'),
                                'TransitGatewayId': route.get('TransitGatewayId'),
                                'VpcPeeringConnectionId': route.get('VpcPeeringConnectionId'),
                                'State': route.get('State'),
                                'Origin': route.get('Origin'),
                            })

                        # 获取关联的子网
                        associations = []
                        for assoc in rt.get('Associations', []):
                            associations.append({
                                'SubnetId': assoc.get('SubnetId'),
                                'RouteTableAssociationId': assoc.get('RouteTableAssociationId'),
                                'Main': assoc.get('Main', False),
                            })

                        asset_data = {
                            'RouteTableId': rt.get('RouteTableId'),
                            'RouteTableName': name,
                            'VpcId': rt.get('VpcId'),
                            'RouteTableType': 'Main' if any(a.get('Main') for a in rt.get('Associations', [])) else 'Custom',
                            'RegionId': self.ec2_client.meta.region_name,
                            'OwnerId': rt.get('OwnerId'),
                            'Routes': routes,
                            'Associations': associations,
                            'Tags': tags,
                        }

                        self.db_helper.save_asset(
                            asset_type='route_table',
                            uuid=rt.get('RouteTableId'),
                            name=name,
                            source='aws_vpc',
                            data=asset_data,
                            host_uuid=rt.get('VpcId')
                        )

                        total_count += 1

                    except Exception as e:
                        self.log_error(f"保存路由表 {rt.get('RouteTableId')} 失败: {str(e)}")
                        continue

        except Exception as e:
            self.log_error(f"获取路由表列表失败: {str(e)}")
            raise

        return total_count

    def import_nat_gateways(self):
        """导入NAT网关"""
        total_count = 0

        try:
            paginator = self.ec2_client.get_paginator('describe_nat_gateways')

            for page in paginator.paginate():
                nat_gateways = page.get('NatGateways', [])

                for nat in nat_gateways:
                    try:
                        tags = self.get_tags_dict(nat.get('Tags', []))
                        name = self.get_tag_name(nat.get('Tags', [])) or nat.get('NatGatewayId')

                        # 获取公网IP地址
                        nat_addresses = []
                        for addr in nat.get('NatGatewayAddresses', []):
                            nat_addresses.append({
                                'PublicIp': addr.get('PublicIp'),
                                'AllocationId': addr.get('AllocationId'),
                                'PrivateIp': addr.get('PrivateIp'),
                                'NetworkInterfaceId': addr.get('NetworkInterfaceId'),
                            })

                        asset_data = {
                            'NatGatewayId': nat.get('NatGatewayId'),
                            'Name': name,
                            'Status': nat.get('State', 'unknown').title(),
                            'VpcId': nat.get('VpcId'),
                            'SubnetId': nat.get('SubnetId'),
                            'RegionId': self.ec2_client.meta.region_name,
                            'CreateTime': nat.get('CreateTime').isoformat() if nat.get('CreateTime') else None,
                            'NatGatewayAddresses': nat_addresses,
                            'ConnectivityType': nat.get('ConnectivityType'),
                            'Tags': tags,
                        }

                        self.db_helper.save_asset(
                            asset_type='nat_gateway',
                            uuid=nat.get('NatGatewayId'),
                            name=name,
                            source='aws_vpc',
                            data=asset_data,
                            host_uuid=nat.get('VpcId')
                        )

                        total_count += 1

                    except Exception as e:
                        self.log_error(f"保存NAT网关 {nat.get('NatGatewayId')} 失败: {str(e)}")
                        continue

        except Exception as e:
            self.log_error(f"获取NAT网关列表失败: {str(e)}")
            raise

        return total_count

    def import_internet_gateways(self):
        """导入Internet网关"""
        total_count = 0

        try:
            paginator = self.ec2_client.get_paginator('describe_internet_gateways')

            for page in paginator.paginate():
                igws = page.get('InternetGateways', [])

                for igw in igws:
                    try:
                        tags = self.get_tags_dict(igw.get('Tags', []))
                        name = self.get_tag_name(igw.get('Tags', [])) or igw.get('InternetGatewayId')

                        # 获取附件信息
                        attachments = []
                        vpc_id = None
                        for attach in igw.get('Attachments', []):
                            attachments.append({
                                'VpcId': attach.get('VpcId'),
                                'State': attach.get('State'),
                            })
                            if attach.get('VpcId') and not vpc_id:
                                vpc_id = attach.get('VpcId')

                        asset_data = {
                            'InternetGatewayId': igw.get('InternetGatewayId'),
                            'Name': name,
                            'Status': 'Attached' if attachments else 'Detached',
                            'VpcId': vpc_id,
                            'RegionId': self.ec2_client.meta.region_name,
                            'OwnerId': igw.get('OwnerId'),
                            'Attachments': attachments,
                            'Tags': tags,
                        }

                        self.db_helper.save_asset(
                            asset_type='internet_gateway',
                            uuid=igw.get('InternetGatewayId'),
                            name=name,
                            source='aws_vpc',
                            data=asset_data,
                            host_uuid=vpc_id
                        )

                        total_count += 1

                    except Exception as e:
                        self.log_error(f"保存Internet网关 {igw.get('InternetGatewayId')} 失败: {str(e)}")
                        continue

        except Exception as e:
            self.log_error(f"获取Internet网关列表失败: {str(e)}")
            raise

        return total_count

    def import_vpc_peering_connections(self):
        """导入VPC对等连接"""
        total_count = 0

        try:
            paginator = self.ec2_client.get_paginator('describe_vpc_peering_connections')

            for page in paginator.paginate():
                connections = page.get('VpcPeeringConnections', [])

                for conn in connections:
                    try:
                        tags = self.get_tags_dict(conn.get('Tags', []))
                        name = self.get_tag_name(conn.get('Tags', [])) or conn.get('VpcPeeringConnectionId')

                        # 获取接受端和发起端信息
                        accepter_vpc = conn.get('AccepterVpcInfo', {})
                        requester_vpc = conn.get('RequesterVpcInfo', {})

                        asset_data = {
                            'VpcPeeringConnectionId': conn.get('VpcPeeringConnectionId'),
                            'Name': name,
                            'Status': conn.get('Status', {}).get('Code', 'unknown').title(),
                            'AccepterVpcId': accepter_vpc.get('VpcId'),
                            'AccepterRegionId': accepter_vpc.get('Region'),
                            'AccepterOwnerId': accepter_vpc.get('OwnerId'),
                            'AccepterCidrBlock': accepter_vpc.get('CidrBlock'),
                            'RequesterVpcId': requester_vpc.get('VpcId'),
                            'RequesterRegionId': requester_vpc.get('Region'),
                            'RequesterOwnerId': requester_vpc.get('OwnerId'),
                            'RequesterCidrBlock': requester_vpc.get('CidrBlock'),
                            'RegionId': self.ec2_client.meta.region_name,
                            'CreationTime': conn.get('CreationTime').isoformat() if conn.get('CreationTime') else None,
                            'ExpirationTime': conn.get('ExpirationTime').isoformat() if conn.get('ExpirationTime') else None,
                            'Tags': tags,
                        }

                        self.db_helper.save_asset(
                            asset_type='vpc_peer_connection',
                            uuid=conn.get('VpcPeeringConnectionId'),
                            name=name,
                            source='aws_vpc',
                            data=asset_data,
                            host_uuid=None
                        )

                        total_count += 1

                    except Exception as e:
                        self.log_error(f"保存VPC对等连接 {conn.get('VpcPeeringConnectionId')} 失败: {str(e)}")
                        continue

        except Exception as e:
            self.log_error(f"获取VPC对等连接列表失败: {str(e)}")
            raise

        return total_count