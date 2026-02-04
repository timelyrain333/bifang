# 删除Charles代理证书指南

## 问题说明

如果飞书长连接服务出现SSL证书验证失败错误：
```
[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate in certificate chain
```

这通常是因为系统中安装了Charles代理的证书，即使代理已关闭，证书仍会干扰SSL验证。

## 手动删除步骤

### 方法1：通过钥匙串访问应用删除（推荐）

1. **打开钥匙串访问应用**
   - 按 `Command + Space` 打开 Spotlight
   - 输入 `钥匙串访问` 或 `Keychain Access` 并回车
   - 或者从 `应用程序` > `实用工具` > `钥匙串访问` 打开

2. **选择钥匙串**
   - 在左侧选择 `登录` 钥匙串（Login Keychain）
   - 如果没找到，也可以检查 `系统` 钥匙串（System Keychain）

3. **搜索Charles证书**
   - 在右上角搜索框中输入 `Charles`
   - 查找所有包含 "Charles" 的证书

4. **删除证书**
   - 找到 `Charles Proxy CA` 或类似的证书
   - 右键点击证书，选择 `删除 "Charles Proxy CA"`
   - 或者选中证书后按 `Delete` 键

5. **确认删除**
   - 如果提示输入密码，请输入您的Mac登录密码
   - 确认删除操作

6. **重启服务**
   ```bash
   # 停止当前服务
   ps aux | grep "[p]ython.*start_feishu" | awk '{print $2}' | xargs kill
   
   # 重新启动服务
   cd /Users/denggushizhangda/PycharmProjects/bifang
   python3 manage.py start_feishu_long_connection
   ```

### 方法2：通过命令行删除（需要管理员权限）

```bash
# 查找证书
security find-certificate -a -c "Charles Proxy CA"

# 删除证书（从登录钥匙串）
security delete-certificate -c "Charles Proxy CA" ~/Library/Keychains/login.keychain-db

# 如果证书在系统钥匙串中，需要sudo权限
sudo security delete-certificate -c "Charles Proxy CA" /System/Library/Keychains/SystemRootCertificates.keychain
```

## 验证删除

删除证书后，可以通过以下命令验证：

```bash
# 检查是否还有Charles证书
security find-certificate -a -c "Charles" 2>/dev/null | head -5

# 如果没有任何输出，说明证书已删除
```

## 重启服务

删除证书后，必须重启飞书长连接服务才能生效：

```bash
# 停止服务
ps aux | grep "[p]ython.*start_feishu" | awk '{print $2}' | xargs kill

# 重新启动
cd /Users/denggushizhangda/PycharmProjects/bifang
python3 manage.py start_feishu_long_connection
```

## 检查连接状态

服务启动后，查看日志确认连接是否成功：

```bash
# 查看最新日志
tail -f /tmp/feishu_long_connection*.log

# 查找连接成功的日志
grep -i "connected to wss" /tmp/feishu_long_connection*.log
```

如果看到 `connected to wss://` 的日志，说明长连接已成功建立。

## 注意事项

1. **备份证书**：如果将来还需要使用Charles代理，可以先导出证书备份
2. **系统钥匙串**：某些证书可能安装在系统钥匙串中，需要管理员权限才能删除
3. **重启服务**：删除证书后必须重启服务才能生效
4. **其他代理工具**：如果使用其他代理工具（如mitmproxy），也需要删除相应的证书

## 如果问题仍然存在

如果删除证书后仍然有SSL错误，可能的原因：

1. **证书未完全删除**：检查所有钥匙串（登录、系统、系统根证书）
2. **需要重启Mac**：某些情况下需要重启系统才能完全清除证书影响
3. **其他证书干扰**：检查是否有其他自签名证书
4. **WebSocket库配置**：可能需要配置WebSocket库使用certifi证书

## 相关文件

- 服务日志：`/tmp/feishu_long_connection*.log`
- 证书位置：`~/Library/Keychains/login.keychain-db`



