"""
数据模型定义
"""
from django.db import models
from django.utils import timezone
import json


class Plugin(models.Model):
    """插件模型"""
    name = models.CharField(max_length=100, unique=True, verbose_name='插件名称')
    plugin_type = models.CharField(max_length=50, verbose_name='插件类型', 
                                   choices=[
                                       ('data', '数据记录类'),
                                       ('collect', '数据采集类'),
                                       ('risk', '风险检测类'),
                                       ('dump', '数据导出类'),
                                       ('alarm', '告警类'),
                                   ])
    description = models.TextField(blank=True, verbose_name='插件描述')
    file_path = models.CharField(max_length=255, verbose_name='插件文件路径')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'plugins'
        verbose_name = '插件'
        verbose_name_plural = '插件'

    def __str__(self):
        return self.name


class Task(models.Model):
    """任务模型"""
    STATUS_CHOICES = [
        ('pending', '待执行'),
        ('running', '执行中'),
        ('success', '成功'),
        ('failed', '失败'),
        ('paused', '已暂停'),
    ]

    TRIGGER_TYPE_CHOICES = [
        ('manual', '手动执行'),
        ('cron', '定时执行'),
        ('interval', '间隔执行'),
    ]

    name = models.CharField(max_length=100, verbose_name='任务名称')
    plugin = models.ForeignKey(Plugin, on_delete=models.CASCADE, verbose_name='关联插件')
    aliyun_config = models.ForeignKey('AliyunConfig', on_delete=models.SET_NULL, null=True, blank=True, 
                                      verbose_name='阿里云配置', 
                                      help_text='选择使用的阿里云配置，为空则使用默认配置')
    aws_config = models.ForeignKey('AWSConfig', on_delete=models.SET_NULL, null=True, blank=True, 
                                   verbose_name='AWS配置', 
                                   help_text='选择使用的AWS配置，为空则使用默认配置')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    trigger_type = models.CharField(max_length=20, choices=TRIGGER_TYPE_CHOICES, default='manual', verbose_name='触发类型')
    cron_expression = models.CharField(max_length=100, blank=True, null=True, verbose_name='Cron表达式', 
                                       help_text='例如: 0 0 * * * (每天0点执行)')
    config = models.JSONField(default=dict, verbose_name='任务配置', 
                              help_text='插件执行所需的配置参数')
    last_run_time = models.DateTimeField(null=True, blank=True, verbose_name='最后执行时间')
    next_run_time = models.DateTimeField(null=True, blank=True, verbose_name='下次执行时间')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    created_by = models.CharField(max_length=50, blank=True, verbose_name='创建人')

    class Meta:
        db_table = 'tasks'
        verbose_name = '任务'
        verbose_name_plural = '任务'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.plugin.name})'


class TaskExecution(models.Model):
    """任务执行记录"""
    STATUS_CHOICES = [
        ('running', '执行中'),
        ('success', '成功'),
        ('failed', '失败'),
    ]

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='executions', verbose_name='任务')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='running', verbose_name='状态')
    started_at = models.DateTimeField(auto_now_add=True, verbose_name='开始时间')
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name='结束时间')
    result = models.JSONField(default=dict, verbose_name='执行结果')
    error_message = models.TextField(blank=True, verbose_name='错误信息')
    logs = models.TextField(blank=True, verbose_name='执行日志')

    class Meta:
        db_table = 'task_executions'
        verbose_name = '任务执行记录'
        verbose_name_plural = '任务执行记录'
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.task.name} - {self.started_at}'


