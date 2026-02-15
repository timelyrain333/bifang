# 阿里云ECS插件安装指南

## 1. 安装SDK依赖

```bash
pip install aliyun-python-sdk-core aliyun-python-sdk-ecs
```

## 2. 加载插件

在Django项目根目录执行：

```bash
python manage.py load_plugins
```

这将会在数据库中注册 `data_aliyun_ecs` 插件。

## 3. 创建任务

### 方式1: 通过Web界面
1. 访问 http://localhost:8000/tasks
2. 点击"新建任务"
3. 填写任务信息：
   - 任务名称：`阿里云ECS资源采集`
   - 插件：选择 `data_aliyun_ecs`
   - 阿里云配置：选择已配置的阿里云凭证
   - 触发类型：选择 `cron`（定时执行）或 `manual`（手动执行）
   - Cron表达式：例如 `0 */1 * * *`（每小时执行一次）
   - 任务配置（JSON）：
     ```json
     {
       "resource_types": ["ecs_instance", "ecs_image", "ecs_disk", "ecs_snapshot", "ecs_security_group", "ecs_network_interface"]
     }
     ```
   - 启用任务：`是`

4. 保存任务

### 方式2: 通过Django Shell
```python
from app.models import Plugin, Task, AliyunConfig

# 获取插件和配置
plugin = Plugin.objects.get(name='data_aliyun_ecs')
config = AliyunConfig.objects.filter(is_default=True).first()

# 创建任务
Task.objects.create(
    name='阿里云ECS资源采集',
    plugin=plugin,
    aliyun_config=config,
    trigger_type='cron',
    cron_expression='0 */1 * * *',  # 每小时执行一次
    config={
        "resource_types": [
            "ecs_instance",
            "ecs_image",
            "ecs_disk",
            "ecs_snapshot",
            "ecs_security_group",
            "ecs_network_interface"
        ]
    },
    is_active=True
)
```

## 4. 手动执行任务

### 方式1: 通过Web界面
1. 访问 http://localhost:8000/tasks
2. 找到"阿里云ECS资源采集"任务
3. 点击"执行"按钮

### 方式2: 通过Django Shell
```python
from app.tasks import execute_task
from app.models import Task

task = Task.objects.get(name='阿里云ECS资源采集')
execute_task(task.id)
```

## 5. 查看采集的数据

数据采集完成后，可以通过以下方式查看：

1. **Web界面**：访问"云服务器"页面（http://localhost:8000/assets/cloud-servers）
2. **API接口**：`GET /api/assets/?source=aliyun_ecs`
3. **数据库**：查询 `assets` 表，`source='aliyun_ecs'`

## 支持的资源类型

插件支持采集以下资源类型：

- `ecs_instance` - ECS实例
- `ecs_image` - 镜像
- `ecs_disk` - 磁盘
- `ecs_snapshot` - 快照
- `ecs_security_group` - 安全组
- `ecs_network_interface` - 弹性网卡

## 任务配置示例

### 仅采集ECS实例
```json
{
  "resource_types": ["ecs_instance"]
}
```

### 采集实例和磁盘
```json
{
  "resource_types": ["ecs_instance", "ecs_disk"]
}
```

### 采集所有资源
```json
{
  "resource_types": ["ecs_instance", "ecs_image", "ecs_disk", "ecs_snapshot", "ecs_security_group", "ecs_network_interface"]
}
```

## 故障排查

### 1. SDK未安装
错误信息：`阿里云ECS SDK未安装`

解决方法：
```bash
pip install aliyun-python-sdk-core aliyun-python-sdk-ecs
```

### 2. 认证失败
错误信息：`缺少阿里云认证配置`

解决方法：检查阿里云配置中的 AccessKey ID 和 AccessKey Secret 是否正确

### 3. 权限不足
错误信息：`服务器异常: 403`

解决方法：确保 AccessKey 拥有以下权限：
- ecs:DescribeInstances
- ecs:DescribeImages
- ecs:DescribeDisks
- ecs:DescribeSnapshots
- ecs:DescribeSecurityGroups
- ecs:DescribeSecurityGroupAttribute
- ecs:DescribeNetworkInterfaces

### 4. 区域错误
错误信息：`服务器异常: InvalidRegionId`

解决方法：检查阿里云配置中的 RegionId 是否正确

## 常用Cron表达式

```
*/5 * * * *     # 每5分钟执行一次
0 */1 * * *     # 每小时执行一次
0 0 * * *       # 每天0点执行一次
0 0 * * 0       # 每周日凌晨执行一次
0 0 1 * *       # 每月1号凌晨执行一次
```