# 阿里云安全中心告警监控插件使用说明

## 插件概述

`alarm_aliyun_security_alerts` 是一个告警类插件，用于定时获取阿里云安全中心的安全告警，并将新告警自动推送到钉钉群或飞书群，以便安全运营人员及时处置告警。

## 功能特性

- ✅ 定时查询阿里云安全中心告警
- ✅ 自动去重，避免重复推送
- ✅ 支持推送到钉钉群
- ✅ 支持推送到飞书群
- ✅ 支持自定义查询时间范围
- ✅ 支持过滤告警级别
- ✅ 支持过滤处理状态

## 配置说明

### 必需配置项

- **access_key_id** (string): 阿里云AccessKey ID
- **access_key_secret** (string): 阿里云AccessKey Secret
- **region_id** (string): 地域ID，如 `cn-hangzhou`

### 可选配置项

- **api_endpoint** (string, 可选): API地址，默认为 `https://sas.{region_id}.aliyuncs.com`
- **page_size** (int, 可选): 分页大小，默认为 20
- **lookback_minutes** (int, 可选): 查询最近N分钟的告警，默认为 60（分钟）
- **levels** (string, 可选): 告警级别，多个用逗号分隔，默认 `serious,suspicious`
  - 可选值：`serious`（紧急）、`suspicious`（可疑）、`remind`（提醒）
- **dealed** (string, 可选): 是否已处理，默认 `N`（待处理）
  - `N`: 待处理
  - `Y`: 已处理
- **push_dingtalk** (boolean, 可选): 是否推送到钉钉，默认 `true`
- **push_feishu** (boolean, 可选): 是否推送到飞书，默认 `true`
- **notification_config_id** (integer, 可选): 通知配置ID（AliyunConfig的ID），如果不指定，将使用默认的钉钉/飞书配置

### 配置示例

```json
{
  "access_key_id": "LTAI5txxxxxxxxxxxx",
  "access_key_secret": "xxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "region_id": "cn-hangzhou",
  "lookback_minutes": 60,
  "levels": "serious,suspicious",
  "dealed": "N",
  "push_dingtalk": true,
  "push_feishu": true
}
```

## 使用方法

### 1. 运行数据库迁移

首先需要运行数据库迁移以创建 `SecurityAlert` 模型：

```bash
python manage.py migrate
```

### 2. 加载插件

运行以下命令加载插件到数据库：

```bash
python manage.py load_plugins
```

### 3. 配置钉钉/飞书通知

在系统配置页面配置钉钉或飞书机器人的Webhook地址：

1. 登录系统，进入"系统配置"页面
2. 创建或编辑一个阿里云配置
3. 配置类型选择"钉钉配置"、"飞书配置"或"阿里云+钉钉配置"
4. 填写Webhook地址和签名密钥（如使用）
5. 启用通知功能

### 4. 创建定时任务

1. 登录系统，进入"任务管理"页面
2. 点击"新建任务"
3. 选择插件：`alarm_aliyun_security_alerts`
4. 设置触发类型：
   - **手动执行**: 测试时手动点击执行
   - **定时执行**: 设置Cron表达式，例如：
     - `*/5 * * * *` - 每5分钟执行一次
     - `*/1 * * * *` - 每分钟执行一次
     - `0 */1 * * *` - 每小时执行一次
5. 填写配置JSON（参考上面的配置示例）
6. 保存任务

### 5. 执行任务

- **手动执行**: 在任务列表页面点击"执行"按钮进行测试
- **定时执行**: 系统会根据Cron表达式自动执行（需要启动Celery Beat）

## 执行结果说明

插件执行完成后会返回以下信息：

```json
{
  "success": true,
  "message": "获取20条告警，新增5条，钉钉推送5条，飞书推送5条",
  "data": {
    "total_fetched": 20,
    "new_alerts": 5,
    "pushed_dingtalk": 5,
    "pushed_feishu": 5,
    "failed": 0
  }
}
```

