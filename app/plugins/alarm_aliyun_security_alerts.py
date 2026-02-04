"""
阿里云安全中心告警监控插件
定时获取安全告警并推送到钉钉/飞书
"""
import sys
import os
import logging
import io
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import django
from django.utils import timezone
from django.conf import settings

# 添加项目根目录到路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

# 确保Django已初始化
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bifang.settings')
try:
    django.setup()
except Exception:
    pass

from app.lib.base_plugin import BasePlugin

# 钉钉和飞书工具函数将在需要时动态导入（避免模块加载时的导入问题）

# 尝试导入阿里云SDK
def _check_aliyun_sdk():
    """检查阿里云SDK是否可用"""
    try:
        from aliyunsdkcore.client import AcsClient
        from aliyunsdkcore.acs_exception.exceptions import ClientException, ServerException
        from aliyunsdksas.request.v20181203 import DescribeSuspEventsRequest
        return True, AcsClient, ClientException, ServerException, DescribeSuspEventsRequest
    except ImportError as e:
        logging.warning(f"阿里云SDK未安装: {e}，请使用: pip install aliyun-python-sdk-core aliyun-python-sdk-sas")
        return False, None, None, None, None


class Plugin(BasePlugin):
    """阿里云安全中心告警监控插件"""
    
    def __init__(self, config=None):
        super().__init__(config)
        
        # 创建日志缓冲区
        self.log_buffer = io.StringIO()
        self.log_handler = logging.StreamHandler(self.log_buffer)
        self.log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.log_handler.setLevel(logging.DEBUG)
        # 确保日志被正确添加到logger
        if self.logger.handlers:
            # 移除可能存在的其他handler，避免日志重复
            for handler in self.logger.handlers[:]:
                if isinstance(handler, logging.StreamHandler) and handler.stream == self.log_buffer:
                    continue
        self.logger.addHandler(self.log_handler)
        self.logger.setLevel(logging.DEBUG)
        
        # 确保立即输出
        self.log_info("=" * 60)
        self.log_info("告警监控插件开始执行")
        self.log_info("=" * 60)
        
        # 验证配置
        required_keys = ['access_key_id', 'access_key_secret', 'region_id']
        try:
            self.validate_config(required_keys)
        except ValueError as e:
            self.log_error(f"配置验证失败: {str(e)}")
            raise
        
        # 检查SDK
        sdk_available, AcsClient, ClientException, ServerException, DescribeSuspEventsRequest = _check_aliyun_sdk()
        if not sdk_available:
            raise ImportError("阿里云SDK未安装，请使用: pip install aliyun-python-sdk-core aliyun-python-sdk-sas")
        
        self.AcsClient = AcsClient
        self.ClientException = ClientException
        self.ServerException = ServerException
        self.DescribeSuspEventsRequest = DescribeSuspEventsRequest
        
        # 初始化阿里云客户端
        self.client = AcsClient(
            self.config['access_key_id'],
            self.config['access_key_secret'],
            self.config.get('region_id', 'cn-hangzhou')
        )
        
        # 配置参数
        self.region_id = self.config.get('region_id', 'cn-hangzhou')
        self.page_size = self.config.get('page_size', 20)
        self.lookback_minutes = self.config.get('lookback_minutes', 1440)  # 默认查询最近24小时（1440分钟）
        # levels为空字符串表示查询所有级别
        levels_config = self.config.get('levels', 'serious,suspicious')
        self.levels = levels_config if levels_config and levels_config.strip() else None
        
        # dealt为空字符串表示查询所有状态
        dealt_config = self.config.get('dealed', 'N')
        self.dealed = dealt_config if dealt_config and dealt_config.strip() else None
        
        # 是否使用本地时间（而不是UTC时间）发送给API
        self.use_local_time = self.config.get('use_local_time', True)
        
        # 是否跳过时间范围设置（用于测试）
        self.skip_time_range = self.config.get('skip_time_range', False)
        
        # 是否跳过时间范围设置（用于测试，查询所有时间的告警）
        self.skip_time_range = self.config.get('skip_time_range', False)
        
        if not self.levels:
            self.log_info("未设置级别过滤，将查询所有级别的告警")
        if not self.dealed:
            self.log_info("未设置处理状态过滤，将查询所有状态的告警")
        self.push_dingtalk = self.config.get('push_dingtalk', True)
        self.push_feishu = self.config.get('push_feishu', True)
        # 是否强制重新推送（即使已经推送过）
        self.force_repush = self.config.get('force_repush', False)
        
        self.log_info(f"插件初始化成功，查询最近{self.lookback_minutes}分钟的告警")
    
    def execute(self, *args, **kwargs) -> Dict[str, Any]:
        """
        执行告警监控
        
        Returns:
            dict: 执行结果
        """
        # 确保日志缓冲区已准备好
        self.log_buffer.seek(0)
        self.log_buffer.truncate(0)
        
        result = {
            'success': True,
            'message': '告警监控完成',
            'data': {
                'total_fetched': 0,
                'new_alerts': 0,
                'pushed_dingtalk': 0,
                'pushed_feishu': 0,
                'failed': 0
            },
            'logs': []
        }
        
        try:
            self.log_info(f"开始执行告警监控任务")
            self.log_info(f"配置信息: region_id={self.region_id}, lookback_minutes={self.lookback_minutes}")
            # 导入Django模型（延迟导入，避免初始化问题）
            from django.apps import apps
            SecurityAlert = apps.get_model('app', 'SecurityAlert')
            AliyunConfig = apps.get_model('app', 'AliyunConfig')
            
            # 获取告警列表
            alerts = self._get_security_alerts()
            result['data']['total_fetched'] = len(alerts)
            self.log_info(f"总共获取到 {len(alerts)} 条告警")
            
            if alerts:
                self.log_info(f"第一条告警示例: {json.dumps(alerts[0] if isinstance(alerts[0], dict) else str(alerts[0]), ensure_ascii=False)[:200]}")
            
            if not alerts:
                result['message'] = '未发现新告警'
                return result
            
            # 处理每个告警
            new_alerts = []
            for alert_data in alerts:
                try:
                    # 检查是否已存在
                    # 根据API返回的数据，告警ID可能是SecurityEventIds或UniqueInfo
                    alert_id = str(
                        alert_data.get('Id') or 
                        alert_data.get('id') or 
                        alert_data.get('SecurityEventIds') or 
                        alert_data.get('UniqueInfo') or 
                        ''
                    )
                    unique_info = alert_data.get('UniqueInfo') or alert_data.get('AlarmUniqueInfo') or alert_id
                    
                    self.log_info(f"处理告警: ID={alert_id}, UniqueInfo={unique_info}, Name={alert_data.get('Name', 'N/A')}")
                    
                    # 解析处理状态
                    dealt_status = alert_data.get('Dealed', 'N') == 'Y' or alert_data.get('Dealed') == 'Y'
                    
                    # 创建或更新告警记录
                    alert, created = SecurityAlert.objects.get_or_create(
                        alert_id=alert_id,
                        defaults={
                            'unique_info': unique_info,
                            'name': alert_data.get('EventName') or 
                                   alert_data.get('AlarmEventNameDisplay') or 
                                   alert_data.get('AlarmEventName') or 
                                   alert_data.get('Name', '未知告警'),
                            'level': alert_data.get('Level') or self._parse_level_from_alert(alert_data),
                            'status': str(alert_data.get('Status') or alert_data.get('EventStatus', '')),
                            'dealt': dealt_status,
                            'alert_time': self._parse_datetime(
                                alert_data.get('OccurrenceTime') or 
                                alert_data.get('CreateTime') or 
                                alert_data.get('GmtCreate') or
                                alert_data.get('OperateTime') or
                                alert_data.get('LastTime') or
                                alert_data.get('EventTime') or
                                alert_data.get('AlarmTime') or
                                alert_data.get('FirstTime') or
                                alert_data.get('StartTime')
                            ),
                            'event_type': alert_data.get('EventType') or 
                                        alert_data.get('AlarmEventType') or
                                        alert_data.get('ParentEventType', ''),
                            'instance_id': alert_data.get('InstanceId', ''),
                            'instance_name': alert_data.get('InstanceName', ''),
                            'ip': alert_data.get('InternetIp') or alert_data.get('IntranetIp') or '',
                            'uuid': alert_data.get('Uuid', ''),
                            'data': alert_data,
                            # 新创建的告警，如果未处理，不标记为已推送
                            'pushed_to_dingtalk': False,
                            'pushed_to_feishu': False,
                        }
                    )
                    
                    # 如果已存在但数据有更新，更新数据
                    if not created:
                        self.log_info(f"告警已存在，更新数据: {alert.name} (ID: {alert_id})")
                        self.log_info(f"当前推送状态: pushed_to_dingtalk={alert.pushed_to_dingtalk}, pushed_to_feishu={alert.pushed_to_feishu}, dealt={alert.dealt}")
                        alert.data = alert_data
                        alert.updated_at = timezone.now()
                        # 更新处理状态（从API返回的数据中获取）
                        alert.dealt = alert_data.get('Dealed', 'N') == 'Y' or alert_data.get('Dealed') == 'Y'
                        # 更新event_type字段（用于判断是否为精准防御）
                        alert.event_type = alert_data.get('EventType') or alert_data.get('AlarmEventType') or alert_data.get('ParentEventType', '')
                        alert.save(update_fields=['data', 'updated_at', 'dealt', 'event_type'])
                        
                        # 判断是否为精准防御类型的告警
                        is_precision_defense = self._is_precision_defense_alert(alert)
                        
                        # 未处理的告警（dealt=False）始终加入推送队列，不管之前是否推送过
                        # 精准防御类型的告警，即使已处理也要加入推送队列
                        # 已处理的告警（dealt=True）如果之前推送过，则不再推送（精准防御除外）
                        if not alert.dealt:
                            # 未处理的告警，始终推送
                            new_alerts.append(alert)
                            self.log_info(f"告警未处理（dealt=False），加入推送队列: {alert.name}")
                        elif is_precision_defense:
                            # 精准防御类型的告警，即使已处理也要推送
                            new_alerts.append(alert)
                            self.log_info(f"精准防御类型告警（已处理），加入推送队列: {alert.name} (event_type={alert.event_type})")
                        elif not alert.pushed_to_dingtalk or not alert.pushed_to_feishu:
                            # 已处理但未推送过的告警，也加入推送队列
                            new_alerts.append(alert)
                            self.log_info(f"告警已处理但未完全推送，加入推送队列: {alert.name} (钉钉={not alert.pushed_to_dingtalk}, 飞书={not alert.pushed_to_feishu})")
                        else:
                            # 已处理且已推送的告警，不再推送
                            self.log_info(f"告警已处理且已推送，跳过: {alert.name}")
                    else:
                        new_alerts.append(alert)
                        result['data']['new_alerts'] += 1
                        self.log_info(f"发现新告警: {alert.name} (ID: {alert_id})")
                    
                except Exception as e:
                    self.log_error(f"处理告警失败: {str(e)}", exc_info=True)
                    result['data']['failed'] += 1
                    continue
            
            # 推送新告警
            self.log_info(f"准备推送告警: 新告警数={len(new_alerts)}, push_dingtalk={self.push_dingtalk}, push_feishu={self.push_feishu}")
            if new_alerts and (self.push_dingtalk or self.push_feishu):
                # 获取通知配置
                notification_config = self._get_notification_config()
                self.log_info(f"通知配置: dingtalk={'已配置' if notification_config.get('dingtalk') else '未配置'}, feishu={'已配置' if notification_config.get('feishu') else '未配置'}")
                
                if not notification_config.get('dingtalk') and not notification_config.get('feishu'):
                    self.log_warning("⚠️ 未找到可用的通知配置（钉钉或飞书），无法推送告警！请在系统配置中配置钉钉或飞书机器人。")
                
                for alert in new_alerts:
                    self.log_info(f"开始推送告警: {alert.name} (ID: {alert.alert_id})")
                    
                    # 推送到钉钉
                    if self.push_dingtalk:
                        if notification_config.get('dingtalk'):
                            try:
                                # 重新从数据库加载，确保获取最新的推送状态
                                alert.refresh_from_db()
                                # 判断是否为精准防御类型的告警
                                is_precision_defense = self._is_precision_defense_alert(alert)
                                
                                # 未处理的告警（dealt=False）始终推送，不管之前是否推送过
                                # 精准防御类型的告警，即使已处理也要推送
                                # 已处理的告警（dealt=True）如果之前推送过，则不再推送（精准防御除外）
                                should_push = False
                                if not alert.dealt:
                                    # 未处理的告警，始终推送
                                    should_push = True
                                    self.log_info(f"准备推送到钉钉（未处理告警，始终推送）: {alert.name}")
                                elif is_precision_defense:
                                    # 精准防御类型的告警，即使已处理也要推送
                                    should_push = True
                                    self.log_info(f"准备推送到钉钉（精准防御类型，已处理也要推送）: {alert.name} (event_type={alert.event_type})")
                                elif self.force_repush or not alert.pushed_to_dingtalk:
                                    # 已处理但未推送过，或者强制重新推送
                                    should_push = True
                                    self.log_info(f"准备推送到钉钉: {alert.name} (已处理={alert.dealt}, pushed_to_dingtalk={alert.pushed_to_dingtalk})")
                                
                                if should_push:
                                    success = self._push_to_dingtalk(alert, notification_config['dingtalk'])
                                    if success:
                                        # 只有已处理的告警才标记为已推送，未处理的告警不标记
                                        if alert.dealt:
                                            alert.pushed_to_dingtalk = True
                                            alert.pushed_at = timezone.now()
                                            alert.save(update_fields=['pushed_to_dingtalk', 'pushed_at'])
                                            self.log_info(f"✅ 成功推送到钉钉（已处理告警，已标记为已推送）: {alert.name}")
                                        else:
                                            # 未处理的告警不标记为已推送，下次还会推送
                                            self.log_info(f"✅ 成功推送到钉钉（未处理告警，不标记为已推送，下次仍会推送）: {alert.name}")
                                        result['data']['pushed_dingtalk'] += 1
                                    else:
                                        self.log_warning(f"❌ 推送到钉钉返回失败: {alert.name}，未更新推送状态")
                                else:
                                    self.log_info(f"⏭️ 告警已处理且已推送，跳过: {alert.name}")
                            except Exception as e:
                                self.log_error(f"推送到钉钉异常: {str(e)}", exc_info=True)
                        else:
                            self.log_warning(f"钉钉通知未配置，跳过推送: {alert.name}")
                    
                    # 推送到飞书
                    if self.push_feishu:
                        if notification_config.get('feishu'):
                            try:
                                # 重新从数据库加载，确保获取最新的推送状态
                                alert.refresh_from_db()
                                # 判断是否为精准防御类型的告警
                                is_precision_defense = self._is_precision_defense_alert(alert)
                                
                                # 未处理的告警（dealt=False）始终推送，不管之前是否推送过
                                # 精准防御类型的告警，即使已处理也要推送
                                # 已处理的告警（dealt=True）如果之前推送过，则不再推送（精准防御除外）
                                should_push = False
                                if not alert.dealt:
                                    # 未处理的告警，始终推送
                                    should_push = True
                                    self.log_info(f"准备推送到飞书（未处理告警，始终推送）: {alert.name}")
                                elif is_precision_defense:
                                    # 精准防御类型的告警，即使已处理也要推送
                                    should_push = True
                                    self.log_info(f"准备推送到飞书（精准防御类型，已处理也要推送）: {alert.name} (event_type={alert.event_type})")
                                elif self.force_repush or not alert.pushed_to_feishu:
                                    # 已处理但未推送过，或者强制重新推送
                                    should_push = True
                                    self.log_info(f"准备推送到飞书: {alert.name} (已处理={alert.dealt}, pushed_to_feishu={alert.pushed_to_feishu})")
                                
                                if should_push:
                                    success = self._push_to_feishu(alert, notification_config['feishu'])
                                    if success:
                                        # 只有已处理的告警才标记为已推送，未处理的告警不标记
                                        if alert.dealt:
                                            alert.pushed_to_feishu = True
                                            alert.pushed_at = timezone.now()
                                            alert.save(update_fields=['pushed_to_feishu', 'pushed_at'])
                                            self.log_info(f"✅ 成功推送到飞书（已处理告警，已标记为已推送）: {alert.name}")
                                        else:
                                            # 未处理的告警不标记为已推送，下次还会推送
                                            self.log_info(f"✅ 成功推送到飞书（未处理告警，不标记为已推送，下次仍会推送）: {alert.name}")
                                        result['data']['pushed_feishu'] += 1
                                    else:
                                        self.log_warning(f"❌ 推送到飞书返回失败: {alert.name}，未更新推送状态")
                                else:
                                    self.log_info(f"⏭️ 告警已处理且已推送，跳过: {alert.name}")
                            except Exception as e:
                                self.log_error(f"推送到飞书异常: {str(e)}", exc_info=True)
                        else:
                            self.log_warning(f"飞书通知未配置，跳过推送: {alert.name}")
            
            result['message'] = f"获取{result['data']['total_fetched']}条告警，新增{result['data']['new_alerts']}条，钉钉推送{result['data']['pushed_dingtalk']}条，飞书推送{result['data']['pushed_feishu']}条"
            
        except Exception as e:
            self.log_error(f"执行失败: {str(e)}", exc_info=True)
            result['success'] = False
            result['message'] = f"执行失败: {str(e)}"
        finally:
            # 确保日志handler刷新
            self.log_handler.flush()
            
            # 获取日志
            log_content = self.log_buffer.getvalue()
            if log_content and log_content.strip():
                result['logs'] = [line for line in log_content.split('\n') if line.strip()]
            else:
                # 如果日志为空，添加基本信息
                result['logs'] = [
                    f"插件执行完成",
                    f"成功: {result['success']}",
                    f"消息: {result['message']}",
                    f"获取告警数: {result['data']['total_fetched']}"
                ]
            
            # 添加执行结束标记
            self.log_info("=" * 60)
            self.log_info("告警监控插件执行完成")
            self.log_info("=" * 60)
            
            # 再次获取日志（包含结束标记）
            final_log_content = self.log_buffer.getvalue()
            if final_log_content and final_log_content.strip():
                result['logs'] = [line for line in final_log_content.split('\n') if line.strip()]
        
        return result
    
    def _get_security_alerts(self) -> List[Dict]:
        """
        获取安全告警列表
        
        Returns:
            list: 告警列表
        """
        alerts = []
        current_page = 1
        
        try:
            # 计算时间范围 - 使用Django配置的时区（应该是Asia/Shanghai）
            # timezone.now()返回UTC时间，需要转换为本地时区
            end_time_utc = timezone.now()
            # 转换为本地时区（Asia/Shanghai）
            end_time = timezone.localtime(end_time_utc)
            start_time = end_time - timedelta(minutes=self.lookback_minutes)
            
            # 显示时间（转换为本地时区）
            current_time = timezone.localtime(timezone.now())
            
            self.log_info(f"查询告警时间范围: {start_time.strftime('%Y-%m-%d %H:%M:%S')} 到 {end_time.strftime('%Y-%m-%d %H:%M:%S')} ({settings.TIME_ZONE})")
            self.log_info(f"查询条件: levels={self.levels or '全部'}, dealt={self.dealed or '全部'}")
            self.log_info(f"当前系统时间: {current_time.strftime('%Y-%m-%d %H:%M:%S')} ({settings.TIME_ZONE})")
            
            # 如果查询范围超过7天，给出警告（阿里云API可能有时间范围限制）
            if self.lookback_minutes > 7 * 24 * 60:
                self.log_warning(f"查询时间范围较大（{self.lookback_minutes}分钟），建议控制在7天内")
            
            while True:
                request = self.DescribeSuspEventsRequest.DescribeSuspEventsRequest()
                request.set_PageSize(self.page_size)
                request.set_CurrentPage(current_page)
                
                # 设置过滤条件
                # 注意：为了确保能查询到"精准防御"类型的已处理告警，即使配置了dealed='N'，
                # 我们也查询所有状态的告警，然后在处理时进行过滤
                # 如果dealed或levels为None或空字符串，不设置过滤条件
                # 如果配置了dealed='N'，我们仍然查询所有状态的告警，以便获取已处理的"精准防御"告警
                if self.dealed and self.dealed != 'N':
                    # 只有当dealed不是'N'时才设置过滤条件（例如dealed='Y'时只查询已处理的）
                    request.set_Dealed(self.dealed)
                    self.log_info(f"设置过滤条件: Dealed={self.dealed}")
                else:
                    if self.dealed == 'N':
                        self.log_info("配置了dealed='N'，但为了获取已处理的'精准防御'告警，查询所有状态的告警")
                    else:
                        self.log_info("未设置处理状态过滤，将查询所有状态的告警")
                
                if self.levels:
                    request.set_Levels(self.levels)
                    self.log_info(f"设置过滤条件: Levels={self.levels}")
                else:
                    self.log_info("未设置级别过滤，将查询所有级别的告警")
                
                # 设置时间范围
                # 注意：根据测试和文档，阿里云API的TimeStart/TimeEnd可能期望本地时间（北京时间）
                # 而不是UTC时间。我们先尝试使用本地时间。
                skip_time = self.skip_time_range
                
                if not skip_time:
                    # 使用本地时间（北京时间）- 不转换为UTC
                    # 因为阿里云API在中国区域通常使用北京时间
                    time_start_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
                    time_end_str = end_time.strftime('%Y-%m-%d %H:%M:%S')
                    request.set_TimeStart(time_start_str)
                    request.set_TimeEnd(time_end_str)
                    self.log_info(f"设置时间范围（本地时间，北京时间）: {time_start_str} 到 {time_end_str}")
                else:
                    self.log_info("跳过时间范围设置，查询所有时间的告警（用于测试）")
                
                # 如果查询失败，可以尝试使用UTC时间（备用方案，暂时注释）
                # from datetime import timezone as dt_timezone
                # utc_tz = dt_timezone.utc
                # if timezone.is_aware(start_time):
                #     start_time_utc = start_time.astimezone(utc_tz)
                #     end_time_utc = end_time.astimezone(utc_tz)
                #     start_time_utc_naive = timezone.make_naive(start_time_utc, utc_tz)
                #     end_time_utc_naive = timezone.make_naive(end_time_utc, utc_tz)
                #     time_start_str = start_time_utc_naive.strftime('%Y-%m-%d %H:%M:%S')
                #     time_end_str = end_time_utc_naive.strftime('%Y-%m-%d %H:%M:%S')
                #     request.set_TimeStart(time_start_str)
                #     request.set_TimeEnd(time_end_str)
                #     self.log_info(f"设置时间范围（UTC备用）: {time_start_str} 到 {time_end_str}")
                
                # 设置API endpoint（必须设置，否则会报错"No endpoint for product 'Sas'"）
                endpoint = self.config.get('api_endpoint')
                if not endpoint:
                    # 根据region_id自动生成endpoint
                    endpoint = f'https://sas.{self.region_id}.aliyuncs.com'
                request.set_endpoint(endpoint)
                
                # 输出完整的请求参数（用于调试）
                self.log_info(f"调用API: DescribeSuspEvents")
                self.log_info(f"  endpoint: {endpoint}")
                self.log_info(f"  page: {current_page}, page_size: {self.page_size}")
                if self.dealed:
                    self.log_info(f"  dealt: {self.dealed}")
                else:
                    self.log_info(f"  dealt: 未设置（查询所有状态）")
                if self.levels:
                    self.log_info(f"  levels: {self.levels}")
                else:
                    self.log_info(f"  levels: 未设置（查询所有级别）")
                if not skip_time:
                    self.log_info(f"  time_start: {time_start_str}, time_end: {time_end_str} (北京时间)")
                else:
                    self.log_info(f"  时间范围: 未设置（查询所有时间）")
                self.log_info(f"Region ID: {self.region_id}, 使用的endpoint: {endpoint}")
                
                # 发送请求
                response = self.client.do_action_with_exception(request)
                
                # 解析响应
                if isinstance(response, bytes):
                    response = response.decode('utf-8')
                response_data = json.loads(response)
                
                # 记录响应信息（调试用）
                self.log_info(f"API响应: RequestId={response_data.get('RequestId', 'N/A')}")
                # 输出完整的响应结构以便调试（限制长度）
                response_str = json.dumps(response_data, ensure_ascii=False, indent=2)
                if len(response_str) > 2000:
                    self.log_info(f"API响应内容（前2000字符）: {response_str[:2000]}")
                else:
                    self.log_info(f"API响应内容: {response_str}")
                
                # 检查是否有错误
                if 'Code' in response_data and response_data['Code'] != '200':
                    error_msg = response_data.get('Message', '未知错误')
                    self.log_warning(f"API返回错误: Code={response_data['Code']}, Message={error_msg}")
                    break
                
                # 获取告警列表 - 尝试多种可能的字段名
                page_alerts = []
                total_count = 0
                
                # 首先输出响应数据的顶层键，帮助调试
                self.log_info(f"响应数据顶层键: {list(response_data.keys())}")
                
                # 方法1: 检查SuspEvents字段（标准格式）
                if 'SuspEvents' in response_data:
                    susp_events = response_data['SuspEvents']
                    self.log_info(f"SuspEvents类型: {type(susp_events)}")
                    
                    if isinstance(susp_events, dict):
                        self.log_info(f"SuspEvents字典的键: {list(susp_events.keys())}")
                        # 尝试多个可能的字段名
                        for key in ['SuspEvent', 'SuspEvents', 'list', 'List', 'items', 'Items']:
                            if key in susp_events:
                                page_alerts = susp_events[key]
                                self.log_info(f"从SuspEvents.{key}获取到数据: {len(page_alerts) if isinstance(page_alerts, list) else 1}条")
                                break
                    elif isinstance(susp_events, list):
                        page_alerts = susp_events
                        self.log_info(f"从SuspEvents直接获取到列表: {len(page_alerts)}条")
                
                # 方法2: 检查List字段
                if not page_alerts and 'List' in response_data:
                    list_data = response_data['List']
                    self.log_info(f"List字段类型: {type(list_data)}")
                    if isinstance(list_data, list):
                        page_alerts = list_data
                        self.log_info(f"从List直接获取到列表: {len(page_alerts)}条")
                    elif isinstance(list_data, dict):
                        self.log_info(f"List字典的键: {list(list_data.keys())}")
                        for key in ['SuspEvent', 'list', 'List', 'items', 'Items']:
                            if key in list_data:
                                page_alerts = list_data[key]
                                self.log_info(f"从List.{key}获取到数据: {len(page_alerts) if isinstance(page_alerts, list) else 1}条")
                                break
                
                # 方法3: 检查其他可能的字段
                if not page_alerts:
                    for key in ['data', 'Data', 'result', 'Result', 'items', 'Items']:
                        if key in response_data:
                            data = response_data[key]
                            self.log_info(f"检查字段{key}: {type(data)}")
                            if isinstance(data, list):
                                page_alerts = data
                                self.log_info(f"从{key}获取到列表: {len(page_alerts)}条")
                                break
                            elif isinstance(data, dict):
                                for sub_key in ['SuspEvent', 'list', 'List', 'items', 'Items']:
                                    if sub_key in data:
                                        page_alerts = data[sub_key]
                                        self.log_info(f"从{key}.{sub_key}获取到数据: {len(page_alerts) if isinstance(page_alerts, list) else 1}条")
                                        break
                                if page_alerts:
                                    break
                
                # 方法4: 直接是数组
                if not page_alerts and isinstance(response_data, list):
                    page_alerts = response_data
                    self.log_info(f"响应本身就是数组: {len(page_alerts)}条")
                
                # 处理单个告警的情况
                if page_alerts and not isinstance(page_alerts, list):
                    page_alerts = [page_alerts]
                
                # 获取总数
                page_info = response_data.get('PageInfo', {})
                if isinstance(page_info, dict):
                    total_count = page_info.get('TotalCount', 0) or page_info.get('count', 0)
                else:
                    total_count = response_data.get('TotalCount', 0) or response_data.get('count', 0)
                
                self.log_info(f"第{current_page}页: 获取到{len(page_alerts) if isinstance(page_alerts, list) else 0}条告警，总计{total_count}条")
                
                if not page_alerts:
                    self.log_info("当前页无告警数据，结束查询")
                    break
                
                alerts.extend(page_alerts)
                
                # 检查是否还有下一页
                if total_count > 0 and len(alerts) >= total_count:
                    self.log_info(f"已获取全部{total_count}条告警，结束查询")
                    break
                
                if len(page_alerts) < self.page_size:
                    self.log_info("已到最后一页，结束查询")
                    break
                
                current_page += 1
                
                # 防止无限循环
                if current_page > 100:
                    self.log_warning("查询页数超过100页，强制结束")
                    break
                
        except self.ClientException as e:
            self.log_error(f"客户端错误: {str(e)}")
            raise
        except self.ServerException as e:
            self.log_error(f"服务器错误: {str(e)}")
            raise
        except Exception as e:
            self.log_error(f"获取告警列表失败: {str(e)}", exc_info=True)
            raise
        
        return alerts
    
    def _parse_level_from_alert(self, alert_data: Dict) -> str:
        """从告警数据中解析级别"""
        # 尝试多种可能的字段
        level = alert_data.get('Level') or alert_data.get('level') or alert_data.get('Severity')
        if level:
            return level
        
        # 根据告警类型或其他信息推断级别
        # 这里可以根据实际API返回的数据进行调整
        name = alert_data.get('Name', '') or alert_data.get('AlarmEventNameDisplay', '')
        if '高危' in name or 'serious' in name.lower():
            return 'serious'
        elif '可疑' in name or 'suspicious' in name.lower():
            return 'suspicious'
        elif '提醒' in name or 'remind' in name.lower():
            return 'remind'
        
        return 'suspicious'  # 默认值
    
    def _is_precision_defense_alert(self, alert) -> bool:
        """判断是否为精准防御类型的告警"""
        # 检查event_type字段
        event_type = alert.event_type if hasattr(alert, 'event_type') else ''
        if event_type and '精准防御' in str(event_type):
            return True
        
        # 检查告警数据中的类型字段
        if hasattr(alert, 'data') and isinstance(alert.data, dict):
            event_type = (
                alert.data.get('EventType') or 
                alert.data.get('AlarmEventType') or 
                alert.data.get('ParentEventType') or 
                alert.data.get('eventType') or 
                ''
            )
            if event_type and '精准防御' in str(event_type):
                return True
        
        return False
    
    def _parse_datetime(self, time_str: Optional[str]) -> datetime:
        """解析时间字符串，返回Django配置时区的datetime对象"""
        if not time_str:
            # 返回当前时间（已考虑时区）
            return timezone.now()
        
        try:
            # 尝试多种时间格式
            formats = [
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%dT%H:%M:%S.%f',
                '%Y-%m-%dT%H:%M:%SZ',
                '%Y-%m-%d %H:%M:%S.%f',
            ]
            
            dt = None
            for fmt in formats:
                try:
                    dt = datetime.strptime(time_str, fmt)
                    break
                except ValueError:
                    continue
            
            if dt is None:
                # 如果都不匹配，返回当前时间
                return timezone.now()
            
            # 如果解析的时间是naive（没有时区信息），假设是Django配置的时区
            if timezone.is_naive(dt):
                # 使用Django的make_aware，会自动使用settings.TIME_ZONE
                dt = timezone.make_aware(dt)
            else:
                # 如果有时区信息，转换为Django配置的时区
                dt = timezone.localtime(dt)
            
            return dt
        except Exception:
            # 出错时返回当前时间
            return timezone.now()
    
    def _get_notification_config(self) -> Dict:
        """获取通知配置"""
        from django.apps import apps
        from django.contrib.auth.models import User
        from django.db.models import Q
        AliyunConfig = apps.get_model('app', 'AliyunConfig')
        
        config = {'dingtalk': None, 'feishu': None}
        
        # 从任务配置中获取配置ID（如果有）
        config_id = self.config.get('notification_config_id')
        
        if config_id:
            try:
                notification_config = AliyunConfig.objects.get(id=config_id, is_active=True)
                
                # 检查钉钉配置（优先Stream模式，其次Webhook模式）
                has_dingtalk_stream = (
                    notification_config.dingtalk_enabled and 
                    notification_config.dingtalk_use_stream_push and
                    notification_config.dingtalk_client_id and 
                    notification_config.dingtalk_client_secret
                )
                has_dingtalk_webhook = (
                    notification_config.dingtalk_enabled and 
                    notification_config.dingtalk_webhook and 
                    notification_config.dingtalk_webhook.strip()
                )
                
                if has_dingtalk_stream or has_dingtalk_webhook:
                    config['dingtalk'] = notification_config
                    mode = 'Stream模式' if has_dingtalk_stream else 'Webhook模式'
                    self.log_info(f"找到钉钉通知配置: {notification_config.name} (ID: {config_id}, {mode})")
                
                if notification_config.feishu_enabled and notification_config.feishu_webhook and notification_config.feishu_webhook.strip():
                    config['feishu'] = notification_config
                    self.log_info(f"找到飞书通知配置: {notification_config.name} (ID: {config_id})")
                
                if config['dingtalk'] or config['feishu']:
                    return config
            except AliyunConfig.DoesNotExist:
                self.log_warning(f"未找到通知配置 ID: {config_id}")
        
        # 如果没有指定配置ID，尝试查找可用的通知配置
        # 优先查找使用Stream模式的配置（企业应用内部机器人）
        try:
            # 查找所有启用的配置，然后手动筛选包含有效通知配置的
            all_configs = AliyunConfig.objects.filter(is_active=True)
            
            # 筛选包含有效通知配置的
            notification_configs = []
            for cfg in all_configs:
                # 钉钉配置：优先检查Stream模式（Client ID + Client Secret），其次检查Webhook
                has_dingtalk_stream = (
                    cfg.dingtalk_enabled and 
                    cfg.dingtalk_use_stream_push and
                    cfg.dingtalk_client_id and 
                    cfg.dingtalk_client_secret
                )
                has_dingtalk_webhook = (
                    cfg.dingtalk_enabled and 
                    cfg.dingtalk_webhook and 
                    cfg.dingtalk_webhook.strip()
                )
                has_dingtalk = has_dingtalk_stream or has_dingtalk_webhook
                
                # 飞书配置
                has_feishu = (
                    cfg.feishu_enabled and 
                    cfg.feishu_webhook and 
                    cfg.feishu_webhook.strip()
                )
                
                config_type_ok = cfg.config_type in ['dingtalk', 'feishu', 'both']
                
                if has_dingtalk or has_feishu or config_type_ok:
                    notification_configs.append(cfg)
            
            if notification_configs:
                # 优先选择默认配置
                default_config = next((c for c in notification_configs if c.is_default), None)
                if not default_config:
                    # 如果没有默认配置，优先选择使用Stream模式的配置
                    stream_config = next((
                        c for c in notification_configs 
                        if c.dingtalk_enabled and c.dingtalk_use_stream_push and c.dingtalk_client_id
                    ), None)
                    if stream_config:
                        default_config = stream_config
                    else:
                        # 最后选择第一个可用的配置
                        default_config = notification_configs[0]
                
                if default_config:
                    # 检查钉钉配置（Stream模式或Webhook模式）
                    has_dingtalk_stream = (
                        default_config.dingtalk_enabled and 
                        default_config.dingtalk_use_stream_push and
                        default_config.dingtalk_client_id and 
                        default_config.dingtalk_client_secret
                    )
                    has_dingtalk_webhook = (
                        default_config.dingtalk_enabled and 
                        default_config.dingtalk_webhook and 
                        default_config.dingtalk_webhook.strip()
                    )
                    
                    if has_dingtalk_stream or has_dingtalk_webhook:
                        config['dingtalk'] = default_config
                        mode = 'Stream模式' if has_dingtalk_stream else 'Webhook模式'
                        self.log_info(f"找到默认钉钉通知配置: {default_config.name} (ID: {default_config.id}, {mode})")
                    
                    # 检查飞书配置
                    if default_config.feishu_enabled and default_config.feishu_webhook and default_config.feishu_webhook.strip():
                        config['feishu'] = default_config
                        self.log_info(f"找到默认飞书通知配置: {default_config.name} (ID: {default_config.id})")
        except Exception as e:
            self.log_warning(f"获取默认通知配置失败: {str(e)}", exc_info=True)
        
        return config
    
    def _push_to_dingtalk(self, alert, config) -> bool:
        """推送告警到钉钉（优先使用Stream模式）"""
        # 动态导入，避免模块加载时的导入问题
        send_security_alert_to_dingtalk = None
        try:
            # 尝试导入函数
            from app.utils.dingtalk import send_security_alert_to_dingtalk
            
            # 验证函数是否存在且可调用
            if send_security_alert_to_dingtalk is None:
                raise ImportError("send_security_alert_to_dingtalk 函数未导入")
            if not callable(send_security_alert_to_dingtalk):
                raise ImportError("send_security_alert_to_dingtalk 不是可调用对象")
                
        except ImportError as e:
            self.log_error(f"send_security_alert_to_dingtalk 函数未导入，无法推送到钉钉: {str(e)}", exc_info=True)
            self.log_error(f"尝试导入路径: app.utils.dingtalk", exc_info=False)
            self.log_error(f"当前工作目录: {os.getcwd()}", exc_info=False)
            self.log_error(f"BASE_DIR: {BASE_DIR}", exc_info=False)
            return False
        except Exception as e:
            self.log_error(f"导入钉钉工具函数时发生未知错误: {str(e)}", exc_info=True)
            return False
        
        try:
            # 优先使用Stream模式（企业应用内部机器人）
            # 如果配置了Client ID和Client Secret，且启用了Stream推送，则使用Stream模式
            use_stream = (
                config.dingtalk_use_stream_push and 
                config.dingtalk_client_id and 
                config.dingtalk_client_secret
            )
            
            result = send_security_alert_to_dingtalk(
                config=config,
                alert=alert,
                use_stream=use_stream
            )
            
            if result.get('success'):
                self.log_info(f"成功推送到钉钉（{'Stream模式' if use_stream else 'Webhook模式'}）: {alert.name}")
                return True
            else:
                self.log_warning(f"推送到钉钉失败: {result.get('message', '未知错误')}")
                return False
        except NameError as e:
            self.log_error(f"send_security_alert_to_dingtalk 函数未定义: {str(e)}", exc_info=True)
            return False
        except Exception as e:
            self.log_error(f"推送到钉钉失败: {str(e)}", exc_info=True)
            return False
    
    def _push_to_feishu(self, alert, config) -> bool:
        """推送告警到飞书"""
        # 动态导入，避免模块加载时的导入问题
        try:
            from app.utils.feishu import send_feishu_message, format_security_alert_message
        except Exception as e:
            self.log_error(f"无法导入飞书工具函数: {str(e)}", exc_info=True)
            return False
        
        try:
            title, text = format_security_alert_message(alert)
            result = send_feishu_message(
                webhook_url=config.feishu_webhook,
                title=title,
                text=text,
                secret=config.feishu_secret if config.feishu_secret else None
            )
            return result.get('success', False)
        except Exception as e:
            self.log_error(f"推送到飞书失败: {str(e)}", exc_info=True)
            return False


