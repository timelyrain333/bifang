"""
阿里云ECS资源数据导入插件
支持导入: 实例(Instances)、镜像(Images)、磁盘(Disks)、快照(Snapshots)、安全组(SecurityGroups)、弹性网卡(NetworkInterfaces)
"""
import sys
import os
import logging
from typing import Dict, List, Any
from datetime import datetime

# 添加项目根目录到路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from app.lib.base_plugin import BasePlugin
from app.lib.db_helper import DBHelper

# 尝试导入阿里云ECS SDK（延迟导入，在运行时检查）
def _check_aliyun_ecs_sdk():
    """检查阿里云ECS SDK是否可用"""
    try:
        from aliyunsdkcore.client import AcsClient
        from aliyunsdkcore.acs_exception.exceptions import ClientException, ServerException
        from aliyunsdkecs.request.v20140526.DescribeInstancesRequest import DescribeInstancesRequest
        from aliyunsdkecs.request.v20140526.DescribeImagesRequest import DescribeImagesRequest
        from aliyunsdkecs.request.v20140526.DescribeDisksRequest import DescribeDisksRequest
        from aliyunsdkecs.request.v20140526.DescribeSnapshotsRequest import DescribeSnapshotsRequest
        from aliyunsdkecs.request.v20140526.DescribeSecurityGroupsRequest import DescribeSecurityGroupsRequest
        from aliyunsdkecs.request.v20140526.DescribeSecurityGroupAttributeRequest import DescribeSecurityGroupAttributeRequest
        from aliyunsdkecs.request.v20140526.DescribeNetworkInterfacesRequest import DescribeNetworkInterfacesRequest

        return True, AcsClient, ClientException, ServerException, {
            'DescribeInstancesRequest': DescribeInstancesRequest,
            'DescribeImagesRequest': DescribeImagesRequest,
            'DescribeDisksRequest': DescribeDisksRequest,
            'DescribeSnapshotsRequest': DescribeSnapshotsRequest,
            'DescribeSecurityGroupsRequest': DescribeSecurityGroupsRequest,
            'DescribeSecurityGroupAttributeRequest': DescribeSecurityGroupAttributeRequest,
            'DescribeNetworkInterfacesRequest': DescribeNetworkInterfacesRequest,
        }
    except ImportError as e:
        logging.warning(f"阿里云ECS SDK未安装: {e}，请使用: pip install aliyun-python-sdk-core aliyun-python-sdk-ecs")
        return False, None, None, None, None


