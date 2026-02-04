# Bifang 系统架构设计文档

## 1. 系统概述

Bifang 是一个基于 Django 和 Vue.js 的云端网络安全威胁感知系统，采用前后端分离架构，支持插件化数据采集、风险检测和告警功能。系统通过 Celery 实现异步任务处理，支持定时任务调度，并集成了钉钉、飞书等办公平台的智能体功能。

## 2. 技术栈

### 2.1 后端技术栈

- **框架**: Django 6.0
- **API**: Django REST Framework
- **任务队列**: Celery + Redis
- **数据库**: 
  - SQLite（默认，适合单机部署）
  - MySQL（可选，适合生产环境）
- **认证**: Session Authentication
- **CORS**: django-cors-headers

### 2.2 前端技术栈

- **框架**: Vue 3
- **路由**: Vue Router
- **状态管理**: Pinia
- **HTTP客户端**: Axios
- **构建工具**: Vue CLI
- **Web服务器**: Nginx（生产环境）

### 2.3 基础设施

- **容器化**: Docker + Docker Compose
- **消息队列**: Redis
- **AI集成**: HexStrike AI（资产安全评估）
- **办公平台集成**: 
  - 钉钉（Stream推送、智能体）
  - 飞书（长连接、智能体）

## 3. 系统架构

