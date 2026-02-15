"""
阿里云API客户端封装
"""
import logging
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.acs_exception.exceptions import ClientException, ServerException
from aliyunsdkcbn.request.v20170912 import DescribeCenBandwidthPackagesRequest
import json

logger = logging.getLogger(__name__)


class AliyunSecurityClient:
    """阿里云安全中心API客户端"""
    
    def __init__(self, access_key_id, access_key_secret, region_id='cn-hangzhou'):
        """
        初始化阿里云客户端
        
        Args:
            access_key_id: 阿里云AccessKey ID
            access_key_secret: 阿里云AccessKey Secret
            region_id: 地域ID，默认为杭州
        """
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.region_id = region_id
        self.client = AcsClient(
            access_key_id,
            access_key_secret,
            region_id
        )
    
    def _make_request(self, request, max_retries=3):
        """
        发送API请求
        
        Args:
            request: API请求对象
            max_retries: 最大重试次数
            
        Returns:
            dict: API响应数据
        """
        for attempt in range(max_retries):
            try:
                response = self.client.do_action_with_exception(request)
                return json.loads(response)
            except (ClientException, ServerException) as e:
                logger.error(f'阿里云API请求失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}')
                if attempt == max_retries - 1:
                    raise
                import time
                time.sleep(2 ** attempt)  # 指数退避
            except Exception as e:
                logger.error(f'请求处理异常: {str(e)}')
                raise
    
    def get_servers(self, page_size=100, current_page=1):
        """
        获取服务器列表
        
        Args:
            page_size: 每页大小
            current_page: 当前页码
            
        Returns:
            dict: 服务器列表数据
        """
        from aliyunsdksas.request.v20181203 import DescribeCloudCenterInstancesRequest
        
        request = DescribeCloudCenterInstancesRequest.DescribeCloudCenterInstancesRequest()
        request.set_PageSize(page_size)
        request.set_CurrentPage(current_page)
        
        return self._make_request(request)
    
    def get_assets_by_type(self, asset_type, page_size=100, current_page=1):
        """
        根据资产类型获取资产列表
        注意: 阿里云安全中心不同资产类型使用不同的API，这里提供统一接口
        
        Args:
            asset_type: 资产类型
            page_size: 每页大小
            current_page: 当前页码
            
        Returns:
            dict: 资产列表数据
        """
        # 这里根据不同资产类型调用不同的API
        # 由于阿里云API较多，这里提供一个基础框架
        # 实际使用时需要根据具体的API文档实现
        
        api_mapping = {
            'server': self.get_servers,
            # 其他资产类型的API映射
            # 'account': self.get_accounts,
            # 'port': self.get_ports,
            # ...
        }
        
        if asset_type in api_mapping:
            return api_mapping[asset_type](page_size, current_page)
        else:
            raise ValueError(f'不支持的资产类型: {asset_type}')