class Plugin(BasePlugin):
    """阿里云ECS资源数据导入插件"""

    # 支持的资源类型
    RESOURCE_TYPES = [
        'ecs_instance',        # ECS实例
        'ecs_image',           # 镜像
        'ecs_disk',            # 磁盘
        'ecs_snapshot',        # 快照
        'ecs_security_group',  # 安全组
        'ecs_network_interface', # 弹性网卡
    ]

    # 资源类型显示名称
    RESOURCE_TYPE_LABELS = {
        'ecs_instance': 'ECS实例',
        'ecs_image': '镜像',
        'ecs_disk': '磁盘',
        'ecs_snapshot': '快照',
        'ecs_security_group': '安全组',
        'ecs_network_interface': '弹性网卡',
    }

    def __init__(self, config=None):
        """初始化插件"""
        super().__init__(config)
        self.db_helper = DBHelper()

        # 检查SDK
        self.sdk_available, self.AcsClient, self.ClientException, self.ServerException, self.request_classes = \
            _check_aliyun_ecs_sdk()

        # 初始化客户端
        self.client = None

    def init_client(self):
        """初始化阿里云ECS客户端"""
        if not self.sdk_available:
            raise Exception("阿里云ECS SDK未安装，请先安装: pip install aliyun-python-sdk-core aliyun-python-sdk-ecs")

        if not self.config.get('access_key_id') or not self.config.get('access_key_secret'):
            raise Exception("缺少阿里云认证配置: access_key_id 和 access_key_secret")

        region_id = self.config.get('region_id', 'cn-hangzhou')

        self.client = self.AcsClient(
            self.config['access_key_id'],
            self.config['access_key_secret'],
            region_id
        )

        self.log_info(f"阿里云ECS客户端初始化成功，区域: {region_id}")

    def execute(self, *args, **kwargs):
        """执行插件，导入所有类型的ECS资源"""
        try:
            self.log_info("开始执行阿里云ECS资源数据导入...")

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

            self.log_info(f"阿里云ECS资源数据导入完成！共导入 {total_imported} 条记录")

            return {
                'success': True,
                'message': f'成功导入 {total_imported} 条ECS资源记录',
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
            'ecs_instance': self.import_instances,
            'ecs_image': self.import_images,
            'ecs_disk': self.import_disks,
            'ecs_snapshot': self.import_snapshots,
            'ecs_security_group': self.import_security_groups,
            'ecs_network_interface': self.import_network_interfaces,
        }

        method = import_method_map.get(resource_type)
        if not method:
            raise Exception(f"未实现的资源类型: {resource_type}")

        return method()

    def make_request(self, request_class, params=None):
        """发起阿里云API请求"""
        if params is None:
            params = {}

        request = request_class()
        for key, value in params.items():
            if value is not None:
                # 使用 add_query_param 方法正确添加参数
                request.add_query_param(key, value)

        try:
            response = self.client.do_action_with_exception(request)
            import json
            return json.loads(response.decode('utf-8'))
        except self.ServerException as e:
            self.log_error(f"服务器异常: {e.get_error_msg()}")
            raise
        except self.ClientException as e:
            self.log_error(f"客户端异常: {e.get_error_msg()}")
            raise

    def import_instances(self):
        """导入ECS实例"""
        from django.apps import apps
        Asset = apps.get_model('app', 'Asset')

        # 分页查询参数
        params = {
            'PageSize': 100,
            'PageNumber': 1,
        }

        total_count = 0
        page_number = 1
        cloud_uuids = set()  # 收集云上所有实例的UUID

        while True:
            params['PageNumber'] = page_number
            result = self.make_request(self.request_classes['DescribeInstancesRequest'], params)

            instances = result.get('Instances', {}).get('Instance', [])
            if not instances:
                break

            for instance in instances:
                instance_id = instance.get('InstanceId')
                cloud_uuids.add(instance_id)

                try:
                    # 构造资产数据
                    asset_data = {
                        'InstanceId': instance_id,
                        'InstanceName': instance.get('InstanceName'),
                        'Status': instance.get('Status'),
                        'InstanceType': instance.get('InstanceType'),
                        'RegionId': instance.get('RegionId'),
                        'ZoneId': instance.get('ZoneId'),
                        'Cpu': instance.get('Cpu'),
                        'Memory': instance.get('Memory'),
                        'OsName': instance.get('OsName'),
                        'CreationTime': instance.get('CreationTime'),
                        'ExpiredTime': instance.get('ExpiredTime'),
                        'InstanceNetworkType': instance.get('InstanceNetworkType'),
                        'InternetMaxBandwidthOut': instance.get('InternetMaxBandwidthOut'),
                        'InternetMaxBandwidthIn': instance.get('InternetMaxBandwidthIn'),
                        # 公网IP
                        'PublicIpAddress': instance.get('PublicIpAddress', {}).get('IpAddress', []),
                        # 内网IP
                        'InnerIpAddress': instance.get('InnerIpAddress', {}).get('IpAddress', []),
                        # VPC IP
                        'VpcAttributes': instance.get('VpcAttributes', {}),
                        # 安全组
                        'SecurityGroupIds': instance.get('SecurityGroupIds', {}).get('SecurityGroupId', []),
                    }

                    # 保存到数据库
                    self.db_helper.save_asset(
                        asset_type='ecs_instance',
                        uuid=instance_id,
                        name=instance.get('InstanceName', instance_id),
                        source='aliyun_ecs',
                        data=asset_data,
                        host_uuid=None
                    )

                    total_count += 1

                except Exception as e:
                    self.log_error(f"保存实例 {instance_id} 失败: {str(e)}")
                    continue

            # 检查是否还有下一页
            total_count_in_api = int(result.get('TotalCount', 0))
            if len(instances) == 0 or total_count >= total_count_in_api:
                break

            page_number += 1

        # 清理云上已不存在的实例（删除已释放的ECS记录）
        if cloud_uuids:
            deleted_count, _ = Asset.objects.filter(
                asset_type='ecs_instance',
                source='aliyun_ecs'
            ).exclude(uuid__in=cloud_uuids).delete()

            if deleted_count > 0:
                self.log_info(f"清理了 {deleted_count} 条已释放的ECS实例记录")

        return total_count

    def import_images(self):
        """导入镜像"""
        params = {
            'PageSize': 100,
            'PageNumber': 1,
            'Status': 'Available',  # 只导入可用状态的镜像
        }

        total_count = 0
        page_number = 1

        while True:
            params['PageNumber'] = page_number
            result = self.make_request(self.request_classes['DescribeImagesRequest'], params)

            images = result.get('Images', {}).get('Image', [])
            if not images:
                break

            for image in images:
                try:
                    asset_data = {
                        'ImageId': image.get('ImageId'),
                        'ImageName': image.get('ImageName'),
                        'Status': image.get('Status'),
                        'ImageSize': image.get('ImageSize'),
                        'OSName': image.get('OSName'),
                        'Architecture': image.get('Architecture'),
                        'Description': image.get('Description'),
                        'CreationTime': image.get('CreationTime'),
                        'Platform': image.get('Platform'),
                        'ImageFamily': image.get('ImageFamily'),
                        'IsSelfShared': image.get('IsSelfShared'),
                        'Usage': image.get('Usage'),
                    }

                    self.db_helper.save_asset(
                        asset_type='ecs_image',
                        uuid=image.get('ImageId'),
                        name=image.get('ImageName', image.get('ImageId')),
                        source='aliyun_ecs',
                        data=asset_data,
                        host_uuid=None
                    )

                    total_count += 1

                except Exception as e:
                    self.log_error(f"保存镜像 {image.get('ImageId')} 失败: {str(e)}")
                    continue

            total_count_in_api = int(result.get('TotalCount', 0))
            if len(images) == 0 or total_count >= total_count_in_api:
                break

            page_number += 1

        return total_count

    def import_disks(self):
        """导入磁盘"""
        params = {
            'PageSize': 100,
            'PageNumber': 1,
        }

        total_count = 0
        page_number = 1

        while True:
            params['PageNumber'] = page_number
            result = self.make_request(self.request_classes['DescribeDisksRequest'], params)

            disks = result.get('Disks', {}).get('Disk', [])
            if not disks:
                break

            for disk in disks:
                try:
                    asset_data = {
                        'DiskId': disk.get('DiskId'),
                        'DiskName': disk.get('DiskName'),
                        'Status': disk.get('Status'),
                        'RegionId': disk.get('RegionId'),
                        'ZoneId': disk.get('ZoneId'),
                        'DiskType': disk.get('DiskType'),
                        'Category': disk.get('Category'),
                        'Size': disk.get('Size'),
                        'Device': disk.get('Device'),
                        'IOPS': disk.get('IOPS'),
                        'Bps': disk.get('Bps'),
                        'InstanceIds': disk.get('InstanceIds', {}).get('InstanceId', []),
                        'AttachedTime': disk.get('AttachedTime'),
                        'CreationTime': disk.get('CreationTime'),
                        'ExpireTime': disk.get('ExpireTime'),
                        'DiskChargeType': disk.get('DiskChargeType'),
                        'DeleteAutoSnapshot': disk.get('DeleteAutoSnapshot'),
                        'EnableAutoSnapshot': disk.get('EnableAutoSnapshot'),
                        'Encrypted': disk.get('Encrypted'),
                    }

                    self.db_helper.save_asset(
                        asset_type='ecs_disk',
                        uuid=disk.get('DiskId'),
                        name=disk.get('DiskName', disk.get('DiskId')),
                        source='aliyun_ecs',
                        data=asset_data,
                        host_uuid=None
                    )

                    total_count += 1

                except Exception as e:
                    self.log_error(f"保存磁盘 {disk.get('DiskId')} 失败: {str(e)}")
                    continue

            total_count_in_api = int(result.get('TotalCount', 0))
            if len(disks) == 0 or total_count >= total_count_in_api:
                break

            page_number += 1

        return total_count

    def import_snapshots(self):
        """导入快照"""
        params = {
            'PageSize': 100,
            'PageNumber': 1,
        }

        total_count = 0
        page_number = 1

        while True:
            params['PageNumber'] = page_number
            result = self.make_request(self.request_classes['DescribeSnapshotsRequest'], params)

            snapshots = result.get('Snapshots', {}).get('Snapshot', [])
            if not snapshots:
                break

            for snapshot in snapshots:
                try:
                    asset_data = {
                        'SnapshotId': snapshot.get('SnapshotId'),
                        'SnapshotName': snapshot.get('SnapshotName'),
                        'Status': snapshot.get('Status'),
                        'RegionId': snapshot.get('RegionId'),
                        'SourceDiskId': snapshot.get('SourceDiskId'),
                        'SourceDiskSize': snapshot.get('SourceDiskSize'),
                        'SourceDiskType': snapshot.get('SourceDiskType'),
                        'RetentionDays': snapshot.get('RetentionDays'),
                        'CreationTime': snapshot.get('CreationTime'),
                        'Progress': snapshot.get('Progress'),
                        'ProductCode': snapshot.get('ProductCode'),
                        'Usage': snapshot.get('Usage'),
                        'Description': snapshot.get('Description'),
                        'InstantAccess': snapshot.get('InstantAccess'),
                        'Encrypted': snapshot.get('Encrypted'),
                    }

                    self.db_helper.save_asset(
                        asset_type='ecs_snapshot',
                        uuid=snapshot.get('SnapshotId'),
                        name=snapshot.get('SnapshotName', snapshot.get('SnapshotId')),
                        source='aliyun_ecs',
                        data=asset_data,
                        host_uuid=None
                    )

                    total_count += 1

                except Exception as e:
                    self.log_error(f"保存快照 {snapshot.get('SnapshotId')} 失败: {str(e)}")
                    continue

            total_count_in_api = int(result.get('TotalCount', 0))
            if len(snapshots) == 0 or total_count >= total_count_in_api:
                break

            page_number += 1

        return total_count

    def import_security_groups(self):
        """导入安全组"""
        params = {}

        result = self.make_request(self.request_classes['DescribeSecurityGroupsRequest'], params)

        security_groups = result.get('SecurityGroups', {}).get('SecurityGroup', [])
        total_count = 0

        for sg in security_groups:
            try:
                # 获取安全组详细规则
                sg_rules = self.get_security_group_rules(sg.get('SecurityGroupId'))

                asset_data = {
                    'SecurityGroupId': sg.get('SecurityGroupId'),
                    'SecurityGroupName': sg.get('SecurityGroupName'),
                    'Description': sg.get('Description'),
                    'RegionId': sg.get('RegionId'),
                    'VpcId': sg.get('VpcId'),
                    'CreationTime': sg.get('CreationTime'),
                    'SecurityGroupType': sg.get('SecurityGroupType'),
                    'ServiceManaged': sg.get('ServiceManaged'),
                    'Rules': sg_rules,
                }

                self.db_helper.save_asset(
                    asset_type='ecs_security_group',
                    uuid=sg.get('SecurityGroupId'),
                    name=sg.get('SecurityGroupName', sg.get('SecurityGroupId')),
                    source='aliyun_ecs',
                    data=asset_data,
                    host_uuid=None
                )

                total_count += 1

            except Exception as e:
                self.log_error(f"保存安全组 {sg.get('SecurityGroupId')} 失败: {str(e)}")
                continue

        return total_count

    def get_security_group_rules(self, security_group_id):
        """获取安全组规则"""
        try:
            params = {'SecurityGroupId': security_group_id}
            result = self.make_request(self.request_classes['DescribeSecurityGroupAttributeRequest'], params)

            permissions = result.get('Permissions', {}).get('Permission', [])

            # 分为入方向和出方向规则
            inbound_rules = []
            outbound_rules = []

            for perm in permissions:
                rule = {
                    'IpProtocol': perm.get('IpProtocol'),
                    'PortRange': perm.get('PortRange'),
                    'SourceGroupId': perm.get('SourceGroupId'),
                    'SourceCidrIp': perm.get('SourceCidrIp'),
                    'DestGroupId': perm.get('DestGroupId'),
                    'DestCidrIp': perm.get('DestCidrIp'),
                    'Policy': perm.get('Policy'),  # accept/drop
                    'Priority': perm.get('Priority'),
                    'Direction': perm.get('Direction'),  # ingress/egress
                }

                if perm.get('Direction') == 'ingress':
                    inbound_rules.append(rule)
                else:
                    outbound_rules.append(rule)

            return {
                'inbound': inbound_rules,
                'outbound': outbound_rules
            }
        except Exception as e:
            self.log_warning(f"获取安全组 {security_group_id} 规则失败: {str(e)}")
            return {'inbound': [], 'outbound': []}

    def import_network_interfaces(self):
        """导入弹性网卡"""
        params = {
            'PageSize': 100,
            'PageNumber': 1,
        }

        total_count = 0
        page_number = 1

        while True:
            params['PageNumber'] = page_number
            result = self.make_request(self.request_classes['DescribeNetworkInterfacesRequest'], params)

            interfaces = result.get('NetworkInterfaceSets', {}).get('NetworkInterfaceSet', [])
            if not interfaces:
                break

            for interface in interfaces:
                try:
                    asset_data = {
                        'NetworkInterfaceId': interface.get('NetworkInterfaceId'),
                        'Status': interface.get('Status'),
                        'Type': interface.get('Type'),
                        'MacAddress': interface.get('MacAddress'),
                        'PrivateIpAddress': interface.get('PrivateIpAddress'),
                        'PublicIpAddress': interface.get('PublicIpAddress'),
                        'VSwitchId': interface.get('VSwitchId'),
                        'VpcId': interface.get('VpcId'),
                        'ZoneId': interface.get('ZoneId'),
                        'RegionId': interface.get('RegionId'),
                        'InstanceId': interface.get('InstanceId'),
                        'Description': interface.get('Description'),
                        'CreationTime': interface.get('CreationTime'),
                        'ServiceID': interface.get('ServiceID'),
                        'ServiceIDLength': interface.get('ServiceIDLength'),
                        'QueueNumber': interface.get('QueueNumber'),
                        'PrimaryIpAddress': interface.get('PrimaryIpAddress'),
                        'Ipv6Set': interface.get('Ipv6Set', {}).get('Ipv6Address', []),
                    }

                    self.db_helper.save_asset(
                        asset_type='ecs_network_interface',
                        uuid=interface.get('NetworkInterfaceId'),
                        name=interface.get('NetworkInterfaceId'),
                        source='aliyun_ecs',
                        data=asset_data,
                        host_uuid=interface.get('InstanceId')  # 关联到实例
                    )

                    total_count += 1

                except Exception as e:
                    self.log_error(f"保存弹性网卡 {interface.get('NetworkInterfaceId')} 失败: {str(e)}")
                    continue

            total_count_in_api = int(result.get('TotalCount', 0))
            if len(interfaces) == 0 or total_count >= total_count_in_api:
                break

            page_number += 1

        return total_count
