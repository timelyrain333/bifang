# 飞书长连接故障排查指南

## 问题：应用未建立长连接（错误代码 10068）

### 可能原因

1. **长连接服务未启动**
2. **SSL证书验证失败**（常见于使用代理的环境）
3. **网络连接问题**
4. **App ID或App Secret配置错误**

## 解决方案

### 1. 确认服务已启动

```bash
# 检查服务是否运行
ps aux | grep "start_feishu_long_connection"

# 查看服务日志
tail -f /tmp/feishu_long_connection.log
```

### 2. SSL证书验证失败

如果看到以下错误：
```
[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate in certificate chain
```

**解决方案A：安装代理的CA证书**

如果使用代理（如Clash、V2Ray等），需要安装代理的CA证书：

1. 打开代理软件，导出CA证书
2. 安装到系统钥匙串（macOS）或系统证书存储（Linux）
3. 重启服务

**解决方案B：临时禁用系统代理（仅用于测试）**

macOS:
```bash
# 临时禁用Wi-Fi代理
networksetup -setwebproxystate "Wi-Fi" off
networksetup -setsecurewebproxystate "Wi-Fi" off

# 启动服务
python manage.py start_feishu_long_connection

# 测试完成后，重新启用代理
networksetup -setwebproxystate "Wi-Fi" on
networksetup -setsecurewebproxystate "Wi-Fi" on
```

**解决方案C：配置环境变量使用代理**

如果必须使用代理，设置环境变量：
```bash
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890
python manage.py start_feishu_long_connection
```

### 3. 检查连接状态

服务启动后，应该看到类似以下日志：
```
[Lark] [INFO] connected to wss://xxxxx
```

如果看到 `connected to wss://`，说明长连接已成功建立。

### 4. 在飞书开放平台配置

**重要**：必须在长连接服务成功建立后，才能在飞书开放平台配置订阅方式。

1. 确保服务正在运行并已建立连接
2. 登录飞书开放平台
3. 进入"事件与回调 > 事件配置"
4. 选择"使用长连接接收事件"
5. 保存配置

如果此时仍然提示"应用未建立长连接"，请：
- 等待1-2分钟，让飞书平台检测到连接
- 检查服务日志，确认连接已建立
- 确认App ID和App Secret正确

### 5. 常见错误

#### 错误：python-socks is required to use a SOCKS proxy

**解决**：
```bash
pip install python-socks
```

#### 错误：SSL证书验证失败

**解决**：参考上面的"SSL证书验证失败"解决方案

#### 错误：配置未启用AI或缺少API Key

**说明**：这是警告，不影响长连接建立，但智能体功能不可用。

**解决**：在系统配置中启用通义千问AI配置

## 验证连接

服务启动成功后，应该看到：
1. `INFO 已创建WebSocket客户端`
2. `INFO 正在建立飞书WebSocket长连接...`
3. `[Lark] [INFO] connected to wss://xxxxx`（连接成功）

如果看到 `connected to wss://`，说明长连接已建立，可以在飞书开放平台配置订阅方式了。

## 保持服务运行

建议使用以下方式保持服务运行：

### 使用screen
```bash
screen -S feishu_long_connection
python manage.py start_feishu_long_connection
# 按 Ctrl+A 然后 D 退出screen
```

### 使用tmux
```bash
tmux new -s feishu_long_connection
python manage.py start_feishu_long_connection
# 按 Ctrl+B 然后 D 退出tmux
```

### 使用systemd（Linux）
创建 `/etc/systemd/system/feishu-long-connection.service`：
```ini
[Unit]
Description=Feishu Long Connection Service
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/bifang
ExecStart=/usr/bin/python3 manage.py start_feishu_long_connection
Restart=always

[Install]
WantedBy=multi-user.target
```

然后：
```bash
sudo systemctl enable feishu-long-connection
sudo systemctl start feishu-long-connection
```



