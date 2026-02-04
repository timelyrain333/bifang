<template>
  <div class="task-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>任务管理</span>
          <el-button type="primary" @click="handleCreate">
            <el-icon><Plus /></el-icon>
            新建任务
          </el-button>
        </div>
      </template>
      
      <el-table :data="tasks" v-loading="loading" stripe>
        <el-table-column prop="name" label="任务名称" width="200" />
        <el-table-column prop="plugin_name" label="关联插件" width="150" />
        <el-table-column prop="plugin_type" label="插件类型" width="120">
          <template #default="{ row }">
            <el-tag :type="getPluginTypeTag(row.plugin_type)">
              {{ getPluginTypeName(row.plugin_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusTag(row.status)">
              {{ getStatusName(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="trigger_type" label="触发类型" width="120">
          <template #default="{ row }">
            {{ getTriggerTypeName(row.trigger_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="cron_expression" label="Cron表达式" width="150" />
        <el-table-column prop="last_run_time" label="最后执行时间" width="180" />
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleExecute(row)" :disabled="row.status === 'running'">
              执行
            </el-button>
            <el-button size="small" type="primary" @click="handleEdit(row)">
              编辑
            </el-button>
            <el-button size="small" type="info" @click="handleViewExecutions(row)">
              历史
            </el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <!-- 分页组件 -->
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50, 100, 200]"
        :total="total"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handlePageSizeChange"
        @current-change="handlePageChange"
        style="margin-top: 20px; justify-content: flex-end;"
      />
    </el-card>
    
    <!-- 执行历史对话框 -->
    <el-dialog v-model="executionDialogVisible" title="执行历史" width="90%">
      <el-table :data="executions" stripe>
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
            <el-button size="small" type="info" @click="handleViewLogs(row)" v-if="row.logs">
              查看日志
            </el-button>
            <span v-else>无日志</span>
          </template>
        </el-table-column>
      </el-table>
      
      <!-- 日志查看对话框 -->
      <el-dialog v-model="logDialogVisible" title="执行日志" width="80%" append-to-body>
        <el-scrollbar height="500px">
          <pre style="white-space: pre-wrap; word-wrap: break-word; font-family: monospace; font-size: 12px;">{{ currentLogs }}</pre>
        </el-scrollbar>
      </el-dialog>
    </el-dialog>
  </div>
</template>

<script>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { taskApi } from '../api/task'

export default {
  name: 'TaskList',
  setup() {
    const router = useRouter()
    const loading = ref(false)
    const tasks = ref([])
    const executionDialogVisible = ref(false)
    const executions = ref([])
    const logDialogVisible = ref(false)
    const currentLogs = ref('')
    const currentPage = ref(1)
    const pageSize = ref(20)
    const total = ref(0)
    const eventSource = ref(null) // SSE连接
    
    const loadTasks = async () => {
      loading.value = true
      try {
        const params = {
          page: currentPage.value,
          page_size: pageSize.value
        }
        const response = await taskApi.getTasks(params)
        // 处理分页响应格式：{count, next, previous, results: [...]}
        tasks.value = response.results || response || []
        total.value = response.count || tasks.value.length
        console.log('任务列表加载:', {
          count: response.count,
          resultsCount: tasks.value.length,
          page: currentPage.value,
          pageSize: pageSize.value,
          tasks: tasks.value.map(t => ({ id: t.id, name: t.name }))
        })
      } catch (error) {
        console.error('加载任务列表失败:', error)
        ElMessage.error('加载任务列表失败')
        tasks.value = []
        total.value = 0
      } finally {
        loading.value = false
      }
    }
    
    // 更新单个任务的状态
    const updateTaskStatus = (taskId, taskData) => {
      console.log('updateTaskStatus 被调用:', { taskId, taskData, taskIdType: typeof taskId })
      console.log('当前任务列表:', tasks.value.map(t => ({ id: t.id, idType: typeof t.id, name: t.name, status: t.status })))
      
      // 确保taskId是数字类型
      const taskIdNum = typeof taskId === 'string' ? parseInt(taskId, 10) : taskId
      
      const index = tasks.value.findIndex(t => {
        const tId = typeof t.id === 'string' ? parseInt(t.id, 10) : t.id
        return tId === taskIdNum
      })
      
      if (index !== -1) {
        // 更新任务数据
        const oldStatus = tasks.value[index].status
        tasks.value[index] = {
          ...tasks.value[index],
          ...taskData,
          last_run_time: taskData.last_run_time || tasks.value[index].last_run_time
        }
        console.log(`✅ 任务状态已更新: task_id=${taskIdNum}, 从 ${oldStatus} 更新为 ${taskData.status}`)
      } else {
        // 如果任务不在当前页，可能需要重新加载列表
        console.warn(`⚠️ 任务 ${taskIdNum} 不在当前页，忽略更新。当前页任务ID:`, tasks.value.map(t => t.id))
      }
    }
    
    const handlePageChange = (page) => {
      currentPage.value = page
      loadTasks()
    }
    
    const handlePageSizeChange = (size) => {
      pageSize.value = size
      currentPage.value = 1
      loadTasks()
    }
    
    const handleCreate = () => {
      router.push('/tasks/new')
    }
    
    const handleEdit = (row) => {
      router.push(`/tasks/${row.id}/edit`)
    }
    
    const handleExecute = async (row) => {
      try {
        await ElMessageBox.confirm('确定要执行此任务吗？', '提示', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        })
        
        await taskApi.executeTask(row.id)
        ElMessage.success('任务已开始执行')
        // 刷新任务列表以获取最新状态
        await loadTasks()
        // SSE会自动推送状态更新
      } catch (error) {
        if (error !== 'cancel') {
          console.error('执行任务失败:', error)
          const errorMsg = error.response?.data?.error || error.response?.data?.message || error.message || '执行任务失败'
          ElMessage.error(errorMsg)
        }
      }
    }
    
    const handleDelete = async (row) => {
      try {
        await ElMessageBox.confirm('确定要删除此任务吗？', '提示', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        })
        
        await taskApi.deleteTask(row.id)
        ElMessage.success('删除成功')
        loadTasks()
      } catch (error) {
        if (error !== 'cancel') {
          ElMessage.error('删除失败')
        }
      }
    }
    
    const handleViewExecutions = async (row) => {
      try {
        const response = await taskApi.getTaskExecutions(row.id)
        // 处理分页响应格式
        executions.value = response.results || response || []
        executionDialogVisible.value = true
      } catch (error) {
        ElMessage.error('加载执行历史失败')
        executions.value = []
      }
    }
    
    const handleViewLogs = (row) => {
      currentLogs.value = row.logs || '无日志内容'
      logDialogVisible.value = true
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
    
    const getTriggerTypeName = (type) => {
      const map = {
        'manual': '手动执行',
        'cron': '定时执行',
        'interval': '间隔执行'
      }
      return map[type] || type
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
    
    // 启动SSE连接
    const startSSE = () => {
      // 如果已经有连接，先关闭
      stopSSE()
      
      try {
        // 建立SSE连接
        // EventSource会自动发送cookies，无需withCredentials选项
        const sseUrl = '/api/tasks/sse/'
        eventSource.value = new EventSource(sseUrl)
        
        // 监听消息
        eventSource.value.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            console.log('收到SSE消息:', data)
            
            if (data.type === 'connected') {
              // 连接成功消息
              console.log('SSE连接已建立:', data.message)
            } else if (data.type === 'task_update') {
              // 收到任务状态更新
              console.log('收到任务状态更新:', {
                task_id: data.task_id,
                task_data: data.data,
                status: data.data?.status
              })
              if (data.task_id && data.data) {
                updateTaskStatus(data.task_id, data.data)
              } else {
                console.warn('任务状态更新数据不完整:', data)
              }
            } else if (data.type === 'heartbeat') {
              // 心跳消息，保持连接
              console.debug('收到SSE心跳')
            } else if (data.type === 'error') {
              console.error('SSE错误:', data.message)
            } else {
              // 未知类型的消息
              console.warn('收到未知类型的SSE消息:', data)
            }
          } catch (error) {
            console.error('解析SSE消息失败:', error, event.data)
          }
        }
        
        // 监听连接打开
        eventSource.value.onopen = () => {
          console.log('✅ SSE连接已打开，readyState:', eventSource.value?.readyState, 'URL:', sseUrl)
        }
        
        // 监听错误
        eventSource.value.onerror = (error) => {
          const readyState = eventSource.value?.readyState
          console.error('SSE连接错误:', {
            error,
            readyState,
            readyStateText: readyState === EventSource.CONNECTING ? 'CONNECTING' : 
                           readyState === EventSource.OPEN ? 'OPEN' : 
                           readyState === EventSource.CLOSED ? 'CLOSED' : 'UNKNOWN',
            url: sseUrl
          })
          
          // 连接断开时，尝试重新连接
          if (readyState === EventSource.CLOSED) {
            console.log('SSE连接已关闭，5秒后尝试重连...')
            setTimeout(() => {
              if (eventSource.value?.readyState === EventSource.CLOSED) {
                startSSE()
              }
            }, 5000)
          }
        }
        
        console.log('SSE连接已建立')
      } catch (error) {
        console.error('建立SSE连接失败:', error)
      }
    }
    
    // 停止SSE连接
    const stopSSE = () => {
      if (eventSource.value) {
        eventSource.value.close()
        eventSource.value = null
        console.log('SSE连接已关闭')
      }
    }
    
    onMounted(async () => {
      await loadTasks()
      // 启动SSE连接以接收实时状态更新
      startSSE()
    })
    
    // 组件卸载前清理SSE连接
    onBeforeUnmount(() => {
      stopSSE()
    })
    
    return {
      loading,
      tasks,
      executionDialogVisible,
      executions,
      logDialogVisible,
      currentLogs,
      currentPage,
      pageSize,
      total,
      handleCreate,
      handleEdit,
      handleExecute,
      handleDelete,
      handleViewExecutions,
      handleViewLogs,
      handlePageChange,
      handlePageSizeChange,
      getStatusTag,
      getStatusName,
      getTriggerTypeName,
      getPluginTypeTag,
      getPluginTypeName
    }
  }
}
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
