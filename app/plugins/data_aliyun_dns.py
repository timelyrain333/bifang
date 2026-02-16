"""
阿里云云解析DNS资源数据导入插件
支持导入: 域名、解析记录
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


# 尝试导入阿里云DNS SDK（延迟导入，在运行时检查）
def _check_aliyun_dns_sdk():
    """检查阿里云DNS SDK是否可用"""
    try:
        from aliyunsdkcore.client import AcsClient
        from aliyunsdkcore.acs_exception.exceptions import ClientException, ServerException
        from aliyunsdkalidns.request.v20150109.DescribeDomainsRequest import DescribeDomainsRequest
        from aliyunsdkalidns.request.v20150109.DescribeDomainRecordsRequest import DescribeDomainRecordsRequest

        return True, AcsClient, ClientException, ServerException, {
            'DescribeDomainsRequest': DescribeDomainsRequest,
            'DescribeDomainRecordsRequest': DescribeDomainRecordsRequest,
        }
    except ImportError as e:
        logging.warning(f"阿里云DNS SDK未安装: {e}，请使用: pip install aliyun-python-sdk-alidns")
        return False, None, None, None, None


class Plugin(BasePlugin):
    """阿里云云解析DNS资源数据导入插件"""

    # 支持的资源类型
    RESOURCE_TYPES = [
        'dns_domain',       # 域名
        'dns_record',       # 解析记录
    ]

    # 资源类型显示名称
    RESOURCE_TYPE_LABELS = {
        'dns_domain': '域名',
        'dns_record': '解析记录',
    }

    def __init__(self, config=None):
        """初始化插件"""
        super().__init__(config)
        self.db_helper = DBHelper()

        # 检查SDK
        self.sdk_available, self.AcsClient, self.ClientException, self.ServerException, self.request_classes = \
            _check_aliyun_dns_sdk()

        # 初始化客户端
        self.client = None

        # 缓存域名列表
        self._domains = []

    def init_client(self):
        """初始化阿里云DNS客户端"""
        if not self.sdk_available:
            raise Exception("阿里云DNS SDK未安装，请先安装: pip install aliyun-python-sdk-core aliyun-python-sdk-alidns")

        if not self.config.get('access_key_id') or not self.config.get('access_key_secret'):
            raise Exception("缺少阿里云认证配置: access_key_id 和 access_key_secret")

        region_id = self.config.get('region_id', 'cn-hangzhou')

        self.client = self.AcsClient(
            self.config['access_key_id'],
            self.config['access_key_secret'],
            region_id
        )

        self.log_info(f"阿里云DNS客户端初始化成功，区域: {region_id}")

    def execute(self, *args, **kwargs):
        """执行插件，导入所有类型的DNS资源"""
        try:
            self.log_info("开始执行阿里云云解析DNS资源数据导入...")

            # 初始化客户端
            self.init_client()

            # 确定要导入的资源类型
            resource_types = kwargs.get('resource_types', self.RESOURCE_TYPES)
            if isinstance(resource_types, str):
                resource_types = [resource_types]

            total_imported = 0

            # 先导入域名
            if 'dns_domain' in resource_types:
                self.log_info("开始导入 域名...")
                try:
                    count = self.import_domains()
                    total_imported += count
                    self.log_info(f"域名 导入完成，共导入 {count} 条记录")
                except Exception as e:
                    self.log_error(f"导入 域名 失败: {str(e)}")

            # 导入解析记录
            if 'dns_record' in resource_types:
                self.log_info("开始导入 解析记录...")
                try:
                    count = self.import_records()
                    total_imported += count
                    self.log_info(f"解析记录 导入完成，共导入 {count} 条记录")
                except Exception as e:
                    self.log_error(f"导入 解析记录 失败: {str(e)}")

            self.log_info(f"阿里云云解析DNS资源数据导入完成！共导入 {total_imported} 条记录")

            return {
                'success': True,
                'message': f'成功导入 {total_imported} 条DNS资源记录',
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

    def import_domains(self):
        """导入域名列表"""
        params = {
            'PageSize': 100,
            'PageNumber': 1,
        }

        total_count = 0
        page_number = 1
        self._domains = []  # 清空域名缓存

        while True:
            params['PageNumber'] = page_number
            result = self.make_request(self.request_classes['DescribeDomainsRequest'], params)

            domains = result.get('Domains', {}).get('Domain', [])
            if not domains:
                break

            for domain in domains:
                try:
                    # 构造资产数据
                    asset_data = {
                        'DomainId': domain.get('DomainId'),
                        'DomainName': domain.get('DomainName'),
                        'DnsServers': domain.get('DnsServers', {}).get('DnsServer', []),
                        'VersionCode': domain.get('VersionCode'),
                        'VersionName': domain.get('VersionName', '免费版'),
                        'Status': self._format_domain_status(domain.get('Status')),
                        'DomainStatus': domain.get('Status'),
                        'CreateTime': domain.get('CreateTime'),
                        'CreateTimeTimestamp': domain.get('CreateTimeTimestamp'),
                        'RegistrantType': domain.get('RegistrantType', 'REGISTRAR'),
                        'Remark': domain.get('Remark'),
                        'PunyCode': domain.get('PunyCode'),
                        'DnsServersStr': ','.join(domain.get('DnsServers', {}).get('DnsServer', [])),
                    }

                    # 保存到数据库
                    self.db_helper.save_asset(
                        asset_type='dns_domain',
                        uuid=domain.get('DomainId') or domain.get('DomainName'),
                        name=domain.get('DomainName'),
                        source='aliyun_dns',
                        data=asset_data,
                        host_uuid=None
                    )

                    # 缓存域名信息
                    self._domains.append({
                        'DomainName': domain.get('DomainName'),
                        'DomainId': domain.get('DomainId'),
                    })

                    total_count += 1

                except Exception as e:
                    self.log_error(f"保存域名 {domain.get('DomainName')} 失败: {str(e)}")
                    continue

            # 检查是否还有下一页
            total_count_in_api = int(result.get('TotalCount', 0))
            if len(domains) == 0 or total_count >= total_count_in_api:
                break

            page_number += 1

        return total_count

    def import_records(self):
        """导入解析记录"""
        # 如果没有缓存域名，先获取
        if not self._domains:
            self._fetch_all_domains()

        total_count = 0

        for domain_info in self._domains:
            domain_name = domain_info['DomainName']
            domain_id = domain_info.get('DomainId')

            try:
                params = {
                    'DomainName': domain_name,
                    'PageSize': 500,
                    'PageNumber': 1,
                }

                page_number = 1
                while True:
                    params['PageNumber'] = page_number
                    result = self.make_request(self.request_classes['DescribeDomainRecordsRequest'], params)

                    records = result.get('DomainRecords', {}).get('Record', [])
                    if not records:
                        break

                    for record in records:
                        try:
                            asset_data = {
                                'RecordId': record.get('RecordId'),
                                'RR': record.get('RR'),
                                'Type': record.get('Type'),
                                'Value': record.get('Value'),
                                'TTL': record.get('TTL'),
                                'Priority': record.get('Priority'),
                                'Line': record.get('Line'),
                                'LineName': record.get('Line'),
                                'Status': self._format_record_status(record.get('Status')),
                                'RecordStatus': record.get('Status'),
                                'Locked': record.get('Locked', False),
                                'DomainName': domain_name,
                                'DomainId': domain_id,
                                'FullRecord': f"{record.get('RR')}.{domain_name}" if record.get('RR') != '@' else domain_name,
                                'Weight': record.get('Weight'),
                                'Remark': record.get('Remark'),
                                'StatusReason': record.get('StatusReason'),
                            }

                            # 生成唯一UUID
                            uuid = record.get('RecordId') or f"{domain_name}_{record.get('RR')}_{record.get('Type')}_{record.get('Line')}"

                            self.db_helper.save_asset(
                                asset_type='dns_record',
                                uuid=uuid,
                                name=f"{record.get('RR')}.{domain_name}" if record.get('RR') != '@' else domain_name,
                                source='aliyun_dns',
                                data=asset_data,
                                host_uuid=domain_id  # 关联到域名
                            )

                            total_count += 1

                        except Exception as e:
                            self.log_error(f"保存解析记录 {record.get('RR')}.{domain_name} 失败: {str(e)}")
                            continue

                    # 检查下一页
                    total_count_in_api = int(result.get('TotalCount', 0))
                    if len(records) == 0 or page_number * 500 >= total_count_in_api:
                        break
                    page_number += 1

            except Exception as e:
                self.log_error(f"获取域名 {domain_name} 的解析记录失败: {str(e)}")
                continue

        return total_count

    def _fetch_all_domains(self):
        """获取所有域名列表"""
        params = {
            'PageSize': 100,
            'PageNumber': 1,
        }

        page_number = 1
        while True:
            params['PageNumber'] = page_number
            result = self.make_request(self.request_classes['DescribeDomainsRequest'], params)

            domains = result.get('Domains', {}).get('Domain', [])
            if not domains:
                break

            for domain in domains:
                self._domains.append({
                    'DomainName': domain.get('DomainName'),
                    'DomainId': domain.get('DomainId'),
                })

            total_count_in_api = int(result.get('TotalCount', 0))
            if len(domains) == 0 or len(self._domains) >= total_count_in_api:
                break

            page_number += 1

    def _format_domain_status(self, status):
        """格式化域名状态"""
        if not status:
            return 'Unknown'

        status_map = {
            '1': '未实名认证',
            '2': '实名认证审核中',
            '3': '实名认证失败',
            '4': '正常',
            '5': '域名锁定',
            '6': '域名过期',
        }

        return status_map.get(str(status), status)

    def _format_record_status(self, status):
        """格式化解析记录状态"""
        if not status:
            return 'Unknown'

        status_map = {
            'ENABLE': '启用',
            'DISABLE': '暂停',
        }

        return status_map.get(str(status).upper(), status)