# 插件元信息
PLUGIN_INFO = {
    'name': 'alarm_aliyun_security_alerts',
    'type': 'alarm',
    'description': '阿里云安全中心告警监控插件，定时获取安全告警并推送到钉钉/飞书',
    'version': '1.0.0',
    'author': 'Bifang',
    'config_schema': {
        'type': 'object',
        'required': ['access_key_id', 'access_key_secret', 'region_id'],
        'properties': {
            'access_key_id': {
                'type': 'string',
                'description': '阿里云AccessKey ID'
            },
            'access_key_secret': {
                'type': 'string',
                'description': '阿里云AccessKey Secret'
            },
            'region_id': {
                'type': 'string',
                'description': '地域ID，如：cn-hangzhou',
                'default': 'cn-hangzhou'
            },
            'api_endpoint': {
                'type': 'string',
                'description': 'API地址（可选）'
            },
            'page_size': {
                'type': 'integer',
                'description': '分页大小',
                'default': 20
            },
            'lookback_minutes': {
                'type': 'integer',
                'description': '查询最近N分钟的告警',
                'default': 60
            },
            'levels': {
                'type': 'string',
                'description': '告警级别，多个用逗号分隔：serious,suspicious,remind',
                'default': 'serious,suspicious'
            },
            'dealed': {
                'type': 'string',
                'description': '是否已处理：N-待处理，Y-已处理',
                'default': 'N'
            },
            'push_dingtalk': {
                'type': 'boolean',
                'description': '是否推送到钉钉',
                'default': True
            },
            'push_feishu': {
                'type': 'boolean',
                'description': '是否推送到飞书',
                'default': True
            },
            'notification_config_id': {
                'type': 'integer',
                'description': '通知配置ID（AliyunConfig的ID），可选'
            }
        }
    }
}