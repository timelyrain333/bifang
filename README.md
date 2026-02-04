# Bifang - 云端网络安全威胁感知系统

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-6.0-green.svg)](https://www.djangoproject.com/)
[![Vue](https://img.shields.io/badge/Vue-3.x-4FC08D.svg)](https://vuejs.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Bifang 是一个现代化的云端网络安全威胁感知系统，采用前后端分离架构，支持插件化数据采集、风险检测和智能告警。系统集成了钉钉、飞书等办公平台的智能体功能，提供便捷的安全运营体验。

## ✨ 核心特性

### 🔌 插件化架构
- **数据记录类插件** (`data_*`): 将云端数据导入数据库（阿里云安全中心、AWS Inspector等）
- **数据采集类插件** (`collect_*`): 采集外部数据源（CNVD、OSS安全等）
- **风险检测类插件** (`risk_*`): 云端风险检测与分析
- **数据导出类插件** (`dump_*`): 导出数据为JSON/CSV格式
- **告警类插件** (`alarm_*`): 通过钉钉、飞书等渠道发送安全告警

### 🚀 核心功能
- **多数据源支持**: 阿里云安全中心、AWS Inspector、CNVD、OSS安全等
- **智能任务调度**: 支持手动执行、Cron定时任务、间隔执行
- **实时任务监控**: SSE实时推送任务执行状态
- **资产统一管理**: 服务器、端口、进程、漏洞等资产统一视图
- **安全告警去重**: 智能去重，避免重复告警
- **智能体交互**: 集成钉钉/飞书智能体，支持自然语言查询

### 🤖 智能体功能
- **SecOps智能体**: 通过钉钉/飞书与系统交互，查询资产、漏洞、告警等信息
- **AI增强**: 集成通义千问AI，提供漏洞详情解析和智能对话
- **HexStrike集成**: 资产安全评估和风险分析

### 📊 数据管理
- **资产数据**: 服务器、账户、端口、进程、中间件、数据库等14种资产类型
- **漏洞情报**: CVE、CNVD漏洞信息采集和管理
- **安全告警**: 阿里云安全中心告警统一管理

## 🏗️ 系统架构

### 技术栈

**后端**
- Django 6.0 + Django REST Framework
- Celery + Redis（异步任务）
- SQLite（默认）/ MySQL（可选）

**前端**
- Vue 3 + Vue Router + Pinia
- Axios + Element Plus（UI组件）
- Nginx（生产环境）

**基础设施**
- Docker + Docker Compose
- Redis（消息队列）
- HexStrike AI（安全评估）

### 服务组件

| 服务 | 端口 | 说明 |
|------|------|------|
| frontend | 8080 | Vue前端 + Nginx |
| backend | 8000 | Django API服务 |
| redis | 6379 | Redis消息队列 |
| celery-worker | - | 异步任务执行 |
| celery-beat | - | 定时任务调度 |
| dingtalk-stream | - | 钉钉Stream推送 |
| hexstrike-ai | 8888 | HexStrike AI服务 |

详细架构设计请参考 [架构文档](docs/ARCHITECTURE.md)

## 📦 快速开始

### 方式一：Docker一键启动（推荐）

```bash
# 克隆项目
git clone <repository-url>
cd bifang

# 一键启动所有服务
docker compose up -d --build

# 创建管理员账号
docker compose exec backend python manage.py createsuperuser
```

访问地址：
- **前端**: http://localhost:8080
- **后端API**: http://localhost:8000/api/
- **Admin**: http://localhost:8000/admin/

### 方式二：本地开发部署

详细步骤请参考 [快速开始指南](QUICKSTART.md)

## 📚 文档目录

- [架构设计文档](docs/ARCHITECTURE.md) - 系统架构、模块设计、数据流等
- [快速开始指南](QUICKSTART.md) - 本地开发环境搭建
- [Docker部署文档](docs/DOCKER_DEPLOY.md) - Docker Compose部署说明
- [项目结构说明](PROJECT_STRUCTURE.md) - 代码组织结构
- [钉钉机器人设置](DINGTALK_BOT_SETUP.md) - 钉钉智能体配置
- [飞书机器人设置](docs/feishu_bot_setup.md) - 飞书智能体配置
- [SecOps智能体实现](SECOPS_AGENT_IMPLEMENTATION.md) - 智能体功能说明

## 🔧 插件系统

### 已实现插件

**数据记录类**
- `data_aliyun_security.py` - 阿里云安全中心资产导入
- `data_aws_inspector.py` - AWS Inspector资产导入

**数据采集类**
- `collect_cnvd_list.py` - CNVD漏洞采集
- `collect_oss_security.py` - OSS安全漏洞采集

**告警类**
- `alarm_aliyun_security_alerts.py` - 阿里云安全告警推送

### 开发新插件

所有插件继承 `BasePlugin` 基类：

```python
from app.lib.base_plugin import BasePlugin

class MyPlugin(BasePlugin):
    def execute(self, *args, **kwargs):
        # 插件逻辑
        return {
            'success': True,
            'message': '执行成功',
            'data': {}
        }
```

插件开发完成后，运行 `python manage.py load_plugins` 自动注册。

## 🎯 使用指南

### 创建第一个任务

1. **配置云服务凭证**
   - 进入"系统配置" → "阿里云配置"（或"AWS配置"）
   - 添加AccessKey等凭证信息

2. **创建任务**
   - 进入"任务管理" → "新建任务"
   - 选择插件（如：`data_aliyun_security`）
   - 选择触发类型（手动/定时）
   - 配置任务参数（JSON格式）

3. **执行任务**
   - 手动执行：点击"执行"按钮
   - 定时执行：配置Cron表达式后自动执行

4. **查看结果**
   - 任务执行历史：任务列表 → "历史"
   - 资产数据：进入"资产数据"页面
   - 漏洞情报：进入"漏洞情报"页面

### Cron表达式

格式: `分钟 小时 日 月 周`

示例:
- `0 0 * * *` - 每天0点执行
- `0 */6 * * *` - 每6小时执行一次
- `0 0 * * 1` - 每周一0点执行
- `0 0 1 * *` - 每月1号0点执行

## 🔌 API接口

### 认证
- `POST /api/auth/login/` - 用户登录
- `POST /api/auth/logout/` - 用户登出
- `GET /api/auth/user/` - 获取当前用户信息

### 任务管理
- `GET /api/tasks/` - 任务列表
- `POST /api/tasks/` - 创建任务
- `GET /api/tasks/{id}/` - 任务详情
- `PUT /api/tasks/{id}/` - 更新任务
- `DELETE /api/tasks/{id}/` - 删除任务
- `POST /api/tasks/{id}/execute/` - 执行任务
- `GET /api/task-executions/` - 执行记录列表

### 数据查询
- `GET /api/assets/` - 资产列表
- `GET /api/vulnerabilities/` - 漏洞列表
- `GET /api/plugins/` - 插件列表

### 配置管理
- `GET /api/aliyun-configs/` - 阿里云配置列表
- `POST /api/aliyun-configs/` - 创建阿里云配置
- `GET /api/aws-configs/` - AWS配置列表
- `POST /api/aws-configs/` - 创建AWS配置

### 智能体
- `POST /api/secops-agent/` - SecOps智能体交互
- `POST /api/dingtalk/bot/` - 钉钉机器人回调
- `POST /api/feishu/bot/` - 飞书机器人回调

## 🛠️ 开发指南

### 环境要求

- Python 3.11+
- Node.js 16+
- MySQL 5.7+（可选，默认使用SQLite）
- Redis 6.0+

### 本地开发

```bash
# 1. 安装Python依赖
pip install -r requirements.txt

# 2. 配置数据库（可选，默认SQLite）
export DB_ENGINE=mysql
export DB_NAME=bifang
export DB_USER=root
export DB_PASSWORD=your_password

# 3. 初始化数据库
python manage.py migrate
python manage.py createsuperuser
python manage.py load_plugins

# 4. 启动Redis
redis-server

# 5. 启动服务（需要3个终端）
# 终端1: Django
python manage.py runserver

# 终端2: Celery Worker
celery -A app.celery_app worker -l info

# 终端3: Celery Beat
celery -A app.celery_app beat -l info

# 6. 启动前端
cd frontend
npm install
npm run serve
```

### 插件开发

参考 [插件开发文档](docs/ai_agent_development.md) 和现有插件实现。

## 📋 项目结构

```
bifang/
├── app/                    # Django应用
│   ├── lib/               # 基础库（插件基类、数据库助手等）
│   ├── plugins/           # 插件目录
│   ├── services/          # 服务层（智能体、钉钉/飞书集成等）
│   ├── management/        # Django管理命令
│   ├── models.py          # 数据模型
│   ├── views.py           # API视图
│   └── tasks.py           # Celery任务
├── frontend/              # Vue前端
│   ├── src/
│   │   ├── views/        # 页面组件
│   │   ├── api/          # API封装
│   │   └── router/       # 路由配置
│   └── package.json
├── bifang/                # Django项目配置
├── docker/                # Docker相关文件
├── docs/                  # 文档目录
├── docker-compose.yml     # Docker Compose配置
├── Dockerfile             # 后端镜像
├── Dockerfile.frontend    # 前端镜像
└── requirements.txt       # Python依赖
```

详细结构说明请参考 [项目结构文档](PROJECT_STRUCTURE.md)

## 🔒 安全建议

1. **生产环境配置**
   - 使用MySQL替代SQLite
   - 启用HTTPS（`SESSION_COOKIE_SECURE=True`）
   - 配置 `ALLOWED_HOSTS`
   - 使用强密码和密钥管理

2. **敏感信息**
   - AccessKey等凭证存储在数据库中，建议加密
   - 使用环境变量管理配置
   - 定期轮换AccessKey

3. **网络安全**
   - 限制CORS允许的源
   - 配置防火墙规则
   - 使用VPN或内网访问

## 🐛 故障排查

常见问题请参考：
- [Docker部署故障排查](docs/DOCKER_DEPLOY.md#故障排查)
- [任务卡住问题](docs/TROUBLESHOOTING_STUCK_TASKS.md)
- [飞书长连接问题](docs/feishu_long_connection_troubleshooting.md)

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

## 📄 许可证

MIT License

## 🔗 相关链接

- [架构设计文档](docs/ARCHITECTURE.md)
- [快速开始指南](QUICKSTART.md)
- [Docker部署文档](docs/DOCKER_DEPLOY.md)
- [钉钉机器人设置](DINGTALK_BOT_SETUP.md)
- [飞书机器人设置](docs/feishu_bot_setup.md)




