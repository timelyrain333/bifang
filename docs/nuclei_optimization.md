# Nuclei 扫描超时优化方案

## 问题摘要

**现状：**
- 超时配置：300 秒（5 分钟）
- Nuclei 实际扫描时间：~10 分钟
- 结果：扫描被中断，用户看到超时错误

**原因：**
Nuclei 默认扫描所有 4000+ 个模板，导致时间过长

---

## 方案对比

| 方案 | 时间 | 效果 | 难度 | 推荐度 |
|------|------|------|------|--------|
| 方案1: 增加超时 | 5分钟 | ⭐⭐ | 简单 | ⭐⭐⭐ |
| 方案2: 参数优化 | 15分钟 | ⭐⭐⭐⭐ | 中等 | ⭐⭐⭐⭐⭐ |
| 方案3: 分阶段扫描 | 30分钟 | ⭐⭐⭐⭐⭐ | 复杂 | ⭐⭐⭐⭐ |

---

## 方案 1：快速修复 - 增加超时时间

### 修改位置

1. **bifang/settings.py** - 添加配置
```python
# HexStrike AI 超时配置（秒）
HEXSTRIKE_TIMEOUT = 600  # 10 分钟
```

2. **或直接修改代码** app/services/hexstrike_client.py
```python
def __init__(self, base_url: str, timeout: int = 600):  # 从 300 改为 600
```

### 优缺点
✅ 优点：快速解决
❌ 缺点：用户仍需等待 10 分钟

---

## 方案 2：参数优化 - 限制扫描范围 ⭐推荐

### 2.1 修改 Nuclei 调用参数

在调用 Nuclei 时添加优化参数：

```python
# app/services/secops_agent.py 中的 hexstrike_run_scan 函数

# 原代码
result = client.run_command(tool_name, arguments)

# 优化后：为 nuclei 添加默认参数
if tool_name == 'nuclei_scan' or tool_name == 'nuclei':
    # 如果用户没有指定严重级别，默认只扫描高危和严重漏洞
    if 'severity' not in arguments:
        arguments['severity'] = 'critical,high'

    # 限制并发和速率，加快扫描
    if 'rl' not in arguments:
        arguments['rl'] = 50  # 每秒请求数

    if 'c' not in arguments:
        arguments['c'] = 10  # 并发模板数

    # 减少超时和重试
    if 'timeout' not in arguments:
        arguments['timeout'] = 10  # 单个请求超时

    if 'retries' not in arguments:
        arguments['retries'] = 1  # 减少重试

result = client.run_command(tool_name, arguments)
```

### 2.2 针对已知端口扫描（更快）

```python
# 先用 nmap 快速扫描端口
# 然后针对发现的端口进行 nuclei 扫描

# 示例：只扫描 Elasticsearch 端口
if tool_name == 'nuclei_scan':
    # 如果没有指定 target，从 nmap 结果中提取端口
    if 'target' in arguments and not arguments['target'].startswith(('http://', 'https://')):
        # 只扫描发现的端口：22, 80, 443, 9200
        arguments['target'] = [
            f"http://{arguments['target']}:80",
            f"https://{arguments['target']}:443",
            f"http://{arguments['target']}:9200",  # Elasticsearch
        ]
```

### 2.3 修改 AI 提示词

在 secops_agent.py 中修改 AI 的工具描述，引导其使用优化的参数：

```python
# 修改 hexstrike_run_scan 工具的描述
{
    "name": "hexstrike_run_scan",
    "description": """使用 HexStrike AI 执行安全扫描工具。

重要：对于 nuclei_scan，建议使用以下优化参数以避免超时：
- 针对 Elasticsearch 扫描：nuclei_scan, {"target": "http://IP:9200", "severity": "critical,high", "rl": 20}
- 快速漏洞扫描：nuclei_scan, {"target": "IP", "severity": "critical", "rl": 20, "c": 5}
- 标准 Web 扫描：nuclei_scan, {"target": "http://IP", "tags": "cve,rce,sqli", "severity": "critical,high"}

可用工具：
- 网络: nmap_scan, masscan_scan
- Web: nuclei_scan, gobuster_scan, ffuf_scan, sqlmap_scan
- 云: trivy_scan, kube_hunter_scan
""",
    ...
}
```

### 效果预估
- **时间：** 从 10 分钟降低到 **2-3 分钟**
- **覆盖范围：** 优先扫描高危和严重漏洞
- **用户体验：** 显著提升

---

## 方案 3：智能分阶段扫描（未来优化）

### 3.1 快速评估阶段（1-2分钟）

```python
# 只扫描关键端口和严重漏洞
{
    "nmap": "快速 Top 100 端口扫描",
    "nuclei": {"severity": "critical", "rl": 30}
}
```

### 3.2 深度扫描阶段（3-5分钟）

```python
# 完整端口扫描 + 高危漏洞
{
    "nmap": "全端口扫描",
    "nuclei": {"severity": "critical,high", "rl": 50}
}
```

### 3.3 完整扫描阶段（8-10分钟）

```python
# 全面扫描所有漏洞
{
    "nmap": "服务版本检测",
    "nuclei": {"severity": "all", "tags": "cve"}
}
```

---

## 实施建议

### 立即执行（方案1）
```bash
# 修改 bifang/settings.py
echo "HEXSTRIKE_TIMEOUT = 600" >> bifang/settings.py
```

### 今天执行（方案2）
1. 修改 secops_agent.py 添加默认参数
2. 优化 AI 提示词
3. 测试验证

### 下一步（方案3）
设计多阶段扫描架构

---

## 测试验证

### 测试命令
```python
# 在 Django shell 中测试
python manage.py shell

from app.services.hexstrike_client import HexStrikeClient

client = HexStrikeClient('http://localhost:8888', timeout=600)

# 测试优化后的参数
result = client.run_command('nuclei', {
    'target': '101.37.29.229',
    'severity': 'critical,high',
    'rl': 50,
    'c': 10,
    'timeout': 10,
    'retries': 1
})

print(f"Success: {result.get('success')}")
print(f"Execution time: {result['data'].get('execution_time')}")
```

---

## 预期效果

| 指标 | 优化前 | 优化后 | 改善 |
|------|--------|--------|------|
| 扫描时间 | 10分钟+ | 2-3分钟 | 70%↓ |
| 超时率 | 100% | <5% | 95%↓ |
| 漏洞覆盖率 | 100% | 80% | 可接受 |
| 用户体验 | 差 | 好 | ⬆️⬆️⬆️ |