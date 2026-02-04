# 快速开始指南

本指南提供两种部署方式：**Docker一键启动**（推荐）和**本地开发部署**。

## 方式一：Docker 一键启动（推荐）

无需安装 Python/Node/Redis，所有服务通过 Docker 运行：

```bash
# 克隆项目（如果还没有）
git clone <repository-url>
cd bifang

# 一键启动所有服务
docker compose up -d --build

# 创建管理员账号
docker compose exec backend python manage.py createsuperuser
```

**访问地址**：
- **前端**: http://localhost:8080
- **后端API**: http://localhost:8000/api/
- **Admin**: http://localhost:8000/admin/

**详细说明**: 请参考 [Docker部署文档](docs/DOCKER_DEPLOY.md)

---

## 方式二：本地开发部署

### 前置要求

- **Python**: 3.11+（推荐3.11或更高版本）
- **Node.js**: 16+（推荐18+）
- **数据库**: 
  - SQLite（默认，无需安装）
  - MySQL 5.7+（可选，生产环境推荐）
- **Redis**: 6.0+（用于Celery消息队列）

## 快速部署步骤

### 1. 安装Python依赖

```bash
pip install -r requirements.txt
```

### 2. 配置数据库

系统默认使用SQLite，无需额外配置。如需使用MySQL，请设置环境变量：

```bash
# 使用MySQL（可选）
export DB_ENGINE=mysql
export DB_NAME=bifang
export DB_USER=root
export DB_PASSWORD=your_password
export DB_HOST=localhost
export DB_PORT=3306
```

如果使用MySQL，需要先创建数据库：

```sql
CREATE DATABASE bifang CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

**注意**: 默认使用SQLite（`db.sqlite3`），适合开发和单机部署。生产环境建议使用MySQL。

### 3. 初始化数据库

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py load_plugins
```

### 4. 启动Redis

```bash
# macOS
brew services start redis

# Linux
systemctl start redis
# 或
redis-server
```

### 5. 启动后端服务

```bash
# 终端1: Django服务
python manage.py runserver

# 终端2: Celery Worker
celery -A app.celery_app worker -l info

# 终端3: Celery Beat（定时任务）
celery -A app.celery_app beat -l info
```

### 6. 启动前端服务

```bash
cd frontend
npm install
npm run serve
```

### 7. 访问系统

- 前端地址: http://localhost:8080
- 后端API: http://localhost:8000/api/
- Django Admin: http://localhost:8000/admin/

## 创建第一个任务

### 1. 获取阿里云AccessKey

1. 登录阿里云控制台
2. 进入 AccessKey 管理页面
3. 创建新的 AccessKey 并保存 ID 和 Secret

### 2. 配置云服务凭证（推荐方式）

**方式一：通过系统配置管理（推荐）**

1. 访问 http://localhost:8080
2. 登录系统（使用创建的superuser账号）
3. 进入"系统配置" → "阿里云配置"（或"AWS配置"）
4. 点击"新建配置"，填写：
   - 配置名称（如：生产环境）
   - AccessKey ID 和 Secret
   - 地域ID（如：cn-hangzhou）
   - 其他配置项
5. 保存配置

**方式二：在任务配置中直接填写**

在创建任务时，直接在任务配置JSON中填写AccessKey等信息。

### 3. 创建任务

1. 进入"任务管理"页面
2. 点击"新建任务"
3. 填写任务信息：
   - **任务名称**: 阿里云安全中心数据导入
   - **关联插件**: data_aliyun_security
   - **触发类型**: 选择"定时执行"
   - **Cron表达式**: `0 0 * * *` (每天0点执行)
   - **关联配置**: 如果已创建系统配置，可选择使用；否则在任务配置中填写
   - **任务配置**（如果未使用系统配置）:
   ```json
   {
     "access_key_id": "你的AccessKey ID",
     "access_key_secret": "你的AccessKey Secret",
     "region_id": "cn-hangzhou",
     "asset_types": ["server", "account", "port", "process"],
     "page_size": 100
   }
   ```
4. 点击"保存"

### 4. 执行任务

- **手动执行**: 在任务列表页面点击"执行"按钮
- **自动执行**: 定时任务会在设定时间自动执行（需要Celery Beat运行）

### 5. 查看结果

- **执行历史**: 点击任务列表的"历史"按钮，查看执行记录和日志
- **资产数据**: 进入"资产数据"页面，按来源筛选查看导入的数据
- **漏洞情报**: 进入"漏洞情报"页面，查看采集的CVE/CNVD漏洞信息

## 常见问题

### Q: 数据库连接失败

**A**: 检查MySQL服务是否启动，数据库配置是否正确

```bash
# 检查MySQL服务
# macOS
brew services list | grep mysql

# Linux
systemctl status mysql
```

### Q: Celery Worker无法启动

**A**: 检查Redis服务是否启动

```bash
# 检查Redis服务
redis-cli ping
# 应该返回 PONG
```

### Q: 插件加载失败

**A**: 运行以下命令重新加载插件

```bash
python manage.py load_plugins
```

### Q: 前端页面无法访问后端API

**A**: 检查 `frontend/vue.config.js` 中的代理配置是否正确

### Q: 任务执行失败

**A**: 检查以下几点：
1. 插件配置中的AccessKey是否正确
2. AccessKey是否有相应权限
3. 查看任务执行历史中的错误信息
4. 查看日志文件: `logs/bifang.log`

## 生产环境部署

### 使用Gunicorn

```bash
pip install gunicorn
gunicorn bifang.wsgi:application --bind 0.0.0.0:8000
```

### 使用Supervisor管理进程

创建 `/etc/supervisor/conf.d/bifang.conf`:

```ini
[program:bifang_django]
command=/path/to/venv/bin/gunicorn bifang.wsgi:application --bind 0.0.0.0:8000
directory=/path/to/bifang
user=www-data
autostart=true
autorestart=true

[program:bifang_celery]
command=/path/to/venv/bin/celery -A app.celery_app worker -l info
directory=/path/to/bifang
user=www-data
autostart=true
autorestart=true

[program:bifang_beat]
command=/path/to/venv/bin/celery -A app.celery_app beat -l info
directory=/path/to/bifang
user=www-data
autostart=true
autorestart=true
```

### 前端构建

```bash
cd frontend
npm run build
```

构建后的文件在 `project/frontend/` 目录，可以配置Nginx静态文件服务。

## 下一步

- **配置钉钉/飞书智能体**: 参考 [钉钉机器人设置](DINGTALK_BOT_SETUP.md) 和 [飞书机器人设置](docs/feishu_bot_setup.md)
- **了解系统架构**: 查看 [架构设计文档](docs/ARCHITECTURE.md)
- **开发新插件**: 参考 [插件开发文档](docs/ai_agent_development.md)
- **生产环境部署**: 参考 [Docker部署文档](docs/DOCKER_DEPLOY.md) 或使用Gunicorn+Supervisor

## 更多文档

- [README.md](README.md) - 项目总览和功能特性
- [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) - 项目结构说明
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - 系统架构设计
- [docs/DOCKER_DEPLOY.md](docs/DOCKER_DEPLOY.md) - Docker部署详解




