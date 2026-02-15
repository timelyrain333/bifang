"""
SSE Streaming API 视图
提供实时流式对话接口
"""
import json
import asyncio
import logging
from django.http import StreamingHttpResponse, HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from asgiref.sync import async_to_sync, sync_to_async

from app.services.secops_agent_langchain import SecOpsLangChainAgent
from django.conf import settings

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def chat_stream(request: HttpRequest):
    """
    SSE Streaming 聊天接口

    GET 参数：
    - message: 用户消息
    - conversation_history: 对话历史（JSON 字符串，可选）

    返回：
    - text/event-stream 格式的流式响应
    """
    # 获取参数
    if request.method == "POST":
        data = json.loads(request.body)
        user_message = data.get("message", "")
        conversation_history = data.get("conversation_history", [])
    else:
        user_message = request.GET.get("message", "")
        history_str = request.GET.get("conversation_history", "[]")
        try:
            conversation_history = json.loads(history_str)
        except:
            conversation_history = []

    if not user_message:
        return HttpResponse(
            json.dumps({"error": "缺少 message 参数"}),
            status=400,
            content_type="application/json"
        )

    # 获取用户 ID
    user_id = None
    qianwen_api_key = None
    qianwen_api_base = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    qianwen_model = 'qwen-plus'

    if request.user.is_authenticated:
        user_id = request.user.username

        # 从 AliyunConfig 中获取通义千问配置
        from app.models import AliyunConfig
        try:
            # 优先查找已配置API Key的激活配置
            qianwen_config = AliyunConfig.objects.filter(
                user=request.user,
                is_active=True,
                qianwen_api_key__isnull=False
            ).exclude(qianwen_api_key='').first()

            if qianwen_config:
                qianwen_api_key = qianwen_config.qianwen_api_key
                if qianwen_config.qianwen_api_base:
                    qianwen_api_base = qianwen_config.qianwen_api_base
                if qianwen_config.qianwen_model:
                    qianwen_model = qianwen_config.qianwen_model
                logger.info(f"使用配置: {qianwen_config.name} (ID: {qianwen_config.id})")
            else:
                logger.warning(f"用户 {user_id} 未配置通义千问API Key")
        except Exception as e:
            logger.error(f"获取通义千问配置失败: {e}")

    if not qianwen_api_key:
        return HttpResponse(
            json.dumps({"error": "未配置通义千问API Key，请先在系统配置中添加"}),
            status=400,
            content_type="application/json"
        )

    logger.info(f"[SSE Chat] user={user_id}, message={user_message[:50]}")

    # 定义流式生成器
    async def event_stream():
        try:
            # 初始化 Agent
            agent = SecOpsLangChainAgent(
                api_key=qianwen_api_key,
                model=qianwen_model
            )

            # 流式对话
            async for chunk in agent.astream_chat(
                message=user_message,
                user_id=user_id,
                chat_history=conversation_history,
            ):
                # SSE 格式 - 使用前端期望的格式
                event_data = {
                    "content": chunk,  # 前端期望的字段名
                }
                yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"

            # 发送完成标记
            done_data = {"done": True}
            yield f"data: {json.dumps(done_data, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.error(f"[SSE Chat] 错误: {e}", exc_info=True)
            # 使用前端期望的错误格式
            error_data = {
                "error": str(e),
            }
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"

    # 包装为生成器（async generator 转 sync）
    def async_generator():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            async_gen = event_stream()
            while True:
                try:
                    chunk = loop.run_until_complete(async_gen.__anext__())
                    # 立即 flush 确保 chunk 被发送
                    yield chunk
                except StopAsyncIteration:
                    break
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()

    # 返回 StreamingResponse
    response = StreamingHttpResponse(
        async_generator(),
        content_type="text/event-stream",
    )
    # 禁用所有缓存
    response['Cache-Control'] = 'no-cache, no-transform, no-store'
    response['X-Accel-Buffering'] = 'no'  # 禁用 Nginx 缓冲
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'

    return response


@require_http_methods(["GET"])
@login_required
def chat_status(request: HttpRequest):
    """
    获取聊天状态（WebSocket/SSE 连接状态）
    """
    from app.utils.sse_manager import SSEManager

    user_id = request.user.username
    channel = f"user_{user_id}"

    # 测试 Redis 连接
    sse = SSEManager(channel)
    test_ok = sse.send_progress("test", 0, "连接测试")

    return HttpResponse(
        json.dumps({
            "status": "ok",
            "user_id": user_id,
            "channel": channel,
            "redis_ok": test_ok,
        }),
        content_type="application/json"
    )
