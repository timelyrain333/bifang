"""
飞书机器人消息发送工具
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


def send_feishu_message(webhook_url: str, title: str, text: str, secret: str = None, 
                       message_type: str = 'interactive') -> dict:
    """
    发送飞书机器人消息
    
    Args:
        webhook_url: 飞书机器人Webhook地址
        title: 消息标题
        text: 消息内容
        secret: 加签密钥（可选）
        message_type: 消息类型，'text' 或 'interactive'，默认 'interactive'
    
    Returns:
        dict: {'success': bool, 'message': str, 'data': dict}
    """
    try:
        # 验证webhook URL格式
        if not webhook_url:
            return {
                'success': False,
                'message': 'Webhook地址不能为空',
                'data': {}
            }
        
        webhook_url = webhook_url.strip()
        
        if not webhook_url.startswith('https://'):
            return {
                'success': False,
                'message': 'Webhook地址格式不正确，必须以https://开头',
                'data': {}
            }
        
        # 验证是否是飞书webhook地址格式
        if 'open.feishu.cn' not in webhook_url and 'larkoffice.com' not in webhook_url:
            return {
                'success': False,
                'message': 'Webhook地址格式不正确，应该是飞书官方地址（open.feishu.cn 或 larkoffice.com）',
                'data': {}
            }
        
        # 如果提供了secret，需要生成签名并添加到URL参数中
        if secret:
            # 获取当前时间戳（秒级，整数）
            # 注意：飞书要求时间戳与服务器时间相差不超过1小时
            current_time = time.time()
            timestamp = int(current_time)
            
            # 拼接待签名字符串：timestamp + "\n" + secret
            # 根据飞书官方文档：将 timestamp + "\n" + 密钥 当做签名字符串
            string_to_sign = f'{timestamp}\n{secret}'
            
            # 使用HMAC-SHA256算法计算签名
            # 根据飞书官方文档的Java示例：密钥是stringToSign，消息是空字节数组
            # Python实现：hmac.new(key, msg, digestmod)
            hmac_code = hmac.new(
                string_to_sign.encode('utf-8'),  # 密钥：string_to_sign
                b'',  # 消息：空字节数组（根据Java示例：mac.doFinal(new byte[]{})）
                digestmod=hashlib.sha256
            ).digest()
            
            # Base64编码
            sign = base64.b64encode(hmac_code).decode('utf-8')
            
            # 在URL中添加timestamp和sign参数
            # 根据飞书官方文档，sign参数需要URL编码
            separator = '&' if '?' in webhook_url else '?'
            # 使用quote_plus进行URL编码（将+转换为%2B，=转换为%3D，/转换为%2F）
            sign_encoded = urllib.parse.quote_plus(sign)
            webhook_url = f"{webhook_url}{separator}timestamp={timestamp}&sign={sign_encoded}"
            
            # 记录调试信息（帮助排查问题）
            logger.info(f"飞书加签: timestamp={timestamp}, sign长度={len(sign)}, webhook_url前100字符={webhook_url[:100]}")
        
        # 构建消息内容
        if message_type == 'interactive':
            # 飞书交互式卡片格式（支持Markdown）
            message = {
                "msg_type": "interactive",
                "card": {
                    "config": {
                        "wide_screen_mode": True,
                        "enable_forward": True
                    },
                    "header": {
                        "title": {
                            "tag": "plain_text",
                            "content": title
                        },
                        "template": "blue"  # blue, green, red, orange, yellow, purple
                    },
                    "elements": [
                        {
                            "tag": "div",
                            "text": {
                                "tag": "lark_md",
                                "content": text
                            }
                        }
                    ]
                }
            }
        else:
            # 纯文本消息
            message = {
                "msg_type": "text",
                "content": {
                    "text": f"{title}\n\n{text}"
                }
            }
        
        # 发送请求
        response = requests.post(
            webhook_url,
            json=message,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        # 检查响应状态
        if response.status_code != 200:
            return {
                'success': False,
                'message': f'HTTP请求失败: {response.status_code}',
                'data': {'status_code': response.status_code, 'text': response.text[:200]}
            }
        
        try:
            result = response.json()
        except json.JSONDecodeError:
            return {
                'success': False,
                'message': f'响应解析失败: {response.text[:200]}',
                'data': {'text': response.text[:200]}
            }
        
        if result.get('code') == 0 or result.get('StatusCode') == 0:
            return {
                'success': True,
                'message': '消息发送成功',
                'data': result
            }
        else:
            error_msg = result.get('msg') or result.get('StatusMessage') or '未知错误'
            # 提供更详细的错误信息
            if 'access token invalid' in error_msg.lower() or 'token invalid' in error_msg.lower():
                error_msg = f'{error_msg}。请检查Webhook地址是否正确，确保从飞书群聊中正确获取Webhook地址。'
            return {
                'success': False,
                'message': f'消息发送失败: {error_msg}',
                'data': result
            }
    
    except Exception as e:
        logger.error(f"发送飞书消息失败: {str(e)}", exc_info=True)
        return {
            'success': False,
            'message': f'发送失败: {str(e)}',
            'data': {}
        }


def format_vulnerability_message(vulnerability) -> tuple:
    """
    格式化漏洞信息为飞书消息
    
    Args:
        vulnerability: Vulnerability模型实例
    
    Returns:
        tuple: (title, content) 标题和内容
    """
    content = vulnerability.content if isinstance(vulnerability.content, dict) else {}
    
    title = f"漏洞预警: {vulnerability.cve_id}"
    
    # 构建Markdown格式的消息内容（飞书支持Markdown）
    text_parts = [
        f"## {vulnerability.cve_id}",
        f"**{vulnerability.title}**",
        "",
        "### 基本信息",
        f"- **CVE编号**: `{vulnerability.cve_id}`",
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
        text_parts.append(f"### 危害等级: **{severity}**")
    
    # 影响组件和版本
    affected_component = content.get('affected_component', '')
    affected_versions = content.get('affected_versions', '')
    if affected_component or affected_versions:
        text_parts.append("")
        text_parts.append("### 影响范围")
        if affected_component:
            text_parts.append(f"- **影响组件**: `{affected_component}`")
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


def send_vulnerability_to_feishu(config, vulnerability) -> dict:
    """
    发送漏洞信息到飞书群
    
    Args:
        config: AliyunConfig模型实例（包含飞书配置）
        vulnerability: Vulnerability模型实例
    
    Returns:
        dict: 发送结果
    """
    if not config.feishu_enabled or not config.feishu_webhook:
        return {
            'success': False,
            'message': '飞书通知未启用或Webhook未配置'
        }
    
    title, text = format_vulnerability_message(vulnerability)
    
    return send_feishu_message(
        webhook_url=config.feishu_webhook,
        title=title,
        text=text,
        secret=config.feishu_secret if config.feishu_secret else None
    )


def format_security_alert_message(alert) -> tuple:
    """
    格式化安全告警信息为飞书消息
    
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
    
    # 构建Markdown格式的消息内容（飞书支持Markdown）
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
        text_parts.append(f"- **告警ID**: `{alert.alert_id}`")
    
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
        text_parts.append(f"- **实例ID**: `{alert.instance_id}`")
    if alert.ip:
        text_parts.append(f"- **IP地址**: `{alert.ip}`")
    if alert.uuid:
        text_parts.append(f"- **资产UUID**: `{alert.uuid}`")
    
    # 告警详情（从data字段中提取）
    alert_data = alert.data if isinstance(alert.data, dict) else {}
    
    # 添加详细信息
    if alert_data:
        text_parts.append("")
        text_parts.append("### 详细信息")
        
        # 尝试提取关键信息
        detail_fields = [
            ('Description', '描述'),
            ('Details', '详情'),
            ('Solution', '解决方案'),
            ('DataSource', '数据来源'),
            ('EventSubType', '事件子类型'),
            ('CanCancelFault', '可取消故障'),
            ('OperateMsg', '操作消息'),
        ]
        
        for field_key, field_name in detail_fields:
            if field_key in alert_data and alert_data[field_key]:
                value = str(alert_data[field_key])
                if len(value) > 200:
                    value = value[:200] + '...'
                text_parts.append(f"- **{field_name}**: {value}")
        
        # 如果有路径信息
        if 'Path' in alert_data:
            text_parts.append(f"- **路径**: `{alert_data['Path']}`")
        
        # 如果有进程信息
        if 'ProcessName' in alert_data:
            text_parts.append(f"- **进程名**: `{alert_data['ProcessName']}`")
    
    # 添加唯一标识（用于查询详情）
    if alert.unique_info:
        text_parts.append("")
        text_parts.append(f"**唯一标识**: `{alert.unique_info}`")
    
    text = "\n".join(text_parts)
    
    return title, text


