# HexStrike AI 集成说明

bifang 已集成 [HexStrike AI](https://github.com/0x4m4/hexstrike-ai)（官方仓库），可通过与 SecOps 智能体或钉钉机器人对资产进行安全评估（渗透测试、漏洞扫描等）。

## 官方能力参考

- **API 文档**: [HexStrike AI - API Reference](https://github.com/0x4m4/hexstrike-ai#api-reference)
- **核心接口**: `/health`、`/api/intelligence/analyze-target`、`/api/intelligence/select-tools`、`/api/command`
- **150+ 工具**: 网络扫描(nmap_scan, masscan_scan)、Web(nuclei_scan, gobuster_scan, ffuf_scan)、云(trivy_scan, kube_hunter_scan) 等，工具名与官方 MCP 一致

## 架构

- **bifang**：提供资产数据与对话入口，SecOps 智能体/钉钉在对话中调用 HexStrike 工具。
- **HexStrike Server**：独立进程，默认 `http://localhost:8888`，提供上述官方接口。

对话流程示例：

1. 用户：「对资产做一次安全评估」
2. 智能体调用 `list_assets` 获取资产列表（IP/域名/主机名）。
3. 智能体调用 `hexstrike_analyze_target(target)` 或 `hexstrike_run_scan(tool_name, arguments)` 请求 HexStrike 执行扫描。
4. HexStrike 返回结果，智能体整理后回复用户。

## 部署 HexStrike Server

### 方式一：Docker 部署（推荐，便于迁移）

使用 Docker 容器部署，便于后期整体系统迁移。详见 [HexStrike Docker 部署说明](./HEXSTRIKE_DOCKER.md)。

在 bifang 项目根目录执行：

```bash
docker-compose -f docker-compose.hexstrike.yml up -d --build
```

bifang 默认连接 `http://localhost:8888`，端口映射后即可使用。验证：`curl http://localhost:8888/health`。

### 方式二：使用 bifang 提供的脚本（本机安装）

在 bifang 项目根目录执行：

```bash
# 安装（克隆仓库、创建虚拟环境、安装 Python 依赖）
./scripts/install_hexstrike.sh

# 启动 HexStrike 服务（默认 8888 端口，日志在 logs/hexstrike.log）
./scripts/start_hexstrike.sh
```

停止服务：执行 `./stop.sh` 会同时停止 HexStrike（若由 start_hexstrike.sh 启动）。

### 方式三：手动安装

1. 克隆并安装依赖：

```bash
git clone https://github.com/0x4m4/hexstrike-ai.git
cd hexstrike-ai
python3 -m venv hexstrike-env
source hexstrike-env/bin/activate   # Windows: hexstrike-env\Scripts\activate
# 若遇 SSL 证书错误（常见于 macOS），可加：
pip3 install -r requirements.txt --trusted-host pypi.org --trusted-host files.pythonhosted.org
```

2. 按 HexStrike 文档安装所需安全工具（如 nmap、nuclei 等）。

3. 启动服务（默认 8888 端口）：

```bash
python3 hexstrike_server.py
# 或指定端口: python3 hexstrike_server.py --port 8888
```

4. 安装常用扫描工具（可选，用于 HexStrike 扫描能力）：

```bash
# 使用项目脚本（Homebrew）
./scripts/install_nmap_nuclei.sh

# 或手动安装
brew install nmap nuclei
# nuclei 首次使用建议更新模板
nuclei -update-templates
```

5. 验证：

```bash
curl http://localhost:8888/health
```

## bifang 配置

在 `bifang/settings.py` 或环境变量中配置：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `HEXSTRIKE_SERVER_URL` | HexStrike 服务地址 | `http://localhost:8888` |
| `HEXSTRIKE_ENABLED` | 是否启用 HexStrike 集成 | `true` |
| `HEXSTRIKE_TIMEOUT` | 请求超时（秒） | `300` |

环境变量示例：

```bash
export HEXSTRIKE_SERVER_URL=http://localhost:8888
export HEXSTRIKE_ENABLED=true
export HEXSTRIKE_TIMEOUT=300
```

## 官方 HexStrike API 与工具（bifang 已对接）

| 端点 | 方法 | 说明 | bifang 调用 |
|------|------|------|-------------|
| /health | GET | 健康检查与工具可用性 | hexstrike_status |
| /api/intelligence/analyze-target | POST | AI 目标分析 | analyze_target() |
| /api/intelligence/select-tools | POST | 智能工具选择 | select_tools()（可选） |
| /api/command | POST | 执行命令（带缓存） | run_command(tool_name, arguments) |

常用工具名（与 [官方 MCP](https://github.com/0x4m4/hexstrike-ai#common-mcp-tools) 一致）：

- **网络**: nmap_scan, rustscan_scan, masscan_scan, autorecon_scan, amass_enum
- **Web**: gobuster_scan, feroxbuster_scan, ffuf_scan, nuclei_scan, sqlmap_scan, wpscan_scan
- **云**: prowler_assess, scout_suite_audit, trivy_scan, kube_hunter_scan, kube_bench_check

验证 analyze-target（与官方示例一致）：

```bash
curl -X POST http://localhost:8888/api/intelligence/analyze-target \
  -H "Content-Type: application/json" \
  -d '{"target": "example.com", "analysis_type": "comprehensive"}'
```

## bifang 对外 API

- **SecOps 对话（流式）**  
  `POST /api/secops-agent/chat`  
  Body: `{"message": "对资产 xxx 做安全评估", "conversation_history": []}`  
  智能体会按需调用 `list_assets`、`hexstrike_analyze_target`、`hexstrike_run_scan`。

- **HexStrike 状态**  
  `GET /api/secops-agent/hexstrike_status/`  
  返回 `enabled`、`connected`、`message`、`server_url`，用于前端展示「资产安全评估」是否可用。

## 如何确认 bifang 是否调用了 HexStrike

发送「对我的云服务器资产 101.37.29.229 做一次全面的安全评估」等指令后，可用以下方式确认是否调用了 HexStrike AI：

1. **看对话回复（最直接）**  
   - 若调用了 HexStrike 且成功，对话中会出现：**「✅ 已对目标 101.37.29.229 完成安全分析」**，并附带 HexStrike 返回的分析结果。  
   - 若未调用或失败，会看到「HexStrike 集成未启用」或「HexStrike 分析失败，请确认 HexStrike 服务已启动」等提示。

2. **查 bifang 应用日志**  
   - 在运行 Django/Celery 的终端或日志文件中搜索：`HexStrike` 或 `analyze_target`。  
   - 若发生调用，会看到类似：  
     - `HexStrike: 调用 analyze_target, target=101.37.29.229, analysis_type=comprehensive`  
     - `HexStrike: analyze_target 成功, target=101.37.29.229`  
   - 若只看到 `HexStrike analyze_target failed`，说明请求已发出但 HexStrike 服务异常或不可达。

3. **查 HexStrike 服务端日志**  
   - 若 HexStrike 以 Docker 或本机进程运行，其日志中会有对 `/api/intelligence/analyze-target` 的 POST 请求记录，可据此确认 bifang 已把请求发到 HexStrike。

4. **确认配置与状态**  
   - 环境变量或 `settings` 中 `HEXSTRIKE_ENABLED=true`、`HEXSTRIKE_SERVER_URL` 正确。  
   - 前端或接口 `GET /api/secops-agent/hexstrike_status/` 返回 `enabled: true`、`connected: true` 表示集成已启用且服务可达。

## 使用说明

- 仅对**你拥有或已获授权**的资产进行评估；对话中智能体会提醒授权问题。
- HexStrike 未启动或不可达时，智能体会提示「请先启动 HexStrike 服务」并说明配置。
- 若 HexStrike 的 `/api/command` 请求体与当前实现不一致，可在 `app/services/hexstrike_client.py` 的 `run_command` 中调整 `payload` 格式以匹配其服务端。
- **Nmap/Nuclei 返回 400**：客户端已优先尝试 `POST /api/tools/<tool_name>`（请求体=arguments），若 404/400 再尝试 `POST /api/command` 的多种请求体格式。若仍 400，请查看官方 [hexstrike_server.py](https://github.com/0x4m4/hexstrike-ai/blob/master/hexstrike_server.py) 中 `/api/command` 或 `/api/tools` 的预期格式，或本地执行 `curl -s http://localhost:8888/health` 查看服务返回的接口说明。

## 参考

- [HexStrike AI 官方仓库](https://github.com/0x4m4/hexstrike-ai)
- [API Reference](https://github.com/0x4m4/hexstrike-ai#api-reference)
- [Common MCP Tools](https://github.com/0x4m4/hexstrike-ai#common-mcp-tools)
- [Installation & Verify](https://github.com/0x4m4/hexstrike-ai#verify-installation)
