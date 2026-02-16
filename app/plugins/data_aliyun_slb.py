"""
阿里云负载均衡(SLB/ALB)数据导入插件
支持导入: CLB实例、ALB实例、监听器、后端服务器
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


# 尝试导入阿里云SLB SDK
def _check_aliyun_slb_sdk():
    """检查阿里云SLB SDK是否可用"""
    try:
        from aliyunsdkcore.client import AcsClient
        from aliyunsdkcore.acs_exception.exceptions import ClientException, ServerException
        # SLB (CLB) SDK
        from aliyunsdkslb.request.v20140515.DescribeLoadBalancersRequest import DescribeLoadBalancersRequest
        from aliyunsdkslb.request.v20140515.DescribeLoadBalancerListenersRequest import DescribeLoadBalancerListenersRequest
        from aliyunsdkslb.request.v20140515.DescribeLoadBalancerAttributeRequest import DescribeLoadBalancerAttributeRequest

        return True, AcsClient, ClientException, ServerException, {
            'DescribeLoadBalancersRequest': DescribeLoadBalancersRequest,
            'DescribeLoadBalancerListenersRequest': DescribeLoadBalancerListenersRequest,
            'DescribeLoadBalancerAttributeRequest': DescribeLoadBalancerAttributeRequest,
        }
    except ImportError as e:
        logging.warning(f"阿里云SLB SDK未安装: {e}，请使用: pip install aliyun-python-sdk-slb")
        return False, None, None, None, None


class Plugin(BasePlugin):
    """阿里云负载均衡数据导入插件"""

    # 支持的资源类型
    RESOURCE_TYPES = [
        'clb',           # 传统型负载均衡 (CLB)
        'listener',      # 监听器
        'backend_server', # 后端服务器
    ]

    # 资源类型显示名称
    RESOURCE_TYPE_LABELS = {
        'clb': 'CLB实例',
        'listener': '监听器',
        'backend_server': '后端服务器',
    }

    def __init__(self, config=None):
        """初始化插件"""
        super().__init__(config)
        self.db_helper = DBHelper()

        # 检查SDK
        self.sdk_available, self.AcsClient, self.ClientException, self.ServerException, self.request_classes = \
            _check_aliyun_slb_sdk()

        # 初始化客户端
        self.client = None

    def init_client(self):
        """初始化阿里云SLB客户端"""
        if not self.sdk_available:
            raise Exception("阿里云SLB SDK未安装，请先安装: pip install aliyun-python-sdk-slb")

        if not self.config.get('access_key_id') or not self.config.get('access_key_secret'):
            raise Exception("缺少阿里云认证配置: access_key_id 和 access_key_secret")

        region_id = self.config.get('region_id', 'cn-hangzhou')

        self.client = self.AcsClient(
            self.config['access_key_id'],
            self.config['access_key_secret'],
            region_id
        )

        self.log_info(f"阿里云SLB客户端初始化成功，区域: {region_id}")

    def execute(self, *args, **kwargs):
        """执行插件，导入所有类型的负载均衡资源"""
        try:
            self.log_info("开始执行阿里云负载均衡数据导入...")

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

            self.log_info(f"阿里云负载均衡数据导入完成！共导入 {total_imported} 条记录")

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
            'clb': self.import_clbs,
            'listener': self.import_listeners,
            'backend_server': self.import_backend_servers,
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

    def import_clbs(self):
        """导入CLB实例"""
        params = {
            'PageSize': 100,
            'PageNumber': 1,
        }

        total_count = 0
        page_number = 1

        while True:
            params['PageNumber'] = page_number
            result = self.make_request(self.request_classes['DescribeLoadBalancersRequest'], params)

            clbs = result.get('LoadBalancers', {}).get('LoadBalancer', [])
            if not clbs:
                break

            for clb in clbs:
                try:
                    # 获取详细属性
                    detail_params = {'LoadBalancerId': clb.get('LoadBalancerId')}
                    try:
                        detail = self.make_request(self.request_classes['DescribeLoadBalancerAttributeRequest'], detail_params)
                    except Exception as e:
                        self.log_warning(f"获取CLB {clb.get('LoadBalancerId')} 详细属性失败: {str(e)}")
                        detail = {}

                    asset_data = {
                        'LoadBalancerId': clb.get('LoadBalancerId'),
                        'LoadBalancerName': clb.get('LoadBalancerName'),
                        'LoadBalancerStatus': clb.get('LoadBalancerStatus'),
                        'Status': clb.get('LoadBalancerStatus', 'unknown').title(),
                        'Address': clb.get('Address'),
                        'AddressType': clb.get('AddressType'),
                        'AddressIPVersion': clb.get('AddressIPVersion'),
                        'VpcId': clb.get('VpcId'),
                        'VSwitchId': clb.get('VSwitchId'),
                        'NetworkType': clb.get('NetworkType'),
                        'RegionId': clb.get('RegionId'),
                        'ZoneId': clb.get('ZoneId'),
                        'MasterZoneId': clb.get('MasterZoneId'),
                        'SlaveZoneId': clb.get('SlaveZoneId'),
                        'LoadBalancerSpec': clb.get('LoadBalancerSpec'),
                        'CreateTime': clb.get('CreateTime'),
                        'PayType': clb.get('PayType'),
                        'ResourceGroupId': clb.get('ResourceGroupId'),
                        'DNSName': detail.get('DNSName'),
                        'ListenerPorts': detail.get('ListenerPorts', {}).get('ListenerPort', []),
                        'BackendServers': detail.get('BackendServers', {}).get('BackendServer', []),
                    }

                    self.db_helper.save_asset(
                        asset_type='clb',
                        uuid=clb.get('LoadBalancerId'),
                        name=clb.get('LoadBalancerName', clb.get('LoadBalancerId')),
                        source='aliyun_slb',
                        data=asset_data,
                        host_uuid=clb.get('VpcId')
                    )

                    total_count += 1

                except Exception as e:
                    self.log_error(f"保存CLB {clb.get('LoadBalancerId')} 失败: {str(e)}")
                    continue

            # 检查是否还有下一页
            total_count_in_api = int(result.get('TotalCount', 0))
            if len(clbs) == 0 or total_count >= total_count_in_api:
                break

            page_number += 1

        return total_count

    def import_listeners(self):
        """导入监听器"""
        # 先获取所有CLB
        clb_params = {'PageSize': 100, 'PageNumber': 1}
        total_count = 0

        while True:
            clb_result = self.make_request(self.request_classes['DescribeLoadBalancersRequest'], clb_params)
            clbs = clb_result.get('LoadBalancers', {}).get('LoadBalancer', [])

            if not clbs:
                break

            for clb in clbs:
                try:
                    # 获取该CLB的所有监听器
                    listener_params = {
                        'LoadBalancerId': clb.get('LoadBalancerId'),
                    }

                    listener_result = self.make_request(
                        self.request_classes['DescribeLoadBalancerListenersRequest'],
                        listener_params
                    )

                    listeners = listener_result.get('Listeners', {}).get('Listener', [])

                    for listener in listeners:
                        try:
                            asset_data = {
                                'ListenerId': listener.get('ListenerPort'),
                                'ListenerPort': listener.get('ListenerPort'),
                                'ListenerProtocol': listener.get('ListenerProtocol'),
                                'Status': listener.get('Status', 'unknown').title(),
                                'Bandwidth': listener.get('Bandwidth'),
                                'Scheduler': listener.get('Scheduler'),
                                'PersistenceTimeout': listener.get('PersistenceTimeout'),
                                'HealthCheck': listener.get('HealthCheck', {}),
                                'LoadBalancerId': clb.get('LoadBalancerId'),
                                'LoadBalancerName': clb.get('LoadBalancerName'),
                                'RegionId': clb.get('RegionId'),
                                'VpcId': clb.get('VpcId'),
                            }

                            listener_uuid = f"{clb.get('LoadBalancerId')}:{listener.get('ListenerPort')}:{listener.get('ListenerProtocol')}"

                            self.db_helper.save_asset(
                                asset_type='listener',
                                uuid=listener_uuid,
                                name=f"{listener.get('ListenerProtocol')}:{listener.get('ListenerPort')}",
                                source='aliyun_slb',
                                data=asset_data,
                                host_uuid=clb.get('LoadBalancerId')
                            )

                            total_count += 1

                        except Exception as e:
                            self.log_error(f"保存监听器 {listener.get('ListenerPort')} 失败: {str(e)}")
                            continue

                except Exception as e:
                    self.log_error(f"获取CLB {clb.get('LoadBalancerId')} 的监听器失败: {str(e)}")
                    continue

            # 检查是否还有下一页CLB
            if len(clbs) < 100:
                break
            clb_params['PageNumber'] += 1

        return total_count

    def import_backend_servers(self):
        """导入后端服务器"""
        # 先获取所有CLB，然后获取后端服务器
        clb_params = {'PageSize': 100, 'PageNumber': 1}
        total_count = 0

        while True:
            clb_result = self.make_request(self.request_classes['DescribeLoadBalancersRequest'], clb_params)
            clbs = clb_result.get('LoadBalancers', {}).get('LoadBalancer', [])

            if not clbs:
                break

            for clb in clbs:
                try:
                    # 获取CLB详细属性中的后端服务器
                    detail_params = {'LoadBalancerId': clb.get('LoadBalancerId')}
                    detail = self.make_request(self.request_classes['DescribeLoadBalancerAttributeRequest'], detail_params)

                    backend_servers = detail.get('BackendServers', {}).get('BackendServer', [])

                    for server in backend_servers:
                        try:
                            asset_data = {
                                'ServerId': server.get('ServerId'),
                                'ServerIp': server.get('ServerIp'),
                                'Port': server.get('Port'),
                                'Weight': server.get('Weight'),
                                'Type': server.get('Type'),
                                'Status': server.get('ServerHealthStatus', 'unknown').title(),
                                'Description': server.get('Description'),
                                'LoadBalancerId': clb.get('LoadBalancerId'),
                                'LoadBalancerName': clb.get('LoadBalancerName'),
                                'RegionId': clb.get('RegionId'),
                                'VpcId': clb.get('VpcId'),
                            }

                            server_uuid = f"{clb.get('LoadBalancerId')}:{server.get('ServerId')}:{server.get('Port')}"

                            self.db_helper.save_asset(
                                asset_type='backend_server',
                                uuid=server_uuid,
                                name=server.get('ServerId'),
                                source='aliyun_slb',
                                data=asset_data,
                                host_uuid=clb.get('LoadBalancerId')
                            )

                            total_count += 1

                        except Exception as e:
                            self.log_error(f"保存后端服务器 {server.get('ServerId')} 失败: {str(e)}")
                            continue

                except Exception as e:
                    self.log_error(f"获取CLB {clb.get('LoadBalancerId')} 的后端服务器失败: {str(e)}")
                    continue

            # 检查是否还有下一页CLB
            if len(clbs) < 100:
                break
            clb_params['PageNumber'] += 1

        return total_count