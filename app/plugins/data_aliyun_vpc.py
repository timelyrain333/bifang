"""
阿里云VPC网络资源数据导入插件
支持导入: VPC实例、交换机(vSwitch)、路由表、NAT网关、IPv4网关、VPC对等连接
"""
import sys
import os
import logging
import json
import time
from typing import Dict, List, Any

# 添加项目根目录到路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from app.lib.base_plugin import BasePlugin
from app.lib.db_helper import DBHelper


# 尝试导入阿里云VPC SDK（延迟导入，在运行时检查）
def _check_aliyun_vpc_sdk():
    """检查阿里云VPC SDK是否可用"""
    try:
        from aliyunsdkcore.client import AcsClient
        from aliyunsdkcore.acs_exception.exceptions import ClientException, ServerException
        from aliyunsdkvpc.request.v20160428.DescribeVpcsRequest import DescribeVpcsRequest
        from aliyunsdkvpc.request.v20160428.DescribeVSwitchesRequest import DescribeVSwitchesRequest
        from aliyunsdkvpc.request.v20160428.DescribeRouteTablesRequest import DescribeRouteTablesRequest
        from aliyunsdkvpc.request.v20160428.DescribeNatGatewaysRequest import DescribeNatGatewaysRequest
        # VPC对等连接API在当前SDK版本中不可用
        # from aliyunsdkvpc.request.v20160428.DescribeVpcPeerConnectionsRequest import DescribeVpcPeerConnectionsRequest
        from aliyunsdkvpc.request.v20160428.ListIpv4GatewaysRequest import ListIpv4GatewaysRequest

        return True, AcsClient, ClientException, ServerException, {
            'DescribeVpcsRequest': DescribeVpcsRequest,
            'DescribeVSwitchesRequest': DescribeVSwitchesRequest,
            'DescribeRouteTablesRequest': DescribeRouteTablesRequest,
            'DescribeNatGatewaysRequest': DescribeNatGatewaysRequest,
            'ListIpv4GatewaysRequest': ListIpv4GatewaysRequest,
        }
    except ImportError as e:
        logging.warning(f"阿里云VPC SDK未安装: {e}，请使用: pip install aliyun-python-sdk-core aliyun-python-sdk-vpc")
        return False, None, None, None, None


