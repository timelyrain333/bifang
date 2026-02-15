"""
API URL 配置
"""
from django.urls import path
from app.api import streaming_views

app_name = 'api'

urlpatterns = [
    # SSE Streaming 聊天接口
    path('chat/stream', streaming_views.chat_stream, name='chat_stream'),
    
    # 聊天状态查询
    path('chat/status', streaming_views.chat_status, name='chat_status'),
]
