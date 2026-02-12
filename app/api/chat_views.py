"""
聊天会话管理 API 视图
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from app.models import ChatSession, ChatMessage
from app.serializers import ChatSessionSerializer, ChatMessageSerializer


class ChatSessionViewSet(viewsets.ModelViewSet):
    """
    聊天会话管理视图集
    提供会话的 CRUD 操作和自定义动作
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ChatSessionSerializer

    def get_queryset(self):
        """
        重写查询集，确保用户只能看到自己的会话
        """
        return ChatSession.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """
        创建会话时自动设为活跃
        """
        # 先将其他会话设为非活跃
        ChatSession.objects.filter(user=self.request.user).update(is_active=False)

        # 创建新会话并设为活跃
        serializer.save(user=self.request.user, is_active=True)
        return serializer

    @action(detail=True, methods=['post'])
    def set_active(self, request, pk=None):
        """
        自定义动作：切换活跃会话
        """
        try:
            session = self.get_object()

            # 将当前用户的所有会话设为非活跃
            ChatSession.objects.filter(user=request.user).update(is_active=False)

            # 将指定会话设为活跃
            session.is_active = True
            session.save()

            return Response({
                'message': '会话已切换',
                'session_id': session.id,
                'title': session.title
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        """
        自定义动作：获取会话的所有消息
        """
        session = self.get_object()
        messages = session.messages.all().order_by('timestamp')

        serializer = ChatMessageSerializer(messages, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def add_message(self, request, pk=None):
        """
        自定义动作：添加消息到会话
        """
        try:
            session = self.get_object()

            # 验证数据
            role = request.data.get('role')
            content = request.data.get('content')

            if not role or not content:
                return Response(
                    {'error': '缺少必要参数: role, content'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if role not in ['user', 'assistant']:
                return Response(
                    {'error': 'role 必须是 user 或 assistant'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 创建消息
            message = ChatMessage.objects.create(
                session=session,
                role=role,
                content=content,
                metadata=request.data.get('metadata', {})
            )

            # 更新会话的 updated_at 时间
            session.save()

            serializer = ChatMessageSerializer(message)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
