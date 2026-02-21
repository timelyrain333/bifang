"""
API序列化器
"""
from rest_framework import serializers
from .models import Plugin, Task, TaskExecution, Asset, AliyunConfig, AWSConfig, Vulnerability, SecurityAlert, ChatSession, ChatMessage, AssetSnapshot, AssetChangeRecord


class PluginSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plugin
        fields = ['id', 'name', 'plugin_type', 'description', 'is_active', 'created_at']


class TaskSerializer(serializers.ModelSerializer):
    plugin_name = serializers.CharField(source='plugin.name', read_only=True)
    plugin_type = serializers.CharField(source='plugin.plugin_type', read_only=True)
    aliyun_config_name = serializers.CharField(source='aliyun_config.name', read_only=True)
    aws_config_name = serializers.CharField(source='aws_config.name', read_only=True)

    class Meta:
        model = Task
        fields = ['id', 'name', 'plugin', 'plugin_name', 'plugin_type', 'aliyun_config', 
                  'aliyun_config_name', 'aws_config', 'aws_config_name', 'status', 'trigger_type', 
                  'cron_expression', 'config', 'last_run_time', 'next_run_time', 'is_active', 
                  'created_at', 'updated_at', 'created_by']
        read_only_fields = ['status', 'last_run_time', 'next_run_time']


class TaskExecutionSerializer(serializers.ModelSerializer):
    task_name = serializers.CharField(source='task.name', read_only=True)

    class Meta:
        model = TaskExecution
        fields = ['id', 'task', 'task_name', 'status', 'started_at', 'finished_at', 
                  'result', 'error_message', 'logs']


class AssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = ['id', 'asset_type', 'uuid', 'host_uuid', 'name', 'data', 
                  'source', 'collected_at', 'updated_at']


