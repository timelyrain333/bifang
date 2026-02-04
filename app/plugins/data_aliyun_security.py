"""
阿里云安全中心主机资产数据导入插件
支持导入: 服务器、账户、端口、进程、中间件、AI组件、数据库、Web服务、软件、计划任务、启动项、内核模块、Web站点、IDC探针发现
"""
import sys
import os
import logging
import io
from typing import Dict, List, Any

# 添加项目根目录到路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from app.lib.base_plugin import BasePlugin
from app.lib.db_helper import DBHelper

# 尝试导入阿里云SDK（延迟导入，在运行时检查）
def _check_aliyun_sdk():
    """检查阿里云SDK是否可用"""
    try:
        from aliyunsdkcore.client import AcsClient
        from aliyunsdkcore.acs_exception.exceptions import ClientException, ServerException
        import aliyunsdksas.request.v20181203 as sas_module
        
        # 基础API类
        from aliyunsdksas.request.v20181203 import (
            DescribeCloudCenterInstancesRequest,  # 服务器
            DescribeAssetDetailByUuidRequest,     # 资产详情
        )
        
        # 尝试导入新的API类
        request_classes = {
            'DescribeCloudCenterInstancesRequest': DescribeCloudCenterInstancesRequest,
            'DescribeAssetDetailByUuidRequest': DescribeAssetDetailByUuidRequest,
        }
        
        # 尝试导入Property相关的API（用于获取详细资产信息）
        # 注意：同一API可能用于多种资产类型，这里列出所有可能的映射
        property_apis = {
            'DescribePropertyPortDetail': 'port',      # 端口信息
            'DescribePropertyAccountDetail': 'account',   # 账户信息（注意：可能是DescribePropertyUserDetail）
            'DescribePropertyUserDetail': 'account',   # 账户信息
            'DescribePropertyProcDetail': 'process',   # 进程信息
            'DescribePropertySoftwareDetail': 'software',  # 软件信息
            'DescribePropertyCronDetail': 'cron_task',  # 计划任务
            'DescribePropertyScheduleDetail': 'cron_task',  # 计划任务（备用）
            'DescribePropertyScaDetail': 'middleware',  # 中间件（SCA - Software Composition Analysis）
            'DescribePropertyStartupItemDetail': 'startup_item',  # 启动项
            'DescribePropertyKernelItemDetail': 'kernel_module',  # 内核模块
            'DescribePropertyKernelDetail': 'kernel_module',  # 内核模块（备用）
            'DescribePropertyWebPathDetail': 'web_site',  # Web站点
            'DescribePropertyWebSiteDetail': 'web_site',  # Web站点（备用）
            'DescribePropertyWebPath': 'web_site',  # Web站点（备用）
            'DescribePropertyAIDetail': 'ai_component',  # AI组件
            # IDC探针发现可能需要特殊API，暂时先尝试通过DescribeAssetDetailByUuid获取
        }
        
        for api_name, asset_type in property_apis.items():
            try:
                api_class = getattr(sas_module, api_name, None)
                if api_class:
                    request_classes[api_name] = api_class
                    logging.info(f"成功导入API: {api_name} (用于 {asset_type})")
            except Exception as e:
                logging.debug(f"无法导入API {api_name}: {e}")
        
        return True, AcsClient, ClientException, ServerException, request_classes
    except ImportError as e:
        logging.warning(f"阿里云SDK未安装: {e}，请使用: pip install aliyun-python-sdk-core aliyun-python-sdk-sas")
        return False, None, None, None, None


