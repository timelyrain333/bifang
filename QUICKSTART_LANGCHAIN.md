# SecOps 智能体重构 - 快速开始指南

## 🎉 重构完成！

基于 LangChain 和 LangGraph 的 SecOps 智能体重构已完成核心功能。

---

## 📦 已安装的依赖

```bash
✅ langchain>=0.1.0
✅ langchain-openai>=0.0.5
✅ langchain-community>=0.0.20
✅ langgraph>=0.0.30
✅ aiohttp>=3.9.0
```

---

## 🏗️ 新增文件结构

```
app/
├── utils/
│   └── sse_manager.py                  # SSE 实时推送管理器
├── agent_tools/                        # LangChain 工具
│   ├── __init__.py
│   └── hexstrike_tools.py              # HexStrike 分阶段扫描工具
├── agent_graphs/                       # LangGraph 工作流
│   └── __init__.py
├── celery_tasks/                       # Celery 异步任务
│   ├── __init__.py
│   └── hexstrike_tasks.py              # 后台完整扫描任务
├── api/                                # API 视图
│   ├── __init__.py
│   ├── streaming_views.py              # SSE 流式接口
│   └── urls.py                         # URL 配置
└── services/
    ├── secops_agent.py                 # 原有 Agent（保留）
    └── secops_agent_langchain.py       # 新 LangChain Agent ⭐
```

---

## 🚀 快速开始

### 1. 配置 URL 路由

编辑 `bifang/urls.py`:

```python
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('app.api.urls')),  # ← 添加这行
    # ... 其他路由
]
```

### 2. 确保 Redis 正在运行

```bash
# 检查 Redis
redis-cli ping
# 应该返回: PONG

# 或使用 Docker
docker ps | grep redis
```

### 3. 确保 Celery Worker 正在运行

```bash
# 启动 Celery Worker（新终端）
celery -A app.celery_app worker -l info

# 如果需要后台运行
celery -A app.celery_app worker -l info --detach
```

### 4. 确保 HexStrike 服务已启动

```bash
# 启动 HexStrike AI（如果使用）
cd hexstrike-ai
python hexstrike_server.py

# 或使用 Docker
docker compose up -d hexstrike-ai
```

### 5. 测试 SSE API

```bash
# 测试流式聊天（使用 curl）
curl -N "http://localhost:8000/api/chat/stream?message=你好"

# 或在浏览器中打开
# http://localhost:8000/api/chat/status
```

---

## 🧪 Python 测试代码

### 测试 1: SSE 管理器

```python
from app.utils.sse_manager import SSEManager

# 创建 SSE 管理器
sse = SSEManager("test_channel")

# 发送测试消息
sse.send_progress("test_stage", 50, "测试进度更新")
sse.send_agent_thinking("AI 正在思考...")
sse.send_complete({"result": "测试完成"})

print("✅ SSE 管理器测试通过")
```

### 测试 2: HexStrike 工具

```python
import asyncio
from app.agent_tools.hexstrike_tools import HexStrikeProgressiveTool

async def test_hexstrike_tool():
    tool = HexStrikeProgressiveTool()
    
    result = await tool._arun(
        target="example.com",
        user_id="test_user"
    )
    
    print(f"结果: {result}")
    assert result["success"] == True
    assert "task_id" in result
    print("✅ HexStrike 工具测试通过")

asyncio.run(test_hexstrike_tool())
```

### 测试 3: LangChain Agent

```python
import asyncio
from app.services.secops_agent_langchain import SecOpsLangChainAgent

async def test_agent():
    # 初始化 Agent
    agent = SecOpsLangChainAgent(
        api_key="your-qwen-api-key",
        model="qwen-plus"
    )
    
    # 流式对话
    async for chunk in agent.astream_chat(
        message="对 example.com 进行安全评估",
        user_id="test_user"
    ):
        print(chunk, end="", flush=True)
    
    print("\n✅ LangChain Agent 测试通过")

asyncio.run(test_agent())
```

### 测试 4: Celery 任务

```python
from app.celery_tasks.hexstrike_tasks import full_hexstrike_scan

# 提交后台任务
task = full_hexstrike_scan.delay("example.com", "test_user")

print(f"任务ID: {task.id}")
print(f"任务状态: {task.state}")

# 等待完成
result = task.get(timeout=600)
print(f"结果: {result}")
```

---

## 📊 API 端点

### 1. SSE 流式聊天

**端点**: `GET /api/chat/stream`

**参数**:
- `message` (必需): 用户消息
- `conversation_history` (可选): 对话历史（JSON 字符串）

**示例**:
```bash
curl -N "http://localhost:8000/api/chat/stream?message=扫描example.com"
```

**响应格式**:
```
data: {"type":"message","text":"🤖 正在处理...","user_id":"test"}

data: {"type":"message","text":"✅ 完成","user_id":"test"}
```

### 2. 聊天状态

**端点**: `GET /api/chat/status`

**响应**:
```json
{
  "status": "ok",
  "user_id": "test",
  "channel": "user_test",
  "redis_ok": true
}
```

---

## 🎯 核心功能

### 1. 分阶段扫描