class Asset(models.Model):
    """资产模型 - 用于存储各类资产数据"""
    ASSET_TYPE_CHOICES = [
        ('server', '服务器'),
        ('account', '账户'),
        ('port', '端口'),
        ('process', '进程'),
        ('middleware', '中间件'),
        ('ai_component', 'AI组件'),
        ('database', '数据库'),
        ('web_service', 'Web服务'),
        ('software', '软件'),
        ('cron_task', '计划任务'),
        ('startup_item', '启动项'),
        ('kernel_module', '内核模块'),
        ('web_site', 'Web站点'),
        ('idc_probe', 'IDC探针发现'),
        ('vpc', 'VPC实例'),
        ('vswitch', '交换机'),
        ('route_table', '路由表'),
        ('nat_gateway', 'NAT网关'),
        ('ipv4_gateway', 'IPv4网关'),
        ('vpc_peer_connection', 'VPC对等连接'),
    ]

    asset_type = models.CharField(max_length=50, choices=ASSET_TYPE_CHOICES, verbose_name='资产类型')
    uuid = models.CharField(max_length=100, db_index=True, verbose_name='资产UUID')
    host_uuid = models.CharField(max_length=100, db_index=True, blank=True, verbose_name='主机UUID')
    name = models.CharField(max_length=200, blank=True, verbose_name='名称')
    data = models.JSONField(default=dict, verbose_name='资产详细数据')
    source = models.CharField(max_length=50, default='aliyun_security', verbose_name='数据来源',
                              help_text='数据来源：aliyun_security（阿里云安全中心）或 aws_inspector（AWS Inspector）')
    collected_at = models.DateTimeField(auto_now_add=True, verbose_name='采集时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'assets'
        verbose_name = '资产'
        verbose_name_plural = '资产'
        unique_together = [['asset_type', 'uuid', 'source']]
        indexes = [
            models.Index(fields=['asset_type', 'host_uuid']),
            models.Index(fields=['collected_at']),
            models.Index(fields=['source']),
        ]

    def __str__(self):
        return f'{self.get_asset_type_display()} - {self.name or self.uuid}'


class AliyunConfig(models.Model):
    """系统配置模型（包含阿里云配置和钉钉配置）"""
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='aliyun_configs', verbose_name='用户')
    name = models.CharField(max_length=100, verbose_name='配置名称', help_text='用于区分不同的配置')
    
    # 阿里云配置字段
    api_endpoint = models.CharField(max_length=200, default='https://sas.cn-hangzhou.aliyuncs.com', verbose_name='API地址', blank=True)
    access_key_id = models.CharField(max_length=100, verbose_name='AccessKey ID', blank=True)
    access_key_secret = models.CharField(max_length=200, verbose_name='AccessKey Secret', blank=True)
    region_id = models.CharField(max_length=50, default='cn-hangzhou', verbose_name='地域ID', blank=True)
    
    # 通义千问AI配置字段
    qianwen_api_key = models.CharField(max_length=200, blank=True, verbose_name='通义千问API Key', 
                                        help_text='阿里云百炼平台的API Key')
    qianwen_api_base = models.URLField(max_length=500, blank=True, 
                                       default='https://dashscope.aliyuncs.com/compatible-mode/v1',
                                       verbose_name='通义千问API地址',
                                       help_text='API地址，中国大陆使用https://dashscope.aliyuncs.com/compatible-mode/v1')
    qianwen_model = models.CharField(max_length=100, blank=True, default='qwen-plus',
                                     verbose_name='通义千问模型名称',
                                     help_text='模型名称，如：qwen-plus, qwen-max, qwen-deepseek')
    qianwen_enabled = models.BooleanField(default=False, verbose_name='启用AI解析',
                                          help_text='是否启用AI模型解析漏洞详情')
    
    # 钉钉配置字段
    dingtalk_webhook = models.URLField(max_length=500, blank=True, verbose_name='钉钉机器人Webhook',
                                       help_text='钉钉自定义机器人的Webhook地址')
    dingtalk_secret = models.CharField(max_length=200, blank=True, verbose_name='钉钉签名密钥',
                                       help_text='钉钉加签密钥（如使用加签方式）')
    dingtalk_enabled = models.BooleanField(default=False, verbose_name='启用钉钉通知')
    dingtalk_app_id = models.CharField(max_length=100, blank=True, verbose_name='钉钉App ID',
                                       help_text='钉钉机器人应用的App ID（用于智能体交互）')
    dingtalk_client_id = models.CharField(max_length=100, blank=True, verbose_name='钉钉Client ID',
                                          help_text='钉钉机器人应用的Client ID（用于智能体交互）')
    dingtalk_client_secret = models.CharField(max_length=200, blank=True, verbose_name='钉钉Client Secret',
                                              help_text='钉钉机器人应用的Client Secret（用于智能体交互）')
    dingtalk_app_secret = models.CharField(max_length=200, blank=True, verbose_name='钉钉App Secret',
                                           help_text='钉钉机器人应用的App Secret（用于流式推送，已废弃，建议使用Client Secret）')
    dingtalk_use_stream_push = models.BooleanField(default=False, verbose_name='使用流式推送',
                                                   help_text='使用流式推送方式接收事件，无需公网地址')
    dingtalk_ai_card_template_id = models.CharField(max_length=100, blank=True, verbose_name='钉钉AI卡片模板ID',
                                                     help_text='用于流式AI卡片回复的模板ID（在钉钉开发者后台创建）')
    dingtalk_enable_stream_card = models.BooleanField(default=False, verbose_name='启用流式AI卡片',
                                                      help_text='是否使用流式AI卡片进行回复（打字机效果）')

    # 飞书配置字段
    feishu_webhook = models.URLField(max_length=500, blank=True, verbose_name='飞书机器人Webhook',
                                     help_text='飞书自定义机器人的Webhook地址（用于发送消息）')
    feishu_secret = models.CharField(max_length=200, blank=True, verbose_name='飞书签名密钥',
                                     help_text='飞书加签密钥（如使用加签方式）')
    feishu_app_id = models.CharField(max_length=100, blank=True, verbose_name='飞书App ID',
                                     help_text='飞书机器人应用的App ID（用于长连接）')
    feishu_app_secret = models.CharField(max_length=200, blank=True, verbose_name='飞书App Secret',
                                         help_text='飞书机器人应用的App Secret（用于长连接）')
    feishu_enabled = models.BooleanField(default=False, verbose_name='启用飞书通知')
    feishu_use_long_connection = models.BooleanField(default=False, verbose_name='使用长连接',
                                                     help_text='使用长连接方式接收事件，无需公网地址')
    # 关联的AI配置（用于飞书智能体功能）
    qianwen_config = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='feishu_configs', verbose_name='关联的AI配置',
                                       help_text='选择已存在的通义千问AI配置，用于飞书智能体功能')
    
    config_type = models.CharField(max_length=20, default='aliyun', choices=[
        ('aliyun', '阿里云配置'),
        ('dingtalk', '钉钉配置'),
        ('feishu', '飞书配置'),
        ('qianwen', '通义千问AI配置'),
        ('both', '阿里云+钉钉配置')
    ], verbose_name='配置类型')
    
    is_default = models.BooleanField(default=False, verbose_name='是否默认', help_text='每个用户只能有一个默认配置')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    description = models.TextField(blank=True, verbose_name='配置描述')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'aliyun_configs'
        verbose_name = '系统配置'
        verbose_name_plural = '系统配置'
        unique_together = [['user', 'name']]
        ordering = ['-is_default', '-created_at']

    def __str__(self):
        return f'{self.user.username} - {self.name}'