class AliyunConfigSerializer(serializers.ModelSerializer):
    # 在列表中不显示Secret，只在编辑时返回（已加密显示）
    access_key_secret = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True
    )
    dingtalk_secret = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True
    )
    qianwen_api_key = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True
    )
    feishu_secret = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True
    )
    feishu_app_id = serializers.CharField(
        required=False,
        allow_blank=True
    )
    feishu_app_secret = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True
    )
    dingtalk_app_id = serializers.CharField(
        required=False,
        allow_blank=True
    )
    dingtalk_client_id = serializers.CharField(
        required=False,
        allow_blank=True
    )
    dingtalk_client_secret = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True
    )
    
    # 添加只读字段，用于前端判断是否配置了API Key（不返回实际值）
    has_qianwen_api_key = serializers.SerializerMethodField()
    
    class Meta:
        model = AliyunConfig
        fields = ['id', 'name', 'api_endpoint', 'access_key_id', 'access_key_secret',
                  'region_id', 'dingtalk_webhook', 'dingtalk_secret', 'dingtalk_enabled',
                  'dingtalk_app_id', 'dingtalk_client_id', 'dingtalk_client_secret',
                  'dingtalk_use_stream_push', 'dingtalk_ai_card_template_id',
                  'dingtalk_enable_stream_card',
                  'feishu_webhook', 'feishu_secret', 'feishu_app_id', 'feishu_app_secret',
                  'feishu_enabled', 'feishu_use_long_connection', 'qianwen_config',
                  'qianwen_api_key', 'qianwen_api_base', 'qianwen_model', 'qianwen_enabled',
                  'has_qianwen_api_key', 'config_type', 'is_default', 'is_active', 'description',
                  'created_at', 'updated_at']
    
    def get_has_qianwen_api_key(self, obj):
        """返回是否配置了API Key（布尔值，不返回实际值）"""
        return bool(obj.qianwen_api_key)
    
    def validate(self, data):
        """验证：每个用户只能有一个默认配置，配置名称不能重复"""
        user = self.context['request'].user
        
        # 临时兼容：如果接收到 dingtalk_app_secret（旧字段名），映射到 dingtalk_client_secret
        # TODO: 前端重新编译并清除缓存后，可以移除此兼容处理
        import logging
        logger = logging.getLogger(__name__)
        if 'dingtalk_app_secret' in data and data.get('dingtalk_app_secret'):
            if 'dingtalk_client_secret' not in data or not data.get('dingtalk_client_secret'):
                data['dingtalk_client_secret'] = data.pop('dingtalk_app_secret')
                # 安全记录：只记录长度，不记录实际内容
                logger.info(f"兼容处理：将 dingtalk_app_secret 映射到 dingtalk_client_secret，长度={len(data['dingtalk_client_secret'])}")
            else:
                logger.info(f"兼容处理：dingtalk_app_secret 和 dingtalk_client_secret 都存在，保留 dingtalk_client_secret")
                data.pop('dingtalk_app_secret', None)
        
        is_default = data.get('is_default', False)
        name = data.get('name', None)
        
        # 验证配置名称唯一性
        if name:
            existing = AliyunConfig.objects.filter(
                user=user,
                name=name
            )
            # 如果是更新操作，排除当前记录
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise serializers.ValidationError({
                    'name': f'配置名称"{name}"已存在，请使用其他名称'
                })
        
        if is_default:
            # 如果设置为默认，检查是否已有其他默认配置
            existing_default = AliyunConfig.objects.filter(
                user=user, 
                is_default=True,
                is_active=True
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing_default.exists():
                # 将其他默认配置设为非默认
                existing_default.update(is_default=False)
        
        return data
    
    def update(self, instance, validated_data):
        """更新时，如果未提供Secret则不更新该字段"""
        import logging
        logger = logging.getLogger(__name__)
        
        # 调试日志：记录接收到的数据
        if 'dingtalk_client_secret' in validated_data:
            secret_value = validated_data.get('dingtalk_client_secret')
            # 安全记录：只记录长度，不记录实际内容
            logger.info(f"更新配置 {instance.id}: 接收到 dingtalk_client_secret, 长度={len(secret_value) if secret_value else 0}")
        
        # 如果Secret为空或未提供，则不更新
        if 'access_key_secret' in validated_data and not validated_data.get('access_key_secret'):
            validated_data.pop('access_key_secret')
        if 'dingtalk_secret' in validated_data and not validated_data.get('dingtalk_secret'):
            validated_data.pop('dingtalk_secret')
        if 'dingtalk_client_secret' in validated_data:
            secret_value = validated_data.get('dingtalk_client_secret')
            if not secret_value:
                logger.info(f"更新配置 {instance.id}: dingtalk_client_secret 为空，将被移除")
                validated_data.pop('dingtalk_client_secret')
            else:
                logger.info(f"更新配置 {instance.id}: dingtalk_client_secret 将被保存，长度={len(secret_value)}")
        if 'feishu_secret' in validated_data and not validated_data.get('feishu_secret'):
            validated_data.pop('feishu_secret')
        if 'feishu_app_secret' in validated_data and not validated_data.get('feishu_app_secret'):
            validated_data.pop('feishu_app_secret')
        if 'qianwen_api_key' in validated_data and not validated_data.get('qianwen_api_key'):
            validated_data.pop('qianwen_api_key')
        return super().update(instance, validated_data)


class AWSConfigSerializer(serializers.ModelSerializer):
    """AWS配置序列化器"""
    # 在列表中不显示Secret，只在编辑时返回（已加密显示）
    secret_access_key = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True
    )
    session_token = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True
    )
    
    class Meta:
        model = AWSConfig
        fields = ['id', 'name', 'access_key_id', 'secret_access_key', 'region', 
                  'session_token', 'is_default', 'is_active', 'description', 
                  'created_at', 'updated_at']
    
    def validate(self, data):
        """验证：每个用户只能有一个默认配置，配置名称不能重复"""
        user = self.context['request'].user
        
        is_default = data.get('is_default', False)
        name = data.get('name', None)
        
        # 验证配置名称唯一性
        if name:
            existing = AWSConfig.objects.filter(
                user=user,
                name=name
            )
            # 如果是更新操作，排除当前记录
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise serializers.ValidationError({
                    'name': f'配置名称"{name}"已存在，请使用其他名称'
                })
        
        if is_default:
            # 如果设置为默认，检查是否已有其他默认配置
            existing_default = AWSConfig.objects.filter(
                user=user, 
                is_default=True,
                is_active=True
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing_default.exists():
                # 将其他默认配置设为非默认
                existing_default.update(is_default=False)
        
        return data
    
    def update(self, instance, validated_data):
        """更新时，如果未提供Secret则不更新该字段"""
        # 如果Secret为空或未提供，则不更新
        if 'secret_access_key' in validated_data and not validated_data.get('secret_access_key'):
            validated_data.pop('secret_access_key')
        if 'session_token' in validated_data and not validated_data.get('session_token'):
            validated_data.pop('session_token')
        return super().update(instance, validated_data)


class VulnerabilitySerializer(serializers.ModelSerializer):
    """漏洞序列化器"""
    source_url = serializers.URLField(source='url', read_only=True, label='邮件链接')

    class Meta:
        model = Vulnerability
        fields = ['id', 'cve_id', 'title', 'description', 'url', 'source_url', 'message_id',
                 'published_date', 'raw_content', 'content', 'source',
                 'collected_at', 'updated_at']
        read_only_fields = ['collected_at', 'updated_at']


class ChatMessageSerializer(serializers.ModelSerializer):
    """聊天消息序列化器"""

    class Meta:
        model = ChatMessage
        fields = ['id', 'session', 'role', 'content', 'timestamp', 'metadata']
        read_only_fields = ['id', 'timestamp']


class ChatSessionSerializer(serializers.ModelSerializer):
    """聊天会话序列化器"""
    messages_count = serializers.SerializerMethodField()

    class Meta:
        model = ChatSession
        fields = ['id', 'title', 'created_at', 'updated_at', 'is_active', 'messages_count']
        read_only_fields = ['created_at', 'updated_at']

    def get_messages_count(self, obj):
        """获取会话的消息总数"""
        return obj.message_count


class AssetSnapshotSerializer(serializers.ModelSerializer):
    """资产快照序列化器"""
    change_count = serializers.SerializerMethodField()

    class Meta:
        model = AssetSnapshot
        fields = ['id', 'snapshot_id', 'asset_type', 'source', 'asset_uuids', 'asset_count',
                  'asset_details', 'changes', 'collected_at', 'created_by',
                  'notification_sent', 'notification_sent_at', 'change_count']
        read_only_fields = ['snapshot_id', 'collected_at']

    def get_change_count(self, obj):
        """获取变化数量"""
        changes = obj.changes or {}
        return len(changes.get('created', [])) + len(changes.get('deleted', [])) + len(changes.get('modified', []))


class AssetChangeRecordSerializer(serializers.ModelSerializer):
    """资产变更记录序列化器"""
    snapshot_id = serializers.CharField(source='snapshot.snapshot_id', read_only=True)
    change_type_display = serializers.CharField(source='get_change_type_display', read_only=True)

    class Meta:
        model = AssetChangeRecord
        fields = ['id', 'snapshot', 'snapshot_id', 'change_type', 'change_type_display',
                  'asset_type', 'asset_uuid', 'asset_name', 'old_value', 'new_value',
                  'detected_at', 'notified']
        read_only_fields = ['detected_at']