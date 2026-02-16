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
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
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
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { pluginApi } from '../api/plugin'
import { taskApi } from '../api/task'

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

    const loadPlugins = async () => {
      loading.value = true
      try {
        const response = await pluginApi.getPlugins()
        // 处理分页响应格式：{count, next, previous, results: [...]}
        plugins.value = response.results || response || []
      } catch (error) {
        console.error('加载插件列表失败:', error)
        ElMessage.error('加载插件列表失败')
        plugins.value = []
      } finally {
        loading.value = false
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
        // 获取所有任务
        const tasksResponse = await taskApi.getTasks({ page_size: 1000 })
        const tasks = tasksResponse.results || tasksResponse || []

        // 过滤出使用当前插件的任务
        const pluginTasks = tasks.filter(task => task.plugin_id === plugin.id)

        if (pluginTasks.length === 0) {
          executions.value = []
          loadingExecutions.value = false
          return
        }

        // 获取所有使用该插件的任务的执行记录
        const allExecutions = []
        for (const task of pluginTasks) {
          try {
            const execResponse = await taskApi.getTaskExecutions(task.id)
            const taskExecutions = execResponse.results || execResponse || []
            // 为每条执行记录添加任务名称
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

        // 按开始时间降序排序
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
      getPluginTypeTag,
      getPluginTypeName,
      getStatusTag,
      getStatusName,
      handleViewLogs,
      handleViewLogsDetail
    }
  }
}
</script>
