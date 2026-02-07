# SecOps 智能体对话历史问题修复说明

**修复时间**：2026-02-06 20:24
**修复版本**：v1.2
**影响范围**：`_analyze_intent` 函数和意图识别逻辑

---

## 🐛 问题描述

用户报告：当有对话历史时，发送新的安全评估请求，智能体会回复之前的扫描结果，而不是执行新的扫描任务。

### 用户反馈

```
现在测试发送消息，智能体之前回复了之前的扫描结果，而并没有再次执行扫描任务。
```

### 复现场景

1. **场景1：重新扫描**
   - 用户第一次：对我的云服务器 101.37.29.229 做一次安全评估
   - 系统执行扫描，返回结果
   - 用户第二次：重新扫描 / 再扫描一次
   - 系统：立即回复之前的扫描结果，没有执行新扫描 ❌

2. **场景2：无目标的扫描请求**
   - 用户第一次：对 192.168.1.1 做安全评估
   - 系统执行扫描，返回结果
   - 用户第二次：再评估一次
   - 系统：使用AI回复，基于历史对话内容，没有执行新扫描 ❌

### 根本原因

1. **意图分析的局限性**
   - `_analyze_intent` 方法只分析当前 `user_message`
   - 当用户说"重新扫描"时，当前消息中没有 IP/域名
   - 意图分析无法提取目标，导致 `hexstrike_target` 为 None

2. **代码流程问题**
   ```python
   # Line 340: 如果没有提取到目标，不会执行 HexStrike
   if needs_hexstrike and hexstrike_target:
       # 执行扫描
   else:
       # 继续执行 AI 调用
   ```
   - 当 `hexstrike_target` 为 None 时，代码跳过 HexStrike 执行
   - 进入 AI 调用流程（line 407+）
   - AI 看到对话历史，基于历史内容生成回复
   - 结果：返回旧的扫描结果

---

## ✅ 修复方案

### 修复 1：增强 `_analyze_intent` 方法

**文件**：`app/services/secops_agent.py`
**位置**：第 646-738 行

#### 1.1 添加 `conversation_history` 参数

**修改前**：
```python
def _analyze_intent(self, user_message: str) -> Dict[str, Any]:
    """分析用户意图"""
    # 只分析当前消息
```

**修改后**：
```python
def _analyze_intent(self, user_message: str, conversation_history: List[Dict] = None) -> Dict[str, Any]:
    """
    分析用户意图

    Args:
        user_message: 用户消息
        conversation_history: 对话历史（用于上下文理解）
    """
    # 可以访问对话历史
```

#### 1.2 添加重新扫描关键词检测

**新增代码**（第 674-679 行）：
```python
# 重新扫描/再次扫描的关键词（从对话历史中提取目标）
rescan_keywords = ['重新扫描', '再扫描一次', '再次扫描', '再评估', '重新评估', '扫描这个', '再次评估']

has_rescan_keyword = any(kw in user_message for kw in rescan_keywords)
```

#### 1.3 从对话历史中提取目标

**新增逻辑**（第 690-719 行）：
```python
# 处理重新扫描的情况：从对话历史中提取之前扫描过的目标
if has_rescan_keyword and not ipv4_in_msg and not domain_in_msg:
    # 从对话历史中查找最近扫描过的目标
    if conversation_history:
        # 倒序查找最近的 IP/域名
        for msg in reversed(conversation_history):
            content = msg.get('content', '')
            # 查找 IPv4 地址
            ipv4_match = re.search(r'(?:\d{1,3}\.){3}\d{1,3}', content)
            if ipv4_match:
                intent['hexstrike_target'] = ipv4_match.group(0).strip()
                intent['needs_hexstrike_assessment'] = True
                logger.info(
                    "意图分析：从对话历史中提取到重新扫描目标，target=%s",
                    intent['hexstrike_target']
                )
                break
            # 查找域名
            domain_match = re.search(
                r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}',
                content
            )
            if domain_match:
                intent['hexstrike_target'] = domain_match.group(0).strip()
                intent['needs_hexstrike_assessment'] = True
                logger.info(
                    "意图分析：从对话历史中提取到重新扫描目标，target=%s",
                    intent['hexstrike_target']
                )
                break
```

### 修复 2：更新调用代码

**文件**：`app/services/secops_agent.py`
**位置**：第 326 行

**修改前**：
```python
intent_analysis = self._analyze_intent(user_message)
```

**修改后**：
```python
intent_analysis = self._analyze_intent(user_message, conversation_history)
```

---

## 📊 修复效果

### 修复前

**用户输入**：重新扫描

**系统行为**：
```
1. 意图分析：识别到"重新扫描"关键词 ✓
2. 目标提取：当前消息中无 IP/域名，hexstrike_target = None ❌
3. 条件判断：needs_hexstrike=True, hexstrike_target=None
4. 代码流程：跳过 HexStrike 执行，进入 AI 调用
5. AI 响应：基于对话历史，返回之前的扫描结果 ❌
```

