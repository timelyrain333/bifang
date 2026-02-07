from django.contrib import admin
from .models import Plugin, Task, TaskExecution, Asset, AliyunConfig, HexStrikeExecution


@admin.register(Plugin)
class PluginAdmin(admin.ModelAdmin):
    list_display = ['name', 'plugin_type', 'is_active', 'created_at']
    list_filter = ['plugin_type', 'is_active']
    search_fields = ['name', 'description']


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['name', 'plugin', 'status', 'trigger_type', 'is_active', 'last_run_time', 'created_at']
    list_filter = ['status', 'trigger_type', 'is_active', 'plugin']
    search_fields = ['name']
    date_hierarchy = 'created_at'


@admin.register(TaskExecution)
class TaskExecutionAdmin(admin.ModelAdmin):
    list_display = ['task', 'status', 'started_at', 'finished_at']
    list_filter = ['status']
    readonly_fields = ['started_at', 'finished_at']
    date_hierarchy = 'started_at'


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ['asset_type', 'name', 'uuid', 'host_uuid', 'source', 'collected_at']
    list_filter = ['asset_type', 'source', 'collected_at']
    search_fields = ['name', 'uuid', 'host_uuid']
    date_hierarchy = 'collected_at'


@admin.register(AliyunConfig)
class AliyunConfigAdmin(admin.ModelAdmin):
    list_display = ['user', 'name', 'api_endpoint', 'region_id', 'is_default', 'is_active', 'created_at']
    list_filter = ['is_default', 'is_active', 'region_id']
    search_fields = ['user__username', 'name', 'access_key_id']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'


@admin.register(HexStrikeExecution)
class HexStrikeExecutionAdmin(admin.ModelAdmin):
    list_display = ['id', 'target', 'tool_name', 'analysis_type', 'status', 'started_at', 'finished_at', 'execution_time', 'created_by']
    list_filter = ['status', 'analysis_type', 'started_at']
    search_fields = ['target', 'tool_name', 'created_by']
    readonly_fields = ['started_at', 'finished_at', 'execution_time']
    date_hierarchy = 'started_at'
    list_per_page = 50
