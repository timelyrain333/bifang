# 钉钉流式AI卡片配置指南

本文档介绍如何为Bifang系统的钉钉机器人配置流式AI卡片回复功能（打字机效果）。

## 目录
1. [功能概述](#功能概述)
2. [前置条件](#前置条件)
3. [步骤一：在钉钉开发者后台创建AI卡片模板](#步骤一在钉钉开发者后台创建ai卡片模板)
4. [步骤二：运行数据库迁移](#步骤二运行数据库迁移)
5. [步骤三：在系统配置中启用流式AI卡片](#步骤三在系统配置中启用流式ai卡片)
6. [步骤四：测试流式回复功能](#步骤四测试流式回复功能)
7. [故障排查](#故障排查)

## 功能概述

流式AI卡片功能可以让钉钉机器人的回复呈现"打字机效果"，即：
- 文本内容逐字显示，而不是一次性全部显示
- 更符合AI对话的交互体验
- 支持Markdown格式的富文本显示

## 前置条件

在开始配置之前，请确保：
1. 已有钉钉企业内部应用机器人（已配置Client ID和Client Secret）
2. 已启用钉钉Stream推送模式
3. 已配置通义千问AI（用于智能对话）

## 步骤一：在钉钉开发者后台创建AI卡片模板

### 1.1 登录钉钉开放平台

访问 [钉钉开放平台](https://open.dingtalk.com/) 并使用钉钉账号登录。

### 1.2 进入应用管理

1. 点击顶部导航栏的"应用开发"
2. 选择你的企业内部应用（机器人应用）
3. 进入应用详情页

### 1.3 创建卡片模板

1. 在左侧菜单中找到"卡片模板"或"互动卡片"
2. 点击"创建模板"按钮
3. 选择"AI卡片"类型
4. 填写模板信息：
   - **模板名称**：例如 "SecOps智能体回复"
   - **模板描述**：例如 "用于SecOps智能体的流式回复卡片"
   - **模板类型**：选择 "AI卡片"

### 1.4 设计卡片结构

创建一个简单的Markdown内容卡片。以下是推荐的卡片JSON配置：

```json
{
  "config": {
    "autoLayout": true,
    "enableForward": true
  },
  "header": {
    "title": {
      "type": "text",
      "text": "SecOps智能体"
    },
    "logo": "@lALPDfJ6V_FPDmvNAfTNAfQ"
  },
  "contents": [
    {
      "type": "markdown",
      "text": "${content}",
      "id": "content_markdown"
    }
  ]
}
```

**卡片设计说明**：
- `header.title`：卡片标题，显示为"SecOps智能体"
- `contents[0].type`：使用 "markdown" 类型支持富文本
- `${content}`：这是占位符，系统会自动替换为实际的AI回复内容
- `logo`：可以自定义卡片头部图标

### 1.5 配置卡片属性

在卡片编辑器中：
1. **基础配置**：
   - 卡片宽度：建议选择 "自适应"
   - 卡片高度：选择 "自适应"

2. **交互配置**：
   - 启用"卡片转发"（可选）
   - 禁用其他交互按钮（保持简洁）

3. **样式配置**：
   - 背景色：使用默认或自定义
   - 字体：使用默认

### 1.6 发布卡片模板

1. 点击"保存"按钮保存模板
2. 点击"发布"按钮发布模板
3. 发布后，会显示一个**卡片模板ID**，格式类似：`dingtalk_card_xxxxx`
4. **复制这个模板ID**，后面需要填写到系统配置中

**重要**：记下这个模板ID，它是配置流式回复的关键！

### 1.7 配置卡片权限（如果需要）

某些卡片功能可能需要额外的权限：
1. 进入"权限管理"
2. 确保"机器人"相关权限已开通：
   - `robot:send:interactive_card`（发送互动卡片）
   - `robot:update:interactive_card`（更新互动卡片）

## 步骤二：运行数据库迁移

在Bifang系统服务器上执行数据库迁移，添加新的配置字段：

```bash
# 进入项目目录
cd /Users/denggushizhangda/PycharmProjects/bifang

# 运行迁移
python manage.py migrate
```

执行成功后，会在`aliyun_configs`表中添加两个新字段：
- `dingtalk_ai_card_template_id`：存储卡片模板ID
- `dingtalk_enable_stream_card`：是否启用流式AI卡片

## 步骤三：在系统配置中启用流式AI卡片

### 3.1 通过Django Admin配置

1. 访问系统管理后台：`http://your-server:8000/admin/`
2. 登录管理员账号
3. 进入"系统配置"（AliyunConfig）管理页面
4. 找到你的钉钉配置项，点击编辑

### 3.2 填写卡片配置

在配置页面中，填写以下字段：

1. **钉钉AI卡片模板ID**：
   - 粘贴你在步骤一中复制的卡片模板ID
   - 例如：`dingtalk_card_123456789`

2. **启用流式AI卡片**：
   - 勾选此选项以启用打字机效果

3. **确认其他配置**：
   - 钉钉Client ID：已填写
   - 钉钉Client Secret：已填写
   - 使用流式推送：已勾选
   - 通义千问API Key：已填写
   - 通义千问模型：已选择（如 `qwen-plus`）

### 3.3 保存配置

点击"保存"按钮保存配置。

## 步骤四：测试流式回复功能

### 4.1 重启钉钉Stream服务

如果钉钉Stream服务正在运行，需要重启以加载新配置：

```bash
# 停止现有服务
python manage.py stop_dingtalk_stream

# 或使用Docker
docker compose restart celery-worker
```

### 4.2 启动服务

```bash
# 方式1：使用管理命令启动
python manage.py start_dingtalk_stream

# 方式2：使用Docker启动
docker compose up -d celery-worker
```

### 4.3 测试流式回复

1. 在钉钉群聊中@机器人，发送一条消息
2. 观察：
   - 是否出现一个卡片（而不是普通文本消息）
   - 卡片内容是否逐字显示（打字机效果）
   - 内容是否完整显示

**测试消息示例**：
```
@SecOps智能体 帮我查看一下最新的漏洞信息
```

### 4.4 验证日志

如果遇到问题，查看系统日志：

```bash
# 查看Django日志
tail -f bifang.log

# 查看钉钉Stream调试日志
tail -f logs/dingtalk_hexstrike_debug.log
```

查找关键日志：
- `使用流式AI卡片回复: template_id=xxx`
- `发送AI卡片响应: {...}`
- `更新AI卡片成功`

## 故障排查

### 问题1：卡片没有显示

**可能原因**：
- 卡片模板ID填写错误
- 卡片模板未发布
- 机器人没有发送卡片权限

**解决方法**：
1. 检查卡片模板ID是否正确
2. 确认卡片模板已发布（不是草稿状态）
3. 检查应用权限是否已开通

### 问题2：没有打字机效果

**可能原因**：
- "启用流式AI卡片"选项未勾选
- 卡片模板配置不正确
- 服务未重启

**解决方法**：
1. 确认配置中已勾选"启用流式AI卡片"
2. 检查卡片模板是否包含正确的占位符（`${content}`）
3. 重启Stream服务

### 问题3：显示"思考中..."但没有内容更新

**可能原因**：
- AI服务异常
- 网络问题
- Token刷新失败

**解决方法**：
1. 检查通义千问API Key是否有效
2. 查看日志中的错误信息
3. 检查网络连接

### 问题4：回退到普通文本回复

**可能原因**：
- 流式卡片发送失败，系统自动回退
- `open_conversation_id` 未获取到

**解决方法**：
1. 查看日志中的错误信息
2. 确认机器人在群聊中（不是单聊）
3. 检查群聊ID是否正确传递

### 问题5：AccessToken获取失败

**可能原因**：
- Client ID或Client Secret错误
- 应用被禁用

**解决方法**：
1. 检查Client ID和Secret是否正确
2. 确认应用状态为"已启用"
3. 重新生成Client Secret

## 高级配置

### 自定义卡片样式

你可以自定义卡片的外观，修改JSON配置：

```json
{
  "config": {
    "autoLayout": true,
    "enableForward": true
  },
  "header": {
    "title": {
      "type": "text",
      "text": "我的自定义标题"
    },
    "logo": "自定义logo地址",
    "iconColor": "#FF0000"
  },
  "contents": [
    {
      "type": "markdown",
      "text": "${content}",
      "id": "content_markdown",
      "style": {
        "fontSize": "14px",
        "color": "#333333"
      }
    }
  ]
}
```

### 调整打字机速度

在代码中修改 `update_interval` 参数：

```python
# 文件：app/services/dingtalk_stream_service.py
# 第555行左右
update_interval=0.05  # 修改此值，单位：秒
```

- `0.05` = 50ms（快速）
- `0.1` = 100ms（中速，默认）
- `0.2` = 200ms（慢速）

### 添加卡片交互按钮

在卡片模板中添加按钮组件：

```json
{
  "contents": [
    {
      "type": "markdown",
      "text": "${content}",
      "id": "content_markdown"
    },
    {
      "type": "action",
      "actions": [
        {
          "id": "btn_copy",
          "type": "button",
          "text": "复制内容",
          "style": "primary"
        },
        {
          "id": "btn_regenerate",
          "type": "button",
          "text": "重新生成",
          "style": "default"
        }
      ]
    }
  ]
}
```

## API参考

### 发送AI卡片

```python
from app.services.dingtalk_ai_card import DingTalkAICardStreamer

streamer = DingTalkAICardStreamer(
    client_id="your_client_id",
    client_secret="your_client_secret"
)

result = streamer.send_ai_card(
    card_template_id="dingtalk_card_xxx",
    open_conversation_id="群会话ID",
    card_data={"content": {"text": "初始内容"}},
    conversation_type="2"  # 1=单聊, 2=群聊
)
```

### 更新AI卡片

```python
streamer.update_ai_card(
    card_biz_id="卡片业务ID",
    card_data={"content": {"text": "更新的内容"}},
    process_query_key="进程查询键"
)
```

### 流式回复

```python
def text_stream():
    yield "Hello"
    yield " World"
    yield "!"

streamer.stream_reply(
    card_template_id="模板ID",
    open_conversation_id="群会话ID",
    text_stream=text_stream(),
    update_interval=0.1
)
```

## 参考文档

- [钉钉AI卡片流式更新API](https://open.dingtalk.com/document/development/api-streamingupdate)
- [打字机效果流式AI卡片](https://open.dingtalk.com/document/dingstart/typewriter-effect-streaming-ai-card)
- [AI卡片模板](https://open.dingtalk.com/document/development/ai-card-template)
- [创建并投放卡片](https://open.dingtalk.com/document/development/create-and-deliver-cards)

## 支持

如有问题，请查看：
1. 系统日志：`logs/dingtalk_hexstrike_debug.log`
2. Django日志：`bifang.log`
3. GitHub Issues：[提交问题](https://github.com/your-repo/issues)
