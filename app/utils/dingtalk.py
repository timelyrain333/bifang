"""
钉钉机器人消息发送工具
"""
import json
import time
import hmac
import hashlib
import base64
import urllib.parse
import requests
import logging

logger = logging.getLogger(__name__)


def send_dingtalk_message(webhook_url: str, title: str, text: str, secret: str = None, 
                         message_type: str = 'markdown') -> dict:
    """
    发送钉钉机器人消息
    
    Args:
        webhook_url: 钉钉机器人Webhook地址
        title: 消息标题
        text: 消息内容
        secret: 加签密钥（可选）
        message_type: 消息类型，'text' 或 'markdown'，默认 'markdown'
    
    Returns:
        dict: {'success': bool, 'message': str, 'data': dict}
    """
    try:
        # 如果提供了secret，需要生成签名
        if secret:
            timestamp = str(round(time.time() * 1000))
            secret_enc = secret.encode('utf-8')
            string_to_sign = f'{timestamp}\n{secret}'
            string_to_sign_enc = string_to_sign.encode('utf-8')
            hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
            sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
            webhook_url = f"{webhook_url}&timestamp={timestamp}&sign={sign}"
        
        # 构建消息内容
        if message_type == 'markdown':
            message = {
                "msgtype": "markdown",
                "markdown": {
                    "title": title,
                    "text": text
                }
            }
        else:
            message = {
                "msgtype": "text",
                "text": {
                    "content": f"{title}\n\n{text}"
                }
            }
        
        # 发送请求
        response = requests.post(
            webhook_url,
            json=message,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        result = response.json()
        
        if result.get('errcode') == 0:
            return {
                'success': True,
                'message': '消息发送成功',
                'data': result
            }
        else:
            error_msg = result.get('errmsg', '未知错误')
            return {
                'success': False,
                'message': f'消息发送失败: {error_msg}',
                'data': result
            }
    
    except Exception as e:
        logger.error(f"发送钉钉消息失败: {str(e)}", exc_info=True)
        return {
            'success': False,
            'message': f'发送失败: {str(e)}',
            'data': {}
        }


def format_vulnerability_message(vulnerability) -> tuple:
    """
    格式化漏洞信息为钉钉消息
    
    Args:
        vulnerability: Vulnerability模型实例
    
    Returns:
        tuple: (title, content) 标题和内容
    """
    content = vulnerability.content if isinstance(vulnerability.content, dict) else {}
    
    title = f"漏洞预警: {vulnerability.cve_id}"
    
    # 构建Markdown格式的消息内容
    text_parts = [
        f"## {vulnerability.cve_id} - {vulnerability.title}",
        "",
        "### 基本信息",
        f"- **CVE编号**: {vulnerability.cve_id}",
        f"- **标题**: {vulnerability.title}",
    ]
    
    if vulnerability.published_date:
        text_parts.append(f"- **发布日期**: {vulnerability.published_date}")
    
    # 基本描述
    basic_desc = content.get('basic_description', '')
    if basic_desc:
        text_parts.append("")
        text_parts.append("### 基本描述")
        text_parts.append(basic_desc[:500])  # 限制长度
    
    # 漏洞描述
    vuln_desc = content.get('vulnerability_description', vulnerability.description or '')
    if vuln_desc:
        text_parts.append("")
        text_parts.append("### 漏洞描述")
        text_parts.append(vuln_desc[:1000])  # 限制长度
    
    # 漏洞影响
    impact = content.get('impact', '')
    if impact:
        text_parts.append("")
        text_parts.append("### 漏洞影响")
        text_parts.append(impact[:500])
    
    # 危害等级
    severity = content.get('severity', '')
    if severity:
        text_parts.append("")
        text_parts.append(f"### 危害等级: {severity}")
    
    # 影响组件和版本
    affected_component = content.get('affected_component', '')
    affected_versions = content.get('affected_versions', '')
    if affected_component or affected_versions:
        text_parts.append("")
        text_parts.append("### 影响范围")
        if affected_component:
            text_parts.append(f"- **影响组件**: {affected_component}")
        if affected_versions:
            text_parts.append(f"- **影响版本**: {affected_versions[:500]}")
    
    # 解决方案
    solution = content.get('solution', '')
    if solution:
        text_parts.append("")
        text_parts.append("### 解决方案")
        text_parts.append(solution[:500])
    
    # 缓解措施
    mitigation = content.get('mitigation', '')
    if mitigation:
        text_parts.append("")
        text_parts.append("### 临时缓解措施")
        text_parts.append(mitigation[:500])
    
    # 参考链接
    references = content.get('references', [])
    if references:
        text_parts.append("")
        text_parts.append("### 参考链接")
        for ref in references[:5]:  # 最多显示5个链接
            text_parts.append(f"- {ref}")
    
    # 添加详情链接
    if vulnerability.url:
        text_parts.append("")
        text_parts.append(f"**详情**: {vulnerability.url}")
    
    text = "\n".join(text_parts)
    
    return title, text


def send_vulnerability_to_dingtalk(config, vulnerability) -> dict:
    """
    发送漏洞信息到钉钉群
    
    Args:
        config: AliyunConfig模型实例（包含钉钉配置）
        vulnerability: Vulnerability模型实例
    
    Returns:
        dict: 发送结果
    """
    if not config.dingtalk_enabled or not config.dingtalk_webhook:
        return {
            'success': False,
            'message': '钉钉通知未启用或Webhook未配置'
        }
    
    title, text = format_vulnerability_message(vulnerability)
    
    return send_dingtalk_message(
        webhook_url=config.dingtalk_webhook,
        title=title,
        text=text,
        secret=config.dingtalk_secret if config.dingtalk_secret else None
    )


def format_security_alert_message(alert) -> tuple:
    """
    格式化安全告警信息为钉钉消息
    
    Args:
        alert: SecurityAlert模型实例
    
    Returns:
        tuple: (title, content) 标题和内容
    """
    # 告警级别映射
    level_map = {
        'serious': '🔴 紧急',
        'suspicious': '🟡 可疑',
        'remind': '🟢 提醒',
    }
    
    level_text = level_map.get(alert.level, alert.level or '未知')
    
    # 标题
    title = f"安全告警: {alert.name}"
    
    # 构建Markdown格式的消息内容
    text_parts = [
        f"## {alert.name}",
        "",
        f"**告警级别**: {level_text}",
        f"**告警类型**: {alert.event_type or '未知'}",
        "",
        "### 基本信息",
    ]
    
    # 告警ID
    if alert.alert_id:
        text_parts.append(f"- **告警ID**: {alert.alert_id}")
    
    # 告警时间
    if alert.alert_time:
        text_parts.append(f"- **告警时间**: {alert.alert_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 处理状态
    status_map = {
        '0': '全部',
        '1': '待处理',
        '2': '已忽略',
        '4': '已确认',
        '8': '已标记误报',
        '16': '处理中',
        '32': '处理完毕',
        '64': '已经过期',
        '128': '已经删除',
    }
    status_text = status_map.get(alert.status, alert.status or '未知')
    text_parts.append(f"- **处理状态**: {status_text}")
    text_parts.append(f"- **是否已处理**: {'是' if alert.dealt else '否'}")
    
    # 资产信息
    if alert.instance_name:
        text_parts.append(f"- **实例名称**: {alert.instance_name}")
    if alert.instance_id:
        text_parts.append(f"- **实例ID**: {alert.instance_id}")
    if alert.ip:
        text_parts.append(f"- **IP地址**: {alert.ip}")
    if alert.uuid:
        text_parts.append(f"- **资产UUID**: {alert.uuid}")
    
    # 告警详情（从data字段中提取）
    alert_data = alert.data if isinstance(alert.data, dict) else {}
    
    # 添加详细信息
    if alert_data:
        text_parts.append("")
        text_parts.append("### 详细信息")
        
        # 处理Details字段（可能是列表或字典）
        if 'Details' in alert_data and alert_data['Details']:
            details = alert_data['Details']
            # 如果Details是列表，格式化每个项目
            if isinstance(details, list):
                for detail_item in details:
                    if isinstance(detail_item, dict):
                        # 提取可读的字段
                        name_display = detail_item.get('NameDisplay') or detail_item.get('Name', '')
                        value_display = detail_item.get('ValueDisplay') or detail_item.get('Value', '')
                        
                        if name_display and value_display:
                            # 限制长度，避免消息过长
                            if len(value_display) > 500:
                                value_display = value_display[:500] + '...'
                            text_parts.append(f"- **{name_display}**: {value_display}")
                        elif value_display:
                            # 如果没有名称，只显示值
                            if len(value_display) > 500:
                                value_display = value_display[:500] + '...'
                            text_parts.append(f"- {value_display}")
            elif isinstance(details, dict):
                # 如果是字典，直接格式化
                for key, value in details.items():
                    value_str = str(value)
                    if len(value_str) > 500:
                        value_str = value_str[:500] + '...'
                    text_parts.append(f"- **{key}**: {value_str}")
            else:
                # 其他类型，转换为字符串
                value_str = str(details)
                if len(value_str) > 500:
                    value_str = value_str[:500] + '...'
                text_parts.append(f"- **详情**: {value_str}")
        
        # 尝试提取其他关键信息
        detail_fields = [
            ('Description', '描述'),
            ('Solution', '解决方案'),
            ('DataSource', '数据来源'),
            ('EventSubType', '事件子类型'),
            ('CanCancelFault', '可取消故障'),
            ('OperateMsg', '操作消息'),
        ]
        
        for field_key, field_name in detail_fields:
            if field_key in alert_data and alert_data[field_key]:
                value = str(alert_data[field_key])
                if len(value) > 500:
                    value = value[:500] + '...'
                text_parts.append(f"- **{field_name}**: {value}")
        
        # 如果有路径信息
        if 'Path' in alert_data:
            text_parts.append(f"- **路径**: {alert_data['Path']}")
        
        # 如果有进程信息
        if 'ProcessName' in alert_data:
            text_parts.append(f"- **进程名**: {alert_data['ProcessName']}")
        
        # 处理Details数组中的其他字段（如木马文件路径、文件MD5等）
        if 'Details' in alert_data and isinstance(alert_data['Details'], list):
            for detail_item in alert_data['Details']:
                if isinstance(detail_item, dict):
                    # 提取特殊字段
                    info_type = detail_item.get('InfoType', '')
                    value_display = detail_item.get('ValueDisplay') or detail_item.get('Value', '')
                    name_display = detail_item.get('NameDisplay') or detail_item.get('Name', '')
                    
                    # 如果是特殊类型（如木马路径、文件MD5等），单独显示
                    if info_type and value_display:
                        type_map = {
                            'trojan_path': '木马文件路径',
                            'file_md5': '文件MD5',
                            'file_path': '文件路径',
                        }
                        label = type_map.get(info_type, info_type)
                        text_parts.append(f"- **{label}**: {value_display}")
                    elif name_display and value_display and name_display not in ['提示', '详情']:
                        # 避免重复显示已处理过的字段
                        if not any(name_display in line for line in text_parts):
                            if len(value_display) > 500:
                                value_display = value_display[:500] + '...'
                            text_parts.append(f"- **{name_display}**: {value_display}")
    
    # 添加唯一标识（用于查询详情）
    if alert.unique_info:
        text_parts.append("")
        text_parts.append(f"**唯一标识**: `{alert.unique_info}`")
    
    text = "\n".join(text_parts)
    
    return title, text


def send_dingtalk_message_via_stream(config, title: str, text: str, 
                                     open_conversation_id: str = None) -> dict:
    """
    通过钉钉Stream模式（企业应用内部机器人）发送消息
    
    使用Client ID和Client Secret获取access_token，然后调用钉钉API发送消息
    
    Args:
        config: AliyunConfig模型实例（包含钉钉配置）
        title: 消息标题
        text: 消息内容（markdown格式）
        open_conversation_id: 群会话ID（可选，如果不提供则尝试从配置中获取）
    
    Returns:
        dict: {'success': bool, 'message': str, 'data': dict}
    """
    try:
        # 检查配置
        if not config.dingtalk_enabled:
            return {
                'success': False,
                'message': '钉钉通知未启用'
            }
        
        if not config.dingtalk_client_id or not config.dingtalk_client_secret:
            return {
                'success': False,
                'message': '钉钉Client ID和Client Secret未配置'
            }
        
        # 获取access_token
        from app.services.dingtalk_stream_service import get_dingtalk_access_token
        access_token = get_dingtalk_access_token(
            config.dingtalk_client_id,
            config.dingtalk_client_secret
        )
        
        if not access_token:
            return {
                'success': False,
                'message': '获取钉钉AccessToken失败'
            }
        
        # 如果没有提供open_conversation_id，尝试从配置中获取
        # 注意：这里可能需要添加一个配置字段来存储群ID
        if not open_conversation_id:
            # 可以尝试从配置中获取（如果将来添加了该字段）
            # open_conversation_id = getattr(config, 'dingtalk_group_id', None)
            pass
        
        # 如果仍然没有open_conversation_id，使用机器人发送消息的API
        # 参考钉钉文档：https://open.dingtalk.com/document/dingstart/the-application-robot-in-the-enterprise-sends-group-chat-messages
        if open_conversation_id:
            # 发送到指定群
            from app.services.dingtalk_stream_service import send_dingtalk_group_message
            robot_code = getattr(config, 'dingtalk_app_id', None)
            success = send_dingtalk_group_message(
                access_token=access_token,
                open_conversation_id=open_conversation_id,
                text=text,
                robot_code=robot_code
            )
            
            if success:
                return {
                    'success': True,
                    'message': '消息发送成功',
                    'data': {}
                }
            else:
                return {
                    'success': False,
                    'message': '发送群聊消息失败',
                    'data': {}
                }
        else:
            # 如果没有群ID，Stream模式无法直接发送消息
            # 因为主动推送需要知道目标群会话ID
            # 提示用户配置群ID或使用Webhook模式
            logger.warning("Stream模式发送消息需要群会话ID（open_conversation_id），但未提供。"
                          "请确保机器人已加入目标群，或在配置中添加群会话ID。")
            return {
                'success': False,
                'message': 'Stream模式发送消息需要群会话ID（open_conversation_id）。'
                          '如果没有群ID，请使用Webhook模式，或确保机器人已加入目标群并配置群会话ID。'
            }
    
    except Exception as e:
        logger.error(f"通过Stream模式发送钉钉消息失败: {str(e)}", exc_info=True)
        return {
            'success': False,
            'message': f'发送失败: {str(e)}',
            'data': {}
        }


def send_security_alert_to_dingtalk(config, alert, use_stream: bool = True) -> dict:
    """
    发送安全告警到钉钉群
    
    Args:
        config: AliyunConfig模型实例（包含钉钉配置）
        alert: SecurityAlert模型实例
        use_stream: 是否使用Stream模式（企业应用内部机器人），默认True
    
    Returns:
        dict: 发送结果
    """
    if not config.dingtalk_enabled:
        return {
            'success': False,
            'message': '钉钉通知未启用'
        }
    
    title, text = format_security_alert_message(alert)
    
    # 优先使用Stream模式（企业应用内部机器人）
    if use_stream and config.dingtalk_use_stream_push and config.dingtalk_client_id and config.dingtalk_client_secret:
        result = send_dingtalk_message_via_stream(
            config=config,
            title=title,
            text=text
        )
        # 如果Stream模式失败（例如缺少群ID），回退到Webhook模式
        if not result.get('success') and config.dingtalk_webhook:
            logger.info("Stream模式发送失败，回退到Webhook模式")
            return send_dingtalk_message(
                webhook_url=config.dingtalk_webhook,
                title=title,
                text=text,
                secret=config.dingtalk_secret if config.dingtalk_secret else None
            )
        return result
    # 回退到Webhook模式
    elif config.dingtalk_webhook:
        return send_dingtalk_message(
            webhook_url=config.dingtalk_webhook,
            title=title,
            text=text,
            secret=config.dingtalk_secret if config.dingtalk_secret else None
        )
    else:
        return {
            'success': False,
            'message': '钉钉配置不完整：Stream模式需要Client ID和Client Secret，Webhook模式需要Webhook地址'
        }





