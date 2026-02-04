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
      </el-table>
    </el-card>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { pluginApi } from '../api/plugin'

export default {
  name: 'PluginList',
  setup() {
    const loading = ref(false)
    const plugins = ref([])
    
    const loadPlugins = async () => {
      loading.value = true
      try {
        const response = await pluginApi.getPlugins()
        // 处理分页响应格式：{count, next, previous, results: [...]}
        plugins.value = response.results || response || []
      } catch (error) {
        console.error('加载插件列表失败:', error)
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
    
    onMounted(() => {
      loadPlugins()
    })
    
    return {
      loading,
      plugins,
      getPluginTypeTag,
      getPluginTypeName
    }
  }
}
</script>
