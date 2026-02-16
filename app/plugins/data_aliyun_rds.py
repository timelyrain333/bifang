"""
阿里云RDS数据库资源数据导入插件
支持导入: RDS实例、只读实例、数据库、数据库账号
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


# 尝试导入阿里云RDS SDK（延迟导入，在运行时检查）
def _check_aliyun_rds_sdk():
    """检查阿里云RDS SDK是否可用"""
    try:
        from aliyunsdkcore.client import AcsClient
        from aliyunsdkcore.acs_exception.exceptions import ClientException, ServerException
        from aliyunsdkrds.request.v20140815.DescribeDBInstancesRequest import DescribeDBInstancesRequest
        from aliyunsdkrds.request.v20140815.DescribeDatabasesRequest import DescribeDatabasesRequest
        from aliyunsdkrds.request.v20140815.DescribeAccountsRequest import DescribeAccountsRequest

        return True, AcsClient, ClientException, ServerException, {
            'DescribeDBInstancesRequest': DescribeDBInstancesRequest,
            'DescribeDatabasesRequest': DescribeDatabasesRequest,
            'DescribeAccountsRequest': DescribeAccountsRequest,
        }
    except ImportError as e:
        logging.warning(f"阿里云RDS SDK未安装: {e}，请使用: pip install aliyun-python-sdk-core aliyun-python-sdk-rds")
        return False, None, None, None, None


class Plugin(BasePlugin):
    """阿里云RDS数据库资源数据导入插件"""

    # 支持的资源类型
    RESOURCE_TYPES = [
        'rds_instance',         # RDS实例（主实例）
        'rds_readonly_instance', # 只读实例
        'rds_database',         # 数据库
        'rds_account',          # 数据库账号
    ]

    # 资源类型显示名称
    RESOURCE_TYPE_LABELS = {
        'rds_instance': 'RDS实例',
        'rds_readonly_instance': '只读实例',
        'rds_database': '数据库',
        'rds_account': '数据库账号',
    }

    def __init__(self, config=None):
        """初始化插件"""
        super().__init__(config)
        self.db_helper = DBHelper()

        # 检查SDK
        self.sdk_available, self.AcsClient, self.ClientException, self.ServerException, self.request_classes = \
            _check_aliyun_rds_sdk()

        # 初始化客户端
        self.client = None

        # 缓存实例列表用于导入数据库和账号
        self._instance_ids = []

    def init_client(self):
        """初始化阿里云RDS客户端"""
        if not self.sdk_available:
            raise Exception("阿里云RDS SDK未安装，请先安装: pip install aliyun-python-sdk-core aliyun-python-sdk-rds")

        if not self.config.get('access_key_id') or not self.config.get('access_key_secret'):
            raise Exception("缺少阿里云认证配置: access_key_id 和 access_key_secret")

        region_id = self.config.get('region_id', 'cn-hangzhou')

        self.client = self.AcsClient(
            self.config['access_key_id'],
            self.config['access_key_secret'],
            region_id
        )

        self.log_info(f"阿里云RDS客户端初始化成功，区域: {region_id}")

    def execute(self, *args, **kwargs):
        """执行插件，导入所有类型的RDS资源"""
        try:
            self.log_info("开始执行阿里云RDS数据库资源数据导入...")

            # 初始化客户端
            self.init_client()

            # 确定要导入的资源类型
            resource_types = kwargs.get('resource_types', self.RESOURCE_TYPES)
            if isinstance(resource_types, str):
                resource_types = [resource_types]

            total_imported = 0

            # 先导入实例，获取实例ID列表
            if 'rds_instance' in resource_types or 'rds_readonly_instance' in resource_types:
                self.log_info("开始导入 RDS实例...")
                try:
                    count = self.import_rds_instances()
                    total_imported += count
                    self.log_info(f"RDS实例 导入完成，共导入 {count} 条记录")
                except Exception as e:
                    self.log_error(f"导入 RDS实例 失败: {str(e)}")

            # 导入数据库（需要实例ID）
            if 'rds_database' in resource_types:
                self.log_info("开始导入 数据库...")
                try:
                    count = self.import_databases()
                    total_imported += count
                    self.log_info(f"数据库 导入完成，共导入 {count} 条记录")
                except Exception as e:
                    self.log_error(f"导入 数据库 失败: {str(e)}")

            # 导入账号（需要实例ID）
            if 'rds_account' in resource_types:
                self.log_info("开始导入 数据库账号...")
                try:
                    count = self.import_accounts()
                    total_imported += count
                    self.log_info(f"数据库账号 导入完成，共导入 {count} 条记录")
                except Exception as e:
                    self.log_error(f"导入 数据库账号 失败: {str(e)}")

            self.log_info(f"阿里云RDS数据库资源数据导入完成！共导入 {total_imported} 条记录")

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

    def import_rds_instances(self):
        """导入RDS实例（包括主实例和只读实例）"""
        params = {
            'PageSize': 100,
            'PageNumber': 1,
        }

        total_count = 0
        page_number = 1
        self._instance_ids = []  # 清空实例ID缓存

        while True:
            params['PageNumber'] = page_number
            result = self.make_request(self.request_classes['DescribeDBInstancesRequest'], params)

            instances = result.get('Items', {}).get('DBInstance', [])
            if not instances:
                break

            for instance in instances:
                try:
                    # 判断实例类型
                    db_instance_type = instance.get('DBInstanceType', 'Primary')
                    is_readonly = db_instance_type == 'Readonly' or instance.get('ReadonlyInstanceSQLDelayedTime') is not None

                    # 获取连接信息
                    connection_string = instance.get('ConnectionString', '')
                    port = instance.get('Port', '')

                    # 构造资产数据
                    asset_data = {
                        'DBInstanceId': instance.get('DBInstanceId'),
                        'DBInstanceName': instance.get('DBInstanceName'),
                        'DBInstanceStatus': instance.get('DBInstanceStatus'),
                        'Status': self._format_status(instance.get('DBInstanceStatus', 'unknown')),
                        'Engine': instance.get('Engine'),
                        'EngineVersion': instance.get('EngineVersion'),
                        'DBInstanceClass': instance.get('DBInstanceClass'),
                        'DBInstanceType': db_instance_type,
                        'DBInstanceNetType': instance.get('DBInstanceNetType'),
                        'RegionId': instance.get('RegionId'),
                        'ZoneId': instance.get('ZoneId'),
                        'VpcId': instance.get('VpcId'),
                        'VSwitchId': instance.get('VSwitchId'),
                        'ConnectionString': connection_string,
                        'Port': port,
                        'DBInstanceStorage': instance.get('DBInstanceStorage'),
                        'DBInstanceCPU': instance.get('DBInstanceCPU'),
                        'DBInstanceMemory': instance.get('DBInstanceMemory'),
                        'CreationTime': instance.get('CreationTime'),
                        'ExpireTime': instance.get('ExpireTime'),
                        'PayType': instance.get('PayType'),
                        'LockMode': instance.get('LockMode'),
                        'ReadonlyInstanceSQLDelayedTime': instance.get('ReadonlyInstanceSQLDelayedTime'),
                        'MasterInstanceId': instance.get('MasterInstanceId'),
                        'ResourceGroupId': instance.get('ResourceGroupId'),
                        'Category': instance.get('Category'),
                        'StorageType': instance.get('StorageType'),
                        'DBInstanceDescription': instance.get('DBInstanceDescription'),
                    }

                    # 确定资产类型
                    asset_type = 'rds_readonly_instance' if is_readonly else 'rds_instance'

                    # 保存到数据库
                    self.db_helper.save_asset(
                        asset_type=asset_type,
                        uuid=instance.get('DBInstanceId'),
                        name=instance.get('DBInstanceName') or instance.get('DBInstanceId'),
                        source='aliyun_rds',
                        data=asset_data,
                        host_uuid=instance.get('VpcId')  # 关联到VPC
                    )

                    # 缓存实例ID
                    self._instance_ids.append(instance.get('DBInstanceId'))

                    total_count += 1

                except Exception as e:
                    self.log_error(f"保存RDS实例 {instance.get('DBInstanceId')} 失败: {str(e)}")
                    continue

            # 检查是否还有下一页
            total_count_in_api = int(result.get('TotalCount', 0))
            if len(instances) == 0 or total_count >= total_count_in_api:
                break

            page_number += 1

        return total_count

    def import_databases(self):
        """导入数据库"""
        if not self._instance_ids:
            # 如果没有缓存实例ID，先获取所有实例
            self._fetch_all_instance_ids()

        total_count = 0

        for instance_id in self._instance_ids:
            try:
                params = {
                    'DBInstanceId': instance_id,
                    'PageSize': 100,
                    'PageNumber': 1,
                }

                page_number = 1
                while True:
                    params['PageNumber'] = page_number
                    result = self.make_request(self.request_classes['DescribeDatabasesRequest'], params)

                    databases = result.get('Databases', {}).get('Database', [])
                    if not databases:
                        break

                    for db in databases:
                        try:
                            asset_data = {
                                'DBName': db.get('DBName'),
                                'DBInstanceId': instance_id,
                                'Engine': db.get('Engine'),
                                'DBStatus': db.get('DBStatus'),
                                'Status': self._format_status(db.get('DBStatus', 'unknown')),
                                'CharacterSetName': db.get('CharacterSetName'),
                                'DBDescription': db.get('DBDescription'),
                                'Accounts': db.get('Accounts', {}).get('AccountPrivilegeInfo', []),
                            }

                            # 生成唯一UUID
                            uuid = f"{instance_id}_{db.get('DBName')}"

                            self.db_helper.save_asset(
                                asset_type='rds_database',
                                uuid=uuid,
                                name=db.get('DBName'),
                                source='aliyun_rds',
                                data=asset_data,
                                host_uuid=instance_id  # 关联到RDS实例
                            )

                            total_count += 1

                        except Exception as e:
                            self.log_error(f"保存数据库 {db.get('DBName')} 失败: {str(e)}")
                            continue

                    # 检查下一页
                    total_count_in_api = int(result.get('TotalCount', 0))
                    if len(databases) == 0 or page_number * 100 >= total_count_in_api:
                        break
                    page_number += 1

            except Exception as e:
                self.log_error(f"获取实例 {instance_id} 的数据库列表失败: {str(e)}")
                continue

        return total_count

    def import_accounts(self):
        """导入数据库账号"""
        if not self._instance_ids:
            # 如果没有缓存实例ID，先获取所有实例
            self._fetch_all_instance_ids()

        total_count = 0

        for instance_id in self._instance_ids:
            try:
                params = {
                    'DBInstanceId': instance_id,
                    'PageSize': 100,
                    'PageNumber': 1,
                }

                page_number = 1
                while True:
                    params['PageNumber'] = page_number
                    result = self.make_request(self.request_classes['DescribeAccountsRequest'], params)

                    accounts = result.get('Accounts', {}).get('Account', [])
                    if not accounts:
                        break

                    for account in accounts:
                        try:
                            asset_data = {
                                'AccountName': account.get('AccountName'),
                                'DBInstanceId': instance_id,
                                'AccountStatus': account.get('AccountStatus'),
                                'Status': self._format_status(account.get('AccountStatus', 'unknown')),
                                'AccountType': account.get('AccountType'),
                                'PrivExceeded': account.get('PrivExceeded'),
                                'DatabasePrivileges': account.get('DatabasePrivileges', {}).get('DatabasePrivilege', []),
                                'Description': account.get('Description'),
                            }

                            # 生成唯一UUID
                            uuid = f"{instance_id}_{account.get('AccountName')}"

                            self.db_helper.save_asset(
                                asset_type='rds_account',
                                uuid=uuid,
                                name=account.get('AccountName'),
                                source='aliyun_rds',
                                data=asset_data,
                                host_uuid=instance_id  # 关联到RDS实例
                            )

                            total_count += 1

                        except Exception as e:
                            self.log_error(f"保存账号 {account.get('AccountName')} 失败: {str(e)}")
                            continue

                    # 检查下一页
                    total_count_in_api = int(result.get('TotalCount', 0))
                    if len(accounts) == 0 or page_number * 100 >= total_count_in_api:
                        break
                    page_number += 1

            except Exception as e:
                self.log_error(f"获取实例 {instance_id} 的账号列表失败: {str(e)}")
                continue

        return total_count

    def _fetch_all_instance_ids(self):
        """获取所有RDS实例ID"""
        params = {
            'PageSize': 100,
            'PageNumber': 1,
        }

        page_number = 1
        while True:
            params['PageNumber'] = page_number
            result = self.make_request(self.request_classes['DescribeDBInstancesRequest'], params)

            instances = result.get('Items', {}).get('DBInstance', [])
            if not instances:
                break

            for instance in instances:
                self._instance_ids.append(instance.get('DBInstanceId'))

            total_count_in_api = int(result.get('TotalCount', 0))
            if len(instances) == 0 or len(self._instance_ids) >= total_count_in_api:
                break

            page_number += 1

    def _format_status(self, status):
        """格式化状态为统一格式"""
        if not status:
            return 'Unknown'

        status_lower = status.lower()
        status_map = {
            'running': 'Running',
            'creating': 'Creating',
            'deleting': 'Deleting',
            'rebooting': 'Rebooting',
            'migrating': 'Migrating',
            'restoring': 'Restoring',
            'backingup': 'BackingUp',
            'switching': 'Switching',
            'net_changing': 'NetChanging',
            'guard_switching': 'GuardSwitching',
            'inspecting': 'Inspecting',
            'class_changing': 'ClassChanging',
            'transing': 'Transing',
            'importing': 'Importing',
            'importing_from_oss': 'ImportingFromOSS',
            'available': 'Available',
            'active': 'Active',
        }

        return status_map.get(status_lower, status.title())