class AWSConfig(models.Model):
    """AWS配置模型"""
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='aws_configs', verbose_name='用户')
    name = models.CharField(max_length=100, verbose_name='配置名称', help_text='用于区分不同的配置')
    
    # AWS配置字段
    access_key_id = models.CharField(max_length=100, verbose_name='Access Key ID', blank=True)
    secret_access_key = models.CharField(max_length=200, verbose_name='Secret Access Key', blank=True)
    region = models.CharField(max_length=50, default='ap-northeast-1', verbose_name='区域', 
                             help_text='AWS区域，如：ap-northeast-1 (东京)')
    session_token = models.CharField(max_length=500, blank=True, verbose_name='Session Token',
                                    help_text='临时凭证的Session Token（可选）')
    
    is_default = models.BooleanField(default=False, verbose_name='是否默认', help_text='每个用户只能有一个默认配置')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    description = models.TextField(blank=True, verbose_name='配置描述')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'aws_configs'
        verbose_name = 'AWS配置'
        verbose_name_plural = 'AWS配置'
        unique_together = [['user', 'name']]
        ordering = ['-is_default', '-created_at']

    def __str__(self):
        return f'{self.user.username} - {self.name}'


class Vulnerability(models.Model):
    """漏洞模型 - 用于存储从oss-security邮件列表采集的漏洞信息"""
    cve_id = models.CharField(max_length=50, db_index=True, verbose_name='CVE编号', help_text='例如：CVE-2024-1234')
    title = models.CharField(max_length=500, verbose_name='标题')
    description = models.TextField(blank=True, verbose_name='描述')
    url = models.URLField(max_length=500, unique=True, verbose_name='邮件链接', help_text='原始邮件列表链接')
    message_id = models.CharField(max_length=100, db_index=True, blank=True, verbose_name='邮件ID', help_text='邮件列表中的消息ID')
    published_date = models.DateField(null=True, blank=True, db_index=True, verbose_name='发布日期')
    raw_content = models.TextField(blank=True, verbose_name='原始内容', help_text='邮件的原始内容')
    content = models.JSONField(default=dict, verbose_name='解析后的内容', help_text='结构化后的漏洞信息')
    source = models.CharField(max_length=50, default='oss_security', verbose_name='数据来源')
    collected_at = models.DateTimeField(auto_now_add=True, verbose_name='采集时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'vulnerabilities'
        verbose_name = '漏洞'
        verbose_name_plural = '漏洞'
        unique_together = [['cve_id', 'url']]
        indexes = [
            models.Index(fields=['cve_id', 'published_date']),
            models.Index(fields=['collected_at']),
            models.Index(fields=['source']),
        ]
        ordering = ['-published_date', '-collected_at']

    def __str__(self):
        return f'{self.cve_id} - {self.title[:50]}'


class SecurityAlert(models.Model):
    """安全告警模型 - 用于存储阿里云安全中心的告警信息，实现去重"""
    alert_id = models.CharField(max_length=100, db_index=True, unique=True, verbose_name='告警ID', 
                                help_text='阿里云返回的告警唯一标识')
    unique_info = models.CharField(max_length=200, db_index=True, blank=True, verbose_name='唯一标识', 
                                   help_text='告警的唯一key，用于去重')
    name = models.CharField(max_length=200, verbose_name='告警名称')
    level = models.CharField(max_length=50, blank=True, verbose_name='告警级别', 
                             help_text='serious/suspicious/remind')
    status = models.CharField(max_length=50, blank=True, verbose_name='处理状态', 
                              help_text='0:全部 1:待处理 2:已忽略 4:已确认 8:已标记误报等')
    dealt = models.BooleanField(default=False, verbose_name='是否已处理', 
                                help_text='Y:已处理 N:待处理')
    alert_time = models.DateTimeField(db_index=True, verbose_name='告警时间')
    event_type = models.CharField(max_length=200, blank=True, verbose_name='告警类型', 
                                  help_text='如：WEBSHELL、异常登录等')
    instance_id = models.CharField(max_length=200, blank=True, verbose_name='实例ID')
    instance_name = models.CharField(max_length=200, blank=True, verbose_name='实例名称')
    ip = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP地址')
    uuid = models.CharField(max_length=200, blank=True, db_index=True, verbose_name='资产UUID')
    data = models.JSONField(default=dict, verbose_name='告警详细数据', help_text='完整的告警信息')
    pushed_to_dingtalk = models.BooleanField(default=False, verbose_name='已推送到钉钉')
    pushed_to_feishu = models.BooleanField(default=False, verbose_name='已推送到飞书')
    pushed_at = models.DateTimeField(null=True, blank=True, verbose_name='推送时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'security_alerts'
        verbose_name = '安全告警'
        verbose_name_plural = '安全告警'
        ordering = ['-alert_time', '-created_at']
        indexes = [
            models.Index(fields=['alert_time']),
            models.Index(fields=['level', 'dealt']),
            models.Index(fields=['pushed_to_dingtalk', 'pushed_to_feishu']),
        ]

    def __str__(self):
        return f'{self.name} - {self.alert_time}'


class HexStrikeExecution(models.Model):
    """HexStrike 执行记录模型 - 用于存储 HexStrike 安全评估的执行记录"""
    STATUS_CHOICES = [
        ('running', '执行中'),
        ('success', '成功'),
        ('failed', '失败'),
    ]
    
    target = models.CharField(max_length=255, db_index=True, verbose_name='评估目标', help_text='IP、域名或主机名')
    analysis_type = models.CharField(max_length=50, default='comprehensive', verbose_name='分析类型')
    tool_name = models.CharField(max_length=100, blank=True, verbose_name='工具名称', help_text='如果是指定工具执行，记录工具名')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='running', verbose_name='状态')
    started_at = models.DateTimeField(auto_now_add=True, verbose_name='开始时间', db_index=True)
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name='结束时间')
    result = models.JSONField(default=dict, verbose_name='执行结果', help_text='HexStrike 返回的完整结果数据')
    error_message = models.TextField(blank=True, verbose_name='错误信息')
    execution_time = models.FloatField(null=True, blank=True, verbose_name='执行耗时（秒）')
    created_by = models.CharField(max_length=50, blank=True, verbose_name='执行人', help_text='执行此评估的用户')
    
    class Meta:
        db_table = 'hexstrike_executions'
        verbose_name = 'HexStrike 执行记录'
        verbose_name_plural = 'HexStrike 执行记录'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['target', 'started_at']),
            models.Index(fields=['status', 'started_at']),
        ]
    
    def __str__(self):
        return f'{self.target} - {self.started_at}'


