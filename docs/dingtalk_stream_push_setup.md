# 钉钉Stream推送配置指南

## 概述

钉钉Stream推送是一种无需公网地址的事件推送方式，通过WebSocket长连接接收钉钉事件。相比传统的Webhook方式，Stream推送具有以下优势：

1. **无需公网地址**：不需要配置域名或使用内网穿透工具
2. **更稳定**：长连接方式更稳定可靠
3. **实时性更好**：事件推送更及时

**重要说明**：钉钉Stream推送需要使用官方SDK建立WebSocket长连接，而不是简单的HTTP GET/POST端点。

## 配置步骤

### 1. 安装依赖

```bash
pip install dingtalk-stream
```

### 2. 在钉钉开放平台创建应用

1. 访问 [钉钉开放平台](https://open.dingtalk.com/)
2. 使用企业管理员账号登录
3. 进入"应用开发" > "企业内部开发"
4. 点击"创建应用"，填写应用信息
5. 创建成功后，进入应用详情页面

### 3. 获取应用凭证

在应用详情页面的"凭证与基础信息"中获取：

- **App ID**（应用ID）：用于标识应用
- **Client ID**（原AppKey）：用于Stream推送（**必填**）
- **Client Secret**（原AppSecret）：用于Stream推送（**必填**）

**重要**：请妥善保管Client Secret，不要泄露。

### 4. 在Bifang系统中配置

1. 登录Bifang系统
2. 进入"系统配置"页面
3. 点击"新增配置"，选择"钉钉"类型
4. 填写以下信息：
   - **配置名称**：如"钉钉Stream推送配置"
   - **钉钉App ID**：从钉钉开放平台获取（可选）
   - **钉钉Client ID**：从钉钉开放平台获取（**必填**，用于Stream推送）
   - **钉钉Client Secret**：从钉钉开放平台获取（**必填**，用于Stream推送）
   - **使用流式推送**：**必须开启**此选项
   - **启用钉钉通知**：开启此选项

5. 如果有通义千问AI配置，可以选择关联的AI配置（用于智能体功能）
6. 点击"保存"

### 5. 在钉钉开放平台配置Stream推送

1. 在应用详情页面，进入"开发配置" > "事件订阅"
2. 选择"Stream推送"模式
3. 保存配置（**注意**：钉钉Stream推送不需要填写回调URL，因为是通过SDK建立长连接）

### 6. 启动Stream推送服务

配置完成后，需要启动Stream推送服务来建立长连接：

```bash
# 启动所有启用的配置
python manage.py start_dingtalk_stream

# 或启动指定配置
python manage.py start_dingtalk_stream --config-id <配置ID>
```

**重要**：服务需要持续运行，才能保持与钉钉的长连接。

### 7. 验证配置

在钉钉开放平台的Stream推送配置页面，点击"验证连接通道"按钮。如果配置正确，应该显示验证成功。

## 本地开发环境配置

如果是本地开发环境，**不需要**使用内网穿透工具。Stream推送通过SDK建立WebSocket长连接，钉钉服务器会主动连接到你的服务。

只需要：

1. 确保服务器能够访问互联网（接收钉钉的连接）
2. 启动Stream推送服务：
   ```bash
   python manage.py start_dingtalk_stream
   ```

## 生产环境部署

### 使用Supervisor管理服务（推荐）

创建 `/etc/supervisor/conf.d/dingtalk-stream.conf`：

```ini
[program:dingtalk-stream]
command=/path/to/venv/bin/python /path/to/manage.py start_dingtalk_stream
directory=/path/to/project
autostart=true
autorestart=true
user=www-data
redirect_stderr=true
stdout_logfile=/path/to/logs/dingtalk-stream.log
```

然后：

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start dingtalk-stream
```

### 使用systemd服务（Linux）

创建 `/etc/systemd/system/dingtalk-stream.service`：

```ini
[Unit]
Description=DingTalk Stream Push Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/project
ExecStart=/path/to/venv/bin/python manage.py start_dingtalk_stream
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

然后：

```bash
sudo systemctl daemon-reload
sudo systemctl enable dingtalk-stream
sudo systemctl start dingtalk-stream
```

## 常见问题

### Q1: Stream推送验证失败？

**可能原因**：
1. Client ID或Client Secret配置错误
2. 未启用"使用流式推送"选项
3. Stream推送服务未运行

**解决方案**：
1. 检查系统配置中的Client ID和Client Secret是否正确
2. 确保"使用流式推送"选项已开启
3. 启动Stream推送服务：`python manage.py start_dingtalk_stream`
4. 查看日志：`tail -f logs/bifang.log | grep -i dingtalk`

### Q2: 如何查看日志？

```bash
# 查看Django日志
tail -f logs/bifang.log

# 查看实时日志（过滤钉钉相关）
tail -f logs/bifang.log | grep -i dingtalk

# 如果使用supervisor管理
tail -f /path/to/logs/dingtalk-stream.log
```

### Q3: 验证成功但收不到消息？

**可能原因**：
1. Stream推送服务未运行
2. 连接断开（网络问题）
3. 应用未发布

**解决方案**：
1. 确保Stream推送服务正在运行
2. 检查网络连接
3. 确保应用已发布并激活
4. 查看日志确认是否收到事件

### Q4: 服务启动后立即退出？

**可能原因**：
1. Client ID或Client Secret配置错误
2. 网络连接问题
3. 依赖未安装

**解决方案**：
1. 检查配置是否正确
2. 检查网络连接
3. 确保已安装：`pip install dingtalk-stream`
4. 查看详细错误日志

### Q5: 如何测试Stream推送？

1. 启动Stream推送服务
2. 在钉钉群中@机器人发送消息
3. 查看日志文件，确认是否收到事件
4. 如果配置了智能体功能，机器人应该会回复

## 技术说明

### Stream推送工作原理

1. **建立连接**：
   - 使用钉钉官方SDK（`dingtalk-stream`）
   - 通过Client ID和Client Secret认证
   - 建立WebSocket长连接

2. **接收事件**：
   - 钉钉通过WebSocket推送事件
   - SDK自动处理连接管理
   - 应用实现事件处理器

3. **处理消息**：
   - 接收聊天机器人消息事件
   - 调用SecOps智能体处理
   - 通过SDK回复消息

### 与Webhook模式的区别

| 特性 | Webhook模式 | Stream模式 |
|------|------------|-----------|
| 连接方式 | HTTP POST | WebSocket长连接 |
| 公网地址 | 需要 | 不需要 |
| 稳定性 | 一般 | 更好 |
| 实现复杂度 | 简单 | 需要SDK |

## 参考文档

- [钉钉Stream推送官方文档](https://open.dingtalk.com/document/orgapp/configure-stream-push)
- [钉钉Stream SDK Python](https://github.com/open-dingtalk/dingtalk-stream-sdk-python)
- [飞书长连接配置指南](./feishu_long_connection_setup.md)（类似实现）

## 注意事项

1. **服务持续运行**：
   - Stream推送服务必须持续运行
   - 连接断开会自动重连
   - 建议使用进程管理工具（如supervisor）

2. **安全性**：
   - Client Secret是敏感信息，请妥善保管
   - 生产环境建议使用环境变量或密钥管理系统

3. **性能**：
   - 消息处理采用异步方式
   - 避免在处理中执行耗时操作
   - 长时间处理应在后台线程中执行

4. **故障恢复**：
   - 网络异常会自动重连
   - 建议配置监控和告警
   - 定期检查服务状态
