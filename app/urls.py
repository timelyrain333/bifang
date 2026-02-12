"""
App URL配置
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PluginViewSet, TaskViewSet, TaskExecutionViewSet, AssetViewSet, VulnerabilityViewSet,
    AliyunConfigViewSet, AWSConfigViewSet, LoginView, LogoutView, CurrentUserView, SecOpsAgentViewSet,
    DingTalkBotView, FeishuBotView, TaskSSEView, HexStrikeReportDownloadView
)
from .api.chat_views import ChatSessionViewSet

router = DefaultRouter()
router.register(r'plugins', PluginViewSet, basename='plugin')
router.register(r'tasks', TaskViewSet, basename='task')
router.register(r'task-executions', TaskExecutionViewSet, basename='task-execution')
router.register(r'assets', AssetViewSet, basename='asset')
router.register(r'vulnerabilities', VulnerabilityViewSet, basename='vulnerability')
router.register(r'secops-agent', SecOpsAgentViewSet, basename='secops-agent')
router.register(r'aliyun-configs', AliyunConfigViewSet, basename='aliyun-config')
router.register(r'aws-configs', AWSConfigViewSet, basename='aws-config')
router.register(r'chat/sessions', ChatSessionViewSet, basename='chat-session')

urlpatterns = [
    path('api/auth/login/', LoginView.as_view(), name='login'),
    path('api/auth/logout/', LogoutView.as_view(), name='logout'),
    path('api/auth/user/', CurrentUserView.as_view(), name='current-user'),
    path('api/tasks/sse/', TaskSSEView.as_view(), name='task-sse'),
    path('api/dingtalk/bot/', DingTalkBotView.as_view(), name='dingtalk-bot'),
    path('api/feishu/bot/', FeishuBotView.as_view(), name='feishu-bot'),
    path('api/reports/hexstrike/<str:filename>/', HexStrikeReportDownloadView.as_view(), name='hexstrike-report-download'),
    path('api/', include(router.urls)),
    # 新增：包含新的SSE streaming API
    path('api/', include('app.api.urls')),
]
