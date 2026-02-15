# SecOps 智能体重构方案

## 📋 现状分析

### 当前架构问题
1. **同步阻塞调用**：HexStrike 调用是同步的，用户必须等待整个扫描完成（可能超过10分钟）
2. **无中间反馈**：用户看不到扫描进度，长时间无响应
3. **单次执行**：无法分阶段返回结果
4. **超时问题**：即使增加了超时时间，用户体验仍然很差

### 现有文件结构
```
app/services/
├── secops_agent.py              # 主智能体（使用通义千问 OpenAI API）
├── secops_conversation.py       # 统一对话服务
├── hexstrike_client.py          # HexStrike HTTP 客户端
├── hexstrike_pdf_reporter.py    # PDF 报告生成
├── hexstrike_html_reporter.py   # HTML 报告生成
└── ...
```

---

## 🎯 重构目标

### 1. **Streaming 中间步骤**（最高优先级）
- ✅ 立即回复用户"已开始扫描"
- ✅ 实时推送扫描进度（如"正在ping目标"、"扫描端口中..."）
- ✅ 逐步返回中间结果

### 2. **分阶段执行**
- ✅ 阶段1（秒级）：Ping + 主机存活检测
- ✅ 阶段2（10-30秒）：快速端口扫描（Top 100端口）
- ✅ 阶段3（分钟级）：完整扫描 + 漏洞扫描
- ✅ 每个阶段完成后立即返回结果

### 3. **异步后台执行**
- ✅ 使用 Celery 后台任务执行长时间扫描
- ✅ Agent 立即返回任务ID
- ✅ 用户可以继续聊天或查询进度

---

## 🏗️ 技术架构

### 核心技术栈
```python
# LangChain 核心库
langchain>=0.1.0
langchain-openai>=0.0.5
langchain-community>=0.0.20

# LangGraph 用于工作流编排
langgraph>=0.0.30

# 异步支持
aiohttp>=3.9.0
```

### 架构设计

```
┌─────────────────────────────────────────────────────────┐
│                     前端 (Vue.js)                       │
│  - SSE 实时接收进度更新                                    │
│  - WebSocket 处理任务状态查询                              │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              Django REST API (views.py)                  │
│  - /api/chat/stream (SSE streaming endpoint)            │
│  - /api/tasks/{id}/status (任务状态查询)                 │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│         LangChain Agent (secops_agent_langchain.py)     │
│  - 意图识别（Intent Recognition）                         │
│  - 工具调用（Tool Calling）                               │
│  - Streaming Events (astream_events)                     │
└────────────────────┬────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
┌───────▼────────┐      ┌─────────▼──────────┐
│  LangGraph     │      │   Celery Workers   │
│  工作流编排     │      │   异步任务执行      │
│                │      │                    │
│ ┌────────────┐ │      │ ┌────────────────┐ │
│ │阶段1: Ping │ │      │ │ HexStrike 扫描 │ │
│ └────────────┘ │      │ └────────────────┘ │
│ ┌────────────┐ │      │ ┌────────────────┐ │
│ │阶段2: 快速 │ │      │ │ 后台进度推送    │ │
│ │端口扫描    │ │      │ │ (SSE/Redis)    │ │
│ └────────────┘ │      │ └────────────────┘ │
│ ┌────────────┐ │      └──────────────────────┘
│ │阶段3: 完整 │ │
│ │扫描+漏洞   │ │
│ └────────────┘ │
└────────────────┘
```

---

## 📝 实施步骤

### Phase 1: 安装依赖和基础设施 ✅
- [ ] 安装 LangChain 和 LangGraph
- [ ] 更新 requirements.txt
- [ ] 创建新的服务目录结构

### Phase 2: 创建 LangChain 工具定义
- [ ] 创建 `app/agent_tools/` 目录
- [ ] 实现 `hexstrike_progressive_scan.py` (分阶段扫描工具)
- [ ] 实现 `task_management_tools.py` (任务管理工具)
- [ ] 实现 `asset_query_tools.py` (资产查询工具)

### Phase 3: 实现 LangGraph 工作流
- [ ] 创建 `app/agent_graphs/` 目录
- [ ] 定义状态类（ScanState, TaskState等）
- [ ] 实现工作流节点：
  - `node_intent_recognition` (意图识别)
  - `node_quick_scan` (快速扫描)
  - `node_full_scan` (完整扫描)
  - `node_report_generation` (报告生成)

### Phase 4: 集成 


















异步任务
- [ ] 创建 `app/celery_tasks/agent_tasks.py`
- [ ] 实现后台扫描任务
- [ ] 实现进度推送机制（Redis Pub/Sub）
- [ ] 实现任务状态查询接口

### Phase 5: 实现 SSE Streaming API
- [ ] 创建 Django SSE 视图
- [ ] 实现 astream_events() 推送
- [ ] 前端适配（EventSource）

### Phase 6: 测试和优化
- [ ] 单元测试
- [ ] 集成测试
- [ ] 性能优化
- [ ] 用户测试

