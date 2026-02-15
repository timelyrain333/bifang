# LangGraph 异步任务管理指南

## 🎯 新架构设计

不再使用 Celery，完全基于 **LangGraph 内置机制**管理异步任务：

### 核心组件

1. **Redis Checkpointer** - 持久化图状态
2. **Dispatcher 节点** - 异步发起工具调用，存储任务ID
3. **Checker 节点** - 轮询任务状态，完成后更新state
4. **Async Tool Wrapper** - 支持 async generator 中间进度推送

---

## 📦 依赖安装

```bash
# 已安装的依赖
✅ langgraph>=0.0.30
✅ langchain-core>=1.2.9
✅ redis>=5.0.1
✅ aiohttp>=3.9.0

# 额外需要（可选，用于 PostgreSQL checkpointer）
pip install asyncpg  # 如果使用 PostgreSQL
```

---

## 🏗️ 架构详解

### 1. Dispatcher-Checker 模式

```
┌─────────────────────────────────────────────────────────────┐
│                    LangGraph 工作流                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────┐    ┌─────────┐    ┌────────────┐             │
│  │  Init   │───▶│  Ping   │───▶│ Quick Scan │             │
│  └─────────┘    └─────────┘    └────────────┘             │
│                                      │                       │
│                                      ▼                       │
│                          ┌─────────────────────┐            │
│                          │   Dispatcher Node   │            │
│                          │  - 创建后台任务      │            │
│                          │  - 存储task_id      │            │
│                          │  - 立即返回         │            │
│                          └─────────┬───────────┘            │
│                                    │                        │
│                                    ▼                        │
│                          ┌─────────────────────┐            │
│                          │   Checker Node      │            │
│                          │  - 轮询任务状态      │            │
│                          │  - 更新state       │            │
│                          │  - 完成后结束       │            │
│                          └─────────┬───────────┘            │
│                                    │                        │
│                              ┌─────┴─────┐                   │
│                              │  继续轮询  │                   │
│                              │  或结束    │                   │
│                              └───────────┘                   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
            ┌───────────────────────────────┐
            │   Redis Checkpointer         │
            │  - 持久化 graph state        │
            │  - 支持中断恢复              │
            │  - 并发安全                  │
            └───────────────────────────────┘
```

### 2. 状态流转

```python
# 初始状态
state = {
    "current_stage": "init",
    "background_tasks": {},  # 存储任务ID
    "progress": 0,
    "final_result": None,
}

# → Ping 完成
state["ping_result"] = {"alive": True}

# → 快速扫描完成
state["quick_scan_result"] = {"ports": [...]}

# → Dispatcher 创建后台任务
state["background_tasks"] = {
    "task-abc-123": {"stage": "full_scan"}
}

# → 立即返回（用户得到快速结果）

# → Checker 轮询（后台）
# 每次调用检查任务状态
done, result = await async_task_manager.get_task_result("task-abc-123")
if done:
    state["final_result"] = result
    state["current_stage"] = "complete"
else:
    # 继续轮询
    pass
```

---

## 💻 使用示例

### 1. 基础使用（内存 Checkpointer）

```python
import asyncio
from app.agent_graphs.security_scan_graph import create_security_scan_graph

async def main():
    # 创建工作流（使用内存 checkpointer）
    from langgraph.checkpoint.memory import MemorySaver
    checkpointer = MemorySaver()
    
    graph = create_security_scan_graph(checkpointer)
    
    # 初始状态
    initial_state = {
        "target": "example.com",
        "user_id": "test_user",
        # ... 其他必需字段
    }
    
    # 执行工作流
    config = {"configurable": {"thread_id": "scan-123"}}
    
    # 流式执行
    async for event in graph.astream(initial_state, config):
        print(f"Event: {event}")
    
    # 获取最终状态
    final_state = await graph.ainvoke(initial_state, config)
    print(f"结果: {final_state}")

asyncio.run(main())
```

### 2. 生产环境（Redis Checkpointer）

```python
import asyncio
from app.agent_graphs.security_scan_graph import create_security_scan_graph

async def main_with_redis():
    # 创建 Redis checkpointer
    from langgraph.checkpoint.sqlite.aio import AsyncSaver as AsyncSqliteSaver
    
    # 使用 SQLite（简单）
    checkpointer = AsyncSqliteSaver.from_conn_string("checkpoints.db")
    
    # 或使用 Redis（需要自定义实现）
    # checkpointer = create_redis_checkpointer()
    
    graph = create_security_scan_graph(checkpointer)
    
    initial_state = {
        "target": "192.168.1.1",
        "user_id": "admin",
        # ...
    }
    
    config = {"configurable": {"thread_id": "scan-456"}}
    
    # 执行
    result = await graph.ainvoke(initial_state, config)
    print(f"扫描完成: {result}")

asyncio.run(main_with_redis())
```

