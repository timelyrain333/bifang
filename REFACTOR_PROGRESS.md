
# SecOps 智能体重构 - 当前进展总结

## ✅ 已完成的工作

### 1. 依赖安装
- ✅ 安装 LangChain 核心库
- ✅ 安装 LangGraph 工作流框架
- ✅ 安装 aiohttp 异步支持库

### 2. 核心组件创建

#### 📁 目录结构
```
app/
├── agent_tools/          ✅ 已创建
│   ├── __init__.py
│   └── hexstrike_tools.py
├── agent_graphs/         ✅ 已创建
│   └── __init__.py
├── celery_tasks/        ✅ 已创建
│   ├── __init__.py
│   └── hexstrike_tasks.py
└── utils/
    └── sse_manager.py    ✅ 已创建
```

#### 📄 文件清单

1. **`app/utils/sse_manager.py`** - SSE 实时推送管理器
   - `SSEManager`: Redis Pub/Sub 消息发布
   - `SSEProgress`: 进度上下文管理器
   - 支持的工具方法：
     - `send_progress()` - 进度更新
     - `send_tool_start/end()` - 工具执行事件
     - `send_agent_thinking()` - Agent 思考过程
     - `send_error()` - 错误通知
     - `send_complete()` - 完成通知

2. **`app/agent_tools/hexstrike_tools.py`** - HexStrike 分阶段扫描工具
   - `HexStrikeProgressiveTool`: LangChain 工具类
   - **分阶段执行**：
     - 阶段1: Ping 主机存活检测（秒级）
     - 阶段2: 快速端口扫描 Top 100（10-30秒）
     - 阶段3: 提交后台完整扫描任务（分钟级）
   - **异步支持**: `_arun()` 方法
   - **实时推送**: 通过 SSEManager 推送进度

3. **`app/celery_tasks/hexstrike_tasks.py`** - Celery 异步扫描任务
   - `full_hexstrike_scan()`: 后台完整扫描
   - **执行流程**：
     1. Nmap 端口扫描（进度 10-40%）
     2. Nuclei 漏洞扫描（进度 40-80%）
     3. PDF 报告生成（进度 80-100%）
   - **状态管理**: 使用 Celery task state
   - **进度推送**: 实时通过 SSE 推送
   - **数据库记录**: 保存到 HexStrikeExecution 模型

---

## 🚧 待完成的工作

### 高优先级（核心功能）

#### 1. 创建 LangChain Agent 主类
**文件**: `app/services/secops_agent_langchain.py`

需要实现：
- 使用 `langchain_openai.ChatOpenAI` (兼容通义千问)
- 定义系统提示词
- 实现 `astream_chat()` 方法 (streaming 对话)
- 实现 `astream_events()` 推送（LangChain streaming events）
- 集成 `HexStrikeProgressiveTool`

参考代码框架：
```python
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.prompts import ChatPromptTemplate
from app.agent_tools.hexstrike_tools import HexStrikeProgressiveTool

class SecOpsLangChainAgent:
    def __init__(self, api_key: str, model: str = "qwen-plus"):
        self.llm = ChatOpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model=model,
            temperature=0.3,
            streaming=True,
        )
        self.tools = [HexStrikeProgressiveTool()]
        
    async def astream_chat(self, message: str, user_id: str = None):
        """流式对话 + 中间步骤推送"""
        # 实现 astream_events() 逻辑
        async for event in self.executor.astream_events(...):
            if event["event"] == "on_tool_start":
                yield f"🔧 执行: {event['name']}\n"
            elif event["event"] == "on_tool_stream":
                yield event["data"]["chunk"]
            # ... 其他事件
```

#### 2. 创建 SSE API Endpoint
**文件**: `app/api/views.py` (添加新视图)

需要实现：
```python
from django.http import StreamingHttpResponse
import json

def chat_stream(request):
    """SSE Streaming 聊天接口"""
    user_message = request.GET.get("message")
    user_id = request.user.username
    
    async def event_stream():
        agent = SecOpsLangChainAgent(api_key=settings.QWEN_API_KEY)
        async for chunk in agent.astream_chat(user_message, user_id):
            yield f"data: {json.dumps({'text': chunk}, ensure_ascii=False)}\n\n"
    
    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response['Cache-Control'] = 'no-cache'
    return response
```

URL 配置 (`app/urls.py`):
```python
urlpatterns = [
    path("api/chat/stream", chat_stream, name="chat_stream"),
]
```

#### 3. 前端适配（Vue.js）
**文件**: `frontend/src/api/chat.js`

