# 飞书机器人应用配置指南（本地开发环境）

## 问题说明

飞书机器人应用的事件订阅需要公网可访问的地址，而本地开发环境（localhost）无法被飞书服务器访问。因此需要使用内网穿透工具将本地服务暴露到公网。

## 解决方案：使用内网穿透工具

### 方案一：使用 ngrok（推荐）

ngrok 是最常用的内网穿透工具，提供免费和付费版本。

#### 1. 安装 ngrok

**macOS:**
```bash
brew install ngrok/ngrok/ngrok
```

**Windows:**
- 访问 https://ngrok.com/download
- 下载并解压到任意目录
- 将 ngrok.exe 添加到系统 PATH

**Linux:**
```bash
# 下载
wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz
tar -xzf ngrok-v3-stable-linux-amd64.tgz
sudo mv ngrok /usr/local/bin/
```

#### 2. 注册 ngrok 账号（可选，免费版有限制）

1. 访问 https://dashboard.ngrok.com/signup
2. 注册账号并获取 authtoken
3. 配置 authtoken：
```bash
ngrok config add-authtoken YOUR_AUTH_TOKEN
```

#### 3. 启动本地服务

确保 Bifang 后端服务正在运行：
```bash
python manage.py runserver 0.0.0.0:8000
```

#### 4. 启动 ngrok

在**新的终端窗口**中运行：
```bash
ngrok http 8000
```

或者指定域名（需要付费版）：
```bash
ngrok http 8000 --domain=your-domain.ngrok.io
```

#### 5. 获取公网地址

ngrok 启动后会显示类似以下信息：
```
Forwarding  https://xxxx-xx-xx-xx-xx.ngrok-free.app -> http://localhost:8000
```

**重要**: 复制 `https://xxxx-xx-xx-xx-xx.ngrok-free.app` 这个地址。

#### 6. 配置飞书机器人应用

1. 登录飞书开放平台：https://open.feishu.cn/
2. 进入您的机器人应用
3. 进入"事件订阅"页面
4. 设置请求地址为：`https://xxxx-xx-xx-xx-xx.ngrok-free.app/api/feishu/bot/`
   - 注意：必须使用 HTTPS 地址
   - 注意：地址末尾的 `/api/feishu/bot/` 不能省略
5. 订阅"接收消息"事件（`im.message.receive_v1`）
6. 保存配置

#### 7. 验证配置

访问以下地址验证配置是否正确：
```
https://xxxx-xx-xx-xx-xx.ngrok-free.app/api/feishu/bot/
```

应该返回配置信息。

### 方案二：使用其他内网穿透工具

#### frp (Fast Reverse Proxy)

1. 需要一台有公网IP的服务器
2. 在服务器上部署 frp 服务端
3. 在本地运行 frp 客户端
4. 配置域名指向服务器

#### natapp

1. 访问 https://natapp.cn/
2. 注册账号并购买隧道（有免费版）
3. 下载客户端并运行
4. 使用提供的公网地址

#### localtunnel

```bash
# 安装
npm install -g localtunnel

# 启动
lt --port 8000
```

### 方案三：使用云服务器（生产环境推荐）

如果用于生产环境，建议直接部署到云服务器：

1. 购买云服务器（阿里云、腾讯云等）
2. 部署 Bifang 服务
3. 配置域名和 HTTPS
4. 使用域名配置飞书事件订阅

## 配置步骤总结

### 1. 启动本地服务

```bash
# 确保后端服务运行在 8000 端口
python manage.py runserver 0.0.0.0:8000
```

### 2. 启动内网穿透（以 ngrok 为例）

```bash
ngrok http 8000
```

### 3. 获取公网地址

从 ngrok 输出中复制 HTTPS 地址，例如：
```
https://abc123.ngrok-free.app
```

### 4. 配置飞书机器人应用

- 事件订阅地址：`https://abc123.ngrok-free.app/api/feishu/bot/`
- 订阅事件：`im.message.receive_v1`（接收消息）

### 5. 配置 Bifang 系统

在 Bifang 系统的"系统配置"中：
- 添加飞书配置
- 填写飞书 Webhook 地址（从机器人应用获取）
- 填写飞书签名密钥（如果启用了签名校验）
- 确保配置了通义千问 AI（用于智能体对话）

### 6. 测试

在飞书群中 @ 机器人发送消息，例如：
```
@SecOps 请捕获最新的漏洞并检查我的资产是否受影响
```

## 注意事项

### ngrok 免费版限制

1. **地址会变化**：每次重启 ngrok，地址都会变化
   - 解决方案：使用付费版固定域名，或每次重启后更新飞书配置

2. **访问限制**：免费版有访问次数限制
   - 解决方案：使用付费版，或使用其他工具

3. **警告页面**：免费版首次访问会显示警告页面
   - 解决方案：点击"Visit Site"继续，或使用付费版

### 安全建议

1. **使用 HTTPS**：确保使用 HTTPS 地址（ngrok 默认提供）
2. **签名校验**：在飞书机器人应用中启用签名校验，提高安全性
3. **限制访问**：如果可能，配置 IP 白名单

### 调试技巧

1. **查看日志**：检查后端日志，确认是否收到消息
   ```bash
   # 查看 Django 日志
   tail -f logs/django.log
   ```

2. **测试接口**：访问 `GET /api/feishu/bot/` 查看配置状态

3. **检查 ngrok 流量**：访问 http://localhost:4040 查看 ngrok 的请求日志

## 常见问题

### Q: ngrok 地址每次重启都变化怎么办？

**A**: 
- 使用 ngrok 付费版可以固定域名
- 或者使用其他工具如 frp（需要公网服务器）
- 或者每次重启后更新飞书配置

### Q: 收到 "ngrok warning page" 怎么办？

**A**: 
- 这是 ngrok 免费版的正常行为
- 点击 "Visit Site" 按钮继续访问
- 或使用付费版避免此问题

### Q: 飞书无法访问我的地址？

**A**: 
- 确保 ngrok 正在运行
- 确保本地服务正在运行
- 检查防火墙设置
- 确保使用 HTTPS 地址（不是 HTTP）

### Q: 如何保持 ngrok 长期运行？

**A**: 
- 使用 `screen` 或 `tmux` 保持会话
- 或使用 systemd 服务（Linux）
- 或使用 Supervisor 管理进程

## 生产环境建议

对于生产环境，强烈建议：

1. **使用云服务器**：部署到有公网IP的服务器
2. **配置域名**：使用自己的域名
3. **启用 HTTPS**：配置 SSL 证书
4. **使用固定地址**：避免地址变化导致配置失效





