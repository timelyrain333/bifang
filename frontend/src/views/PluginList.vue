<template>
  <div class="plugin-list">
    <el-card>
      <template #header>
        <span>插件管理</span>
      </template>

      <el-table :data="plugins" v-loading="loading" stripe>
        <el-table-column prop="name" label="插件名称" width="200" />
        <el-table-column prop="plugin_type" label="插件类型" width="120">
          <template #default="{ row }">
            <el-tag :type="getPluginTypeTag(row.plugin_type)">
              {{ getPluginTypeName(row.plugin_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" show-overflow-tooltip />
        <el-table-column prop="is_active" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="handleCreateTask(row)"
                       v-if="row.name === 'collect_asset_monitor'">
              创建任务
            </el-button>
            <el-button size="small" type="info" @click="handleViewLogs(row)">
              查看日志
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 执行历史对话框 -->
    <el-dialog v-model="executionDialogVisible" :title="`${currentPlugin?.name} - 运行日志`" width="90%">
      <el-table :data="executions" stripe v-loading="loadingExecutions">
        <el-table-column prop="task_name" label="任务名称" width="200" show-overflow-tooltip />
        <el-table-column prop="started_at" label="开始时间" width="180" />
        <el-table-column prop="finished_at" label="结束时间" width="180" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusTag(row.status)">
              {{ getStatusName(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="error_message" label="错误信息" show-overflow-tooltip />
        <el-table-column label="执行日志" width="120">
          <template #default="{ row }">
            <el-button size="small" type="info" @click="handleViewLogsDetail(row)" v-if="row.logs">
              查看日志
            </el-button>
            <span v-else>无日志</span>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loadingExecutions && executions.length === 0" description="暂无运行记录" />
    </el-dialog>

    <!-- 日志详情对话框 -->
    <el-dialog v-model="logDialogVisible" title="执行日志" width="80%" append-to-body>
      <el-scrollbar height="500px">
        <pre style="white-space: pre-wrap; word-wrap: break-word; font-family: monospace; font-size: 12px;">{{ currentLogs }}</pre>
      </el-scrollbar>
    </el-dialog>

    <!-- 创建任务对话框 -->
    <el-dialog v-model="taskDialogVisible" title="创建资产监测任务" width="600px">
      <el-form :model="taskForm" label-width="150px">
        <el-form-item label="任务名称" required>
          <el-input v-model="taskForm.name" placeholder="请输入任务名称" />
        </el-form-item>

        <el-form-item label="触发类型">
          <el-select v-model="taskForm.trigger_type" placeholder="选择触发类型">
            <el-option label="手动执行" value="manual" />
            <el-option label="定时执行" value="cron" />
          </el-select>
        </el-form-item>

        <el-form-item label="Cron表达式" v-if="taskForm.trigger_type === 'cron'">
          <el-input v-model="taskForm.cron_expression" placeholder="例如: 0 */6 * * * (每6小时)" />
          <div class="form-tip">格式: 分 时 日 月 周，如 0 */6 * * * 表示每6小时执行一次</div>
        </el-form-item>

        <el-divider content-position="left">监测配置</el-divider>

        <el-form-item label="监测资产类型">
          <el-select v-model="taskForm.config.asset_types" multiple placeholder="选择要监测的资产类型">
            <el-option label="ECS云服务器" value="ecs_instance" />
            <el-option label="VPC专有网络" value="vpc" />
            <el-option label="负载均衡" value="slb" />
            <el-option label="云数据库" value="rds" />
          </el-select>
        </el-form-item>

        <el-divider content-position="left">通知配置</el-divider>

        <el-form-item label="启用钉钉通知">
          <el-switch v-model="taskForm.config.enable_dingtalk" />
        </el-form-item>

        <el-form-item label="通知配置" v-if="taskForm.config.enable_dingtalk">
          <el-select v-model="taskForm.config.notification_config_id" placeholder="选择钉钉配置">
            <el-option v-for="config in aliyunConfigs"
                       :key="config.id"
                       :label="config.name"
                       :value="config.id" />
          </el-select>
          <div class="form-tip">选择已配置钉钉Webhook的系统配置</div>
        </el-form-item>

        <el-form-item label="新增资产时通知" v-if="taskForm.config.enable_dingtalk">
          <el-switch v-model="taskForm.config.notify_on_add" />
        </el-form-item>

        <el-form-item label="删除资产时通知" v-if="taskForm.config.enable_dingtalk">
          <el-switch v-model="taskForm.config.notify_on_delete" />
        </el-form-item>

        <el-form-item label="属性变更时通知" v-if="taskForm.config.enable_dingtalk">
          <el-switch v-model="taskForm.config.notify_on_modify" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="taskDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitTask" :loading="submitting">创建任务</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { pluginApi } from '../api/plugin'
import { taskApi } from '../api/task'
import { aliyunConfigApi } from '../api/aliyunConfig'

export default {
  name: 'PluginList',
  setup() {
    const loading = ref(false)
    const plugins = ref([])
    const executionDialogVisible = ref(false)
    const executions = ref([])
    const loadingExecutions = ref(false)
    const logDialogVisible = ref(false)
    const currentLogs = ref('')
    const currentPlugin = ref(null)

    // 任务相关
    const taskDialogVisible = ref(false)
    const submitting = ref(false)
    const aliyunConfigs = ref([])
    const taskForm = ref({
      name: '',
      plugin: null,
      trigger_type: 'cron',
      cron_expression: '0 */6 * * *',
      is_active: true,
      config: {
        asset_types: ['ecs_instance'],
        source: 'aliyun_ecs',
        enable_dingtalk: true,
        notification_config_id: null,
        notify_on_add: true,
        notify_on_delete: true,
        notify_on_modify: false
      }
    })

    const loadPlugins = async () => {
      loading.value = true
      try {
        const response = await pluginApi.getPlugins()
        plugins.value = response.results || response || []
      } catch (error) {
        console.error('加载插件列表失败:', error)
        ElMessage.error('加载插件列表失败')
        plugins.value = []
      } finally {
        loading.value = false
      }
    }

    const loadAliyunConfigs = async () => {
      try {
        const response = await aliyunConfigApi.getConfigs()
        const configs = response.results || response || []
        // 只显示启用了钉钉的配置
        aliyunConfigs.value = configs.filter(c => c.dingtalk_enabled && c.is_active)
      } catch (error) {
        console.error('加载阿里云配置失败:', error)
      }
    }

    const getPluginTypeTag = (type) => {
      const map = {
        'data': 'primary',
        'collect': 'success',
        'risk': 'warning',
        'dump': 'info',
        'alarm': 'danger'
      }
      return map[type] || 'info'
    }

    const getPluginTypeName = (type) => {
      const map = {
        'data': '数据记录',
        'collect': '数据采集',
        'risk': '风险检测',
        'dump': '数据导出',
        'alarm': '告警'
      }
      return map[type] || type
    }

    const getStatusTag = (status) => {
      const map = {
        'pending': 'info',
        'running': 'warning',
        'success': 'success',
        'failed': 'danger',
        'paused': 'info'
      }
      return map[status] || 'info'
    }

    const getStatusName = (status) => {
      const map = {
        'pending': '待执行',
        'running': '执行中',
        'success': '成功',
        'failed': '失败',
        'paused': '已暂停'
      }
      return map[status] || status
    }

    const handleViewLogs = async (plugin) => {
      currentPlugin.value = plugin
      loadingExecutions.value = true
      executionDialogVisible.value = true

      try {
        const tasksResponse = await taskApi.getTasks({ page_size: 1000 })
        const tasks = tasksResponse.results || tasksResponse || []
        const pluginTasks = tasks.filter(task => task.plugin === plugin.id || task.plugin_id === plugin.id)

        if (pluginTasks.length === 0) {
          executions.value = []
          loadingExecutions.value = false
          return
        }

        const allExecutions = []
        for (const task of pluginTasks) {
          try {
            const execResponse = await taskApi.getTaskExecutions(task.id)
            const taskExecutions = execResponse.results || execResponse || []
            taskExecutions.forEach(exec => {
              allExecutions.push({
                ...exec,
                task_name: task.name,
                task_id: task.id
              })
            })
          } catch (error) {
            console.error(`获取任务 ${task.id} 的执行记录失败:`, error)
          }
        }

        allExecutions.sort((a, b) => {
          const timeA = a.started_at ? new Date(a.started_at).getTime() : 0
          const timeB = b.started_at ? new Date(b.started_at).getTime() : 0
          return timeB - timeA
        })

        executions.value = allExecutions
      } catch (error) {
        console.error('加载运行日志失败:', error)
        ElMessage.error('加载运行日志失败')
        executions.value = []
      } finally {
        loadingExecutions.value = false
      }
    }

    const handleViewLogsDetail = (row) => {
      currentLogs.value = row.logs || '无日志内容'
      logDialogVisible.value = true
    }

    const handleCreateTask = async (plugin) => {
      currentPlugin.value = plugin
      taskForm.value = {
        name: `${plugin.name} 任务`,
        plugin: plugin.id,
        trigger_type: 'cron',
        cron_expression: '0 */6 * * *',
        is_active: true,
        config: {
          asset_types: ['ecs_instance'],
          source: 'aliyun_ecs',
          enable_dingtalk: true,
          notification_config_id: null,
          notify_on_add: true,
          notify_on_delete: true,
          notify_on_modify: false
        }
      }
      await loadAliyunConfigs()
      taskDialogVisible.value = true
    }

    const submitTask = async () => {
      if (!taskForm.value.name) {
        ElMessage.warning('请输入任务名称')
        return
      }

      if (taskForm.value.config.asset_types.length === 0) {
        ElMessage.warning('请选择至少一个资产类型')
        return
      }

      if (taskForm.value.config.enable_dingtalk && !taskForm.value.config.notification_config_id) {
        ElMessage.warning('请选择钉钉通知配置')
        return
      }

      submitting.value = true
      try {
        // 将 asset_types 数组转换为逗号分隔的字符串
        const submitData = {
          ...taskForm.value,
          config: {
            ...taskForm.value.config,
            asset_types: taskForm.value.config.asset_types.join(',')
          }
        }

        await taskApi.createTask(submitData)
        ElMessage.success('任务创建成功')
        taskDialogVisible.value = false
      } catch (error) {
        console.error('创建任务失败:', error)
        ElMessage.error(error.response?.data?.detail || '创建任务失败')
      } finally {
        submitting.value = false
      }
    }

    onMounted(() => {
      loadPlugins()
    })

    return {
      loading,
      plugins,
      executionDialogVisible,
      executions,
      loadingExecutions,
      logDialogVisible,
      currentLogs,
      currentPlugin,
      taskDialogVisible,
      submitting,
      aliyunConfigs,
      taskForm,
      getPluginTypeTag,
      getPluginTypeName,
      getStatusTag,
      getStatusName,
      handleViewLogs,
      handleViewLogsDetail,
      handleCreateTask,
      submitTask
    }
  }
}
</script>

<style scoped>
.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
</style>