class ChatSession(models.Model):
    """
    聊天会话模型
    存储用户与 AI 的对话会话
    """
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='chat_sessions',
        verbose_name='用户'
    )
    title = models.CharField(
        max_length=200,
        verbose_name='标题',
        help_text='会话标题，可由用户编辑或AI自动生成'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name='创建时间'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        db_index=True,
        verbose_name='更新时间'
    )
    is_active = models.BooleanField(
        default=False,
        verbose_name='是否活跃',
        help_text='标记当前正在使用的会话'
    )

    class Meta:
        db_table = 'chat_sessions'
        verbose_name = '聊天会话'
        verbose_name_plural = '聊天会话'
        ordering = ['-updated_at']  # 最近更新的排在前面
        indexes = [
            models.Index(fields=['user', '-updated_at']),
        ]

    def __str__(self):
        return self.title[:50]

    @property
    def message_count(self):
        """消息数量"""
        return self.messages.count()


class ChatMessage(models.Model):
    """
    聊天消息模型
    存储会话中的所有消息
    """
    id = models.AutoField(primary_key=True)
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='会话'
    )
    role = models.CharField(
        max_length=20,
        choices=[('user', 'user'), ('assistant', 'assistant')],
        verbose_name='角色'
    )
    content = models.TextField(
        verbose_name='内容',
        help_text='消息内容，支持长文本'
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name='时间戳'
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='元数据',
        help_text='存储tokens、模型等信息'
    )

    class Meta:
        db_table = 'chat_messages'
        verbose_name = '聊天消息'
        verbose_name_plural = '聊天消息'
        ordering = ['timestamp']

    def __str__(self):
        content_preview = self.content[:50]
        return f"{self.role}: {content_preview}"