## 告警去重机制

插件使用以下机制确保告警不重复推送：

1. **告警ID去重**: 使用阿里云返回的告警ID（`Id`）作为唯一标识
2. **唯一标识去重**: 使用告警的唯一key（`AlarmUniqueInfo`）作为备用唯一标识
3. **推送状态记录**: 每个告警会记录是否已推送到钉钉/飞书，避免重复推送

## 告警消息格式

推送到钉钉/飞书的告警消息包含以下信息：

- 告警名称
- 告警级别（紧急/可疑/提醒）
- 告警类型
- 告警ID
- 告警时间
- 处理状态
- 实例信息（名称、ID、IP、UUID）
- 详细信息（描述、路径、进程等）

## 注意事项

1. **权限要求**: 确保阿里云AccessKey具有以下权限：
   - `yundun-sas:DescribeSuspEvents` - 查询异常告警权限

2. **API限制**: 阿里云API可能有频率限制，建议：
   - 查询时间范围（`lookback_minutes`）不要设置太大，避免一次查询过多数据
   - 定时任务执行频率不要太高，建议每分钟或每5分钟执行一次

3. **时区问题**: 插件使用服务器本地时区，确保服务器时区设置正确

4. **通知配置**: 
   - 如果不指定 `notification_config_id`，插件会自动查找默认的钉钉/飞书配置
   - 确保至少配置了一个启用的钉钉或飞书通知配置

5. **Celery配置**: 
   - 定时任务需要Celery Beat运行
   - 确保Celery Worker也在运行以执行任务

## 故障排查

### 问题1: 插件执行失败，提示"无法加载插件"

**解决方案**: 
- 检查插件文件是否存在: `app/plugins/alarm_aliyun_security_alerts.py`
- 运行 `python manage.py load_plugins` 重新加载插件

### 问题2: API请求失败

**解决方案**:
- 检查AccessKey和Secret是否正确
- 检查AccessKey是否有 `DescribeSuspEvents` 权限
- 检查网络连接是否正常
- 检查region_id和api_endpoint是否正确

### 问题3: 获取到告警但没有推送

**解决方案**:
- 检查是否配置了钉钉/飞书Webhook
- 检查通知配置是否启用（`dingtalk_enabled`/`feishu_enabled`）
- 检查 `push_dingtalk`/`push_feishu` 配置是否为 `true`
- 查看执行日志了解详细错误信息

### 问题4: 告警重复推送

**解决方案**:
- 检查数据库迁移是否成功执行
- 检查 `SecurityAlert` 表是否存在
- 查看告警记录是否正确保存到数据库

## API参考

插件使用的阿里云安全中心API：

- `DescribeSuspEvents` - 查询异常告警列表

更多API文档请参考：
- [DescribeSuspEvents API文档](https://help.aliyun.com/zh/security-center/developer-reference/api-sas-2018-12-03-describesusevents)
- [ExportSuspEvents API文档](https://help.aliyun.com/zh/security-center/developer-reference/api-sas-2018-12-03-exportsuspevents)

## 示例任务配置

### 每分钟监控紧急告警

```json
{
  "access_key_id": "LTAI5txxxxxxxxxxxx",
  "access_key_secret": "xxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "region_id": "cn-hangzhou",
  "lookback_minutes": 5,
  "levels": "serious",
  "dealed": "N",
  "push_dingtalk": true,
  "push_feishu": false
}
```

Cron表达式: `*/1 * * * *`（每分钟执行）

### 每5分钟监控所有可疑告警

```json
{
  "access_key_id": "LTAI5txxxxxxxxxxxx",
  "access_key_secret": "xxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "region_id": "cn-hangzhou",
  "lookback_minutes": 10,
  "levels": "serious,suspicious",
  "dealed": "N",
  "push_dingtalk": true,
  "push_feishu": true,
  "notification_config_id": 1
}
```

Cron表达式: `*/5 * * * *`（每5分钟执行）