### 3. 中断恢复

```python
async def resume_scan(thread_id: str):
    """从中断处恢复扫描"""
    from app.agent_graphs.security_scan_graph import create_security_scan_graph
    from langgraph.checkpoint.memory import MemorySaver
    
    checkpointer = MemorySaver()
    graph = create_security_scan_graph(checkpointer)
    
    config = {"configurable": {"thread_id": thread_id}}
    
    # 查看当前状态
    current_state = await graph.aget_state(config)
    print(f"当前阶段: {current_state.values['current_stage']}")
    print(f"进度: {current_state.values['progress']}%")
    
    # 继续执行
    async for event in graph.astream(None, config):
        print(f"恢复执行: {event}")

# 恢复之前中断的扫描
asyncio.run(resume_scan("scan-123"))
```

### 4. 使用异步工具

```python
from app.agent_tools.async_tools import async_hexstrike_scan_tool

async def scan_with_progress():
    """执行带进度推送的扫描"""
    
    # 进度回调
    def on_progress(progress, message):
        print(f"[{progress}%] {message}")
    
    # 执行扫描（async generator）
    result_accumulator = []
    
    async for chunk in async_hexstrike_scan_tool._arun_with_progress(
        target="example.com",
        user_id="test_user",
        progress_callback=on_progress
    ):
        print(f"收到事件: {chunk['type']}")
        result_accumulator.append(chunk)
        
        # 根据 event 类型处理
        if chunk["type"] == "stage_complete":
            print(f"阶段完成: {chunk['stage']}")
        elif chunk["type"] == "background_task_created":
            print(f"后台任务ID: {chunk['task_id']}")
    
    print(f"最终结果: {result_accumulator[-1]}")

asyncio.run(scan_with_progress())
```

---

## 🔧 配置

### Django Settings (`bifang/settings.py`)

```python
# LangGraph 配置
LANGGRAPH_CHECKPOINTER_TYPE = "redis"  # 或 "memory", "sqlite"
LANGGRAPH_REDIS_URL = "redis://localhost:6379/1"
LANGGRAPH_SQLITE_PATH = os.path.join(BASE_DIR, "checkpoints.db")
```

### 创建 Redis Checkpointer（高级）

```python
from langchain_core.runnables import RunnableConfig
from redis import asyncio as aioredis
import pickle

class RedisCheckpointSaver:
    """自定义 Redis Checkpointer"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/1"):
        self.redis = aioredis.from_url(redis_url)
    
    async def put(self, config: RunnableConfig, checkpoint: dict):
        """保存 checkpoint"""
        thread_id = config["configurable"]["thread_id"]
        key = f"checkpoint:{thread_id}"
        
        await self.redis.set(
            key,
            pickle.dumps(checkpoint),
            ex=86400  # 24小时过期
        )
    
    async def get(self, config: RunnableConfig) -> Optional[dict]:
        """获取 checkpoint"""
        thread_id = config["configurable"]["thread_id"]
        key = f"checkpoint:{thread_id}"
        
        data = await self.redis.get(key)
        if data:
            return pickle.loads(data)
        return None
    
    async def adelete(self, config: RunnableConfig):
        """删除 checkpoint"""
        thread_id = config["configurable"]["thread_id"]
        key = f"checkpoint:{thread_id}"
        await self.redis.delete(key)

# 使用
checkpointer = RedisCheckpointSaver("redis://localhost:6379/1")
graph = create_security_scan_graph(checkpointer)
```

---

## 🎯 与 Celery 方案对比

| 特性 | Celery 方案 | LangGraph 方案（推荐） |
|------|-------------|----------------------|
| 依赖 | Celery + Redis | 仅 LangGraph + Redis |
| 状态管理 | Celery Result Backend | LangGraph Checkpointer |
| 中间进度 | 需手动推送 | Native 支持 |
| 恢复机制 | Task ID | Thread ID + Checkpoint |
| 轮询 | Celery backend | Checker 节点 |
| 代码复杂度 | 高 | 低 |
| 类型安全 | 弱 | 强（TypedDict） |

---

## 📝 API 集成

### 1. 启动扫描 API

```python
# app/api/async_scan_views.py
from django.http import JsonResponse
from app.agent_graphs.security_scan_graph import create_security_scan_graph

async def start_scan(request):
    """启动异步扫描"""
    data = json.loads(request.body)
    target = data["target"]
    user_id = request.user.username
    
    # 创建 graph
    from langgraph.checkpoint.memory import MemorySaver
    checkpointer = MemorySaver()
    graph = create_security_scan_graph(checkpointer)
    
    # 生成 thread_id
    import uuid
    thread_id = f"scan_{uuid.uuid4()}"
    
    # 初始状态
    initial_state = {
        "target": target,
        "user_id": user_id,
        "ping_result": None,
        "quick_scan_result": None,
        "full_scan_result": None,
        "current_stage": "init",
        "background_tasks": {},
        "progress": 0,
        "progress_messages": [],
        "final_result": None,
        "error": None,
    }
    
    config = {"configurable": {"thread_id": thread_id}}
    
    # 异步执行（不等待完成）
    asyncio.create_task(graph.ainvoke(initial_state, config))
    
    return JsonResponse({
        "success": True,
        "thread_id": thread_id,
        "message": "扫描已启动"
    })
```