---

## 🔧 核心代码结构

### 1. LangChain Agent (secops_agent_langchain.py)

```python
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_openai import ChatOpenAI
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from app.agent_tools.hexstrike_tools import HexStrikeProgressiveTool

class SecOpsLangChainAgent:
    def __init__(self, api_key: str, model: str = "qwen-plus"):
        self.llm = ChatOpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model=model,
            temperature=0.3,
            streaming=True,  # 启用 streaming
        )
        self.tools = [
            HexStrikeProgressiveTool(),
            # ... 其他工具
        ]
        self.agent = create_openai_tools_agent(self.llm, self.tools, prompt)
        self.executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=True,
            return_intermediate_steps=True,  # 返回中间步骤
        )

    async def astream_chat(self, message: str):
        """异步流式对话"""
        async for event in self.executor.astream_events(
            {"input": message},
            version="v1",
        ):
            kind = event["event"]
            if kind == "on_chat_start":
                yield "🤖 正在启动安全评估...\n\n"
            elif kind == "on_tool_start":
                tool = event["name"]
                yield f"🔧 执行工具: {tool}\n"
            elif kind == "on_tool_end":
                yield f"✅ 工具执行完成\n"
            elif kind == "on_tool_stream":
                chunk = event["data"]["chunk"]
                yield chunk
```

### 2. 分阶段 HexStrike 工具 (hexstrike_progressive_scan.py)

```python
from langchain.tools import StructuredTool
from typing import Optional, Dict, Any

class HexStrikeProgressiveTool(StructuredTool):
    name = "hexstrike_progressive_scan"
    description = """分阶段执行安全扫描：
    阶段1: Ping + 主机存活检测（秒级）
    阶段2: 快速端口扫描（10-30秒）
    阶段3: 完整扫描 + 漏洞扫描（分钟级）
    """

    async def _arun(
        self,
        target: str,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """异步执行分阶段扫描"""

        # 阶段1: Ping
        yield "📡 阶段1/3: 正在 Ping 目标主机...\n"
        ping_result = await self._ping_target(target)
        yield f"✅ 主机存活: {ping_result['alive']}\n\n"

        # 阶段2: 快速端口扫描
        yield "🔍 阶段2/3: 正在执行快速端口扫描（Top 100端口）...\n"
        quick_scan = await self._quick_port_scan(target)
        yield f"✅ 发现 {len(quick_scan['ports'])} 个开放端口\n\n"

        # 提交 Celery 任务执行完整扫描
        yield "🚀 阶段3/3: 已启动后台完整扫描（含漏洞检测）\n"
        task_id = await self._submit_full_scan_task(target, user_id)
        yield f"📋 任务ID: {task_id}\n"
        yield "💡 您可以继续对话，扫描完成后我会自动通知您\n\n"

        return {
            "success": True,
            "task_id": task_id,
            "quick_results": quick_scan,
        }

    async def _ping_target(self, target: str) -> Dict:
        """Ping 目标主机"""
        # 使用 asyncio 子进程执行 ping
        proc = await asyncio.create_subprocess_exec(
            "ping", "-c", "1", "-W", "2", target,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        alive = proc.returncode == 0
        return {"alive": alive, "output": stdout.decode()}

    async def _quick_port_scan(self, target: str) -> Dict:
        """快速端口扫描（Top 100）"""
        # 调用 HexStrike 快速扫描 API
        # 或使用 nmap -F 参数
        pass

    async def _submit_full_scan_task(self, target: str, user_id: str) -> str:
        """提交后台完整扫描任务"""
        from app.celery_tasks.agent_tasks import full_hexstrike_scan
        task = full_hexstrike_scan.delay(target, user_id)
        return task.id
```

### 3. Celery 异步任务 (celery_tasks/agent_tasks.py)

```python
from celery import shared_task
from app.services.hexstrike_client import HexStrikeClient
from app.utils.sse_manager import SSEManager

@shared_task(bind=True)
def full_hexstrike_scan(self, target: str, user_id: str):
    """后台执行完整 HexStrike 扫描"""

    # 1. 更新任务状态
    self.update_state(state='PROGRESS', meta={'stage': 'starting', 'progress': 0})

    # 2. 执行 Nmap 扫描
    sse = SSEManager(f"user_{user_id}")
    sse.publish({"stage": "nmap", "message": "正在执行 Nmap 端口扫描..."})

    client = HexStrikeClient(timeout=600)  # 10分钟超时
    nmap_result = client.run_nmap_scan(target)

    # 3. 推送 Nmap 结果
    self.update_state(state='PROGRESS', meta={'stage': 'nmap_done', 'progress': 40})
    sse.publish({
        "stage": "nmap_complete",
        "message": "Nmap 扫描完成",
        "data": nmap_result
    })

    # 4. 执行 Nuclei 漏洞扫描
    self.update_state(state='PROGRESS', meta={'stage': 'nuclei', 'progress': 50})
    sse.publish({"stage": "nuclei", "message": "正在执行 Nuclei 漏洞扫描..."})

    nuclei_result = client.run_nuclei_scan(target)

    # 5. 生成报告
    self.update_state(state='PROGRESS', meta={'stage': 'generating_report', 'progress': 90})
    sse.publish({"stage": "report", "message": "正在生成 PDF 报告..."})

    from app.services.hexstrike_pdf_reporter import HexStrikePDFReporter
    reporter = HexStrikePDFReporter()
    pdf_file = reporter.generate_pdf_report(
        target=target,
        nmap_results=nmap_result,
        nuclei_results=nuclei_result,
    )

    # 6. 完成
    self.update_state(state='SUCCESS', meta={'stage': 'complete', 'progress': 100})
    sse.publish({
        "stage": "complete",
        "message": "✅ 扫描完成！",
        "pdf_file": pdf_file
    })

    return {
        "target": target,
        "nmap_result": nmap_result,
        "nuclei_result": nuclei_result,
        "pdf_file": pdf_file
    }
```

