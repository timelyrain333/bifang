# AI智能体开发文档

## 目录

1. [概述](#概述)
2. [架构设计](#架构设计)
3. [核心组件](#核心组件)
4. [配置说明](#配置说明)
5. [API使用](#api使用)
6. [开发指南](#开发指南)
7. [示例代码](#示例代码)
8. [故障排查](#故障排查)

---

## 概述

Bifang系统的AI智能体（SecOps Agent）基于通义千问大模型，提供自然语言交互能力，帮助用户执行安全运营任务。智能体支持：

- **自然语言理解**：理解用户的安全运营需求
- **任务执行**：自动执行漏洞采集、资产采集、漏洞匹配等操作
- **任务管理**：创建、查询、更新定时任务
- **流式响应**：实时返回执行结果
- **Function Calling**：支持AI调用系统工具函数

### 技术栈

- **AI模型**：通义千问（Qwen）系列模型
- **SDK**：OpenAI兼容API（`openai`库）
- **框架**：Django + Django REST Framework
- **异步处理**：Python生成器（Generator）实现流式输出

---

## 架构设计

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                     用户交互层                                │
│  (钉钉机器人 / 飞书机器人 / Web前端)                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   SecOpsAgent (智能体核心)                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  1. 意图分析 (_analyze_intent)                       │   │
│  │  2. AI对话 (chat)                                     │   │
│  │  3. Function Calling (工具调用)                      │   │
│  │  4. 操作执行 (_execute_action)                        │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
        ▼                             ▼
┌──────────────────┐        ┌──────────────────┐
│  通义千问API      │        │  任务执行引擎      │
│  (qianwen.py)    │        │  (TaskExecutor)  │
└──────────────────┘        └──────────────────┘
        │                             │
        ▼                             ▼
┌──────────────────┐        ┌──────────────────┐
│  任务工具函数     │        │  插件系统         │
│  (task_tools.py)  │        │  (BasePlugin)     │
└──────────────────┘        └──────────────────┘
```

### 数据流

1. **用户输入** → 智能体接收消息
2. **意图分析** → 判断用户意图（查询/执行操作/创建任务）
3. **AI处理** → 调用通义千问模型，可能触发Function Calling
4. **工具调用** → 执行系统工具函数（如`create_task`）
5. **操作执行** → 执行安全运营操作（如漏洞采集）
6. **流式响应** → 实时返回执行结果给用户

---

## 核心组件

### 1. SecOpsAgent (`app/services/secops_agent.py`)

智能体的核心类，负责处理用户对话和执行任务。

#### 主要方法

##### `__init__(api_key, api_base, model)`

初始化智能体。

**参数：**
- `api_key` (str): 通义千问API Key
- `api_base` (str): API地址，默认 `'https://dashscope.aliyuncs.com/compatible-mode/v1'`
- `model` (str): 模型名称，默认 `'qwen-plus'`

**示例：**
```python
from app.services.secops_agent import SecOpsAgent

agent = SecOpsAgent(
    api_key='your-api-key',
    api_base='https://dashscope.aliyuncs.com/compatible-mode/v1',
    model='qwen-plus'
)
```

##### `chat(user_message, conversation_history, user)`

与用户对话，流式返回响应。

**参数：**
- `user_message` (str): 用户消息
- `conversation_history` (List[Dict], optional): 对话历史，格式：
  ```python
  [
      {'role': 'user', 'content': '用户消息'},
      {'role': 'assistant', 'content': 'AI回复'}
  ]
  ```
- `user`: 用户对象（可选，用于任务创建者）

**返回：**
- `Generator[str, None, None]`: 流式响应文本片段

**示例：**
```python
# 基本使用
for chunk in agent.chat("请采集最近3天的漏洞"):
    print(chunk, end='', flush=True)

# 带对话历史
history = [
    {'role': 'user', 'content': '你好'},
    {'role': 'assistant', 'content': '你好！我是SecOps智能体'}
]
for chunk in agent.chat("请帮我创建定时任务", conversation_history=history):
    print(chunk, end='', flush=True)
```

#### 内部方法

##### `_analyze_intent(user_message)`

分析用户意图，判断是否需要执行操作。

**返回：**
```python
{
    'needs_vulnerability_collection': bool,  # 是否需要采集漏洞
    'needs_asset_collection': bool,          # 是否需要采集资产
    'needs_matching': bool,                  # 是否需要匹配漏洞
    'days': int,                             # 时间范围（天数）
    'is_query': bool                         # 是否是查询类消息
}
```

##### `_build_system_prompt()`

构建系统提示词，定义AI的角色和能力。

##### `_extract_actions(response, intent_analysis, user_message)`

从AI响应和意图分析中提取需要执行的操作。

**返回：**
```python
[
    {
        'name': 'collect_vulnerabilities',
        'parameters': {'days': 3}
    }
]
```

##### `_execute_action(action, user)`

执行操作（漏洞采集、资产采集、漏洞匹配）。

##### `_call_tool(function_name, function_args, user)`

调用工具函数（Function Calling）。

**支持的工具函数：**
- `create_task`: 创建任务
- `list_tasks`: 查询任务列表
- `update_task`: 更新任务
- `parse_cron`: 解析cron表达式

---

### 2. 通义千问工具 (`app/utils/qianwen.py`)

提供AI模型调用功能，主要用于漏洞解析。

#### 主要函数

##### `parse_vulnerability_with_ai(raw_content, cve_id, api_key, api_base, model)`

使用AI解析漏洞详情。

**参数：**
- `raw_content` (str): 漏洞原始邮件内容
- `cve_id` (str): CVE编号
- `api_key` (str): API Key
- `api_base` (str): API地址
- `model` (str): 模型名称

**返回：**
```python
{
    'basic_description': str,           # 基本描述
    'vulnerability_description': str,   # 详细描述
    'impact': str,                      # 影响
    'severity': str,                    # 危害等级
    'affected_component': str,          # 受影响组件
    'affected_versions': str,           # 受影响版本
    'solution': str,                    # 解决方案
    'mitigation': str                   # 缓解措施
}
```

**示例：**
```python
from app.utils.qianwen import parse_vulnerability_with_ai

result = parse_vulnerability_with_ai(
    raw_content=email_content,
    cve_id='CVE-2024-1234',
    api_key='your-api-key',
    api_base='https://dashscope.aliyuncs.com/compatible-mode/v1',
    model='qwen-plus'
)
```

##### `test_qianwen_connection(api_key, api_base, model)`

测试通义千问API连接。

**返回：**
```python
{
    'success': bool,
    'message': str
}
```

---

### 3. 任务工具函数 (`app/services/task_tools.py`)

提供任务管理功能，供AI智能体调用。

#### 主要函数

##### `create_task(name, plugin_name_or_keyword, trigger_type, ...)`

创建任务。

**参数：**
- `name` (str): 任务名称
- `plugin_name_or_keyword` (str): 插件名称或关键词（如"漏洞采集"、"资产采集"）
- `trigger_type` (str): 触发类型（'manual'、'cron'、'interval'）
- `cron_expression` (str, optional): Cron表达式
- `task_config` (dict, optional): 任务配置
- `is_active` (bool): 是否启用
- `created_by` (str, optional): 创建者用户名

**返回：**
```python
{
    'success': bool,
    'message': str,
    'task_id': int,
    'task_name': str,
    'plugin_name': str,
    'trigger_type': str,
    'cron_expression': str
}
```

**示例：**
```python
from app.services.task_tools import create_task

result = create_task(
    name='每天采集漏洞',
    plugin_name_or_keyword='漏洞采集',
    trigger_type='cron',
    cron_expression='0 0 * * *',
    created_by='admin'
)
```

##### `list_tasks(plugin_name, trigger_type, is_active, created_by, limit)`

查询任务列表。

##### `update_task(task_id, name, trigger_type, cron_expression, ...)`

更新任务。

##### `parse_cron_from_natural_language(text)`

将自然语言转换为cron表达式。

**示例：**
```python
from app.services.task_tools import parse_cron_from_natural_language

cron = parse_cron_from_natural_language('每天0点')  # 返回: '0 0 * * *'
cron = parse_cron_from_natural_language('每小时')  # 返回: '0 * * * *'
cron = parse_cron_from_natural_language('每6小时')  # 返回: '0 */6 * * *'
```

---

## 配置说明

### 1. 系统配置

在Django管理后台或通过API配置AI参数：

**配置项：**
- `qianwen_api_key`: 通义千问API Key
- `qianwen_api_base`: API地址（默认：`https://dashscope.aliyuncs.com/compatible-mode/v1`）
- `qianwen_model`: 模型名称（默认：`qwen-plus`）
- `qianwen_enabled`: 是否启用AI功能

**配置方式：**

通过`AliyunConfig`模型配置：

```python
from app.models import AliyunConfig

config = AliyunConfig.objects.get(id=1)
config.qianwen_api_key = 'your-api-key'
config.qianwen_api_base = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
config.qianwen_model = 'qwen-plus'
config.qianwen_enabled = True
config.save()
```

### 2. 依赖安装

确保安装以下Python包：

```bash
pip install openai
```

### 3. 环境变量（可选）

可以通过环境变量配置：

```bash
export QIANWEN_API_KEY='your-api-key'
export QIANWEN_API_BASE='https://dashscope.aliyuncs.com/compatible-mode/v1'
export QIANWEN_MODEL='qwen-plus'
```

---

## API使用

### 1. 在Django视图中使用

```python
from app.services.secops_agent import SecOpsAgent
from app.models import AliyunConfig
from django.http import StreamingHttpResponse

def chat_view(request):
    # 获取AI配置
    config = AliyunConfig.objects.filter(qianwen_enabled=True).first()
    if not config or not config.qianwen_api_key:
        return JsonResponse({'error': 'AI配置未启用'}, status=400)
    
    # 创建智能体
    agent = SecOpsAgent(
        api_key=config.qianwen_api_key,
        api_base=config.qianwen_api_base or 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        model=config.qianwen_model or 'qwen-plus'
    )
    
    # 获取用户消息
    user_message = request.POST.get('message', '')
    
    # 流式响应
    def generate():
        for chunk in agent.chat(user_message, user=request.user):
            yield chunk
    
    return StreamingHttpResponse(generate(), content_type='text/plain; charset=utf-8')
```

### 2. 在机器人服务中使用

#### 钉钉机器人

```python
from app.services.secops_agent import SecOpsAgent
from app.models import AliyunConfig

# 在DingTalkStreamChatbotHandler中
class DingTalkStreamChatbotHandler(dingtalk_stream.AsyncChatbotHandler):
    async def process(self, callback):
        # 获取AI配置
        config = AliyunConfig.objects.filter(
            qianwen_enabled=True,
            qianwen_api_key__isnull=False
        ).first()
        
        if not config:
            return self.reply_text("AI配置未启用", incoming_message)
        
        # 创建智能体
        agent = SecOpsAgent(
            api_key=config.qianwen_api_key,
            api_base=config.qianwen_api_base or 'https://dashscope.aliyuncs.com/compatible-mode/v1',
            model=config.qianwen_model or 'qwen-plus'
        )
        
        # 处理消息
        content = self.extract_text_from_incoming_message(incoming_message)
        
        # 收集响应
        response_parts = []
        for part in agent.chat(content, user=user_id):
            response_parts.append(part)
        
        response = ''.join(response_parts)
        self.reply_text(response, incoming_message)
```

#### 飞书机器人

类似钉钉机器人的实现方式。

---

## 开发指南

### 1. 添加新的操作

在`SecOpsAgent`中添加新的操作：

**步骤1：** 在`AVAILABLE_ACTIONS`中添加操作定义

```python
AVAILABLE_ACTIONS = [
    # ... 现有操作
    {
        'name': 'new_action',
        'description': '新操作描述',
        'plugin_name': '插件名称（如果需要）',
        'parameters': {
            'param1': '参数1说明'
        }
    }
]
```

**步骤2：** 在`_execute_action`中添加执行逻辑

```python
def _execute_action(self, action: Dict[str, Any], user=None) -> Generator[str, None, None]:
    action_name = action.get('name')
    
    if action_name == 'new_action':
        yield from self._new_action(action.get('parameters', {}), user)
    # ... 其他操作
```

**步骤3：** 实现操作方法

```python
def _new_action(self, parameters: Dict[str, Any], user=None) -> Generator[str, None, None]:
    """执行新操作"""
    yield "开始执行新操作...\n"
    
    # 执行逻辑
    # ...
    
    yield "操作完成\n"
```

**步骤4：** 更新系统提示词（可选）

在`_build_system_prompt`中添加新操作的说明。

### 2. 添加新的工具函数

**步骤1：** 在`TOOLS`中添加工具定义

```python
TOOLS = [
    # ... 现有工具
    {
        "type": "function",
        "function": {
            "name": "new_tool",
            "description": "工具描述",
            "parameters": {
                "type": "object",
                "properties": {
                    "param1": {
                        "type": "string",
                        "description": "参数1说明"
                    }
                },
                "required": ["param1"]
            }
        }
    }
]
```

**步骤2：** 在`_call_tool`中添加调用逻辑

```python
def _call_tool(self, function_name: str, function_args: Dict[str, Any], user=None) -> Dict[str, Any]:
    if function_name == 'new_tool':
        return self._execute_new_tool(function_args, user)
    # ... 其他工具
```

**步骤3：** 实现工具函数

```python
def _execute_new_tool(self, args: Dict[str, Any], user=None) -> Dict[str, Any]:
    """执行新工具"""
    try:
        # 工具逻辑
        result = do_something(args['param1'])
        
        return {
            'success': True,
            'message': '工具执行成功',
            'data': result
        }
    except Exception as e:
        return {
            'success': False,
            'message': f'工具执行失败: {str(e)}'
        }
```

### 3. 自定义系统提示词

修改`_build_system_prompt`方法，自定义AI的行为和回复风格。

### 4. 优化意图分析

修改`_analyze_intent`方法，添加新的关键词匹配规则。

---

## 示例代码

### 示例1：基本对话

```python
from app.services.secops_agent import SecOpsAgent

# 初始化
agent = SecOpsAgent(
    api_key='your-api-key',
    model='qwen-plus'
)

# 简单对话
for chunk in agent.chat("你好，你能做什么？"):
    print(chunk, end='', flush=True)
```

### 示例2：执行操作

```python
# 采集漏洞
for chunk in agent.chat("请采集最近3天的漏洞"):
    print(chunk, end='', flush=True)

# 采集资产
for chunk in agent.chat("请采集资产信息"):
    print(chunk, end='', flush=True)

# 匹配漏洞
for chunk in agent.chat("请检查最近1天的漏洞是否影响资产"):
    print(chunk, end='', flush=True)
```

### 示例3：创建定时任务

```python
# 使用自然语言
for chunk in agent.chat("请创建一个定时任务，每天0点采集漏洞"):
    print(chunk, end='', flush=True)

# 使用cron表达式
for chunk in agent.chat("请创建一个定时任务，使用cron表达式 '0 0 * * *' 采集漏洞"):
    print(chunk, end='', flush=True)
```

### 示例4：查询任务

```python
# 查询所有任务
for chunk in agent.chat("请列出所有任务"):
    print(chunk, end='', flush=True)

# 查询特定类型的任务
for chunk in agent.chat("请列出所有漏洞采集任务"):
    print(chunk, end='', flush=True)
```

### 示例5：使用对话历史

```python
history = []

# 第一轮对话
user_msg1 = "你好"
for chunk in agent.chat(user_msg1, conversation_history=history):
    print(chunk, end='', flush=True)
    response1 += chunk

history.append({'role': 'user', 'content': user_msg1})
history.append({'role': 'assistant', 'content': response1})

# 第二轮对话（带历史）
user_msg2 = "请帮我采集漏洞"
for chunk in agent.chat(user_msg2, conversation_history=history):
    print(chunk, end='', flush=True)
```

### 示例6：在Django视图中使用

```python
from django.http import StreamingHttpResponse, JsonResponse
from app.services.secops_agent import SecOpsAgent
from app.models import AliyunConfig

def secops_chat(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    # 获取AI配置
    config = AliyunConfig.objects.filter(
        qianwen_enabled=True,
        qianwen_api_key__isnull=False
    ).first()
    
    if not config:
        return JsonResponse({'error': 'AI配置未启用'}, status=400)
    
    # 创建智能体
    agent = SecOpsAgent(
        api_key=config.qianwen_api_key,
        api_base=config.qianwen_api_base or 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        model=config.qianwen_model or 'qwen-plus'
    )
    
    # 获取用户消息
    user_message = request.POST.get('message', '')
    if not user_message:
        return JsonResponse({'error': '消息不能为空'}, status=400)
    
    # 流式响应
    def generate():
        try:
            for chunk in agent.chat(user_message, user=request.user):
                yield chunk
        except Exception as e:
            yield f"❌ 发生错误: {str(e)}\n"
    
    return StreamingHttpResponse(
        generate(),
        content_type='text/plain; charset=utf-8'
    )
```

---

## 故障排查

### 1. AI配置未启用

**错误信息：**
```
AI配置未启用，无法使用智能体功能
```

**解决方法：**
1. 检查`AliyunConfig`中是否配置了`qianwen_api_key`
2. 确保`qianwen_enabled=True`
3. 检查API Key是否有效

### 2. OpenAI库未安装

**错误信息：**
```
openai库未安装，请运行: pip install openai
```

**解决方法：**
```bash
pip install openai
```

### 3. API调用超时

**错误信息：**
```
AI API调用超时（5分钟）
```

**解决方法：**
- 检查网络连接
- 检查API Key是否有效
- 考虑使用更快的模型（如`qwen-turbo`）

### 4. 工具函数调用失败

**错误信息：**
```
调用工具函数失败: ...
```

**解决方法：**
- 检查工具函数参数是否正确
- 查看日志获取详细错误信息
- 确保数据库连接正常

### 5. 操作执行失败

**错误信息：**
```
❌ 操作失败: ...
```

**解决方法：**
- 检查插件是否已启用
- 检查插件配置是否正确
- 查看任务执行日志

### 6. 流式响应中断

**可能原因：**
- 网络连接中断
- 服务器超时
- 客户端断开连接

**解决方法：**
- 检查网络稳定性
- 增加服务器超时时间
- 实现重连机制

---

## 最佳实践

### 1. 错误处理

始终使用try-except捕获异常：

```python
try:
    for chunk in agent.chat(user_message):
        yield chunk
except Exception as e:
    logger.error(f"智能体对话失败: {e}", exc_info=True)
    yield f"❌ 发生错误: {str(e)}\n"
```

### 2. 日志记录

记录关键操作：

```python
logger.info(f"用户 {user.username} 发送消息: {user_message[:100]}")
logger.info(f"AI响应长度: {len(response)}")
```

### 3. 性能优化

- 限制对话历史长度（保留最近10轮）
- 使用流式响应减少延迟
- 缓存AI配置避免重复查询

### 4. 安全考虑

- 验证用户权限
- 限制API调用频率
- 过滤敏感信息

---

## 相关文档

- [钉钉机器人集成文档](./dingtalk_stream_push_setup.md)
- [飞书机器人集成文档](./feishu_bot_setup.md)
- [任务管理API文档](../README.md)

---

## 更新日志

### 2026-01-10
- 初始版本
- 支持基本对话和操作执行
- 支持Function Calling
- 支持流式响应

---

## 联系方式

如有问题或建议，请联系开发团队。

