# Bifang Docker 部署说明

所有服务通过 Docker 统一部署，无需在宿主机安装 Python/Node/Redis 或重复安装依赖。

## 服务组成（前后端分离）

| 服务 | 说明 | 端口 |
|------|------|------|
| **frontend** | Vue 静态 + Nginx（/api 代理到后端） | **8080** |
| **backend** | Django API + Admin（仅后端） | **8000** |
| redis | Redis（Celery 与缓存） | 6379 |
| celery-worker | Celery 异步任务 | - |
| celery-beat | Celery 定时任务 | - |
| dingtalk-stream | 钉钉 Stream 推送 | - |
| hexstrike-ai | 资产安全评估（HexStrike AI） | 8888 |

## 前置要求

- Docker
- Docker Compose（v2 推荐：`docker compose`）

## 一键启动

在项目根目录执行：

```bash
docker compose up -d --build
```

首次会构建前端镜像、后端镜像和 HexStrike 镜像，并启动所有容器。

- **前端（用户访问）**: http://localhost:8080（Vue 页面，/api 由 Nginx 代理到后端）
- **后端 API**: http://localhost:8000/api/
- **Admin**: http://localhost:8000/admin/（也可通过前端同域 http://localhost:8080/admin/）
- **HexStrike 健康检查**: http://localhost:8888/health

## 常用命令

| 操作 | 命令 |
|------|------|
| 启动 | `docker compose up -d` |
| 构建并启动 | `docker compose up -d --build` |
| 停止 | `docker compose down` |
| 查看日志 | `docker compose logs -f` |
| 仅看后端 | `docker compose logs -f backend` |
| 进入后端容器 | `docker compose exec backend bash` |

## 数据持久化

- **Redis**: 数据卷 `redis_data`
- **SQLite 与日志**: 数据卷 `bifang_data`（数据库）、`bifang_logs`（日志）

首次启动后创建管理员：

```bash
docker compose exec backend python manage.py createsuperuser
```

## 环境变量配置

### 默认配置（SQLite）

系统默认使用SQLite，无需额外配置。数据存储在Docker卷 `bifang_data` 中。

### 使用MySQL（生产环境推荐）

如需使用MySQL，需要：

1. **在 `docker-compose.yml` 中添加MySQL服务**：

```yaml
services:
  mysql:
    image: mysql:8.0
    container_name: bifang-mysql
    environment:
      MYSQL_ROOT_PASSWORD: your_root_password
      MYSQL_DATABASE: bifang
      MYSQL_USER: bifang
      MYSQL_PASSWORD: your_password
    volumes:
      - mysql_data:/var/lib/mysql
    ports:
      - "3306:3306"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 3

volumes:
  mysql_data:
```

2. **在 `backend` 服务中添加环境变量**：

```yaml
backend:
  environment:
    - DB_ENGINE=mysql
    - DB_NAME=bifang
    - DB_USER=bifang
    - DB_PASSWORD=your_password
    - DB_HOST=mysql
    - DB_PORT=3306
  depends_on:
    mysql:
      condition: service_healthy
```

### 其他环境变量

在 `docker-compose.yml` 的 `backend`（或对应服务）下可配置：

- `DATABASE_PATH`: SQLite 路径（默认 `/app/data/db.sqlite3`，仅SQLite时使用）
- `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND`: Redis 地址（默认 `redis://redis:6379/0`）
- `HEXSTRIKE_SERVER_URL`: HexStrike 地址（默认 `http://hexstrike-ai:8888`）
- `HEXSTRIKE_ENABLED`: 是否启用（默认 `true`）
- `ALLOWED_HOSTS`: 逗号分隔的 Host（默认 `localhost,127.0.0.1,0.0.0.0`）

## 仅启动部分服务

例如只启动后端与 Redis（不启动 Celery、钉钉、HexStrike）：

```bash
docker compose up -d redis backend
```

需要 HexStrike 时：

```bash
docker compose up -d redis backend hexstrike-ai
```

## 故障排查

1. **后端启动报错 “No such file or directory” 等**  
   确认 `docker/entrypoint.sh` 已复制进镜像并具有执行权限（Dockerfile 中已 `RUN chmod +x`）。

2. **前端页面 404 或空白**  
   确认是用 `docker compose up -d --build` 构建过镜像，前端会在构建阶段打包进 `frontend_dist`。

3. **Celery/钉钉连不上 Redis**  
   确认 `redis` 服务已启动且健康：`docker compose ps`，再 `docker compose logs redis`。

4. **HexStrike 连接失败**  
   确认 `hexstrike-ai` 已启动：`docker compose up -d hexstrike-ai`，然后访问 http://localhost:8888/health。

5. **钉钉 Stream 无推送**  
   在系统配置中启用钉钉 Stream 并填写 Client ID/Secret；`dingtalk-stream` 容器需能访问 `backend`（数据库）和 `redis`。

## 生产环境建议

### 安全配置

1. **修改默认密钥**
   - 修改 `bifang/settings.py` 中的 `SECRET_KEY`
   - 使用环境变量管理敏感配置

2. **启用HTTPS**
   - 配置Nginx SSL证书
   - 设置 `SESSION_COOKIE_SECURE=True`

3. **限制访问**
   - 配置防火墙规则
   - 使用VPN或内网访问
   - 设置 `ALLOWED_HOSTS`

4. **数据加密**
   - 对数据库中的敏感信息加密
   - 使用密钥管理服务（如AWS Secrets Manager）

### 性能优化

1. **使用MySQL替代SQLite**（生产环境必需）
2. **配置Redis持久化**
3. **使用Gunicorn替代runserver**（生产环境）
4. **配置Nginx缓存**
5. **监控和日志收集**（Prometheus、ELK等）

### 高可用部署

- **数据库**: MySQL主从复制或集群
- **Redis**: Redis Sentinel或Cluster
- **应用**: 多实例负载均衡
- **容器编排**: Kubernetes（可选）

## 与原有脚本的关系

- **start.sh / start_celery.sh**：仍可在宿主机虚拟环境中使用，用于本地开发。
- **docker-compose.hexstrike.yml**：已合并进主 `docker-compose.yml`，可保留用于仅单独启动 HexStrike 的场景。

**推荐**: 日常使用直接 `docker compose up -d --build` 启动全部服务，无需在虚拟环境中反复安装依赖。

## 相关文档

- [快速开始指南](../QUICKSTART.md) - 本地开发环境搭建
- [架构设计文档](ARCHITECTURE.md) - 系统架构说明
- [README.md](../README.md) - 项目总览