### 2. 查询状态 API

```python
async def get_scan_status(request, thread_id):
    """查询扫描状态"""
    from app.agent_graphs.security_scan_graph import create_security_scan_graph
    
    checkpointer = MemorySaver()
    graph = create_security_scan_graph(checkpointer)
    
    config = {"configurable": {"thread_id": thread_id}}
    
    # 获取当前状态
    state = await graph.aget_state(config)
    
    if not state:
        return JsonResponse({"error": "扫描不存在"}, status=404)
    
    return JsonResponse({
        "thread_id": thread_id,
        "current_stage": state.values["current_stage"],
        "progress": state.values["progress"],
        "progress_messages": state.values["progress_messages"],
        "background_tasks": state.values["background_tasks"],
        "final_result": state.values["final_result"],
        "error": state.values.get("error"),
    })
```

### 3. SSE 流式进度 API

```python
async def scan_stream(request):
    """SSE 流式扫描进度"""
    thread_id = request.GET.get("thread_id")
    
    async def event_stream():
        from app.agent_graphs.security_scan_graph import create_security_scan_graph
        
        checkpointer = MemorySaver()
        graph = create_security_scan_graph(checkpointer)
        config = {"configurable": {"thread_id": thread_id}}
        
        # 轮询状态
        while True:
            state = await graph.aget_state(config)
            
            if not state:
                yield f"data: {json.dumps({'error': '扫描不存在'})}\n\n"
                break
            
            values = state.values
            
            # 推送进度
            yield f"data: {json.dumps({
                'type': 'progress',
                'stage': values['current_stage'],
                'progress': values['progress'],
                'messages': values['progress_messages']
            }, ensure_ascii=False)}\n\n"
            
            # 检查是否完成
            if values['current_stage'] in ['complete', 'failed']:
                yield f"data: {json.dumps({
                    'type': 'complete',
                    'result': values['final_result'],
                    'error': values.get('error')
                }, ensure_ascii=False)}\n\n"
                break
            
            # 等待 2 秒后再次轮询
            await asyncio.sleep(2)
    
    return StreamingHttpResponse(
        event_stream(),
        content_type="text/event-stream",
    )
```

---

## 🧪 测试

### 测试 Dispatcher-Checker 模式

```python
import asyncio
from app.agent_graphs.security_scan_graph import (
    create_security_scan_graph,
    async_task_manager
)

async def test_dispatcher_checker():
    """测试 Dispatcher-Checker 模式"""
    from langgraph.checkpoint.memory import MemorySaver
    
    checkpointer = MemorySaver()
    graph = create_security_scan_graph(checkpointer)
    
    initial_state = {
        "target": "example.com",
        "user_id": "test",
        # ...
    }
    
    config = {"configurable": {"thread_id": "test-123"}}
    
    # 执行到 Dispatcher 节点（会立即返回）
    result = await graph.ainvoke(initial_state, config)
    
    print(f"当前阶段: {result['current_stage']}")
    print(f"后台任务: {result['background_tasks']}")
    
    # 手动轮询检查任务状态
    for task_id in result['background_tasks']:
        done, task_result = await async_task_manager.get_task_result(task_id)
        print(f"任务 {task_id}: done={done}")
        
        if done:
            print(f"结果: {task_result}")
    
    print("✅ 测试完成")

asyncio.run(test_dispatcher_checker())
```

---

## ✅ 优势总结

### 为什么使用 LangGraph 而不是 Celery？

1. **统一架构**
   - 所有逻辑都在 Graph 中
   - 不需要额外的 Celery 配置

2. **原生支持**
   - Checkpointer 是 LangGraph 内置功能
   - 自动处理状态序列化

3. **类型安全**
   - 使用 TypedDict 定义状态
   - IDE 自动补全

4. **易于调试**
   - 可以可视化 Graph 执行流程
   - LangSmith 自动追踪

5. **中断恢复**
   - 支持暂停和恢复
   - 不丢失进度

---

## 📚 相关文档

- **LangGraph Checkpointers**: https://langchain-ai.github.io/langgraph/concepts/persistence/
- **Async Patterns**: https://langchain-ai.github.io/langgraph/how-tos/persistence/
- **State Graph**: https://langchain-ai.github.io/langgraph/reference/

---

**祝使用愉快！** 🚀