class Plugin(BasePlugin):
    """阿里云VPC网络资源数据导入插件"""

    # 支持的资源类型
    RESOURCE_TYPES = [
        'vpc',                  # VPC实例
        'vswitch',              # 交换机
        'route_table',          # 路由表
        'nat_gateway',          # NAT网关
        'ipv4_gateway',         # IPv4网关
        'vpc_peer_connection',  # VPC对等连接
    ]

    # 资源类型显示名称
    RESOURCE_TYPE_LABELS = {
        'vpc': 'VPC实例',
        'vswitch': '交换机',
        'route_table': '路由表',
        'nat_gateway': 'NAT网关',
        'ipv4_gateway': 'IPv4网关',
        'vpc_peer_connection': 'VPC对等连接',
    }

    def __init__(self, config=None):
        """初始化插件"""
        super().__init__(config)
        self.db_helper = DBHelper()

        # 检查SDK
        self.sdk_available, self.AcsClient, self.ClientException, self.ServerException, self.request_classes = \
            _check_aliyun_vpc_sdk()

        # 初始化客户端
        self.client = None

    def init_client(self):
        """初始化阿里云VPC客户端"""
        if not self.sdk_available:
            raise Exception("阿里云VPC SDK未安装，请先安装: pip install aliyun-python-sdk-core aliyun-python-sdk-vpc")

        if not self.config.get('access_key_id') or not self.config.get('access_key_secret'):
            raise Exception("缺少阿里云认证配置: access_key_id 和 access_key_secret")

        region_id = self.config.get('region_id', 'cn-hangzhou')

        self.client = self.AcsClient(
            self.config['access_key_id'],
            self.config['access_key_secret'],
            region_id
        )

        self.log_info(f"阿里云VPC客户端初始化成功，区域: {region_id}")

    def execute(self, *args, **kwargs):
        """执行插件，导入所有类型的VPC资源"""
        try:
            self.log_info("开始执行阿里云VPC资源数据导入...")

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

            self.log_info(f"阿里云VPC资源数据导入完成！共导入 {total_imported} 条记录")

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
            'vswitch': self.import_vswitches,
            'route_table': self.import_route_tables,
            'nat_gateway': self.import_nat_gateways,
            'ipv4_gateway': self.import_ipv4_gateways,
            'vpc_peer_connection': self.import_vpc_peer_connections,
        }

        method = import_method_map.get(resource_type)
        if not method:
            raise Exception(f"未实现的资源类型: {resource_type}")

        return method()

    def make_request(self, request_class, params=None, max_retries=3):
        """发起阿里云API请求，支持重试机制"""
        if params is None:
            params = {}

        for attempt in range(max_retries):
            try:
                request = request_class()
                for key, value in params.items():
                    if value is not None:
                        setattr(request, key, value)

                response = self.client.do_action_with_exception(request)
                return json.loads(response.decode('utf-8'))

            except self.ServerException as e:
                error_code = e.get_error_code()
                error_msg = e.get_error_msg()

                # 限流错误，使用指数退避
                if error_code == 'Throttling' or 'throttling' in error_msg.lower():
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        self.log_warning(f"API限流，等待 {wait_time} 秒后重试 (尝试 {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        continue

                self.log_error(f"服务器异常: {error_msg}")
                if attempt == max_retries - 1:
                    raise

            except self.ClientException as e:
                self.log_error(f"客户端异常: {e.get_error_msg()}")
                raise

            except Exception as e:
                self.log_error(f"未知异常: {str(e)}")
                if attempt == max_retries - 1:
                    raise

        raise Exception(f"请求失败，已重试 {max_retries} 次")

    def import_vpcs(self):
        """导入VPC实例"""
        params = {
            'PageSize': 100,
            'PageNumber': 1,
        }

        total_count = 0
        page_number = 1

        while True:
            params['PageNumber'] = page_number
            result = self.make_request(self.request_classes['DescribeVpcsRequest'], params)

            vpcs = result.get('Vpcs', {}).get('Vpc', [])
            if not vpcs:
                break

            for vpc in vpcs:
                try:
                    # 构造资产数据
                    asset_data = {
                        'VpcId': vpc.get('VpcId'),
                        'VpcName': vpc.get('VpcName'),
                        'Status': vpc.get('Status'),
                        'CidrBlock': vpc.get('CidrBlock'),
                        'RegionId': vpc.get('RegionId'),
                        'CreationTime': vpc.get('CreationTime'),
                        'IsDefault': vpc.get('IsDefault'),
                        'VSwitchIds': vpc.get('VSwitchIds', {}).get('VSwitchId', []),
                        'UserCidrs': vpc.get('UserCidrs', []),
                        'NatGatewayIds': vpc.get('NatGatewayIds', []),
                        'RouteTableIds': vpc.get('RouteTableIds', {}).get('RouteTableId', []),
                        'DhcpOptionsSetId': vpc.get('DhcpOptionsSet', {}).get('DhcpOptionsId'),
                        'NetworkType': vpc.get('NetworkType'),
                        'ResourceGroupId': vpc.get('ResourceGroupId'),
                        'Description': vpc.get('Description'),
                        'Ipv6CidrBlock': vpc.get('Ipv6CidrBlock'),
                    }

                    # 保存到数据库
                    self.db_helper.save_asset(
                        asset_type='vpc',
                        uuid=vpc.get('VpcId'),
                        name=vpc.get('VpcName', vpc.get('VpcId')),
                        source='aliyun_vpc',
                        data=asset_data,
                        host_uuid=None
                    )

                    total_count += 1

                except Exception as e:
                    self.log_error(f"保存VPC {vpc.get('VpcId')} 失败: {str(e)}")
                    continue

            # 检查是否还有下一页
            total_count_in_api = int(result.get('TotalCount', 0))
            if len(vpcs) == 0 or total_count >= total_count_in_api:
                break

            page_number += 1

        return total_count

    def import_vswitches(self):
        """导入交换机"""
        params = {
            'PageSize': 100,
            'PageNumber': 1,
        }

        total_count = 0
        page_number = 1

        while True:
            params['PageNumber'] = page_number
            result = self.make_request(self.request_classes['DescribeVSwitchesRequest'], params)

            vswitches = result.get('VSwitches', {}).get('VSwitch', [])
            if not vswitches:
                break

            for vswitch in vswitches:
                try:
                    asset_data = {
                        'VSwitchId': vswitch.get('VSwitchId'),
                        'VSwitchName': vswitch.get('VSwitchName'),
                        'Status': vswitch.get('Status'),
                        'CidrBlock': vswitch.get('CidrBlock'),
                        'VpcId': vswitch.get('VpcId'),
                        'ZoneId': vswitch.get('ZoneId'),
                        'RegionId': vswitch.get('RegionId'),
                        'AvailableIpAddressCount': vswitch.get('AvailableIpAddressCount'),
                        'TotalIpAddressCount': vswitch.get('TotalIpAddressCount', 256),
                        'Ipv6CidrBlock': vswitch.get('Ipv6CidrBlock'),
                        'CreationTime': vswitch.get('CreationTime'),
                        'Description': vswitch.get('Description'),
                        'EnableIpv6': vswitch.get('EnableIpv6'),
                        'ResourceGroupId': vswitch.get('ResourceGroupId'),
                    }

                    self.db_helper.save_asset(
                        asset_type='vswitch',
                        uuid=vswitch.get('VSwitchId'),
                        name=vswitch.get('VSwitchName', vswitch.get('VSwitchId')),
                        source='aliyun_vpc',
                        data=asset_data,
                        host_uuid=vswitch.get('VpcId')  # 关联到VPC
                    )

                    total_count += 1

                except Exception as e:
                    self.log_error(f"保存交换机 {vswitch.get('VSwitchId')} 失败: {str(e)}")
                    continue

            total_count_in_api = int(result.get('TotalCount', 0))
            if len(vswitches) == 0 or total_count >= total_count_in_api:
                break

            page_number += 1

        return total_count

    def import_route_tables(self):
        """导入路由表"""
        params = {
            'PageSize': 100,
            'PageNumber': 1,
        }

        total_count = 0
        page_number = 1

        while True:
            params['PageNumber'] = page_number
            result = self.make_request(self.request_classes['DescribeRouteTablesRequest'], params)

            route_tables = result.get('RouteTables', {}).get('RouteTable', [])
            if not route_tables:
                break

            for rt in route_tables:
                try:
                    # 获取路由条目
                    route_entries = rt.get('RouteEntrys', {}).get('RouteEntry', [])

                    asset_data = {
                        'RouteTableId': rt.get('RouteTableId'),
                        'RouteTableName': rt.get('RouteTableName'),
                        'VpcId': rt.get('VpcId'),
                        'RouteTableType': rt.get('RouteTableType'),
                        'RegionId': rt.get('RegionId'),
                        'CreationTime': rt.get('CreationTime'),
                        'Status': rt.get('Status'),
                        'ResourceGroupId': rt.get('ResourceGroupId'),
                        'Description': rt.get('Description'),
                        'RouteEntrys': route_entries,
                        'AssociationCount': len(rt.get('AssociationSet', {}).get('Association', [])),
                    }

                    self.db_helper.save_asset(
                        asset_type='route_table',
                        uuid=rt.get('RouteTableId'),
                        name=rt.get('RouteTableName', rt.get('RouteTableId')),
                        source='aliyun_vpc',
                        data=asset_data,
                        host_uuid=rt.get('VpcId')  # 关联到VPC
                    )

                    total_count += 1

                except Exception as e:
                    self.log_error(f"保存路由表 {rt.get('RouteTableId')} 失败: {str(e)}")
                    continue

            total_count_in_api = int(result.get('TotalCount', 0))
            if len(route_tables) == 0 or total_count >= total_count_in_api:
                break

            page_number += 1

        return total_count

    def import_nat_gateways(self):
        """导入NAT网关"""
        params = {
            'PageSize': 100,
            'PageNumber': 1,
        }

        total_count = 0
        page_number = 1

        while True:
            params['PageNumber'] = page_number
            result = self.make_request(self.request_classes['DescribeNatGatewaysRequest'], params)

            nat_gateways = result.get('NatGateways', {}).get('NatGateway', [])
            if not nat_gateways:
                break

            for nat in nat_gateways:
                try:
                    # 获取SNAT和DNAT条目
                    snat_table = nat.get('SnatTableIds', {}).get('SnatTableId', [])
                    forward_table = nat.get('ForwardTableIds', {}).get('ForwardTableId', [])

                    asset_data = {
                        'NatGatewayId': nat.get('NatGatewayId'),
                        'Name': nat.get('Name'),
                        'Status': nat.get('Status'),
                        'VpcId': nat.get('VpcId'),
                        'RegionId': nat.get('RegionId'),
                        'Spec': nat.get('Spec'),
                        'NatType': nat.get('NatType'),
                        'CreateTime': nat.get('CreateTime'),
                        'ExpiredTime': nat.get('ExpiredTime'),
                        'IpList': nat.get('IpList', []),
                        'BandwidthPackageIds': nat.get('BandwidthPackageIds', []),
                        'ChargeType': nat.get('ChargeType'),
                        'Description': nat.get('Description'),
                        'ResourceGroupId': nat.get('ResourceGroupId'),
                        'SnatTableIds': snat_table,
                        'ForwardTableIds': forward_table,
                        'EipBindMode': nat.get('EipBindMode'),
                        'NetworkType': nat.get('NetworkType'),
                    }

                    self.db_helper.save_asset(
                        asset_type='nat_gateway',
                        uuid=nat.get('NatGatewayId'),
                        name=nat.get('Name', nat.get('NatGatewayId')),
                        source='aliyun_vpc',
                        data=asset_data,
                        host_uuid=nat.get('VpcId')  # 关联到VPC
                    )

                    total_count += 1

                except Exception as e:
                    self.log_error(f"保存NAT网关 {nat.get('NatGatewayId')} 失败: {str(e)}")
                    continue

            total_count_in_api = int(result.get('TotalCount', 0))
            if len(nat_gateways) == 0 or total_count >= total_count_in_api:
                break

            page_number += 1

        return total_count

    def import_ipv4_gateways(self):
        """导入IPv4网关"""
        params = {
            'MaxResult': 100,
            'NextToken': None,
        }

        total_count = 0

        while True:
            result = self.make_request(self.request_classes['ListIpv4GatewaysRequest'], params)

            gateways = result.get('Ipv4Gateways', {}).get('Ipv4Gateway', [])
            if not gateways:
                break

            for gw in gateways:
                try:
                    asset_data = {
                        'Ipv4GatewayId': gw.get('Ipv4GatewayId'),
                        'Ipv4GatewayName': gw.get('Ipv4GatewayName'),
                        'Status': gw.get('Status'),
                        'VpcId': gw.get('VpcId'),
                        'RegionId': gw.get('RegionId'),
                        'Enabled': gw.get('Enabled'),
                        'CreateTime': gw.get('CreateTime'),
                        'IpCount': gw.get('IpCount'),
                        'ActiveIpCount': gw.get('ActiveIpCount'),
                        'RouteTableId': gw.get('RouteTableId'),
                        'Description': gw.get('Description'),
                        'ResourceGroupId': gw.get('ResourceGroupId'),
                    }

                    self.db_helper.save_asset(
                        asset_type='ipv4_gateway',
                        uuid=gw.get('Ipv4GatewayId'),
                        name=gw.get('Ipv4GatewayName', gw.get('Ipv4GatewayId')),
                        source='aliyun_vpc',
                        data=asset_data,
                        host_uuid=gw.get('VpcId')  # 关联到VPC
                    )

                    total_count += 1

                except Exception as e:
                    self.log_error(f"保存IPv4网关 {gw.get('Ipv4GatewayId')} 失败: {str(e)}")
                    continue

            # 检查是否有下一页
            next_token = result.get('NextToken')
            if not next_token:
                break
            params['NextToken'] = next_token

        return total_count

    def import_vpc_peer_connections(self):
        """导入VPC对等连接 - 当前SDK版本不支持此API"""
        self.log_warning("VPC对等连接API在当前SDK版本中不可用，跳过此资源类型")
        return 0
