<template>
  <div class="home">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>系统概览</span>
        </div>
      </template>
      <el-row :gutter="20">
        <el-col :span="6">
          <el-statistic title="插件总数" :value="stats.plugins" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="任务总数" :value="stats.tasks" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="运行中任务" :value="stats.runningTasks" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="资产总数" :value="stats.assets" />
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { pluginApi } from '../api/plugin'
import { taskApi } from '../api/task'
import api from '../api'

export default {
  name: 'Home',
  setup() {
    const stats = ref({
      plugins: 0,
      tasks: 0,
      runningTasks: 0,
      assets: 0
    })
    
    const loadStats = async () => {
      try {
        const [pluginsResp, tasksResp, assetsResp] = await Promise.all([
          pluginApi.getPlugins(),
          taskApi.getTasks(),
          api.get('/assets/')
        ])
        
        // 处理分页响应格式
        const plugins = pluginsResp.results || pluginsResp || []
        const tasks = tasksResp.results || tasksResp || []
        const assets = assetsResp.results || assetsResp || []
        
        stats.value = {
          plugins: Array.isArray(plugins) ? plugins.length : 0,
          tasks: Array.isArray(tasks) ? tasks.length : 0,
          runningTasks: Array.isArray(tasks) ? tasks.filter(t => t.status === 'running').length : 0,
          assets: assetsResp.count || (Array.isArray(assets) ? assets.length : 0)
        }
      } catch (error) {
        console.error('加载统计数据失败:', error)
      }
    }
    
    onMounted(() => {
      loadStats()
    })
    
    return {
      stats
    }
  }
}
</script>

<style scoped>
.home {
  max-width: 1200px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
