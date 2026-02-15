# Bifang 项目结构说明

## Python目录结构

```
bifang/
├── app/                          # Django应用主目录
│   ├── __init__.py
│   ├── apps.py                   # Django应用配置
│   ├── models.py                 # 数据模型定义
│   ├── views.py                  # API视图（ViewSet）
│   ├── serializers.py            # API序列化器
│   ├── urls.py                   # URL路由配置
│   ├── admin.py                  # Django Admin配置
│   ├── tasks.py                  # Celery任务定义
│   ├── celery_app.py             # Celery应用配置
│   ├── schedulers.py             # 定时任务调度器
│   │
│   ├── lib/                      # 依赖库文件
│   │   ├── __init__.py
│   │   ├── base_plugin.py        # 插件基类（所有插件需继承）
│   │   ├── db_helper.py          # 数据库操作辅助类
│   │   └── aliyun_client.py      # 阿里云API客户端封装
│   │
│   ├── plugins/                  # 插件目录
│   │   ├── __init__.py
│   │   └── data_aliyun_security.py  # 阿里云安全中心数据导入插件
│   │
│   └── management/               # Django管理命令
│       ├── __init__.py
│       └── commands/
│           ├── __init__.py
│           └── load_plugins.py   # 加载插件到数据库的命令
│
├── worker/                       # 自动化任务目录
│   ├── __init__.py
│   └── celery_worker.py          # Celery Worker启动脚本
│
├── project/                      # 程序打包目录
│
├── bifang/                       # Django项目配置目录
│   ├── __init__.py               # 初始化Celery应用
│   ├── settings.py               # Django设置
│   ├── urls.py                   # 主URL配置
│   ├── wsgi.py                   # WSGI配置
│   └── asgi.py                   # ASGI配置
│
├── frontend/                     # Vue前端项目
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── main.js               # Vue应用入口
│   │   ├── App.vue               # 根组件
│   │   ├── router/
│   │   │   └── index.js          # 路由配置
│   │   ├── api/                  # API接口封装
│   │   │   ├── index.js          # Axios实例
│   │   │   ├── task.js           # 任务相关API
│   │   │   └── plugin.js         # 插件相关API
│   │   └── views/                # 页面组件
│   │       ├── Home.vue          # 首页
│   │       ├── TaskList.vue      # 任务列表
│   │       ├── TaskForm.vue      # 任务表单（新建/编辑）
│   │       ├── PluginList.vue    # 插件列表
│   │       └── AssetList.vue     # 资产数据列表
│   ├── package.json
│   ├── vue.config.js
│   └── .gitignore
│
├── doc/                          # 工程说明文档
│   └── data_aliyun_security.md   # 阿里云安全中心插件详细说明
│
├── logs/                         # 日志目录
│
├── templates/                    # Django模板目录
│
├── manage.py                     # Django管理脚本
├── requirements.txt              # Python依赖
├── README.md                     # 项目说明
└── PROJECT_STRUCTURE.md          # 项目结构说明（本文件）
```

## 核心模块说明

### 1. 数据模型 (app/models.py)

- **Plugin**: 插件模型，存储插件信息
- **Task**: 任务模型，存储任务配置和执行信息
- **TaskExecution**: 任务执行记录，存储每次执行的详细信息
- **Asset**: 资产模型，存储各类资产数据

### 2. API接口 (app/views.py)

- **PluginViewSet**: 插件管理接口
- **TaskViewSet**: 任务管理接口（包含执行功能）
- **TaskExecutionViewSet**: 任务执行记录查询接口
- **AssetViewSet**: 资产数据查询接口

### 3. 插件系统

#### 插件基类 (app/lib/base_plugin.py)

所有插件必须继承 `BasePlugin` 类并实现 `execute` 方法：

```python
class Plugin(BasePlugin):
    def execute(self, *args, **kwargs):
        # 插件逻辑
        return {
            'success': True,
            'message': '执行成功',
            'data': {}
        }
```

#### 插件类型

- **data_xxx.py**: 数据记录类插件
- **collect_xxx.py**: 数据采集类插件
- **risk_xxx.py**: 风险检测类插件
- **dump_xxx.py**: 数据导出类插件
- **alarm_xxx.py**: 告警类插件

### 4. 任务调度

- **Celery**: 异步任务执行
- **Celery Beat**: 定时任务调度
- 支持Cron表达式配置定时任务

### 5. 前端页面

- **首页**: 系统概览统计
- **任务管理**: 任务列表、新建、编辑、执行
- **插件管理**: 插件列表查看
- **资产数据**: 资产数据查询和筛选

## 数据流程

1. **创建任务**: 用户在前端创建任务，选择插件并配置参数
2. **执行任务**: 
   - 手动执行：点击执行按钮
   - 定时执行：Celery Beat根据Cron表达式触发
3. **加载插件**: 系统动态加载插件模块
4. **执行插件**: 调用插件的 `execute` 方法
5. **保存数据**: 插件将数据保存到数据库
6. **记录结果**: 记录执行结果到 `TaskExecution` 表

## 数据库表结构

### plugins 表
- id: 主键
- name: 插件名称
- plugin_type: 插件类型
- description: 描述
- file_path: 插件文件路径
- is_active: 是否启用

### tasks 表
- id: 主键
- name: 任务名称
- plugin_id: 关联插件ID
- status: 状态（pending/running/success/failed/paused）
- trigger_type: 触发类型（manual/cron/interval）
- cron_expression: Cron表达式
- config: 任务配置（JSON）
- last_run_time: 最后执行时间
- next_run_time: 下次执行时间
- is_active: 是否启用

### task_executions 表
- id: 主键
- task_id: 关联任务ID
- status: 执行状态
- started_at: 开始时间
- finished_at: 结束时间
- result: 执行结果（JSON）
- error_message: 错误信息
- logs: 执行日志

### assets 表
- id: 主键
- asset_type: 资产类型
- uuid: 资产UUID（唯一标识）
- host_uuid: 主机UUID
- name: 资产名称
- data: 资产详细数据（JSON）
- source: 数据来源
- collected_at: 采集时间
- updated_at: 更新时间

## 环境变量

配置方式（推荐使用环境变量）：

- DB_NAME: 数据库名
- DB_USER: 数据库用户
- DB_PASSWORD: 数据库密码
- DB_HOST: 数据库主机
- DB_PORT: 数据库端口
- CELERY_BROKER_URL: Celery Broker URL
- CELERY_RESULT_BACKEND: Celery结果后端URL

## 启动顺序

1. 启动MySQL数据库
2. 启动Redis（Celery需要）
3. 运行数据库迁移：`python manage.py migrate`
4. 加载插件：`python manage.py load_plugins`
5. 启动Django服务：`python manage.py runserver`
6. 启动Celery Worker：`celery -A app.celery_app worker -l info`
7. 启动Celery Beat：`celery -A app.celery_app beat -l info`
8. 启动前端服务：`cd frontend && npm run serve`








