"""
AWS RDS数据库资源数据导入插件
支持导入: RDS实例、只读副本、Aurora集群
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
    """AWS RDS数据库资源数据导入插件"""

    # 支持的资源类型
    RESOURCE_TYPES = [
        'rds_instance',     # RDS实例
        'rds_read_replica', # 只读副本
        'rds_cluster',      # Aurora集群
    ]

    # 资源类型显示名称
    RESOURCE_TYPE_LABELS = {
        'rds_instance': 'RDS实例',
        'rds_read_replica': '只读副本',
        'rds_cluster': 'Aurora集群',
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
        self.rds_client = None

    def init_client(self):
        """初始化AWS RDS客户端"""
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
            self.rds_client = session.client('rds')
        except Exception as e:
            self.log_error(f"创建AWS RDS客户端失败: {str(e)}")
            raise

        self.log_info(f"AWS RDS客户端初始化成功，区域: {region}")

    def execute(self, *args, **kwargs):
        """执行插件，导入所有类型的RDS资源"""
        try:
            self.log_info("开始执行AWS RDS数据库资源数据导入...")

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

            self.log_info(f"AWS RDS数据库资源数据导入完成！共导入 {total_imported} 条记录")

            return {
                'success': True,
                'message': f'成功导入 {total_imported} 条RDS数据库资源记录',
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
            'rds_instance': self.import_rds_instances,
            'rds_read_replica': self.import_read_replicas,
            'rds_cluster': self.import_rds_clusters,
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

    def import_rds_instances(self):
        """导入RDS实例（不包括只读副本）"""
        total_count = 0

        try:
            paginator = self.rds_client.get_paginator('describe_db_instances')

            for page in paginator.paginate():
                instances = page.get('DBInstances', [])

                for db in instances:
                    try:
                        # 跳过只读副本
                        if db.get('ReadReplicaSourceDBInstanceIdentifier'):
                            continue

                        # 跳过Aurora集群实例
                        if db.get('DBClusterIdentifier'):
                            continue

                        tags = self.get_tags_dict(db.get('TagList', []))
                        name = self.get_tag_name(db.get('TagList', [])) or db.get('DBInstanceIdentifier')

                        endpoint = db.get('Endpoint', {})
                        db_subnet_group = db.get('DBSubnetGroup', {})

                        asset_data = {
                            'DBInstanceIdentifier': db.get('DBInstanceIdentifier'),
                            'DBInstanceArn': db.get('DBInstanceArn'),
                            'DBInstanceStatus': db.get('DBInstanceStatus'),
                            'Status': self._format_status(db.get('DBInstanceStatus', 'unknown')),
                            'Engine': db.get('Engine'),
                            'EngineVersion': db.get('EngineVersion'),
                            'DBInstanceClass': db.get('DBInstanceClass'),
                            'DBInstanceType': 'Primary',
                            'RegionId': self.rds_client.meta.region_name,
                            'AvailabilityZone': db.get('AvailabilityZone'),
                            'MultiAZ': db.get('MultiAZ'),
                            'VpcId': db_subnet_group.get('VpcId'),
                            'DBSubnetGroupName': db_subnet_group.get('DBSubnetGroupName'),
                            'Endpoint': endpoint.get('Address'),
                            'Port': endpoint.get('Port'),
                            'AllocatedStorage': db.get('AllocatedStorage'),
                            'MaxAllocatedStorage': db.get('MaxAllocatedStorage'),
                            'StorageType': db.get('StorageType'),
                            'StorageEncrypted': db.get('StorageEncrypted'),
                            'KmsKeyId': db.get('KmsKeyId'),
                            'InstanceCreateTime': db.get('InstanceCreateTime').isoformat() if db.get('InstanceCreateTime') else None,
                            'DBParameterGroups': [pg.get('DBParameterGroupName') for pg in db.get('DBParameterGroups', [])],
                            'VpcSecurityGroups': [sg.get('VpcSecurityGroupId') for sg in db.get('VpcSecurityGroups', [])],
                            'DBSecurityGroups': [sg.get('DBSecurityGroupName') for sg in db.get('DBSecurityGroups', [])],
                            'IAMDBAuthenticationEnabled': db.get('IAMDBAuthenticationEnabled'),
                            'PerformanceInsightsEnabled': db.get('PerformanceInsightsEnabled'),
                            'BackupRetentionPeriod': db.get('BackupRetentionPeriod'),
                            'PreferredBackupWindow': db.get('PreferredBackupWindow'),
                            'PreferredMaintenanceWindow': db.get('PreferredMaintenanceWindow'),
                            'AutoMinorVersionUpgrade': db.get('AutoMinorVersionUpgrade'),
                            'LicenseModel': db.get('LicenseModel'),
                            'Tags': tags,
                            'PubliclyAccessible': db.get('PubliclyAccessible'),
                            'StorageThroughput': db.get('StorageThroughput'),
                            'DBName': db.get('DBName'),
                        }

                        self.db_helper.save_asset(
                            asset_type='rds_instance',
                            uuid=db.get('DBInstanceIdentifier'),
                            name=name,
                            source='aws_rds',
                            data=asset_data,
                            host_uuid=db_subnet_group.get('VpcId')
                        )

                        total_count += 1

                    except Exception as e:
                        self.log_error(f"保存RDS实例 {db.get('DBInstanceIdentifier')} 失败: {str(e)}")
                        continue

        except Exception as e:
            self.log_error(f"获取RDS实例列表失败: {str(e)}")
            raise

        return total_count

    def import_read_replicas(self):
        """导入只读副本"""
        total_count = 0

        try:
            paginator = self.rds_client.get_paginator('describe_db_instances')

            for page in paginator.paginate():
                instances = page.get('DBInstances', [])

                for db in instances:
                    try:
                        # 只处理只读副本
                        if not db.get('ReadReplicaSourceDBInstanceIdentifier'):
                            continue

                        tags = self.get_tags_dict(db.get('TagList', []))
                        name = self.get_tag_name(db.get('TagList', [])) or db.get('DBInstanceIdentifier')

                        endpoint = db.get('Endpoint', {})
                        db_subnet_group = db.get('DBSubnetGroup', {})

                        asset_data = {
                            'DBInstanceIdentifier': db.get('DBInstanceIdentifier'),
                            'DBInstanceArn': db.get('DBInstanceArn'),
                            'DBInstanceStatus': db.get('DBInstanceStatus'),
                            'Status': self._format_status(db.get('DBInstanceStatus', 'unknown')),
                            'Engine': db.get('Engine'),
                            'EngineVersion': db.get('EngineVersion'),
                            'DBInstanceClass': db.get('DBInstanceClass'),
                            'DBInstanceType': 'ReadReplica',
                            'ReadReplicaSourceDBInstanceIdentifier': db.get('ReadReplicaSourceDBInstanceIdentifier'),
                            'RegionId': self.rds_client.meta.region_name,
                            'AvailabilityZone': db.get('AvailabilityZone'),
                            'VpcId': db_subnet_group.get('VpcId'),
                            'DBSubnetGroupName': db_subnet_group.get('DBSubnetGroupName'),
                            'Endpoint': endpoint.get('Address'),
                            'Port': endpoint.get('Port'),
                            'StorageType': db.get('StorageType'),
                            'StorageEncrypted': db.get('StorageEncrypted'),
                            'InstanceCreateTime': db.get('InstanceCreateTime').isoformat() if db.get('InstanceCreateTime') else None,
                            'Tags': tags,
                            'PubliclyAccessible': db.get('PubliclyAccessible'),
                        }

                        self.db_helper.save_asset(
                            asset_type='rds_read_replica',
                            uuid=db.get('DBInstanceIdentifier'),
                            name=name,
                            source='aws_rds',
                            data=asset_data,
                            host_uuid=db_subnet_group.get('VpcId')
                        )

                        total_count += 1

                    except Exception as e:
                        self.log_error(f"保存只读副本 {db.get('DBInstanceIdentifier')} 失败: {str(e)}")
                        continue

        except Exception as e:
            self.log_error(f"获取只读副本列表失败: {str(e)}")
            raise

        return total_count

    def import_rds_clusters(self):
        """导入Aurora集群"""
        total_count = 0

        try:
            paginator = self.rds_client.get_paginator('describe_db_clusters')

            for page in paginator.paginate():
                clusters = page.get('DBClusters', [])

                for cluster in clusters:
                    try:
                        tags = self.get_tags_dict(cluster.get('TagList', []))
                        name = self.get_tag_name(cluster.get('TagList', [])) or cluster.get('DBClusterIdentifier')

                        # 获取集群成员
                        cluster_members = []
                        for member in cluster.get('DBClusterMembers', []):
                            cluster_members.append({
                                'DBInstanceIdentifier': member.get('DBInstanceIdentifier'),
                                'IsClusterWriter': member.get('IsClusterWriter'),
                                'PromotionTier': member.get('PromotionTier'),
                            })

                        # 获取端点信息
                        endpoint = cluster.get('Endpoint')
                        reader_endpoint = cluster.get('ReaderEndpoint')

                        asset_data = {
                            'DBClusterIdentifier': cluster.get('DBClusterIdentifier'),
                            'DBClusterArn': cluster.get('DBClusterArn'),
                            'Status': self._format_status(cluster.get('Status', 'unknown')),
                            'Engine': cluster.get('Engine'),
                            'EngineVersion': cluster.get('EngineVersion'),
                            'EngineMode': cluster.get('EngineMode'),
                            'RegionId': self.rds_client.meta.region_name,
                            'VpcId': cluster.get('VpcId'),
                            'DBSubnetGroup': cluster.get('DBSubnetGroup'),
                            'Endpoint': endpoint,
                            'ReaderEndpoint': reader_endpoint,
                            'Port': cluster.get('Port'),
                            'MasterUsername': cluster.get('MasterUsername'),
                            'DatabaseName': cluster.get('DatabaseName'),
                            'StorageEncrypted': cluster.get('StorageEncrypted'),
                            'KmsKeyId': cluster.get('KmsKeyId'),
                            'ClusterCreateTime': cluster.get('ClusterCreateTime').isoformat() if cluster.get('ClusterCreateTime') else None,
                            'DBClusterMembers': cluster_members,
                            'AvailabilityZones': cluster.get('AvailabilityZones', []),
                            'BackupRetentionPeriod': cluster.get('BackupRetentionPeriod'),
                            'PreferredBackupWindow': cluster.get('PreferredBackupWindow'),
                            'PreferredMaintenanceWindow': cluster.get('PreferredMaintenanceWindow'),
                            'MultiAZ': cluster.get('MultiAZ'),
                            'DeletionProtection': cluster.get('DeletionProtection'),
                            'HttpEndpointEnabled': cluster.get('HttpEndpointEnabled'),
                            'CopyTagsToSnapshot': cluster.get('CopyTagsToSnapshot'),
                            'TagList': tags,
                            'VpcSecurityGroups': [sg.get('VpcSecurityGroupId') for sg in cluster.get('VpcSecurityGroups', [])],
                            'DBClusterParameterGroup': cluster.get('DBClusterParameterGroup'),
                            'IamAuthEnabled': cluster.get('IamAuthEnabled'),
                        }

                        self.db_helper.save_asset(
                            asset_type='rds_cluster',
                            uuid=cluster.get('DBClusterIdentifier'),
                            name=name,
                            source='aws_rds',
                            data=asset_data,
                            host_uuid=cluster.get('VpcId')
                        )

                        total_count += 1

                    except Exception as e:
                        self.log_error(f"保存Aurora集群 {cluster.get('DBClusterIdentifier')} 失败: {str(e)}")
                        continue

        except Exception as e:
            self.log_error(f"获取Aurora集群列表失败: {str(e)}")
            raise

        return total_count

    def _format_status(self, status):
        """格式化状态为统一格式"""
        if not status:
            return 'Unknown'

        status_lower = status.lower()
        status_map = {
            'available': 'Available',
            'creating': 'Creating',
            'deleting': 'Deleting',
            'failed': 'Failed',
            'modifying': 'Modifying',
            'rebooting': 'Rebooting',
            'resetting-master-credentials': 'ResettingMasterCredentials',
            'scaling-compute': 'ScalingCompute',
            'starting': 'Starting',
            'stopped': 'Stopped',
            'stopping': 'Stopping',
            'storage-optimization': 'StorageOptimization',
            'upgrading': 'Upgrading',
            'inaccessible-encryption-credentials': 'InaccessibleEncryptionCredentials',
            'active': 'Active',
        }

        return status_map.get(status_lower, status.title())