```python
from app.agent_tools.hexstrike_tools import HexStrikeProgressiveTool

tool = HexStrikeProgressiveTool()
result = await tool._arun("example.com", "user_123")

# 结果包含:
# - stages_completed: ["ping", "quick_scan"]
# - task_id: "celery-task-id"
# - quick_scan: {"ports": [...], "scan_time": 12.5}
```

**执行流程**:
1. **阶段1** (秒级): Ping 主机存活
2. **阶段2** (10-30秒): 快速端口扫描 Top 100
3. **阶段3** (后台): 完整扫描 + 漏洞检测

### 2. 实时进度推送

```python
from app.utils.sse_manager import SSEManager

sse = SSEManager("user_123")

# 推送进度
sse.send_progress("scanning", 50, "正在扫描端口...")

# 推送工具事件
sse.send_tool_start("nmap", {"target": "example.com"})
sse.send_tool_end("nmap", "扫描完成")

# 推送完成
sse.send_complete({"task_id": "abc-123"})
```

### 3. 后台任务

```python
from app.celery_tasks.hexstrike_tasks import full_hexstrike_scan

# 提交任务
task = full_hexstrike_scan.delay("example.com", "user_123")

# 查询状态
if task.state == "PROGRESS":
    progress = task.info.get('progress')  # 0-100
    stage = task.info.get('stage')        # "nmap", "nuclei", etc.
    print(f"进度: {progress}% ({stage})")

# 获取结果
if task.state == "SUCCESS":
    result = task.result
    pdf_file = result.get("pdf_file")
    print(f"PDF 报告: {pdf_file}")
```

---

## 🔧 配置说明

### Django Settings (`bifang/settings.py`)

确保以下配置已设置：

```python
# 通义千问配置
QWEN_API_KEY = "your-qwen-api-key"
QWEN_MODEL = "qwen-plus"  # 或 "qwen-turbo"

# HexStrike 配置
HEXSTRIKE_ENABLED = True
HEXSTRIKE_SERVER_URL = "http://localhost:8888"
HEXSTRIKE_TIMEOUT = 600  # 10 分钟

# Redis 配置
REDIS_URL = "redis://localhost:6379/0"

# Celery 配置
CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/0"
```

---

## 📝 使用示例

### 完整流程：用户发起安全评估

```python
# 1. 用户发送消息: "对 192.168.1.1 进行安全评估"
# 2. 前端调用 SSE API
streamChat("对 192.168.1.1 进行安全评估", {
    onMessage: (chunk, fullText) => {
        console.log('收到消息:', chunk)
        // 实时显示在 UI 上
    }
})

# 3. 后端处理流程
#    - LangChain Agent 识别意图
#    - 调用 HexStrikeProgressiveTool
#    - 阶段1: Ping (返回: "主机存活")
#    - 阶段2: 快速扫描 (返回: "发现 5 个开放端口")
#    - 阶段3: 提交后台任务 (返回: "任务ID: abc-123")
#    - 10 分钟后: 完成后台扫描，生成 PDF

# 4. 用户看到的实时反馈
#    🤖 正在处理您的请求...
#    📡 阶段1/3: 正在 Ping 目标主机...
#    ✅ 主机存活: 192.168.1.1 响应正常
#    🔍 阶段2/3: 正在执行快速端口扫描（Top 100）...
#    ✅ 快速扫描完成：发现 5 个开放端口
#    🚀 阶段3/3: 已启动后台完整扫描（含漏洞检测）
#    📋 任务ID: abc-123
#    💡 您可以继续对话，扫描完成后我会自动通知您

# 5. 后台任务完成时（10分钟后）
#    后台任务自动推送完成通知
#    用户收到: "✅ 完整扫描完成！PDF 报告: hexstrike_report_....pdf"
```

---

## 🐛 故障排查

### 问题 1: SSE 连接立即断开

**检查**:
```bash
# 检查 Redis
redis-cli ping

# 检查 Django 日志
tail -f /path/to/django.log
```

**解决**: 确保 Redis 正在运行

### 问题 2: Celery 任务不执行

**检查**:
```bash
# 检查 Celery Worker
celery -A app.celery_app inspect active

# 检查任务队列
celery -A app.celery_app inspect registered
```

**解决**: 重启 Celery Worker
```bash
pkill -9 celery
celery -A app.celery_app worker -l info
```

### 问题 3: HexStrike 调用失败

**检查**:
```bash
# 检查 HexStrike 服务
curl http://localhost:8888/health

# 检查日志
tail -f hexstrike-ai/logs/server.log
```

---

## 📚 相关文档

- **完整重构方案**: `SECOPS_AGENT_REFACTOR.md`
- **进展总结**: `REFACTOR_PROGRESS.md`
- **前端适配**: `FRONTEND_ADAPTATION.md`

---

## ✅ 完成清单

- [x] 安装 LangChain 和 LangGraph
- [x] 创建 SSE 管理器
- [x] 创建 HexStrike 分阶段工具
- [x] 创建 Celery 异步任务
- [x] 创建 LangChain Agent
- [x] 创建 SSE API endpoint
- [x] 创建前端适配示例
- [x] 编写使用文档

---

## 🎉 下一步

1. **测试**: 运行上述测试代码
2. **前端集成**: 参考 `FRONTEND_ADAPTATION.md`
3. **生产部署**: 配置 Nginx + Gunicorn
4. **监控**: 使用 Flower 监控 Celery 任务

---

**祝使用愉快！** 🚀