需要实现 EventSource 连接：
```javascript
export function streamChat(message, onMessage, onError) {
  const url = `/api/chat/stream?message=${encodeURIComponent(message)}`;
  const eventSource = new EventSource(url);
  
  eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    onMessage(data.text);
  };
  
  eventSource.onerror = (error) => {
    onError(error);
    eventSource.close();
  };
  
  return eventSource; // 返回以便调用方可以关闭
}
```

### 中优先级（增强功能）

#### 4. LangGraph 工作流定义
**文件**: `app/agent_graphs/security_scan_graph.py`

创建状态机工作流：
```python
from langgraph.graph import StateGraph, END
from typing import TypedDict

class ScanState(TypedDict):
    target: str
    user_id: str
    ping_result: Optional[Dict]
    quick_scan_result: Optional[Dict]
    full_scan_result: Optional[Dict]

def create_security_scan_graph():
    workflow = StateGraph(ScanState)
    workflow.add_node("ping", ping_node)
    workflow.add_node("quick_scan", quick_scan_node)
    workflow.add_node("full_scan", full_scan_node)
    # ... 定义边和条件
    return workflow.compile()
```

#### 5. 任务状态查询 API
**文件**: `app/api/views.py`

```python
from django.http import JsonResponse
from celery.result import AsyncResult

def task_status(request, task_id):
    """查询 Celery 任务状态"""
    task = AsyncResult(task_id)
    return JsonResponse({
        "status": task.state,
        "result": task.result if task.ready() else None,
    })
```

### 低优先级（优化）

- [ ] 单元测试
- [ ] 集成测试
- [ ] 性能优化
- [ ] 错误处理增强

---

## 📊 架构优势

### 解决的核心问题

| 问题 | 解决方案 | 文件 |
|------|---------|------|
| **长时间无响应** | 分阶段快速返回 + 后台任务 | `hexstrike_tools.py` |
| **用户看不到进度** | SSE 实时推送 | `sse_manager.py` |
| **同步阻塞调用** | Celery 异步任务 | `hexstrike_tasks.py` |
| **单次执行耗时** | 拆分阶段，逐步返回 | `HexStrikeProgressiveTool` |

### 关键改进

1. **用户体验提升**
   - 秒级响应：立即返回 Ping 结果
   - 30秒内返回快速扫描结果
   - 后台任务不阻塞用户继续对话

2. **技术架构升级**
   - 异步支持（asyncio + aiohttp）
   - Streaming Events（LangChain astream_events）
   - 消息队列（Celery + Redis）
   - 实时通信（SSE）

3. **可扩展性**
   - 易于添加新工具（LangChain 框架）
   - 易于定义新工作流（LangGraph）
   - 易于监控和调试（SSE 推送中间步骤）

---

## 🎯 下一步行动

### 立即可做（30分钟）

1. **测试现有组件**
   ```python
   # 测试 SSE 管理器
   from app.utils.sse_manager import SSEManager
   sse = SSEManager("test_channel")
   sse.send_progress("test", 50, "测试消息")
   
   # 测试 HexStrike 工具
   from app.agent_tools.hexstrike_tools import HexStrikeProgressiveTool
   tool = HexStrikeProgressiveTool()
   result = await tool._arun("example.com", "user_123")
   ```

2. **创建最小可用的 LangChain Agent**（参考上面的框架代码）

3. **添加 SSE API endpoint**（参考上面的示例代码）

### 后续开发（1-2小时）

1. 实现 `secops_agent_langchain.py`
2. 创建前端 SSE 连接
3. 集成测试

---

## 📚 参考资源

- [LangChain Streaming](https://python.langchain.com/docs/expression_language/streaming)
- [LangGraph Tutorial](https://langchain-ai.github.io/langgraph/tutorials/introduction/)
- [Celery Best Practices](https://docs.celeryq.dev/en/stable/userguide/optimizing.html)
- [MDN: Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)

---

## 📝 总结

本次重构完成了：

1. ✅ **核心框架搭建**
   - SSE 实时推送系统
   - HexStrike 分阶段扫描工具
   - Celery 后台任务系统

2. ✅ **依赖安装**
   - LangChain + LangGraph
   - aiohttp 异步支持

3. ✅ **文档完善**
   - 详细的实施方案（`SECOPS_AGENT_REFACTOR.md`）
   - 当前进展总结（本文档）

**剩余工作**：主要是集成这些组件到现有的 Django API 中，以及前端适配。

预计完整完成需要 **2-3 小时**的额外开发时间。