### 修复后

**用户输入**：重新扫描

**系统行为**：
```
1. 意图分析：识别到"重新扫描"关键词 ✓
2. 目标提取：当前消息中无 IP/域名 ✓
3. 历史搜索：从对话历史中找到最近扫描的目标（如 101.37.29.229）✓
4. 条件判断：needs_hexstrike=True, hexstrike_target='101.37.29.229' ✓
5. 代码流程：执行 HexStrike 扫描 ✓
6. 返回结果：新的扫描结果 ✅
```

---

## 🧪 测试验证

### 测试场景 1：重新扫描

**步骤**：
1. 发送：对我的云服务器资产 101.37.29.229 做一次安全评估
2. 等待扫描完成
3. 发送：重新扫描

**预期结果**：
- ✅ 识别到"重新扫描"关键词
- ✅ 从对话历史中提取目标 101.37.29.229
- ✅ 执行新的扫描任务
- ✅ 返回新的扫描结果

### 测试场景 2：再评估一次

**步骤**：
1. 发送：对 example.com 做安全评估
2. 等待扫描完成
3. 发送：再评估一次

**预期结果**：
- ✅ 识别到"再评估"关键词
- ✅ 从对话历史中提取目标 example.com
- ✅ 执行新的扫描任务
- ✅ 返回新的扫描结果

### 测试场景 3：扫描这个（带指代）

**步骤**：
1. 发送：对 192.168.1.1 做安全评估
2. 等待扫描完成
3. 发送：扫描这个

**预期结果**：
- ✅ 识别到"扫描这个"关键词
- ✅ 从对话历史中提取目标 192.168.1.1
- ✅ 执行新的扫描任务
- ✅ 返回新的扫描结果

### 测试场景 4：正常扫描（不受影响）

**步骤**：
1. 发送：对我的云服务器资产 101.37.29.229 做一次安全评估

**预期结果**：
- ✅ 正常识别安全评估意图
- ✅ 从当前消息提取目标 101.37.29.229
- ✅ 执行扫描任务
- ✅ 返回扫描结果

---

## ⚠️ 注意事项

### 1. 对话历史的优先级

重新扫描时会：
- 倒序搜索对话历史（从最新的消息开始）
- 找到第一个包含 IP/域名的消息
- 使用该 IP/域名作为扫描目标

如果对话历史中有多个目标，会使用**最近扫描过的目标**。

### 2. 确保用户意图准确

如果用户说"重新扫描"但实际想扫描不同的目标，需要明确指定：

- ❌ "重新扫描" → 会扫描之前的目标
- ✅ "重新扫描 192.168.1.100" → 会扫描指定的目标

### 3. 日志记录

修复后会在日志中记录：
```
意图分析：从对话历史中提取到重新扫描目标，target=101.37.29.229
```

可通过以下命令查看日志：
```bash
tail -f logs/django.log | grep "意图分析"
```

---

## 📁 修改的文件

| 文件 | 修改位置 | 修改内容 |
|------|---------|---------|
| `app/services/secops_agent.py` | 第 646 行 | `_analyze_intent` 方法签名：添加 `conversation_history` 参数 |
| `app/services/secops_agent.py` | 第 674-719 行 | 添加重新扫描关键词检测和历史目标提取逻辑 |
| `app/services/secops_agent.py` | 第 326 行 | 调用 `_analyze_intent` 时传递 `conversation_history` |

---

## 🔄 相关文档

- [SecOps Agent 架构](../secops_agent_architecture.md)
- [意图识别机制](../intent_recognition.md)
- [HexStrike 扫描流程](hexstrike_scan_workflow.md)

---

## ✅ 修复确认

- [x] `_analyze_intent` 方法支持对话历史
- [x] 添加重新扫描关键词检测
- [x] 实现从历史中提取目标的逻辑
- [x] 更新调用代码传递对话历史
- [x] Django 服务已重启
- [x] 日志记录已添加

**状态**：✅ 已完成，等待用户验证

---

## 💡 下一步

请用户测试以下场景：

1. **重新扫描**
   - 发送：重新扫描
   - 验证：是否执行新的扫描任务

2. **再评估**
   - 发送：再评估一次
   - 验证：是否执行新的扫描任务

3. **扫描这个**
   - 发送：扫描这个
   - 验证：是否执行新的扫描任务

4. **指定目标重新扫描**
   - 发送：重新扫描 192.168.1.100
   - 验证：是否扫描指定的目标（而不是历史目标）

如果仍有问题，请提供：
- 完整的用户消息
- 完整的智能体回复
- Django 日志：`tail -f logs/django.log | grep "意图分析"`
