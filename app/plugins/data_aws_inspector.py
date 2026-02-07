"""
AWS Inspector V2 资产指纹数据导入插件
通过AWS Inspector V2 API获取EC2实例的资产指纹数据
"""
import sys
import os
import logging
import io
import hashlib
import json
from typing import Dict, List, Any

# 添加项目根目录到路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from app.lib.base_plugin import BasePlugin
from app.lib.db_helper import DBHelper

# 尝试导入boto3（延迟导入，在运行时检查）
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
    """AWS Inspector V2 资产指纹数据导入插件"""
    
    # 支持的资产类型（AWS Inspector主要关注EC2实例）
    ASSET_TYPES = [
        'server',          # EC2实例（服务器）
        'software',        # 软件包（通过SBOM获取）
    ]
    
    def __init__(self, config=None):
        super().__init__(config)
        
        # 创建日志缓冲区用于收集执行日志
        self.log_buffer = io.StringIO()
        self.log_handler = logging.StreamHandler(self.log_buffer)
        self.log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.log_handler.setLevel(logging.DEBUG)
        self.logger.addHandler(self.log_handler)
        self.logger.setLevel(logging.DEBUG)
        
        # 验证配置
        required_keys = ['access_key_id', 'secret_access_key', 'region']
        try:
            self.validate_config(required_keys)
        except ValueError as e:
            self.log_error(f"配置验证失败: {str(e)}")
            raise
        
        # 运行时检查并导入boto3
        boto3_available, boto3_module, ClientError, BotoCoreError = _check_boto3()
        if not boto3_available:
            raise ImportError("boto3未安装，请使用: pip install boto3")
        
        self.boto3 = boto3_module
        self.ClientError = ClientError
        self.BotoCoreError = BotoCoreError
        
        # 验证凭证格式（基本检查）
        if not self.config['access_key_id'] or len(self.config['access_key_id']) < 16:
            raise ValueError("Access Key ID 格式不正确，应该是至少16个字符的字符串")
        if not self.config['secret_access_key'] or len(self.config['secret_access_key']) < 32:
            raise ValueError("Secret Access Key 格式不正确，应该是至少32个字符的字符串")
        
        # 使用 Session 仅传入配置中的凭证，完全忽略环境变量（避免 AWS_SESSION_TOKEN 等干扰）
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
        
        # 调试：确认收到的凭证（不输出敏感内容）。你提供的有效 AK 前缀 AKIA，SK 长度 40
        self.log_info(f"使用凭证: AK 前缀 {ak[:4] if len(ak) >= 4 else ak}***, SK 长度 {len(sk)}, 区域 {region}")
        
        try:
            session = self.boto3.Session(**session_kwargs)
            self.inspector2_client = session.client('inspector2')
            self.ec2_client = session.client('ec2')
        except Exception as e:
            self.log_error(f"创建AWS客户端失败: {str(e)}")
            raise
        
        # 要导入的资产类型列表，默认为全部
        self.asset_types_to_import = self.config.get('asset_types', self.ASSET_TYPES)
        
        # 分页大小
        self.page_size = self.config.get('page_size', 100)
        
        self.log_info(f"插件初始化成功，区域: {self.config.get('region', 'ap-northeast-1')}，将导入资产类型: {', '.join(self.asset_types_to_import)}")
    
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
            # 获取所有覆盖的资源（EC2实例）
            resources = self._get_all_resources()
            self.log_info(f"获取到 {len(resources)} 个资源")
            
            # 在执行导入前，先清理所有旧资产数据（保留server数据）
            resource_ids = [r.get('resourceId') for r in resources if r.get('resourceId')]
            if resource_ids:
                try:
                    from app.models import Asset
                    total_deleted = Asset.objects.filter(
                        host_uuid__in=resource_ids,
                        source='aws_inspector'
                    ).exclude(asset_type='server').delete()[0]
                    if total_deleted > 0:
                        self.log_info(f"已清理 {len(resource_ids)} 个资源下的旧资产数据: {total_deleted} 条")
                except Exception as e:
                    self.log_warning(f"清理旧资产数据失败: {str(e)}，将继续导入新数据")
            
            # 导入服务器资产
            if 'server' in self.asset_types_to_import:
                imported, failed = self._import_servers(resources)
                total_imported += imported
                total_failed += failed
                result['data']['servers'] = {'imported': imported, 'failed': failed}
            
            # 对每个资源，导入其他资产（如软件包）
            for resource in resources:
                resource_id = resource.get('resourceId')
                if not resource_id:
                    continue
                
                self.log_info(f"开始导入资源 {resource_id} 的其他资产")
                
                # 导入软件包资产（通过SBOM）
                if 'software' in self.asset_types_to_import:
                    try:
                        imported, failed = self._import_software_assets(resource_id, resource)
                        total_imported += imported
                        total_failed += failed
                        
                        if 'software' not in result['data']:
                            result['data']['software'] = {'imported': 0, 'failed': 0}
                        result['data']['software']['imported'] += imported
                        result['data']['software']['failed'] += failed
                        
                        if imported > 0:
                            self.log_info(f"成功导入软件包资产: {imported} 条")
                    except Exception as e:
                        self.log_error(f"导入软件包资产失败: {str(e)}", exc_info=True)
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
            if not logs or logs.strip() == '':
                logs = f"执行完成\n成功: {result.get('success', False)}\n消息: {result.get('message', '')}\n"
            result['logs'] = logs
            self.logger.removeHandler(self.log_handler)
        except Exception as e:
            result['logs'] = f'获取日志失败: {str(e)}'
        
        return result
    
    def _get_all_resources(self) -> List[Dict]:
        """
        获取所有覆盖的资源（EC2实例）
        
        Returns:
            list: 资源列表
        """
        resources = []
        next_token = None
        
        try:
            while True:
                request_params = {
                    'maxResults': self.page_size,
                }
                
                if next_token:
                    request_params['nextToken'] = next_token
                
                response = self.inspector2_client.list_coverage(**request_params)
                
                # 获取资源列表
                covered_resources = response.get('coveredResources', [])
                if not covered_resources:
                    break
                
                resources.extend(covered_resources)
                
                # 检查是否还有下一页
                next_token = response.get('nextToken')
                if not next_token:
                    break
                
                self.log_info(f"已获取 {len(resources)} 个资源，继续获取下一页...")
                
        except self.ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            # 提供更详细的错误信息和解决建议
            if error_code == 'UnrecognizedClientException':
                detailed_msg = (
                    f"AWS认证失败: {error_message}\n"
                    f"可能的原因：\n"
                    f"1. 使用根用户/长期 AK/SK 时，配置中仍填写了 Session Token（临时凭证），导致请求被当作临时凭证校验而失败\n"
                    f"2. Access Key ID 或 Secret Access Key 不正确\n"
                    f"3. 凭证已过期或被禁用\n"
                    f"4. IAM用户/角色没有 Inspector2 权限\n"
                    f"5. 区域配置不正确（当前区域: {self.config.get('region', 'ap-northeast-1')})\n\n"
                    f"解决方案：\n"
                    f"1. 若使用根用户或长期 AK/SK：请在 AWS 配置中清空 Session Token 字段（留空）\n"
                    f"2. AWS 报错中的「security token」有时指整组凭证：请用本地 AWS CLI 验证 AK/SK 是否有效：\n"
                    f"   export AWS_ACCESS_KEY_ID=你的AK && export AWS_SECRET_ACCESS_KEY=你的SK && export AWS_DEFAULT_REGION=ap-northeast-1 && aws sts get-caller-identity\n"
                    f"3. 检查 AWS 控制台：该 Access Key 是否被禁用、是否已删除或重新生成\n"
                    f"4. 确认 IAM 用户/角色具有以下权限：\n"
                    f"   - inspector2:ListCoverage\n"
                    f"   - inspector2:ListFindings\n"
                    f"   - inspector2:GetFindings\n"
                    f"   - inspector2:BatchGetFindings\n"
                    f"   - ec2:DescribeInstances (用于获取EC2实例详情)\n"
                    f"5. 确认区域设置正确（例如：ap-northeast-1 表示东京）"
                )
                self.log_error(detailed_msg)
            elif error_code == 'AccessDeniedException':
                detailed_msg = (
                    f"AWS权限不足: {error_message}\n"
                    f"请确保IAM用户/角色具有以下权限：\n"
                    f"   - inspector2:ListCoverage\n"
                    f"   - inspector2:ListFindings\n"
                    f"   - inspector2:GetFindings\n"
                    f"   - inspector2:BatchGetFindings\n"
                    f"   - ec2:DescribeInstances"
                )
                self.log_error(detailed_msg)
            else:
                self.log_error(f"获取资源列表失败 (AWS错误): {error_code} - {error_message}")
            raise
        except Exception as e:
            self.log_error(f"获取资源列表失败: {str(e)}")
            raise
        
        return resources
    
    def _import_servers(self, resources: List[Dict]) -> tuple:
        """
        导入服务器资产（EC2实例）
        
        Args:
            resources: 资源列表
            
        Returns:
            tuple: (成功数量, 失败数量)
        """
        assets_data = []
        
        for resource in resources:
            try:
                resource_id = resource.get('resourceId')
                resource_type = resource.get('resourceType', '')
                
                # 只处理EC2实例
                if resource_type != 'AWS_EC2_INSTANCE' or not resource_id:
                    continue
                
                # 获取EC2实例的详细信息
                instance_info = self._get_ec2_instance_info(resource_id)
                
                # 构建资产数据
                asset_data = {
                    'asset_type': 'server',
                    'uuid': resource_id,
                    'name': instance_info.get('name', resource_id),
                    'host_uuid': resource_id,
                    'data': {
                        'resourceId': resource_id,
                        'resourceType': resource_type,
                        'accountId': resource.get('accountId'),
                        'scanStatus': resource.get('scanStatus', {}),
                        'ec2InstanceInfo': instance_info,
                        'coverageStatus': resource.get('coverageStatus', {}),
                    },
                    'source': 'aws_inspector'
                }
                
                assets_data.append(asset_data)
                
            except Exception as e:
                self.log_error(f"处理服务器资源失败: {str(e)}")
        
        return DBHelper.batch_save_assets(assets_data)
    
    def _get_ec2_instance_info(self, instance_id: str) -> Dict:
        """
        获取EC2实例的详细信息
        
        Args:
            instance_id: EC2实例ID
            
        Returns:
            dict: 实例信息
        """
        try:
            response = self.ec2_client.describe_instances(InstanceIds=[instance_id])
            
            if not response.get('Reservations'):
                return {'name': instance_id}
            
            instance = response['Reservations'][0]['Instances'][0]
            
            # 提取实例信息
            instance_info = {
                'instanceId': instance.get('InstanceId'),
                'name': self._get_instance_name(instance),
                'instanceType': instance.get('InstanceType'),
                'state': instance.get('State', {}).get('Name'),
                'privateIpAddress': instance.get('PrivateIpAddress'),
                'publicIpAddress': instance.get('PublicIpAddress'),
                'imageId': instance.get('ImageId'),
                'launchTime': instance.get('LaunchTime').isoformat() if instance.get('LaunchTime') else None,
                'tags': {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])},
                'securityGroups': [
                    {
                        'groupId': sg.get('GroupId'),
                        'groupName': sg.get('GroupName'),
                    }
                    for sg in instance.get('SecurityGroups', [])
                ],
                'vpcId': instance.get('VpcId'),
                'subnetId': instance.get('SubnetId'),
            }
            
            return instance_info
            
        except self.ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == 'InvalidInstanceID.NotFound':
                self.log_warning(f"EC2实例不存在: {instance_id}")
            else:
                self.log_warning(f"获取EC2实例信息失败: {error_code} - {str(e)}")
            return {'name': instance_id}
        except Exception as e:
            self.log_warning(f"获取EC2实例信息异常: {str(e)}")
            return {'name': instance_id}
    
    def _get_instance_name(self, instance: Dict) -> str:
        """从实例标签中获取名称"""
        tags = instance.get('Tags', [])
        for tag in tags:
            if tag.get('Key') == 'Name':
                return tag.get('Value', '')
        return instance.get('InstanceId', '')
    
    def _import_software_assets(self, resource_id: str, resource: Dict) -> tuple:
        """
        导入软件包资产（通过SBOM）
        
        Args:
            resource_id: 资源ID
            resource: 资源信息
            
        Returns:
            tuple: (成功数量, 失败数量)
        """
        assets_data = []
        
        try:
            # 获取该资源的发现项（findings），仅 PACKAGE_VULNERABILITY 类型包含软件包信息
            findings = self._get_findings_for_resource(resource_id)
            if not findings:
                self.log_info(f"资源 {resource_id} 暂无发现项（若实例未扫描或无漏洞，则无软件包数据）")
            else:
                self.log_info(f"资源 {resource_id} 获取到 {len(findings)} 个发现项")
            software_packages = self._extract_software_packages(findings, resource_id)
            if findings and not software_packages:
                self.log_info(f"资源 {resource_id} 发现项中未解析出软件包（仅从包漏洞类发现中提取）")
            elif software_packages:
                self.log_info(f"资源 {resource_id} 提取到 {len(software_packages)} 个软件包")
            
            for pkg in software_packages:
                try:
                    # 生成软件包的UUID
                    pkg_name = pkg.get('name', '')
                    pkg_version = pkg.get('version', '')
                    pkg_uuid = self._generate_software_uuid(resource_id, pkg_name, pkg_version)
                    
                    assets_data.append({
                        'asset_type': 'software',
                        'uuid': pkg_uuid,
                        'name': f"{pkg_name} {pkg_version}" if pkg_version else pkg_name,
                        'host_uuid': resource_id,
                        'data': {
                            'packageName': pkg_name,
                            'packageVersion': pkg_version,
                            'packageManager': pkg.get('packageManager', ''),
                            'architecture': pkg.get('architecture', ''),
                            'filePath': pkg.get('filePath', ''),
                            'resourceId': resource_id,
                            'source': 'aws_inspector',
                        },
                        'source': 'aws_inspector'
                    })
                except Exception as e:
                    self.log_error(f"处理软件包数据失败: {str(e)}")
            
        except Exception as e:
            self.log_error(f"获取软件包资产失败: {str(e)}")
        
        return DBHelper.batch_save_assets(assets_data)
    
    def _get_findings_for_resource(self, resource_id: str) -> List[Dict]:
        """
        获取指定资源的发现项
        
        Args:
            resource_id: 资源ID
            
        Returns:
            list: 发现项列表
        """
        findings = []
        next_token = None
        
        try:
            while True:
                request_params = {
                    'filterCriteria': {
                        'resourceId': [
                            {'comparison': 'EQUALS', 'value': resource_id}
                        ]
                    },
                    'maxResults': self.page_size,
                }
                if next_token:
                    request_params['nextToken'] = next_token

                response = self.inspector2_client.list_findings(**request_params)
                # ListFindings 返回的是 findings（完整 Finding 对象），不是 findingArns
                batch = response.get('findings', [])
                if batch:
                    findings.extend(batch)
                
                next_token = response.get('nextToken')
                if not next_token:
                    break
                
        except self.ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            self.log_warning(f"获取发现项失败 (AWS错误): {error_code} - {error_message}")
        except Exception as e:
            self.log_warning(f"获取发现项失败: {str(e)}")
        
        return findings
    
    def _extract_software_packages(self, findings: List[Dict], resource_id: str) -> List[Dict]:
        """
        从发现项中提取软件包信息
        
        Args:
            findings: 发现项列表
            resource_id: 资源ID
            
        Returns:
            list: 软件包列表
        """
        packages = []
        seen_packages = set()  # 用于去重
        
        for finding in findings:
            try:
                # 仅处理包漏洞类发现（PACKAGE_VULNERABILITY），软件包在 packageVulnerabilityDetails.vulnerablePackages
                if finding.get('type') != 'PACKAGE_VULNERABILITY':
                    continue
                package_vuln = finding.get('packageVulnerabilityDetails') or {}
                vulnerable_pkgs = package_vuln.get('vulnerablePackages') or []
                if not vulnerable_pkgs:
                    continue
                resource_list = finding.get('resources', [])
                resource_details = (resource_list[0].get('details', {}) if resource_list else {}).get('awsEc2Instance', {})
                for pkg in vulnerable_pkgs:
                    pkg_name = (pkg.get('name') or '').strip()
                    if not pkg_name:
                        continue
                    pkg_version = (pkg.get('version') or '').strip()
                    pkg_key = f"{pkg_name}:{pkg_version}:{resource_id}"
                    if pkg_key in seen_packages:
                        continue
                    seen_packages.add(pkg_key)
                    packages.append({
                        'name': pkg_name,
                        'version': pkg_version,
                        'packageManager': pkg.get('packageManager', ''),
                        'architecture': pkg.get('arch', '') or resource_details.get('architecture', ''),
                        'filePath': pkg.get('filePath', ''),
                    })
            except Exception as e:
                self.log_warning(f"提取软件包信息失败: {str(e)}")
                continue
        
        return packages
    
    def _generate_software_uuid(self, resource_id: str, pkg_name: str, pkg_version: str) -> str:
        """
        生成软件包的UUID
        
        Args:
            resource_id: 资源ID
            pkg_name: 包名
            pkg_version: 包版本
            
        Returns:
            str: UUID
        """
        # 确保UUID长度不超过100字符
        unique_key = f"{pkg_name}_{pkg_version}" if pkg_version else pkg_name
        
        # 如果名称太长，使用哈希
        if len(unique_key) > 50:
            data_hash = hashlib.md5(unique_key.encode()).hexdigest()[:12]
            unique_key = f"{pkg_name[:30]}_{data_hash}"
        
        uuid = f"{resource_id}_software_{unique_key}"
        
        # 如果UUID还是太长，使用哈希
        if len(uuid) > 100:
            uuid_hash = hashlib.md5(uuid.encode()).hexdigest()[:12]
            uuid = f"{resource_id}_software_{uuid_hash}"
        
        return uuid


# 插件信息
PLUGIN_INFO = {
    'name': 'data_aws_inspector',
    'type': 'data',
    'description': 'AWS Inspector V2 资产指纹数据导入插件，支持导入EC2实例和软件包资产数据',
    'version': '1.0.0',
    'author': 'Bifang Team',
    'required_config': [
        {
            'key': 'access_key_id',
            'type': 'string',
            'description': 'AWS Access Key ID',
            'required': True
        },
        {
            'key': 'secret_access_key',
            'type': 'string',
            'description': 'AWS Secret Access Key',
            'required': True
        },
        {
            'key': 'region',
            'type': 'string',
            'description': 'AWS区域，如: ap-northeast-1 (东京)',
            'required': False,
            'default': 'ap-northeast-1'
        },
        {
            'key': 'session_token',
            'type': 'string',
            'description': 'AWS Session Token（临时凭证，可选）',
            'required': False
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