### 3.1 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        用户层                                │
│  Web浏览器 (Vue前端) / 钉钉客户端 / 飞书客户端                │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      前端服务层                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Nginx (端口8080)                                    │   │
│  │  - 静态文件服务 (Vue SPA)                            │   │
│  │  - API反向代理 (/api/* → backend:8000)              │   │
│  │  - Admin代理 (/admin/* → backend:8000)             │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      后端服务层                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Django Backend (端口8000)                          │   │
│  │  - REST API (DRF ViewSets)                          │   │
│  │  - Django Admin                                     │   │
│  │  - Session认证                                       │   │
│  └─────────────────────────────────────────────────────┘   │
│                            │                                │
│                            ▼                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Celery Worker                                      │   │
│  │  - 异步任务执行                                      │   │
│  │  - 插件执行引擎                                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                            │                                │
│                            ▼                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Celery Beat                                        │   │
│  │  - 定时任务调度                                      │   │
│  │  - Cron表达式解析                                    │   │
│  └─────────────────────────────────────────────────────┘   │
│                            │                                │
│                            ▼                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  钉钉 Stream Service                                │   │
│  │  - 事件推送接收                                      │   │
│  │  - 智能体交互                                        │   │
│  └─────────────────────────────────────────────────────┘   │
│                            │                                │
│                            ▼                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  飞书 Long Connection Service                        │   │
│  │  - 长连接事件接收                                    │   │
│  │  - 智能体交互                                        │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      数据存储层                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  数据库      │  │  Redis       │  │  文件存储     │     │
│  │  (SQLite/    │  │  (消息队列/  │  │  (日志/导出)  │     │
│  │   MySQL)     │  │  结果缓存)   │  │              │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      外部服务层                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  阿里云API    │  │  AWS API     │  │  HexStrike   │     │
│  │  (安全中心)   │  │  (Inspector) │  │  AI服务      │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│  ┌──────────────┐  ┌──────────────┐                        │
│  │  钉钉API     │  │  飞书API     │                        │
│  │  (Stream/    │  │  (长连接/    │                        │
│  │   智能体)    │  │   智能体)    │                        │
│  └──────────────┘  └──────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 服务组件说明

| 服务 | 端口 | 说明 |
|------|------|------|
| **frontend** | 8080 | Vue前端 + Nginx，提供静态文件服务和API代理 |
| **backend** | 8000 | Django API服务，提供REST API和Admin界面 |
| **redis** | 6379 | Redis服务，用于Celery消息队列和结果缓存 |
| **celery-worker** | - | Celery Worker，执行异步任务 |
| **celery-beat** | - | Celery Beat，定时任务调度器 |
| **dingtalk-stream** | - | 钉钉Stream推送服务，接收事件和智能体交互 |
| **hexstrike-ai** | 8888 | HexStrike AI服务，资产安全评估 |

## 4. 核心模块设计

### 4.1 插件系统

#### 4.1.1 插件基类

所有插件继承自 `BasePlugin`，位于 `app/lib/base_plugin.py`：

```python
class BasePlugin:
    """插件基类"""
    def execute(self, *args, **kwargs):
        """
        插件执行方法，子类必须实现
        返回格式: {'success': bool, 'message': str, 'data': dict}
        """
        raise NotImplementedError
```

#### 4.1.2 插件类型

| 类型 | 前缀 | 说明 | 示例 |
|------|------|------|------|
| **数据记录类** | `data_` | 将云端数据导入到数据库 | `data_aliyun_security.py` |
| **数据采集类** | `collect_` | 采集外部数据，支持导出JSON | `collect_cnvd_list.py` |
| **风险检测类** | `risk_` | 云端风险检测 | - |
| **数据导出类** | `dump_` | 导出数据为JSON/CSV | - |
| **告警类** | `alarm_` | 通过办公平台发送告警 | `alarm_aliyun_security_alerts.py` |

#### 4.1.3 插件加载机制

1. 插件文件位于 `app/plugins/` 目录
2. 通过 `python manage.py load_plugins` 命令扫描并注册到数据库
3. 任务执行时动态加载插件模块
4. 插件配置通过任务的 `config` 字段（JSON）传递

### 4.2 任务系统

#### 4.2.1 任务模型

- **Task**: 任务定义，包含插件关联、触发类型、配置等
- **TaskExecution**: 任务执行记录，记录每次执行的详细信息

#### 4.2.2 触发类型

| 类型 | 说明 | 配置字段 |
|------|------|----------|
| **manual** | 手动执行 | - |
| **cron** | 定时执行（Cron表达式） | `cron_expression` |
| **interval** | 间隔执行 | - |

#### 4.2.3 任务执行流程

```
用户触发/定时触发
    ↓
创建 TaskExecution 记录
    ↓
发送 Celery 任务到队列
    ↓
Celery Worker 接收任务
    ↓
动态加载插件模块
    ↓
调用插件 execute 方法
    ↓
更新 TaskExecution 状态和结果
    ↓
（可选）触发告警插件
```

### 4.3 数据模型

#### 4.3.1 核心模型

- **Plugin**: 插件元数据
- **Task**: 任务定义
- **TaskExecution**: 任务执行记录
- **Asset**: 资产数据（服务器、端口、进程等）
- **Vulnerability**: 漏洞信息（CVE、CNVD等）
- **SecurityAlert**: 安全告警（去重）
- **AliyunConfig**: 阿里云配置（包含钉钉、飞书、AI配置）
- **AWSConfig**: AWS配置

#### 4.3.2 数据关系

```
User
  ├── AliyunConfig (1:N)
  │   ├── Task (N:1, 可选)
  │   └── FeishuConfig (N:1, 关联AI配置)
  └── AWSConfig (1:N)
      └── Task (N:1, 可选)

Task (N:1) Plugin
Task (1:N) TaskExecution
Task (N:1) AliyunConfig (可选)
Task (N:1) AWSConfig (可选)

Asset (按 asset_type, uuid, source 唯一)
Vulnerability (按 cve_id, url 唯一)
SecurityAlert (按 alert_id 唯一)
```

### 4.4 API设计

#### 4.4.1 RESTful API

使用 Django REST Framework 的 ViewSet 模式：

- **PluginViewSet**: 插件查询（只读）
- **TaskViewSet**: 任务CRUD + 执行
- **TaskExecutionViewSet**: 执行记录查询（只读）
- **AssetViewSet**: 资产查询（只读）
- **VulnerabilityViewSet**: 漏洞查询（只读）
- **AliyunConfigViewSet**: 阿里云配置CRUD
- **AWSConfigViewSet**: AWS配置CRUD
- **SecOpsAgentViewSet**: SecOps智能体交互

#### 4.4.2 认证机制

- **Session Authentication**: 基于Django Session
- **CORS**: 支持跨域请求（开发环境）
- **CSRF**: 通过Session Cookie验证

#### 4.4.3 API路由

```
/api/auth/login/          POST   登录
/api/auth/logout/         POST   登出
/api/auth/user/           GET    当前用户信息
/api/tasks/sse/           GET    SSE实时任务状态
/api/dingtalk/bot/        POST   钉钉机器人回调
/api/feishu/bot/          POST   飞书机器人回调
/api/plugins/             GET    插件列表
/api/tasks/               CRUD   任务管理
/api/tasks/{id}/execute/  POST   执行任务
/api/task-executions/     GET    执行记录
/api/assets/              GET    资产列表
/api/vulnerabilities/     GET    漏洞列表
/api/aliyun-configs/      CRUD   阿里云配置
/api/aws-configs/         CRUD   AWS配置
/api/secops-agent/        POST   智能体交互
```

### 4.5 前端架构

#### 4.5.1 页面路由

- `/login`: 登录页
- `/`: 首页（统计概览）
- `/tasks`: 任务列表
- `/tasks/new`: 新建任务
- `/tasks/:id/edit`: 编辑任务
- `/plugins`: 插件列表
- `/assets/aliyun`: 阿里云资产
- `/assets/aws`: AWS资产
- `/vulnerabilities`: OSS安全漏洞
- `/vulnerabilities/cnvd`: CNVD漏洞
- `/system-config`: 系统配置
- `/aws-config`: AWS配置管理
- `/secops-agent`: SecOps智能体

#### 4.5.2 状态管理

使用 Pinia 管理全局状态：

- **auth**: 用户认证状态
- 其他状态通过组件本地管理

#### 4.5.3 API调用

- 统一通过 `src/api/` 目录封装
- 使用 Axios 实例，配置基础URL和拦截器
- 支持请求/响应拦截（错误处理、认证）

## 5. 集成功能

### 5.1 钉钉集成

#### 5.1.1 Stream推送

- **服务**: `dingtalk-stream` 容器
- **协议**: 钉钉Stream推送协议
- **功能**: 
  - 接收用户消息事件
  - 智能体交互（SecOps Agent）
  - 安全告警推送

#### 5.1.2 配置要求

- `dingtalk_client_id`: 钉钉应用Client ID
- `dingtalk_client_secret`: 钉钉应用Client Secret
- `dingtalk_use_stream_push`: 启用Stream推送

### 5.2 飞书集成

#### 5.2.1 长连接

- **服务**: 通过管理命令 `start_feishu_long_connection` 启动
- **协议**: 飞书长连接协议
- **功能**: 
  - 接收用户消息事件
  - 智能体交互
  - 安全告警推送

#### 5.2.2 配置要求

- `feishu_app_id`: 飞书应用App ID
- `feishu_app_secret`: 飞书应用App Secret
- `feishu_use_long_connection`: 启用长连接
- `qianwen_config`: 关联的AI配置（用于智能体）

### 5.3 HexStrike AI集成

#### 5.3.1 功能

- 资产安全评估
- 漏洞分析
- 智能体增强能力

#### 5.3.2 服务部署

- 独立容器 `hexstrike-ai`（端口8888）
- 通过 `HEXSTRIKE_SERVER_URL` 环境变量配置
- 健康检查: `http://localhost:8888/health`

### 5.4 通义千问AI集成

#### 5.4.1 功能

- 漏洞详情AI解析
- 智能体对话增强

#### 5.4.2 配置

- `qianwen_api_key`: 通义千问API Key
- `qianwen_api_base`: API地址（默认中国大陆地址）
- `qianwen_model`: 模型名称（qwen-plus/qwen-max等）

## 6. 数据流设计

### 6.1 数据采集流程

```
外部数据源（阿里云/AWS/CNVD等）
    ↓
数据采集插件（data_*/collect_*）
    ↓
数据清洗和转换
    ↓
存储到数据库（Asset/Vulnerability等）
    ↓
（可选）触发告警插件（alarm_*）
    ↓
推送到钉钉/飞书
```

### 6.2 任务执行流程

```
用户创建任务 / 定时触发
    ↓
创建 TaskExecution 记录（状态: running）
    ↓
发送 Celery 任务
    ↓
Celery Worker 接收
    ↓
加载插件模块
    ↓
执行插件 execute 方法
    ↓
更新 TaskExecution（状态: success/failed）
    ↓
更新 Task.last_run_time / next_run_time
```

### 6.3 智能体交互流程

```
用户发送消息（钉钉/飞书）
    ↓
Stream/长连接接收事件
    ↓
调用 SecOpsAgent 服务
    ↓
解析用户意图
    ↓
（可选）调用 HexStrike AI
    ↓
（可选）查询数据库
    ↓
生成回复消息
    ↓
发送到钉钉/飞书
```

## 7. 安全设计

### 7.1 认证与授权

- **Session认证**: 基于Django Session，支持跨域
- **权限控制**: 所有API需要认证（除登录接口）
- **CSRF保护**: 通过Session Cookie验证

### 7.2 数据安全

- **敏感信息**: AccessKey、Secret等存储在数据库，建议加密
- **配置隔离**: 每个用户可配置多个云配置，任务可选择使用
- **数据去重**: SecurityAlert通过 `unique_info` 去重

### 7.3 网络安全

- **CORS**: 限制允许的源（开发/生产环境）
- **HTTPS**: 生产环境建议使用HTTPS（SESSION_COOKIE_SECURE=True）

## 8. 部署架构

### 8.1 Docker Compose部署

所有服务通过Docker Compose统一管理：

- **数据持久化**: 使用Docker Volume（`bifang_data`, `bifang_logs`, `redis_data`）
- **服务依赖**: 通过 `depends_on` 和健康检查确保启动顺序
- **环境变量**: 通过环境变量配置（数据库、Redis、HexStrike等）

### 8.2 本地开发部署

- **后端**: `python manage.py runserver`
- **前端**: `npm run serve`（开发服务器）
- **Celery**: 分别启动Worker和Beat
- **数据库**: SQLite（默认）或MySQL

### 8.3 生产环境建议

- **Web服务器**: 使用Gunicorn + Nginx
- **数据库**: MySQL（多实例/高可用）
- **Redis**: Redis Cluster（高可用）
- **监控**: 集成监控系统（Prometheus/Grafana）
- **日志**: 集中日志管理（ELK/EFK）

## 9. 扩展性设计

### 9.1 插件扩展

- 新增插件只需在 `app/plugins/` 目录添加文件
- 运行 `load_plugins` 命令自动注册
- 无需修改核心代码

### 9.2 数据源扩展

- 支持新增云服务商（如Azure、GCP）
- 通过新增 `*Config` 模型和对应插件实现

### 9.3 告警渠道扩展

- 支持新增告警渠道（如企业微信、Slack）
- 通过新增告警插件实现

## 10. 性能优化

### 10.1 数据库优化

- **索引**: 关键字段建立索引（uuid、host_uuid、collected_at等）
- **分页**: API默认分页（20条/页）
- **查询优化**: 使用 `select_related` / `prefetch_related`

### 10.2 缓存策略

- **Redis**: Celery结果缓存、Session存储（可选）
- **前端缓存**: 静态资源缓存（Nginx配置）

### 10.3 异步处理

- **Celery**: 所有耗时操作异步执行
- **SSE**: 实时任务状态推送（Server-Sent Events）

## 11. 监控与运维

### 11.1 日志

- **日志位置**: `logs/bifang.log`
- **日志级别**: INFO（生产）、DEBUG（开发）
- **日志格式**: 包含时间、模块、级别、消息

### 11.2 健康检查

- **Redis**: `redis-cli ping`
- **HexStrike**: `http://localhost:8888/health`
- **Django**: 通过Admin或API接口

### 11.3 故障排查

- **任务卡住**: 使用 `diagnose_stuck_tasks` 命令诊断
- **插件加载失败**: 检查插件文件路径和语法
- **数据库连接**: 检查数据库配置和服务状态

## 12. 未来规划

### 12.1 功能增强

- [ ] 更多云服务商支持（Azure、GCP等）
- [ ] 更多告警渠道（企业微信、Slack等）
- [ ] 可视化大屏
- [ ] 报表导出功能

### 12.2 技术优化

- [ ] 微服务化拆分
- [ ] 消息队列升级（RabbitMQ/Kafka）
- [ ] 分布式任务调度
- [ ] 容器编排（Kubernetes）

---

**文档版本**: v1.0  
**最后更新**: 2026-02-04
