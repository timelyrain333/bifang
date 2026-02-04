# SecOps智能体实现总结

## ✅ 已完成的工作

### 1. 后端服务层
- ✅ `app/services/secops_agent.py` - SecOps智能体核心逻辑
  - 对话接口（流式输出）
  - 意图分析
  - 任务执行编排
  - 漏洞采集、资产采集、漏洞匹配功能

- ✅ `app/services/task_executor.py` - 任务执行器
  - 插件执行
  - 流式日志输出
  - 配置合并（阿里云配置、AI配置）

- ✅ `app/services/asset_matcher.py` - 资产匹配器（已存在）
  - 漏洞与资产匹配
  - 版本范围解析
  - 组件名称匹配

### 2. 后端API层
- ⚠️ `app/views.py` - 需要恢复并添加 `SecOpsAgentViewSet`
  - views.py文件被意外覆盖，需要恢复所有ViewSet
  - 需要添加SecOpsAgentViewSet，支持流式对话

### 3. URL配置
- ✅ `app/urls.py` - 已注册SecOpsAgentViewSet路由

## 📝 需要完成的工作

### 1. 恢复views.py文件
views.py文件被意外覆盖，需要恢复以下ViewSet：
- LoginView
- LogoutView
- CurrentUserView
- PluginViewSet
- TaskViewSet
- TaskExecutionViewSet
- AssetViewSet
- VulnerabilityViewSet
- AliyunConfigViewSet
- **SecOpsAgentViewSet** (新增)

### 2. 添加SecOpsAgentViewSet
在views.py末尾添加：

```python
class SecOpsAgentViewSet(viewsets.ViewSet):
    """SecOps智能体视图集"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def chat(self, request):
        """
        与智能体对话，流式返回响应
        
        Request Body:
            {
                "message": "用户消息",
                "conversation_history": [{"role": "user", "content": "..."}, ...]  # 可选
            }
        """
        user_message = request.data.get('message', '')
        if not user_message:
            return Response({'error': '消息不能为空'}, status=status.HTTP_400_BAD_REQUEST)
        
        conversation_history = request.data.get('conversation_history', [])
        
        # 获取用户的通义千问配置
        qianwen_config = AliyunConfig.objects.filter(
            user=request.user,
            is_active=True
        ).filter(
            Q(config_type='qianwen') | Q(config_type='both')
        ).filter(
            qianwen_enabled=True
        ).exclude(
            qianwen_api_key=''
        ).first()
        
        if not qianwen_config or not qianwen_config.qianwen_api_key:
            return Response(
                {'error': '未找到可用的通义千问配置，请先在系统配置中配置通义千问API'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 创建智能体实例
        try:
            agent = SecOpsAgent(
                api_key=qianwen_config.qianwen_api_key,
                api_base=qianwen_config.qianwen_api_base or 'https://dashscope.aliyuncs.com/compatible-mode/v1',
                model=qianwen_config.qianwen_model or 'qwen-plus'
            )
        except Exception as e:
            logger.error(f"创建智能体失败: {e}", exc_info=True)
            return Response(
                {'error': f'创建智能体失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # 流式响应生成器
        def generate_response():
            try:
                for chunk in agent.chat(user_message, conversation_history, request.user):
                    # 使用SSE格式
                    yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
                # 发送结束标记
                yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            except Exception as e:
                logger.error(f"智能体对话失败: {e}", exc_info=True)
                error_msg = json.dumps({'error': str(e)}, ensure_ascii=False)
                yield f"data: {error_msg}\n\n"
        
        response = StreamingHttpResponse(
            generate_response(),
            content_type='text/event-stream'
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response
```

### 3. 前端实现（待完成）
需要创建前端聊天界面：
- 对话输入框
- 消息列表（支持流式显示）
- SSE连接处理
- 任务执行状态展示

## 🚀 使用场景示例

用户：**"请捕获最新的漏洞并检查我的资产是否受影响"**

智能体执行流程：
1. 理解用户意图：需要采集漏洞 + 匹配资产
2. 执行漏洞采集任务（流式输出执行日志）
3. 执行资产匹配任务（流式输出匹配结果）
4. 返回受影响资产列表和建议

## 📌 下一步
1. 恢复views.py文件（从备份或重新创建所有ViewSet）
2. 添加SecOpsAgentViewSet
3. 创建前端聊天界面
4. 测试完整流程
