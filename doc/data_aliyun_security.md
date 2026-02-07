# 阿里云安全中心数据导入插件使用说明

## 插件概述

`data_aliyun_security.py` 是一个数据记录类插件，用于从阿里云安全中心获取主机资产数据并导入到Bifang数据库中。

## 支持的资产类型

插件支持导入以下14种资产类型：

1. **server** - 服务器
2. **account** - 账户
3. **port** - 端口
4. **process** - 进程
5. **middleware** - 中间件
6. **ai_component** - AI组件
7. **database** - 数据库
8. **web_service** - Web服务
9. **software** - 软件
10. **cron_task** - 计划任务
11. **startup_item** - 启动项
12. **kernel_module** - 内核模块
13. **web_site** - Web站点
14. **idc_probe** - IDC探针发现

## 配置说明

### 必需配置项

- **access_key_id** (string): 阿里云AccessKey ID
- **access_key_secret** (string): 阿里云AccessKey Secret
- **region_id** (string, 可选): 地域ID，默认为 `cn-hangzhou`

### 可选配置项

- **asset_types** (list, 可选): 要导入的资产类型列表。如果不指定，则导入所有资产类型。
  - 示例: `["server", "account", "port"]`
- **page_size** (int, 可选): 分页大小，默认为 100

### 配置示例

```json
{
  "access_key_id": "LTAI5txxxxxxxxxxxx",
  "access_key_secret": "xxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "region_id": "cn-hangzhou",
  "asset_types": ["server", "account", "port", "process"],
  "page_size": 100
}
```

## 使用方法

### 1. 通过前端界面创建任务

1. 登录系统，进入"任务管理"页面
2. 点击"新建任务"
3. 选择插件：`data_aliyun_security`
4. 设置触发类型：
   - **手动执行**: 需要时手动点击执行
   - **定时执行**: 设置Cron表达式，例如 `0 0 * * *` 表示每天0点执行
5. 填写配置JSON（参考上面的配置示例）
6. 保存任务

### 2. 执行任务

- **手动执行**: 在任务列表页面点击"执行"按钮
- **定时执行**: 系统会根据Cron表达式自动执行

### 3. 查看导入结果

- 在任务列表页面点击"历史"查看执行记录
- 在"资产数据"页面查看导入的资产数据

## 执行结果说明

插件执行完成后会返回以下信息：

```json
{
  "success": true,
  "message": "导入完成: 成功 150 条，失败 0 条",
  "data": {
    "servers": {
      "imported": 10,
      "failed": 0
    },
    "account": {
      "imported": 50,
      "failed": 0
    },
    "port": {
      "imported": 90,
      "failed": 0
    },
    "summary": {
      "total_imported": 150,
      "total_failed": 0
    }
  }
}
```

## 注意事项

1. **权限要求**: 确保阿里云AccessKey具有以下权限：
   - 云安全中心读取权限
   - 资产列表查询权限

2. **API限制**: 阿里云API可能有频率限制，如果数据量较大，建议：
   - 适当调整 `page_size`
   - 分批执行任务
   - 使用定时任务避免高峰期

3. **数据更新**: 
   - 插件使用 `update_or_create` 方法，相同UUID的资产会被更新
   - 建议定期执行任务以保持数据最新

4. **错误处理**: 
   - 插件会自动重试失败的API请求（最多3次）
   - 执行失败时会记录详细的错误信息
   - 可以通过执行历史查看错误详情

## 故障排查

### 问题1: 插件执行失败，提示"无法加载插件"

**解决方案**: 
- 检查插件文件是否存在: `app/plugins/data_aliyun_security.py`
- 运行 `python manage.py load_plugins` 重新加载插件

### 问题2: API请求失败

**解决方案**:
- 检查AccessKey和Secret是否正确
- 检查AccessKey是否有相应权限
- 检查网络连接是否正常
- 检查region_id是否正确

### 问题3: 导入的资产数据为空

**解决方案**:
- 检查云安全中心是否有资产数据
- 检查 `asset_types` 配置是否正确
- 查看执行日志了解详细错误信息

## API参考

插件使用的阿里云安全中心API：

- `DescribeCloudCenterInstances` - 获取服务器列表
- `DescribeAssetDetailByUuid` - 获取资产详情

更多API文档请参考：[阿里云安全中心API文档](https://help.aliyun.com/document_detail/431101.html)







