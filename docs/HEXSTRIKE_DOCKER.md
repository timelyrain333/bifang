# HexStrike AI - Docker 部署说明

使用 Docker 部署 HexStrike AI，便于迁移与整体系统部署。bifang 通过 `HEXSTRIKE_SERVER_URL` 连接容器内服务（默认端口映射后为 `http://localhost:8888`）。

## 前置要求

- Docker 与 Docker Compose 已安装
- 本机 8888 端口未被占用

## 快速启动

在 **bifang 项目根目录** 执行：

```bash
# 构建并启动 HexStrike AI 容器（首次会拉取基础镜像并构建）
docker-compose -f docker-compose.hexstrike.yml up -d --build

# 查看日志
docker-compose -f docker-compose.hexstrike.yml logs -f hexstrike-ai

# 健康检查
curl -s http://localhost:8888/health | head -c 200
```

bifang 无需改配置即可使用：默认 `HEXSTRIKE_SERVER_URL=http://localhost:8888`，端口映射后即可连通。

## 常用命令

| 操作       | 命令 |
|------------|------|
| 启动       | `docker-compose -f docker-compose.hexstrike.yml up -d` |
| 停止       | `docker-compose -f docker-compose.hexstrike.yml down` |
| 查看日志   | `docker-compose -f docker-compose.hexstrike.yml logs -f hexstrike-ai` |
| 重启       | `docker-compose -f docker-compose.hexstrike.yml restart hexstrike-ai` |
| 仅重新构建 | `docker-compose -f docker-compose.hexstrike.yml build --no-cache` |

## 镜像说明

- **构建上下文**：`docker/hexstrike-ai/`（仅含 Dockerfile，不依赖本地 hexstrike-ai 目录）
- **镜像内**：从 GitHub 克隆 [0x4m4/hexstrike-ai](https://github.com/0x4m4/hexstrike-ai)，安装 Python 依赖与系统工具（如 nmap）
- **端口**：容器内 8888，映射到主机 8888
- **环境变量**：`HEXSTRIKE_HOST=0.0.0.0`，保证在容器内监听所有接口

## bifang 配置（可选）

- **bifang 跑在本机**：无需改配置，使用默认 `http://localhost:8888` 即可。
- **bifang 也跑在 Docker 同一 compose 内**：在 bifang 服务环境变量中设置  
  `HEXSTRIKE_SERVER_URL=http://hexstrike-ai:8888`（服务名即 compose 中的 `hexstrike-ai`）。

环境变量或 `bifang/settings.py` 中可设置：

```bash
export HEXSTRIKE_SERVER_URL=http://localhost:8888
export HEXSTRIKE_ENABLED=true
export HEXSTRIKE_TIMEOUT=300
```

## 迁移与整体部署

- **仅迁移 HexStrike**：拷贝 `docker/hexstrike-ai/`、`docker-compose.hexstrike.yml` 到新环境，执行 `docker-compose -f docker-compose.hexstrike.yml up -d --build` 即可。
- **与 bifang 一起迁移**：在目标环境部署 bifang 后，用同一 compose 或单独启动 HexStrike 容器，并按要求设置 `HEXSTRIKE_SERVER_URL`。

## 故障排查

1. **构建失败**  
   - 检查网络与 Docker 拉取镜像权限。  
   - 若 `pip install -r requirements.txt` 失败，Dockerfile 中会回退为安装最小依赖集（flask、requests、psutil、aiohttp 等），可先保证服务能起来。

2. **本机访问不到 /health**  
   - 确认容器在运行：`docker-compose -f docker-compose.hexstrike.yml ps`  
   - 确认端口映射：`docker port hexstrike-ai` 应包含 `8888/tcp -> 0.0.0.0:8888`

3. **bifang 显示「资产安全评估未连接」**  
   - 确认 HexStrike 容器已启动且 `curl http://localhost:8888/health` 返回正常。  
   - 确认 bifang 中 `HEXSTRIKE_SERVER_URL` 指向正确（本机部署为 `http://localhost:8888`）。

## 参考

- [HexStrike AI GitHub](https://github.com/0x4m4/hexstrike-ai)
- [HexStrike 集成说明](./HEXSTRIKE_INTEGRATION.md)