### 4. SSE Streaming 视图 (views.py)

```python
from django.http import StreamingHttpResponse
from app.services.secops_agent_langchain import SecOpsLangChainAgent

def chat_stream(request):
    """SSE Streaming 聊天接口"""
    user_message = request.GET.get("message")

    async def event_stream():
        agent = SecOpsLangChainAgent(api_key=settings.QWEN_API_KEY)
        async for chunk in agent.astream_chat(user_message):
            yield f"data: {json.dumps({'text': chunk}, ensure_ascii=False)}\n\n"

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response['Cache-Control'] = 'no-cache'
    return response
```

### 5. LangGraph 工作流定义 (agent_graphs/security_scan_graph.py)

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict

class ScanState(TypedDict):
    target: str
    user_id: str
    ping_result: Optional[Dict]
    quick_scan_result: Optional[Dict]
    full_scan_result: Optional[Dict]
    current_stage: str

def create_security_scan_graph():
    """创建安全扫描工作流图"""
    workflow = StateGraph(ScanState)

    # 添加节点
    workflow.add_node("ping", ping_node)
    workflow.add_node("quick_scan", quick_scan_node)
    workflow.add_node("submit_full_scan", submit_full_scan_node)
    workflow.add_node("generate_report", generate_report_node)

    # 设置入口
    workflow.set_entry_point("ping")

    # 添加边
    workflow.add_edge("ping", "quick_scan")
    workflow.add_edge("quick_scan", "submit_full_scan")
    workflow.add_conditional_edges(
        "submit_full_scan",
        should_generate_report,
        {
            "yes": "generate_report",
            "no": END
        }
    )
    workflow.add_edge("generate_report", END)

    return workflow.compile()

async def ping_node(state: ScanState) -> ScanState:
    """执行 Ping 节点"""
    # ... 实现
    state["current_stage"] = "ping_done"
    return state
```

---

## 📦 新文件结构

```
app/
├── agent_tools/                    # LangChain 工具定义
│   ├── __init__.py
│   ├── hexstrike_tools.py          # HexStrike 相关工具
│   ├── task_tools.py               # 任务管理工具
│   └── asset_tools.py              # 资产查询工具
│
├── agent_graphs/                   # LangGraph 工作流
│   ├── __init__.py
│   ├── security_scan_graph.py      # 安全扫描工作流
│   └── task_management_graph.py    # 任务管理工作流
│
├── celery_tasks/                   # Celery 异步任务
│   ├── __init__.py
│   ├── agent_tasks.py              # Agent 相关任务
│   └── hexstrike_tasks.py          # HexStrike 扫描任务
│
├── services/
│   ├── secops_agent.py             # 原有 Agent（保留兼容）
│   ├── secops_agent_langchain.py   # 新 LangChain Agent ⭐
│   ├── secops_conversation.py      # 对话服务（保留）
│   └── sse_manager.py              # SSE 管理器 ⭐
│
└── api/
    └── views.py                    # 添加 SSE endpoint
```

---

## ⚡ 性能优化

1. **并发控制**
   - 使用 asyncio 并行执行多个工具
   - Celery worker 并发数限制（避免过载）

2. **缓存策略**
   - 漏洞数据库缓存
   - 资产信息缓存（Redis）

3. **超时优化**
   - 快速扫描：30秒
   - Nmap：2分钟
   - Nuclei：5分钟（限制严重级别）
   - 完整扫描：10分钟

---

## 🧪 测试计划

1. **单元测试**
   - 测试每个工具的异步执行
   - 测试工作流状态转换

2. **集成测试**
   - 端到端扫描流程
   - SSE streaming 测试

3. **压力测试**
   - 并发用户数：10、50、100
   - 任务队列堆积处理

---

## 📚 参考资源

- [LangChain Documentation](https://python.langchain.com/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangChain Streaming Example](https://github.com/langchain-ai/langserve/tree/main/examples/agent_custom_streaming)
- [Celery Best Practices](https://docs.celeryq.dev/en/stable/userguide/optimizing.html)