class Plugin(BasePlugin):
    """阿里云安全中心数据导入插件"""
    
    # 支持的资产类型
    ASSET_TYPES = [
        'server',          # 服务器
        'account',         # 账户
        'port',            # 端口
        'process',         # 进程
        'middleware',      # 中间件
        'ai_component',    # AI组件
        'database',        # 数据库
        'web_service',     # Web服务
        'software',        # 软件
        'cron_task',       # 计划任务
        'startup_item',    # 启动项
        'kernel_module',   # 内核模块
        'web_site',        # Web站点
        'idc_probe',       # IDC探针发现
    ]
    
    # 资产类型映射到数据库字段
    ASSET_TYPE_MAPPING = {
        'server': 'server',
        'account': 'account',
        'port': 'port',
        'process': 'process',
        'middleware': 'middleware',
        'ai_component': 'ai_component',
        'database': 'database',
        'web_service': 'web_service',
        'software': 'software',
        'cron_task': 'cron_task',
        'startup_item': 'startup_item',
        'kernel_module': 'kernel_module',
        'web_site': 'web_site',
        'idc_probe': 'idc_probe',
    }
    
    def __init__(self, config=None):
        super().__init__(config)
        
        # 创建日志缓冲区用于收集执行日志
        self.log_buffer = io.StringIO()
        self.log_handler = logging.StreamHandler(self.log_buffer)
        self.log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.log_handler.setLevel(logging.DEBUG)  # 捕获所有级别的日志
        self.logger.addHandler(self.log_handler)
        self.logger.setLevel(logging.DEBUG)  # 确保logger级别允许所有日志
        
        # 验证配置
        required_keys = ['access_key_id', 'access_key_secret', 'region_id']
        try:
            self.validate_config(required_keys)
        except ValueError as e:
            self.log_error(f"配置验证失败: {str(e)}")
            raise
        
        # 运行时检查并导入阿里云SDK
        sdk_available, AcsClient, ClientException, ServerException, request_classes = _check_aliyun_sdk()
        if not sdk_available:
            raise ImportError("阿里云SDK未安装，请使用: pip install aliyun-python-sdk-core aliyun-python-sdk-sas")
        
        # 保存SDK类到实例变量
        self.AcsClient = AcsClient
        self.ClientException = ClientException
        self.ServerException = ServerException
        self.request_classes = request_classes
        
        # 初始化阿里云客户端
        self.client = AcsClient(
            self.config['access_key_id'],
            self.config['access_key_secret'],
            self.config.get('region_id', 'cn-hangzhou')
        )
        
        # 要导入的资产类型列表，默认为全部
        self.asset_types_to_import = self.config.get('asset_types', self.ASSET_TYPES)
        
        # 分页大小
        self.page_size = self.config.get('page_size', 100)
        
        self.log_info(f"插件初始化成功，将导入资产类型: {', '.join(self.asset_types_to_import)}")
    
    def execute(self, *args, **kwargs) -> Dict[str, Any]:
        """
        执行数据导入
        
        Returns:
            dict: 执行结果
        """
        result = {
            'success': True,
            'message': '数据导入完成',
            'data': {},
            'logs': []
        }
        
        total_imported = 0
        total_failed = 0
        
        try:
            # 首先获取所有服务器列表作为基础
            servers = self._get_all_servers()
            self.log_info(f"获取到 {len(servers)} 台服务器")
            
            # 在执行导入前，先清理所有服务器下的旧资产数据（保留server数据）
            # 这样可以确保每次执行后，数据都是最新的，不包含历史数据
            server_uuids = []
            for server in servers:
                if isinstance(server, dict):
                    server_uuid = server.get('uuid') or server.get('Uuid') or server.get('instanceId') or server.get('InstanceId')
                    if server_uuid:
                        server_uuids.append(server_uuid)
            
            # 批量清理所有服务器下的旧资产数据（除了server类型）
            if server_uuids:
                try:
                    from app.models import Asset
                    total_deleted = Asset.objects.filter(
                        host_uuid__in=server_uuids,
                        source='aliyun_security'
                    ).exclude(asset_type='server').delete()[0]
                    if total_deleted > 0:
                        self.log_info(f"已清理 {len(server_uuids)} 台服务器下的旧资产数据: {total_deleted} 条")
                except Exception as e:
                    self.log_warning(f"清理旧资产数据失败: {str(e)}，将继续导入新数据")
            
            # 导入服务器资产
            if 'server' in self.asset_types_to_import:
                imported, failed = self._import_servers(servers)
                total_imported += imported
                total_failed += failed
                result['data']['servers'] = {'imported': imported, 'failed': failed}
            
            # 对每台服务器，导入其他资产
            for server in servers:
                # 确保server是字典类型
                if not isinstance(server, dict):
                    continue
                    
                server_uuid = server.get('uuid') or server.get('Uuid') or server.get('instanceId') or server.get('InstanceId')
                if not server_uuid:
                    self.log_warning(f"服务器数据缺少UUID字段: {server}")
                    continue
                
                self.log_info(f"开始导入服务器 {server_uuid} 的其他资产")
                
                # 导入各类资产
                for asset_type in self.asset_types_to_import:
                    if asset_type == 'server':
                        continue  # 服务器已导入
                    
                    try:
                        self.log_info(f"导入资产类型: {asset_type} (host_uuid: {server_uuid})")
                        imported, failed = self._import_assets_by_type(asset_type, server_uuid)
                        total_imported += imported
                        total_failed += failed
                        
                        if asset_type not in result['data']:
                            result['data'][asset_type] = {'imported': 0, 'failed': 0}
                        result['data'][asset_type]['imported'] += imported
                        result['data'][asset_type]['failed'] += failed
                        
                        if imported > 0:
                            self.log_info(f"成功导入 {asset_type} 资产: {imported} 条")
                        
                    except Exception as e:
                        self.log_error(f"导入资产类型 {asset_type} 失败: {str(e)}", exc_info=True)
                        total_failed += 1
            
            result['data']['summary'] = {
                'total_imported': total_imported,
                'total_failed': total_failed
            }
            result['message'] = f'导入完成: 成功 {total_imported} 条，失败 {total_failed} 条'
            
        except Exception as e:
            result['success'] = False
            result['message'] = f'执行失败: {str(e)}'
            self.log_error(f"插件执行异常: {str(e)}", exc_info=True)
        
        # 获取执行日志
        try:
            self.log_handler.flush()
            logs = self.log_buffer.getvalue()
            # 如果日志为空，至少记录基本信息
            if not logs or logs.strip() == '':
                logs = f"执行完成\n成功: {result.get('success', False)}\n消息: {result.get('message', '')}\n"
            result['logs'] = logs
            # 移除handler以避免重复日志
            self.logger.removeHandler(self.log_handler)
        except Exception as e:
            result['logs'] = f'获取日志失败: {str(e)}'
        
        return result
    
    def _get_all_servers(self) -> List[Dict]:
        """
        获取所有服务器列表
        
        Returns:
            list: 服务器列表
        """
        servers = []
        current_page = 1
        
        try:
            while True:
                request = self.request_classes['DescribeCloudCenterInstancesRequest'].DescribeCloudCenterInstancesRequest()
                request.set_PageSize(self.page_size)
                request.set_CurrentPage(current_page)
                
                response = self._make_request(request)
                
                # 确保response是字典类型
                if not isinstance(response, dict):
                    self.log_error(f"API响应格式错误，期望dict，实际得到: {type(response)}")
                    break
                
                # 获取服务器列表
                instances = response.get('Instances', {})
                if isinstance(instances, dict):
                    page_servers = instances.get('Instance', [])
                elif isinstance(instances, list):
                    page_servers = instances
                else:
                    page_servers = []
                
                if not page_servers:
                    break
                
                servers.extend(page_servers if isinstance(page_servers, list) else [page_servers])
                
                # 检查是否还有下一页
                page_info = response.get('PageInfo', {})
                if isinstance(page_info, dict):
                    total_count = page_info.get('TotalCount', 0)
                else:
                    total_count = 0
                
                if total_count > 0 and len(servers) >= total_count:
                    break
                
                current_page += 1
                
        except Exception as e:
            self.log_error(f"获取服务器列表失败: {str(e)}")
            raise
        
        return servers
    
    def _import_servers(self, servers: List[Dict]) -> tuple:
        """
        导入服务器资产
        
        Args:
            servers: 服务器列表
            
        Returns:
            tuple: (成功数量, 失败数量)
        """
        assets_data = []
        
        for server in servers:
            try:
                # 确保server是字典类型
                if not isinstance(server, dict):
                    self.log_warning(f"服务器数据格式错误，期望dict，实际得到: {type(server)}, 数据: {server}")
                    continue
                
                uuid = server.get('uuid') or server.get('instanceId') or server.get('Uuid') or server.get('InstanceId')
                name = server.get('instanceName') or server.get('InstanceName') or server.get('instanceId') or server.get('InstanceId')
                
                if not uuid:
                    self.log_warning(f"服务器数据缺少UUID字段: {server}")
                    continue
                
                assets_data.append({
                    'asset_type': 'server',
                    'uuid': uuid,
                    'name': name or uuid,
                    'host_uuid': uuid,
                    'data': server,
                    'source': 'aliyun_security'
                })
            except Exception as e:
                self.log_error(f"处理服务器数据失败: {str(e)}")
        
        return DBHelper.batch_save_assets(assets_data)
    
    def _import_assets_by_type(self, asset_type: str, host_uuid: str) -> tuple:
        """
        根据资产类型导入资产
        
        Args:
            asset_type: 资产类型
            host_uuid: 主机UUID
            
        Returns:
            tuple: (成功数量, 失败数量)
        """
        # 在执行导入前，先删除该host_uuid下该类型的旧数据
        # 这样可以确保每次执行后，数据都是最新的，不包含历史数据
        try:
            deleted_count = DBHelper.delete_assets_by_host(host_uuid, asset_type, source='aliyun_security')
            if deleted_count > 0:
                self.log_info(f"已清理 {host_uuid} 的旧 {asset_type} 数据: {deleted_count} 条")
        except Exception as e:
            self.log_warning(f"清理旧数据失败: {str(e)}，将继续导入新数据")
        
        # 根据资产类型调用不同的API获取数据
        # 注意: 阿里云安全中心的不同资产使用不同的API
        # 这里提供一个通用的框架，实际使用时需要根据具体API文档实现
        
        try:
            # 获取资产详情
            assets = self._get_assets_from_detail(host_uuid, asset_type)
            
            assets_data = []
            uuid_seen = {}  # 跟踪已生成的UUID，避免同一批次内重复
            for idx, asset in enumerate(assets):
                try:
                    # 确保asset是字典类型
                    if not isinstance(asset, dict):
                        self.log_warning(f"资产数据格式错误，期望dict，实际得到: {type(asset)}, 数据: {asset}")
                        continue
                    
                    # 根据不同的资产类型，使用不同的字段生成UUID
                    uuid = None
                    name = None
                    
                    if asset_type == 'account':
                        # 账户资产：使用User字段作为唯一标识
                        user = asset.get('User') or asset.get('user') or asset.get('Name') or asset.get('name')
                        uuid = f"{host_uuid}_{asset_type}_{user}" if user else f"{host_uuid}_{asset_type}_{asset.get('Uuid', 'unknown')}"
                        name = user or asset.get('Name') or asset.get('InstanceName') or uuid
                    elif asset_type == 'port':
                        # 端口资产：使用Port+Proto+Ip作为唯一标识，加上数据哈希确保唯一性
                        port = asset.get('Port') or asset.get('port') or ''
                        proto = asset.get('Proto') or asset.get('proto', 'tcp')
                        ip = asset.get('Ip') or asset.get('ip') or asset.get('BindIp') or asset.get('bindIp') or host_uuid
                        
                        import hashlib
                        # 计算数据哈希的一部分，确保唯一性
                        data_hash_short = hashlib.md5(str(sorted(asset.items())).encode()).hexdigest()[:6]
                        
                        if port:
                            # 即使Port、Proto、Ip相同，也加上数据哈希确保唯一性
                            uuid = f"{host_uuid}_{asset_type}_{ip}_{port}_{proto}_{data_hash_short}"
                        else:
                            # 如果端口为空，使用数据哈希
                            data_str = str(sorted(asset.items()))[:200]
                            data_hash = hashlib.md5(data_str.encode()).hexdigest()[:12]
                            uuid = f"{host_uuid}_{asset_type}_hash_{data_hash}"
                        name = f"{proto}:{port}" if port else asset.get('Port') or '未知端口'
                    elif asset_type == 'process':
                        # 进程资产：使用Pid+Name作为唯一标识
                        pid = asset.get('Pid') or asset.get('pid') or ''
                        proc_name = asset.get('ProcName') or asset.get('procName') or asset.get('Name') or asset.get('name') or ''
                        if pid and proc_name:
                            uuid = f"{host_uuid}_{asset_type}_{proc_name}_{pid}"
                        elif proc_name or pid:
                            # 如果只有名称或PID，也尝试生成
                            uuid = f"{host_uuid}_{asset_type}_{proc_name or 'proc'}_{pid or 'unknown'}"
                        else:
                            # 如果都没有，使用数据哈希
                            import hashlib
                            data_str = str(sorted(asset.items()))[:200]
                            data_hash = hashlib.md5(data_str.encode()).hexdigest()[:12]
                            uuid = f"{host_uuid}_{asset_type}_hash_{data_hash}"
                        name = f"{proc_name}({pid})" if pid and proc_name else proc_name or f"进程({pid})" if pid else '未知进程'
                    elif asset_type == 'software':
                        # 软件资产：使用Name+Version作为唯一标识
                        name_field = asset.get('Name') or asset.get('name') or asset.get('SoftwareName') or asset.get('softwareName') or ''
                        version = asset.get('Version') or asset.get('version') or asset.get('SoftwareVersion') or asset.get('softwareVersion') or ''
                        if name_field:
                            # 使用名称+版本（如果有）作为唯一标识
                            # 限制长度以确保UUID不超过100字符
                            if len(name_field) > 40:
                                name_field = name_field[:40]
                            if version and len(version) > 15:
                                version = version[:15]
                            unique_key = f"{name_field}_{version}" if version else name_field
                            uuid = f"{host_uuid}_{asset_type}_{unique_key}"
                            # 如果UUID还是太长，使用哈希
                            if len(uuid) > 100:
                                import hashlib
                                uuid_hash = hashlib.md5(uuid.encode()).hexdigest()[:12]
                                uuid = f"{host_uuid}_{asset_type}_{uuid_hash}"
                        else:
                            # 如果名称也没有，使用数据哈希确保唯一性
                            import hashlib
                            data_str = str(sorted(asset.items()))[:200]
                            data_hash = hashlib.md5(data_str.encode()).hexdigest()[:12]
                            uuid = f"{host_uuid}_{asset_type}_hash_{data_hash}"
                        # 名称字段只包含软件名称，不包含版本号（版本号存储在data字段中）
                        name = name_field if name_field else (asset.get('Path', '').split('/')[-1] if asset.get('Path') else '未知软件')
                    elif asset_type == 'middleware':
                        # 中间件资产：使用Name+Path+Version作为唯一标识，使用路径哈希确保唯一性
                        name_field = asset.get('Name') or asset.get('name') or asset.get('MiddlewareName') or asset.get('middlewareName') or ''
                        version = asset.get('Version') or asset.get('version') or ''
                        path = asset.get('Path') or asset.get('path') or asset.get('InstallPath') or asset.get('installPath') or ''
                        
                        import hashlib
                        # 计算完整数据的哈希值（取前8位），确保每条记录的唯一性
                        data_hash_short = hashlib.md5(str(sorted(asset.items())).encode()).hexdigest()[:8]
                        
                        # 优先使用完整路径+名称+版本，并始终加上数据哈希确保唯一性
                        if path and name_field:
                            # 使用名称和完整路径的哈希（确保不同路径有不同的UUID）
                            path_hash = hashlib.md5(path.encode()).hexdigest()[:10]
                            if len(name_field) > 15:
                                name_field = name_field[:15]
                            # 如果有版本，也加上版本
                            if version:
                                version_short = version[:8] if len(version) > 8 else version
                                unique_key = f"{name_field}_{version_short}_{path_hash[:6]}_{data_hash_short[:6]}"
                            else:
                                unique_key = f"{name_field}_{path_hash[:6]}_{data_hash_short[:6]}"
                        elif name_field and version:
                            # 使用名称+版本，加上数据哈希确保唯一性
                            if len(name_field) > 25:
                                name_field = name_field[:25]
                            if len(version) > 15:
                                version = version[:15]
                            # 即使只有名称和版本，也加上数据哈希避免重复
                            data_hash = hashlib.md5(str(sorted(asset.items())).encode()).hexdigest()[:8]
                            unique_key = f"{name_field}_{version}_{data_hash}"
                        elif name_field:
                            # 只有名称，使用数据哈希确保唯一性
                            name_short = name_field[:30] if len(name_field) > 30 else name_field
                            data_hash = hashlib.md5(str(sorted(asset.items())).encode()).hexdigest()[:8]
                            unique_key = f"{name_short}_{data_hash}"
                        elif path:
                            # 如果只有路径，使用路径哈希
                            path_hash = hashlib.md5(path.encode()).hexdigest()[:12]
                            path_part = path.split('/')[-1][:20] if '/' in path else path[:20]
                            unique_key = f"{path_part}_{path_hash}"
                        else:
                            # 如果都没有，使用完整数据哈希
                            data_str = str(sorted(asset.items()))[:300]
                            data_hash = hashlib.md5(data_str.encode()).hexdigest()[:12]
                            unique_key = f"hash_{data_hash}"
                        
                        # 确保UUID总长度不超过100字符
                        uuid = f"{host_uuid}_{asset_type}_{unique_key}"
                        if len(uuid) > 100:
                            # 如果还是太长，使用哈希
                            uuid_hash = hashlib.md5(uuid.encode()).hexdigest()[:12]
                            uuid = f"{host_uuid}_{asset_type}_{uuid_hash}"
                        
                        name = name_field or (path.split('/')[-1] if path else '未知中间件')
                    elif asset_type == 'cron_task':
                        # 计划任务：使用Name+Command作为唯一标识
                        name_field = asset.get('Name') or asset.get('name') or asset.get('CronName') or asset.get('cronName') or asset.get('ScheduleName') or ''
                        command = asset.get('Command') or asset.get('command') or asset.get('Cmd') or ''
                        cron_expr = asset.get('Cron') or asset.get('Schedule') or ''
                        import hashlib
                        # 计算数据哈希确保唯一性
                        data_hash_short = hashlib.md5(str(sorted(asset.items())).encode()).hexdigest()[:8]
                        
                        if name_field and command:
                            # 使用名称和命令的哈希值
                            cmd_hash = hashlib.md5(command.encode()).hexdigest()[:8]
                            uuid = f"{host_uuid}_{asset_type}_{name_field}_{cmd_hash}"
                        elif name_field and cron_expr:
                            # 如果有名称和cron表达式
                            cron_hash = hashlib.md5(cron_expr.encode()).hexdigest()[:8]
                            uuid = f"{host_uuid}_{asset_type}_{name_field}_{cron_hash}"
                        elif name_field:
                            uuid = f"{host_uuid}_{asset_type}_{name_field}_{data_hash_short}"
                        elif command:
                            # 如果只有命令，使用命令哈希
                            cmd_hash = hashlib.md5(command.encode()).hexdigest()[:8]
                            uuid = f"{host_uuid}_{asset_type}_cmd_{cmd_hash}"
                        else:
                            # 如果都没有，使用数据哈希
                            uuid = f"{host_uuid}_{asset_type}_hash_{data_hash_short}"
                        name = name_field or command[:50] or cron_expr[:50] or '未知计划任务'
                    elif asset_type == 'startup_item':
                        # 启动项：使用Name+Path作为唯一标识
                        name_field = asset.get('Name') or asset.get('name') or asset.get('StartupName') or ''
                        path = asset.get('Path') or asset.get('path') or asset.get('FilePath') or ''
                        import hashlib
                        data_hash_short = hashlib.md5(str(sorted(asset.items())).encode()).hexdigest()[:8]
                        
                        if name_field and path:
                            path_hash = hashlib.md5(path.encode()).hexdigest()[:8]
                            uuid = f"{host_uuid}_{asset_type}_{name_field}_{path_hash}"
                        elif name_field:
                            uuid = f"{host_uuid}_{asset_type}_{name_field}_{data_hash_short}"
                        elif path:
                            path_hash = hashlib.md5(path.encode()).hexdigest()[:8]
                            uuid = f"{host_uuid}_{asset_type}_path_{path_hash}"
                        else:
                            uuid = f"{host_uuid}_{asset_type}_hash_{data_hash_short}"
                        name = name_field or (path.split('/')[-1] if path else '未知启动项')
                    elif asset_type == 'kernel_module':
                        # 内核模块：使用Name作为唯一标识
                        name_field = asset.get('Name') or asset.get('name') or asset.get('ModuleName') or asset.get('KernelModule') or ''
                        version = asset.get('Version') or asset.get('version') or ''
                        import hashlib
                        data_hash_short = hashlib.md5(str(sorted(asset.items())).encode()).hexdigest()[:8]
                        
                        if name_field:
                            if version:
                                uuid = f"{host_uuid}_{asset_type}_{name_field}_{version}"
                            else:
                                uuid = f"{host_uuid}_{asset_type}_{name_field}_{data_hash_short}"
                        else:
                            uuid = f"{host_uuid}_{asset_type}_hash_{data_hash_short}"
                        name = name_field or '未知内核模块'
                    elif asset_type == 'web_site':
                        # Web站点：使用Domain+Path作为唯一标识
                        domain = asset.get('Domain') or asset.get('domain') or asset.get('SiteName') or asset.get('Name') or ''
                        path = asset.get('Path') or asset.get('path') or asset.get('WebPath') or asset.get('RootPath') or ''
                        port = asset.get('Port') or asset.get('port') or ''
                        import hashlib
                        data_hash_short = hashlib.md5(str(sorted(asset.items())).encode()).hexdigest()[:8]
                        
                        if domain and path:
                            path_hash = hashlib.md5(path.encode()).hexdigest()[:8]
                            uuid = f"{host_uuid}_{asset_type}_{domain}_{path_hash}"
                        elif domain and port:
                            uuid = f"{host_uuid}_{asset_type}_{domain}_{port}"
                        elif domain:
                            uuid = f"{host_uuid}_{asset_type}_{domain}_{data_hash_short}"
                        elif path:
                            path_hash = hashlib.md5(path.encode()).hexdigest()[:8]
                            uuid = f"{host_uuid}_{asset_type}_path_{path_hash}"
                        else:
                            uuid = f"{host_uuid}_{asset_type}_hash_{data_hash_short}"
                        name = domain or (path.split('/')[-1] if path else '未知Web站点')
                    elif asset_type == 'ai_component':
                        # AI组件：使用Name+Version作为唯一标识
                        name_field = asset.get('Name') or asset.get('name') or asset.get('ComponentName') or asset.get('AIModel') or ''
                        version = asset.get('Version') or asset.get('version') or ''
                        model_id = asset.get('ModelId') or asset.get('modelId') or ''
                        import hashlib
                        data_hash_short = hashlib.md5(str(sorted(asset.items())).encode()).hexdigest()[:8]
                        
                        if name_field and version:
                            uuid = f"{host_uuid}_{asset_type}_{name_field}_{version}"
                        elif name_field and model_id:
                            uuid = f"{host_uuid}_{asset_type}_{name_field}_{model_id}"
                        elif name_field:
                            uuid = f"{host_uuid}_{asset_type}_{name_field}_{data_hash_short}"
                        elif model_id:
                            uuid = f"{host_uuid}_{asset_type}_model_{model_id}"
                        else:
                            uuid = f"{host_uuid}_{asset_type}_hash_{data_hash_short}"
                        name = name_field or model_id or '未知AI组件'
                    elif asset_type == 'idc_probe':
                        # IDC探针发现：使用IP+Port作为唯一标识
                        ip = asset.get('Ip') or asset.get('ip') or asset.get('HostIp') or ''
                        port = asset.get('Port') or asset.get('port') or ''
                        hostname = asset.get('HostName') or asset.get('hostname') or ''
                        import hashlib
                        data_hash_short = hashlib.md5(str(sorted(asset.items())).encode()).hexdigest()[:8]
                        
                        if ip and port:
                            uuid = f"{host_uuid}_{asset_type}_{ip}_{port}"
                        elif ip and hostname:
                            uuid = f"{host_uuid}_{asset_type}_{ip}_{hostname[:20]}"
                        elif ip:
                            uuid = f"{host_uuid}_{asset_type}_{ip}_{data_hash_short}"
                        else:
                            uuid = f"{host_uuid}_{asset_type}_hash_{data_hash_short}"
                        name = hostname or ip or '未知IDC探针发现'
                    else:
                        # 其他资产类型：使用通用逻辑，优先使用Name字段
                        name_field = asset.get('name') or asset.get('Name') or asset.get('title') or asset.get('Title') or ''
                        unique_id = asset.get('uuid') or asset.get('id') or asset.get('Uuid') or asset.get('Id') or ''
                        
                        if name_field:
                            # 使用名称作为UUID的一部分
                            if len(name_field) > 50:
                                name_field = name_field[:50]
                            uuid = f"{host_uuid}_{asset_type}_{name_field}"
                        elif unique_id:
                            uuid = f"{host_uuid}_{asset_type}_{unique_id}"
                        else:
                            # 如果都没有，使用数据哈希作为唯一标识
                            import hashlib
                            data_str = str(sorted(asset.items()))[:200]  # 取更多字符提高唯一性
                            data_hash = hashlib.md5(data_str.encode()).hexdigest()[:12]
                            uuid = f"{host_uuid}_{asset_type}_hash_{data_hash}"
                        
                        # 确保UUID长度不超过100字符
                        if len(uuid) > 100:
                            import hashlib
                            uuid_hash = hashlib.md5(uuid.encode()).hexdigest()[:12]
                            uuid = f"{host_uuid}_{asset_type}_hash_{uuid_hash}"
                        
                        name = name_field or unique_id or '未知资产'
                    
                    # 确保UUID总是能生成（即使字段不完整）
                    if not uuid:
                        # 如果所有方法都失败，使用数据哈希生成UUID
                        import hashlib
                        data_str = str(sorted(asset.items()))[:200]  # 取更多字符提高唯一性
                        data_hash = hashlib.md5(data_str.encode()).hexdigest()[:16]
                        uuid = f"{host_uuid}_{asset_type}_hash_{data_hash}"
                        self.log_warning(f"使用数据哈希生成UUID: {uuid[:80]}... (原始数据可能缺少必要字段)")
                    
                    # 检查同一批次内是否有UUID重复，如果有则添加索引后缀
                    # 使用计数器来确保索引后缀的唯一性
                    if uuid in uuid_seen:
                        # UUID重复，添加索引后缀确保唯一性
                        original_uuid = uuid
                        # 如果已经添加过索引后缀，继续递增
                        if isinstance(uuid_seen[uuid], int):
                            counter = uuid_seen[uuid] + 1
                        else:
                            counter = 1
                        uuid_seen[original_uuid] = counter  # 记录当前计数器值
                        uuid = f"{original_uuid}_{counter}"
                        uuid_seen[uuid] = True  # 标记新UUID已使用
                        self.log_warning(f"检测到UUID重复 (第{counter}次)，添加索引后缀: {original_uuid[:60]}... -> {uuid[:60]}...")
                    else:
                        uuid_seen[uuid] = 0  # 初始值0，表示没有重复
                    
                    assets_data.append({
                        'asset_type': asset_type,
                        'uuid': uuid,
                        'name': name,
                        'host_uuid': host_uuid,
                        'data': asset,
                        'source': 'aliyun_security'
                    })
                except Exception as e:
                    self.log_error(f"处理资产数据失败: {str(e)}")
            
            return DBHelper.batch_save_assets(assets_data)
            
        except Exception as e:
            self.log_error(f"导入资产类型 {asset_type} 失败: {str(e)}")
            return 0, 1
    
    def _get_assets_from_detail(self, host_uuid: str, asset_type: str) -> List[Dict]:
        """
        从资产详情中获取指定类型的资产
        
        注意：DescribeAssetDetailByUuid API只返回服务器基本信息，
        账户、端口等详细信息需要使用其他API，但目前SDK可能不支持这些API。
        这里先返回空列表，等待后续API支持。
        
        Args:
            host_uuid: 主机UUID
            asset_type: 资产类型
            
        Returns:
            list: 资产列表
        """
        # 尝试使用Property API获取详细资产信息
        api_mapping = {
            'account': ['DescribePropertyAccountDetail', 'DescribePropertyUserDetail'],
            'port': ['DescribePropertyPortDetail'],
            'process': ['DescribePropertyProcDetail'],
            'software': ['DescribePropertySoftwareDetail'],
            'cron_task': ['DescribePropertyCronDetail', 'DescribePropertyScheduleDetail'],
            'middleware': ['DescribePropertyScaDetail'],
            'startup_item': ['DescribePropertyStartupItemDetail'],
            'kernel_module': ['DescribePropertyKernelItemDetail', 'DescribePropertyKernelDetail'],
            'web_site': ['DescribePropertyWebPathDetail', 'DescribePropertyWebSiteDetail', 'DescribePropertyWebPath'],
            'ai_component': ['DescribePropertyAIDetail', 'DescribePropertyScaDetail'],  # AI组件，使用DescribePropertyScaDetail时需要传入BizType参数
            # IDC探针发现可能需要通过其他方式获取，暂时尝试DescribeAssetDetailByUuid
            'idc_probe': [],  # 暂时为空，后续可通过其他API获取
            'database': [],  # 暂时为空
            'web_service': [],  # 暂时为空
        }
        
        api_names = api_mapping.get(asset_type, [])
        for api_name in api_names:
            # 无论SDK中是否有API类，都尝试调用Property API（使用通用RpcRequest方式）
            self.log_info(f"尝试使用Property API {api_name} 获取 {asset_type} 资产")
            result = self._get_assets_by_property_api(host_uuid, asset_type, api_name)
            if result:
                self.log_info(f"成功从API {api_name} 获取 {len(result)} 条 {asset_type} 资产")
                return result
            # 如果这个API失败了，尝试下一个
            self.log_warning(f"API {api_name} 未返回数据，尝试下一个API")
        
        # 如果所有Property API都失败，不再尝试DescribeAssetDetailByUuid（它不包含详细资产）
        if api_names:
            self.log_warning(f"所有Property API都未返回 {asset_type} 数据，可能服务器没有该类型资产或需要其他权限")
        
        return []
        
        try:
            # 获取资产详情（仅用于服务器信息）
            request = self.request_classes['DescribeAssetDetailByUuidRequest'].DescribeAssetDetailByUuidRequest()
            request.set_Uuid(host_uuid)
            
            response = self._make_request(request)
            
            # 确保response是字典类型
            if not isinstance(response, dict):
                self.log_error(f"API响应格式错误，期望dict，实际得到: {type(response)}")
                return []
            
            # 调试：记录响应的所有键
            self.log_info(f"API响应键: {list(response.keys())}")
            
            # 根据资产类型提取对应的数据
            # 尝试多种可能的字段名
            asset_data = response.get('AssetDetail', {}) or response.get('assetDetail', {}) or response.get('Data', {}) or response.get('data', {})
            
            # 如果response直接包含资产数据
            if not asset_data and isinstance(response, dict):
                # 检查response是否直接是资产数据
                if 'uuid' in response or 'Uuid' in response:
                    asset_data = response
                else:
                    # 尝试其他可能的字段
                    for key in ['detail', 'Detail', 'AssetInfo', 'assetInfo']:
                        if key in response:
                            asset_data = response[key]
                            break
            
            # 确保asset_data是字典类型
            if not isinstance(asset_data, dict):
                self.log_warning(f"AssetDetail格式错误，期望dict，实际得到: {type(asset_data)}, 响应内容: {str(response)[:500]}")
                return []
            
            # 调试：记录asset_data的所有键
            all_keys = list(asset_data.keys())
            self.log_info(f"AssetDetail键 ({len(all_keys)}个): {all_keys}")
            
            # 尝试深度搜索：检查是否有嵌套的数据结构
            # 某些API可能会将数据嵌套在其他字段中
            for key, value in asset_data.items():
                if isinstance(value, dict):
                    # 检查嵌套字典中是否有我们需要的字段
                    nested_keys = list(value.keys())
                    self.log_info(f"  {key} (嵌套字段): {nested_keys[:10]}")
                elif isinstance(value, list) and len(value) > 0:
                    # 检查列表中的第一个元素
                    if isinstance(value[0], dict):
                        self.log_info(f"  {key} (列表，第一个元素字段): {list(value[0].keys())[:10]}")
            
            # 映射资产类型到API返回的字段名（尝试多种可能的字段名格式）
            type_field_mapping = {
                'account': ['accounts', 'Accounts', 'AccountList', 'accountList', 'Account', 'account'],
                'port': ['ports', 'Ports', 'PortList', 'portList', 'Port', 'port', 'PortInfo', 'portInfo'],
                'process': ['processes', 'Processes', 'ProcessList', 'processList', 'Process', 'process'],
                'middleware': ['middlewares', 'Middlewares', 'MiddlewareList', 'middlewareList', 'Middleware', 'middleware'],
                'database': ['databases', 'Databases', 'DatabaseList', 'databaseList', 'Database', 'database'],
                'web_service': ['webServices', 'WebServices', 'WebServiceList', 'webServiceList', 'WebService', 'webService'],
                'software': ['softwares', 'Softwares', 'SoftwareList', 'softwareList', 'Software', 'software'],
                'cron_task': ['cronTasks', 'CronTasks', 'CronTaskList', 'cronTaskList', 'CronTask', 'cronTask'],
                'startup_item': ['startupItems', 'StartupItems', 'StartupItemList', 'startupItemList', 'StartupItem', 'startupItem'],
                'kernel_module': ['kernelModules', 'KernelModules', 'KernelModuleList', 'kernelModuleList', 'KernelModule', 'kernelModule'],
                'web_site': ['webSites', 'WebSites', 'WebSiteList', 'webSiteList', 'WebSite', 'webSite'],
            }
            
            field_names = type_field_mapping.get(asset_type, [])
            found_assets = []
            
            # 首先尝试直接字段匹配
            for field_name in field_names:
                if field_name in asset_data:
                    assets = asset_data[field_name]
                    # 确保返回的是列表
                    if isinstance(assets, list):
                        self.log_info(f"找到 {asset_type} 资产 (字段: {field_name}): {len(assets)} 条")
                        found_assets = assets
                        break
                    elif assets and isinstance(assets, dict):
                        self.log_info(f"找到 {asset_type} 资产 (字段: {field_name}): 1 条（单条）")
                        found_assets = [assets]
                        break
            
            # 如果直接匹配失败，尝试在嵌套结构中查找
            if not found_assets:
                for key, value in asset_data.items():
                    if isinstance(value, dict):
                        # 在嵌套字典中查找
                        for field_name in field_names:
                            if field_name in value:
                                assets = value[field_name]
                                if isinstance(assets, list):
                                    self.log_info(f"找到 {asset_type} 资产 (嵌套字段: {key}.{field_name}): {len(assets)} 条")
                                    found_assets = assets
                                    break
                                elif assets and isinstance(assets, dict):
                                    self.log_info(f"找到 {asset_type} 资产 (嵌套字段: {key}.{field_name}): 1 条")
                                    found_assets = [assets]
                                    break
                        if found_assets:
                            break
            
            if found_assets:
                return found_assets
            
            # 如果没有找到对应的字段，记录所有可用字段用于调试
            self.log_warning(f"未找到资产类型 {asset_type} 对应的字段")
            self.log_warning(f"提示：DescribeAssetDetailByUuid API不返回 {asset_type} 详细信息")
            self.log_warning(f"这些详细信息需要通过其他专门的API获取")
            self.log_warning(f"可用字段: {all_keys[:50]}")
            return []
            
        except Exception as e:
            self.log_error(f"获取资产详情失败 (host_uuid={host_uuid}, type={asset_type}): {str(e)}", exc_info=True)
            return []
    
    def _get_assets_by_property_api(self, host_uuid: str, asset_type: str, api_name: str) -> List[Dict]:
        """
        使用Property API获取资产详细信息
        
        Args:
            host_uuid: 主机UUID
            asset_type: 资产类型
            api_name: API名称（如 DescribePropertyUserDetail）
            
        Returns:
            list: 资产列表
        """
        try:
            # 首先获取服务器信息以便使用IP或主机名作为Remark参数
            remark = host_uuid  # 默认使用UUID
            try:
                detail_request = self.request_classes['DescribeAssetDetailByUuidRequest'].DescribeAssetDetailByUuidRequest()
                detail_request.set_Uuid(host_uuid)
                detail_response = self._make_request(detail_request)
                asset_detail = detail_response.get('AssetDetail', {})
                
                # Property API通常使用Remark参数（可以是IP、主机名或UUID）
                remark = asset_detail.get('IntranetIp') or asset_detail.get('Ip') or asset_detail.get('HostName') or asset_detail.get('InstanceName') or host_uuid
                self.log_info(f"使用 {remark} 作为Remark参数")
            except Exception as e:
                self.log_warning(f"获取服务器信息失败，使用UUID作为Remark: {str(e)}")
            
            # 优先尝试使用SDK中的API类（如果可用）
            if api_name in self.request_classes:
                api_class = self.request_classes[api_name]
                try:
                    request = api_class()
                    
                    # 根据API类型设置参数
                    if hasattr(request, 'set_Remark'):
                        request.set_Remark(remark)
                    if hasattr(request, 'set_Uuid'):
                        request.set_Uuid(host_uuid)
                    
                    # 对于DescribePropertyScaDetail API，如果用于AI组件，需要传入BizType参数
                    if api_name == 'DescribePropertyScaDetail' and asset_type == 'ai_component':
                        if hasattr(request, 'set_BizType'):
                            request.set_BizType('ai_component')
                            self.log_info(f"为AI组件添加BizType参数: ai_component")
                    
                    if hasattr(request, 'set_CurrentPage'):
                        request.set_CurrentPage(1)
                    if hasattr(request, 'set_PageSize'):
                        request.set_PageSize(self.page_size)
                    
                    self.log_info(f"使用SDK API类调用: {api_name}")
                    return self._get_assets_by_api_pagination(request, api_name)
                    
                except Exception as e:
                    self.log_warning(f"使用SDK API类失败，改用通用RpcRequest方式: {str(e)}")
            
            # 使用通用RpcRequest方式调用（即使SDK中没有对应的类）
            self.log_info(f"使用通用RpcRequest调用Property API: {api_name}")
            from aliyunsdkcore.request import RpcRequest
            
            # RpcRequest构造函数需要product, version, action_name参数
            request = RpcRequest('Sas', '2018-12-03', api_name)
            request.set_accept_format('json')
            request.set_method('POST')
            
            # 设置endpoint（必须设置，否则会报错"No endpoint for product 'Sas'"）
            region_id = self.config.get('region_id', 'cn-hangzhou')
            # 阿里云安全中心的endpoint格式: https://sas.{region_id}.aliyuncs.com
            endpoint = self.config.get('api_endpoint') or f'https://sas.{region_id}.aliyuncs.com'
            request.set_endpoint(endpoint)
            self.log_info(f"设置endpoint: {endpoint}")
            
            # 设置请求参数（根据官方文档，Remark可以是IP或主机名，Uuid是服务器UUID）
            request.add_query_param('Remark', remark)
            request.add_query_param('Uuid', host_uuid)
            
            # 对于DescribePropertyScaDetail API，如果用于AI组件，需要传入BizType参数
            if api_name == 'DescribePropertyScaDetail' and asset_type == 'ai_component':
                request.add_query_param('BizType', 'ai_component')
                self.log_info(f"为AI组件添加BizType参数: ai_component")
            
            request.add_query_param('CurrentPage', 1)
            request.add_query_param('PageSize', self.page_size)
            
            self.log_info(f"调用Property API: {api_name} (Remark: {remark}, Uuid: {host_uuid}, Endpoint: {endpoint})")
            
            # 分页获取所有数据
            all_assets = []
            current_page = 1
            
            while True:
                # 更新页码
                request.add_query_param('CurrentPage', current_page)
                
                try:
                    response_str = self.client.do_action_with_exception(request)
                    import json
                    response = json.loads(response_str)
                except Exception as e:
                    self.log_error(f"API调用失败: {str(e)}")
                    break
                
                if not isinstance(response, dict):
                    self.log_error(f"API响应格式错误: {type(response)}")
                    break
                
                # 处理API响应格式：可能直接包含data字段，或者Propertys字段
                # 根据用户提供的信息，DescribePropertyScaDetail返回格式为: {code: 200, data: {Propertys: [...]}}
                properties = []
                if 'data' in response and isinstance(response['data'], dict):
                    # 响应格式：{code: 200, data: {Propertys: [...]}}
                    data_obj = response['data']
                    properties = data_obj.get('Propertys', []) or data_obj.get('properties', [])
                else:
                    # 兼容旧格式：直接包含Propertys字段
                    properties = response.get('Propertys', []) or response.get('properties', []) or response.get('data', [])
                
                # 确保properties是列表
                if properties and not isinstance(properties, list):
                    properties = [properties] if properties else []
                
                # 对于DescribePropertyScaDetail，如果用于AI组件，需要过滤BizType=ai_component的数据
                # 注意：即使传入了BizType参数，API可能仍然返回所有数据，需要再次过滤确保准确性
                if api_name == 'DescribePropertyScaDetail' and asset_type == 'ai_component':
                    # 过滤出BizType为ai_component的数据
                    original_count = len(properties) if isinstance(properties, list) else 0
                    properties = [p for p in properties if isinstance(p, dict) and p.get('BizType') == 'ai_component']
                    if original_count > 0 and len(properties) < original_count:
                        self.log_info(f"过滤后AI组件数据: {len(properties)} 条 (原始: {original_count} 条，已过滤中间件数据)")
                    elif properties:
                        self.log_info(f"获取到AI组件数据: {len(properties)} 条")
                
                if not properties:
                    # 如果没有数据，检查是否是因为API不支持或需要其他参数
                    # 检查响应中的code和success字段
                    if 'code' in response and response.get('code') != 200:
                        self.log_warning(f"API返回错误code: {response.get('code')}, message: {response.get('message', '未知错误')}")
                    elif 'Code' in response and response.get('Code') != 'Success':
                        self.log_warning(f"API返回错误: {response.get('Message', '未知错误')}")
                    break
                
                if not isinstance(properties, list):
                    properties = [properties]
                
                all_assets.extend(properties)
                self.log_info(f"第{current_page}页获取到 {len(properties)} 条数据")
                
                # 检查是否还有下一页
                # 注意：PageInfo可能在data字段中（根据用户提供的API响应格式）
                page_info = None
                if 'data' in response and isinstance(response['data'], dict):
                    page_info = response['data'].get('PageInfo', {})
                else:
                    page_info = response.get('PageInfo', {})
                
                if isinstance(page_info, dict):
                    total_count = page_info.get('TotalCount', 0)
                    if total_count > 0 and len(all_assets) >= total_count:
                        break
                
                # 如果没有总数信息，且当前页没有数据，则停止
                if len(properties) == 0:
                    break
                
                current_page += 1
                
                # 防止无限循环
                if current_page > 100:
                    self.log_warning(f"达到最大页数限制，停止分页")
                    break
            
            self.log_info(f"从 {api_name} 总共获取到 {len(all_assets)} 条 {asset_type} 资产")
            return all_assets
            
        except Exception as e:
            self.log_error(f"调用Property API失败 ({api_name}): {str(e)}", exc_info=True)
            return []
    
    def _make_request(self, request, max_retries=3):
        """
        发送API请求
        
        Args:
            request: API请求对象
            max_retries: 最大重试次数
            
        Returns:
            dict: API响应数据
        """
        import json
        import time
        
        for attempt in range(max_retries):
            try:
                response = self.client.do_action_with_exception(request)
                result = json.loads(response)
                
                # 确保返回的是字典类型（如果API返回的是其他类型，进行转换）
                if isinstance(result, dict):
                    return result
                elif isinstance(result, list):
                    # 如果返回的是列表，包装成字典
                    self.log_warning(f"API返回列表类型，包装成字典: {len(result)} items")
                    return {'data': result, 'count': len(result)}
                else:
                    self.log_warning(f"API返回未知类型: {type(result)}, 包装成字典")
                    return {'data': result}
            except (self.ClientException, self.ServerException) as e:
                self.log_error(f'阿里云API请求失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}')
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 ** attempt)  # 指数退避
            except Exception as e:
                self.log_error(f'请求处理异常: {str(e)}')
                raise


# 插件信息
PLUGIN_INFO = {
    'name': 'data_aliyun_security',
    'type': 'data',
    'description': '阿里云安全中心主机资产数据导入插件，支持导入服务器、账户、端口、进程、中间件、AI组件、数据库、Web服务、软件、计划任务、启动项、内核模块、Web站点、IDC探针发现等资产数据',
    'version': '1.0.0',
    'author': 'Bifang Team',
    'required_config': [
        {
            'key': 'access_key_id',
            'type': 'string',
            'description': '阿里云AccessKey ID',
            'required': True
        },
        {
            'key': 'access_key_secret',
            'type': 'string',
            'description': '阿里云AccessKey Secret',
            'required': True
        },
        {
            'key': 'region_id',
            'type': 'string',
            'description': '地域ID，如: cn-hangzhou',
            'required': False,
            'default': 'cn-hangzhou'
        },
        {
            'key': 'asset_types',
            'type': 'list',
            'description': '要导入的资产类型列表，不指定则导入全部',
            'required': False
        },
        {
            'key': 'page_size',
            'type': 'int',
            'description': '分页大小',
            'required': False,
            'default': 100
        }
    ]
}
