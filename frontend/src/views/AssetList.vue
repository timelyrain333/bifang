<template>
  <div class="asset-list">
    <el-card>
      <template #header>
        <span>{{ pageTitle }}</span>
      </template>
      
      <el-form :inline="true" :model="filters" class="filter-form">
        <el-form-item label="资产类型">
          <el-select 
            v-model="filters.asset_type" 
            placeholder="请选择资产类型（可多选）" 
            multiple
            collapse-tags
            collapse-tags-tooltip
            clearable
            style="width: 300px;"
          >
            <el-option label="服务器" value="server" />
            <el-option label="账户" value="account" />
            <el-option label="端口" value="port" />
            <el-option label="进程" value="process" />
            <el-option label="中间件" value="middleware" />
            <el-option label="数据库" value="database" />
            <el-option label="Web服务" value="web_service" />
            <el-option label="软件" value="software" />
            <el-option label="计划任务" value="cron_task" />
            <el-option label="启动项" value="startup_item" />
            <el-option label="内核模块" value="kernel_module" />
            <el-option label="Web站点" value="web_site" />
            <el-option label="AI组件" value="ai_component" />
            <el-option label="IDC探针发现" value="idc_probe" />
          </el-select>
        </el-form-item>
        <el-form-item label="名称">
          <el-input 
            v-model="filters.name" 
            placeholder="输入名称关键词" 
            clearable
            style="width: 200px;"
            @keyup.enter="loadAssets"
          />
        </el-form-item>
        <el-form-item label="内网IP">
          <el-input 
            v-model="filters.intranet_ip" 
            placeholder="输入内网IP" 
            clearable
            style="width: 150px;"
            @keyup.enter="loadAssets"
          />
        </el-form-item>
        <el-form-item label="公网IP">
          <el-input 
            v-model="filters.internet_ip" 
            placeholder="输入公网IP" 
            clearable
            style="width: 150px;"
            @keyup.enter="loadAssets"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleQuery" :icon="Search">查询</el-button>
          <el-button @click="resetFilters" :icon="Refresh">重置</el-button>
          <el-button type="success" @click="handleExport" :loading="exporting">导出Excel</el-button>
        </el-form-item>
      </el-form>
      
      <el-table 
        :data="assets" 
        v-loading="loading" 
        stripe
        ref="tableRef"
      >
        <el-table-column 
          prop="asset_type" 
          label="资产类型" 
          width="180"
          column-key="asset_type"
        >
          <template #header>
            <div style="display: flex; align-items: center;">
              <span>资产类型</span>
              <el-select
                v-model="tableFilters.asset_type"
                placeholder="筛选"
                multiple
                collapse-tags
                collapse-tags-tooltip
                size="small"
                style="width: 150px; margin-left: 8px;"
                @change="loadAssets"
                clearable
              >
                <el-option label="服务器" value="server" />
                <el-option label="账户" value="account" />
                <el-option label="端口" value="port" />
                <el-option label="进程" value="process" />
                <el-option label="中间件" value="middleware" />
                <el-option label="数据库" value="database" />
                <el-option label="Web服务" value="web_service" />
                <el-option label="软件" value="software" />
                <el-option label="计划任务" value="cron_task" />
                <el-option label="启动项" value="startup_item" />
                <el-option label="内核模块" value="kernel_module" />
                <el-option label="Web站点" value="web_site" />
                <el-option label="AI组件" value="ai_component" />
                <el-option label="IDC探针发现" value="idc_probe" />
              </el-select>
            </div>
          </template>
          <template #default="{ row }">
            {{ getAssetTypeName(row.asset_type) }}
          </template>
        </el-table-column>
        <el-table-column 
          prop="name" 
          label="名称" 
          width="200"
          column-key="name"
        >
          <template #header>
            <div style="display: flex; align-items: center;">
              <span>名称</span>
              <el-input
                v-model="filters.name"
                placeholder="筛选名称"
                size="small"
                style="width: 120px; margin-left: 8px;"
                @input="loadAssets"
                clearable
              />
            </div>
          </template>
        </el-table-column>
        <el-table-column 
          label="内网IP" 
          width="150"
          column-key="intranet_ip"
        >
          <template #header>
            <div style="display: flex; align-items: center;">
              <span>内网IP</span>
              <el-input
                v-model="filters.intranet_ip"
                placeholder="筛选内网IP"
                size="small"
                style="width: 120px; margin-left: 8px;"
                @input="loadAssets"
                @keyup.enter="loadAssets"
                clearable
              />
            </div>
          </template>
          <template #default="{ row }">
            {{ getIntranetIp(row) || '-' }}
          </template>
        </el-table-column>
        <el-table-column 
          label="公网IP" 
          width="150"
          column-key="internet_ip"
        >
          <template #header>
            <div style="display: flex; align-items: center;">
              <span>公网IP</span>
              <el-input
                v-model="filters.internet_ip"
                placeholder="筛选公网IP"
                size="small"
                style="width: 120px; margin-left: 8px;"
                @input="loadAssets"
                @keyup.enter="loadAssets"
                clearable
              />
            </div>
          </template>
          <template #default="{ row }">
            {{ getInternetIp(row) || '-' }}
          </template>
        </el-table-column>
        <el-table-column 
          prop="uuid" 
          label="UUID" 
          width="250" 
          show-overflow-tooltip
          column-key="uuid"
        >
          <template #header>
            <div style="display: flex; align-items: center;">
              <span>UUID</span>
              <el-input
                v-model="filters.uuid"
                placeholder="筛选UUID"
                size="small"
                style="width: 200px; margin-left: 8px;"
                @input="loadAssets"
                @keyup.enter="loadAssets"
                clearable
              />
            </div>
          </template>
        </el-table-column>
        <el-table-column 
          prop="host_uuid" 
          label="主机UUID" 
          width="250" 
          show-overflow-tooltip
          column-key="host_uuid"
        >
          <template #header>
            <div style="display: flex; align-items: center;">
              <span>主机UUID</span>
              <el-input
                v-model="filters.host_uuid"
                placeholder="筛选主机UUID"
                size="small"
                style="width: 200px; margin-left: 8px;"
                @input="loadAssets"
                @keyup.enter="loadAssets"
                clearable
              />
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="source" label="数据来源" width="150" />
        <el-table-column prop="collected_at" label="采集时间" width="180" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="showDetail(row)">
              查看详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <!-- 资产详情对话框 -->
      <el-dialog
        v-model="detailDialogVisible"
        :title="`${getAssetTypeName(currentAsset?.asset_type)}详情`"
        width="80%"
        :close-on-click-modal="false"
      >
        <div v-if="currentAsset" class="asset-detail">
          <!-- 基本信息 -->
          <el-card class="detail-card" shadow="never">
            <template #header>
              <span>基本信息</span>
            </template>
            <el-descriptions :column="3" border>
              <el-descriptions-item label="资产类型">
                {{ getAssetTypeName(currentAsset.asset_type) }}
              </el-descriptions-item>
              <el-descriptions-item label="名称">
                {{ currentAsset.name || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="UUID">
                {{ currentAsset.uuid }}
              </el-descriptions-item>
              <el-descriptions-item label="主机UUID">
                {{ currentAsset.host_uuid || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="内网IP">
                {{ getIntranetIp(currentAsset) || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="公网IP">
                {{ getInternetIp(currentAsset) || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="数据来源">
                {{ currentAsset.source }}
              </el-descriptions-item>
              <el-descriptions-item label="采集时间">
                {{ formatDateTime(currentAsset.collected_at) }}
              </el-descriptions-item>
            </el-descriptions>
          </el-card>
          
          <!-- 服务器信息（如果有host_uuid） -->
          <el-card v-if="serverInfo && currentAsset.host_uuid" class="detail-card" shadow="never">
            <template #header>
              <span>服务器信息</span>
            </template>
            <el-descriptions :column="3" border>
              <el-descriptions-item label="服务器名称">
                {{ serverInfo.name || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="内网IP">
                {{ serverInfo.data?.IntranetIp || serverInfo.data?.Ip || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="公网IP">
                {{ serverInfo.data?.InternetIp || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="实例ID">
                {{ serverInfo.data?.InstanceId || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="操作系统">
                {{ serverInfo.data?.Os || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="状态">
                {{ serverInfo.data?.Status || '-' }}
              </el-descriptions-item>
            </el-descriptions>
          </el-card>
          
          <!-- 详细数据 -->
          <el-card class="detail-card" shadow="never">
            <template #header>
              <span>详细信息</span>
            </template>
            <el-descriptions :column="getDetailColumns(currentAsset.asset_type)" border>
              <template v-for="(value, key) in currentAsset.data" :key="key">
                <el-descriptions-item :label="getFieldLabel(key, currentAsset.asset_type)">
                  {{ formatFieldValue(key, value, currentAsset.asset_type) }}
                </el-descriptions-item>
              </template>
            </el-descriptions>
          </el-card>
        </div>
        
        <template #footer>
          <el-button @click="detailDialogVisible = false">关闭</el-button>
        </template>
      </el-dialog>
      
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50, 100]"
        :total="total"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadAssets"
        @current-change="loadAssets"
      />
    </el-card>
  </div>
</template>

<script>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Search, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '../api'

export default {
  name: 'AssetList',
  setup() {
    const route = useRoute()
    // 根据路由 meta.source 确定当前展示的云：aws_inspector | aliyun_security
    const cloudSource = computed(() => route.meta.source || 'aliyun_security')
    const pageTitle = computed(() => {
      return route.meta.source === 'aws_inspector' ? 'AWS 资产' : '阿里云资产'
    })
    const loading = ref(false)
    const assets = ref([])
    const total = ref(0)
    const currentPage = ref(1)
    const pageSize = ref(20)
    const detailDialogVisible = ref(false)
    const currentAsset = ref(null)
    const serverInfo = ref(null)
    const tableRef = ref(null)
    const exporting = ref(false)
    
    const filters = reactive({
      asset_type: [], // 改为数组支持多选
      name: '',
      intranet_ip: '',
      internet_ip: '',
      uuid: '',
      host_uuid: ''
    })
    
    // 表格筛选器（与查询表单独立）
    const tableFilters = reactive({
      asset_type: []
    })
    
    const loadAssets = async () => {
      loading.value = true
      try {
        // 合并查询表单和表格筛选器的资产类型
        const selectedTypes = []
        if (filters.asset_type && filters.asset_type.length > 0) {
          selectedTypes.push(...filters.asset_type)
        }
        if (tableFilters.asset_type && tableFilters.asset_type.length > 0) {
          selectedTypes.push(...tableFilters.asset_type)
        }
        const uniqueTypes = [...new Set(selectedTypes)]
        
        // 判断是否有其他筛选条件（名称、IP、UUID等）
        const hasOtherFilters = !!(filters.name || filters.intranet_ip || filters.internet_ip || filters.uuid || filters.host_uuid)
        
        // 判断是否需要前端筛选
        // 只有在没有类型选择，或有其他筛选条件时才需要前端筛选
        // 如果有类型选择且无其他筛选条件，应该使用后端筛选
        const needFrontendFilter = uniqueTypes.length === 0 || hasOtherFilters
        
        // 构建API请求参数
        const params = {}
        if (cloudSource.value) {
          params.source = cloudSource.value
        }
        
        // 如果选择了资产类型，且没有其他筛选条件，可以在后端筛选以提高性能
        if (uniqueTypes.length > 0 && !hasOtherFilters) {
          // 有类型选择且无其他筛选条件：后端筛选，使用正常分页
          // Axios会自动将数组参数转换为多个同名参数，如：?asset_type=server&asset_type=account
          if (uniqueTypes.length === 1) {
            params.asset_type = uniqueTypes[0]
          } else {
            // 多个类型：使用数组，Axios会自动处理为多个同名参数
            params.asset_type = uniqueTypes
          }
          params.page = currentPage.value
          params.page_size = pageSize.value
        } else {
          // 无类型选择或有其他筛选条件：需要获取更多数据以便前端筛选
          // 增大page_size以获取足够的数据进行前端筛选
          params.page = 1 // 前端筛选时，先从第一页获取足够的数据
          params.page_size = 1000 // 获取足够多的数据
        }
        
        const response = await api.get('/assets/', { params })
        // 处理分页响应格式：{count, next, previous, results: [...]}
        let allAssets = response.results || (Array.isArray(response) ? response : [])
        
        console.log('API请求参数:', params)
        console.log('API返回:', {
          count: response.count,
          resultsCount: allAssets.length,
          selectedTypes: uniqueTypes,
          needFrontendFilter: needFrontendFilter,
          hasNext: !!response.next
        })
        
        // 如果需要前端筛选（多个类型、无类型选择、或有其他筛选条件）
        if (needFrontendFilter) {
          // 前端筛选（合并查询表单和表格筛选器）
          allAssets = allAssets.filter(asset => {
            // 资产类型筛选（支持多选）
            if (uniqueTypes.length > 0) {
              if (!uniqueTypes.includes(asset.asset_type)) {
                return false
              }
            }
            
            // 名称筛选
            if (filters.name && asset.name) {
              if (!asset.name.toString().toLowerCase().includes(filters.name.toLowerCase())) {
                return false
              }
            }
            
            // 内网IP筛选
            if (filters.intranet_ip) {
              const ip = getIntranetIp(asset)
              if (!ip || !ip.toString().toLowerCase().includes(filters.intranet_ip.toLowerCase())) {
                return false
              }
            }
            
            // 公网IP筛选
            if (filters.internet_ip) {
              const ip = getInternetIp(asset)
              if (!ip || !ip.toString().toLowerCase().includes(filters.internet_ip.toLowerCase())) {
                return false
              }
            }
            
            // UUID筛选
            if (filters.uuid && asset.uuid) {
              if (!asset.uuid.toString().toLowerCase().includes(filters.uuid.toLowerCase())) {
                return false
              }
            }
            
            // 主机UUID筛选
            if (filters.host_uuid && asset.host_uuid) {
              if (!asset.host_uuid.toString().toLowerCase().includes(filters.host_uuid.toLowerCase())) {
                return false
              }
            }
            
            return true
          })
          
          // 保存筛选后的总数（用于分页计算）
          const filteredTotal = allAssets.length
          
          console.log('前端筛选完成:', {
            beforeFilter: response.results?.length || 0,
            afterFilter: filteredTotal,
            selectedTypes: uniqueTypes
          })
          
          // 前端分页处理（如果使用了前端筛选）
          const start = (currentPage.value - 1) * pageSize.value
          const end = start + pageSize.value
          allAssets = allAssets.slice(start, end)
          
          // 使用筛选后的总数
          total.value = filteredTotal
        } else {
          // 没有前端筛选，使用后端返回的count
          total.value = response.count || allAssets.length
        }
        
        console.log('最终结果:', {
          displayedAssets: allAssets.length,
          total: total.value,
          currentPage: currentPage.value,
          pageSize: pageSize.value
        })
        
        assets.value = allAssets
      } catch (error) {
        console.error('加载资产列表失败:', error)
        assets.value = []
        total.value = 0
      } finally {
        loading.value = false
      }
    }
    
    // 处理查询按钮点击
    const handleQuery = () => {
      currentPage.value = 1 // 查询时重置到第一页
      loadAssets()
    }
    
    const resetFilters = () => {
      filters.asset_type = []
      filters.name = ''
      filters.intranet_ip = ''
      filters.internet_ip = ''
      filters.uuid = ''
      filters.host_uuid = ''
      tableFilters.asset_type = []
      currentPage.value = 1
      loadAssets()
    }
    
    // 导出Excel功能
    const handleExport = async () => {
      exporting.value = true
      try {
        // 合并查询表单和表格筛选器的资产类型
        const selectedTypes = []
        if (filters.asset_type && filters.asset_type.length > 0) {
          selectedTypes.push(...filters.asset_type)
        }
        if (tableFilters.asset_type && tableFilters.asset_type.length > 0) {
          selectedTypes.push(...tableFilters.asset_type)
        }
        const uniqueTypes = [...new Set(selectedTypes)]
        
        // 构建导出参数（使用与查询相同的筛选条件）
        const params = {}
        if (cloudSource.value) {
          params.source = cloudSource.value
        }
        
        // 添加筛选参数
        if (uniqueTypes.length > 0) {
          if (uniqueTypes.length === 1) {
            params.asset_type = uniqueTypes[0]
          } else {
            params.asset_type = uniqueTypes
          }
        }
        if (filters.name) {
          params.name = filters.name
        }
        if (filters.intranet_ip) {
          params.intranet_ip = filters.intranet_ip
        }
        if (filters.internet_ip) {
          params.internet_ip = filters.internet_ip
        }
        if (filters.uuid) {
          params.uuid = filters.uuid
        }
        if (filters.host_uuid) {
          params.host_uuid = filters.host_uuid
        }
        
        // 调用导出接口，使用axios原生方法以支持blob响应
        const axios = (await import('axios')).default
        const response = await axios.get('/api/assets/export/', {
          params,
          responseType: 'blob',
          withCredentials: true
        })
        
        // 创建下载链接
        const blob = new Blob([response.data], { 
          type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' 
        })
        const url = window.URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        
        // 从响应头获取文件名，如果没有则使用默认名称
        const contentDisposition = response.headers['content-disposition'] || ''
        let filename = `资产数据导出_${new Date().toISOString().slice(0, 19).replace(/[:-]/g, '')}.xlsx`
        if (contentDisposition) {
          const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
          if (filenameMatch && filenameMatch[1]) {
            filename = decodeURIComponent(filenameMatch[1].replace(/['"]/g, ''))
          }
        }
        
        link.download = filename
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        window.URL.revokeObjectURL(url)
        
        // 显示成功消息
        ElMessage.success('导出成功！')
      } catch (error) {
        console.error('导出失败:', error)
        // 如果是错误响应，尝试读取错误信息
        if (error.response && error.response.data) {
          try {
            const text = await error.response.data.text()
            const errorData = JSON.parse(text)
            ElMessage.error(errorData.error || '导出失败')
          } catch {
            ElMessage.error('导出失败，请稍后重试')
          }
        } else {
          ElMessage.error('导出失败，请稍后重试')
        }
      } finally {
        exporting.value = false
      }
    }
    
    const getAssetTypeName = (type) => {
      const typeMap = {
        'server': '服务器',
        'account': '账户',
        'port': '端口',
        'process': '进程',
        'middleware': '中间件',
        'database': '数据库',
        'web_service': 'Web服务',
        'software': '软件',
        'cron_task': '计划任务',
        'startup_item': '启动项',
        'kernel_module': '内核模块',
        'web_site': 'Web站点',
        'ai_component': 'AI组件',
        'idc_probe': 'IDC探针发现'
      }
      return typeMap[type] || type
    }
    
    // 获取服务器信息
    const loadServerInfo = async (hostUuid) => {
      if (!hostUuid) {
        serverInfo.value = null
        return
      }
      try {
        // 先尝试通过uuid精确匹配（服务器资产的uuid应该等于host_uuid）
        const response = await api.get('/assets/', {
          params: {
            asset_type: 'server',
            page_size: 100  // 获取更多结果以便查找
          }
        })
        if (response.results && response.results.length > 0) {
          // 首先查找uuid等于host_uuid的服务器资产
          let server = response.results.find(asset => asset.uuid === hostUuid)
          
          // 如果没找到，尝试通过host_uuid字段匹配
          if (!server) {
            server = response.results.find(asset => asset.host_uuid === hostUuid)
          }
          
          // 如果还是没找到，尝试部分匹配（处理UUID格式变化的情况）
          if (!server) {
            server = response.results.find(asset => 
              (asset.uuid && asset.uuid.includes(hostUuid)) ||
              (asset.host_uuid && asset.host_uuid.includes(hostUuid))
            )
          }
          
          serverInfo.value = server || null
        } else {
          serverInfo.value = null
        }
      } catch (error) {
        console.error('加载服务器信息失败:', error)
        serverInfo.value = null
      }
    }
    
    // 显示详情
    const showDetail = async (asset) => {
      currentAsset.value = asset
      detailDialogVisible.value = true
      
      // 如果有host_uuid，加载服务器信息
      if (asset.host_uuid) {
        await loadServerInfo(asset.host_uuid)
      } else {
        serverInfo.value = null
      }
    }
    
    // 格式化日期时间
    const formatDateTime = (dateStr) => {
      if (!dateStr) return '-'
      const date = new Date(dateStr)
      return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      })
    }
    
    // 格式化时间戳
    const formatTimestamp = (timestamp) => {
      if (!timestamp) return '-'
      if (timestamp === 'never' || timestamp === 'Never') return '永不过期'
      
      // 处理毫秒级时间戳
      let ts = timestamp
      if (typeof ts === 'string' && /^\d+$/.test(ts)) {
        ts = parseInt(ts)
      }
      if (typeof ts === 'number') {
        // 如果时间戳小于10000000000，认为是秒级，否则是毫秒级
        if (ts < 10000000000) {
          ts = ts * 1000
        }
        const date = new Date(ts)
        return date.toLocaleString('zh-CN', {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit'
        })
      }
      return timestamp
    }
    
    // 格式化字段值
    const formatFieldValue = (key, value, assetType) => {
      if (value === null || value === undefined || value === '') {
        return '-'
      }
      
      // 布尔值处理
      if (typeof value === 'boolean' || 
          (typeof value === 'number' && (value === 0 || value === 1))) {
        return value === true || value === 1 ? '是' : '否'
      }
      
      // 字符串形式的布尔值
      if (typeof value === 'string') {
        if (value === '1' || value.toLowerCase() === 'true' || value.toLowerCase() === 'yes') {
          return '是'
        }
        if (value === '0' || value.toLowerCase() === 'false' || value.toLowerCase() === 'no') {
          return '否'
        }
      }
      
      // 时间戳字段
      const timestampKeys = ['LastLoginTimestamp', 'LastLoginTimeDt', 'CreateTimestamp', 
                            'ProcessStarted', 'CreateTime', 'ModifyTime', 'UpdateTime']
      if (timestampKeys.includes(key) || key.includes('Timestamp') || key.includes('Time')) {
        return formatTimestamp(value)
      }
      
      // 数组处理
      if (Array.isArray(value)) {
        return value.join(', ') || '-'
      }
      
      // 对象处理
      if (typeof value === 'object') {
        return JSON.stringify(value, null, 2)
      }
      
      return String(value)
    }
    
    // 获取字段中文标签
    const getFieldLabel = (key, assetType) => {
      const labelMap = {
        // 账户类型
        'User': '账号',
        'IsRoot': 'ROOT权限',
        'GroupNames': '用户组',
        'AccountsExpirationDate': '用户到期时间',
        'IsPasswdExpired': '密码是否过期',
        'IsPasswdLocked': '密码是否锁定',
        'IsUserExpired': '用户是否过期',
        'IsSudoer': '是否sudo账户',
        'IsCouldLogin': '是否交互登录账号',
        'LastLoginTime': '上次登录时间',
        'LastLoginTimestamp': '上次登录时间',
        'LastLoginTimeDt': '上次登录时间',
        'CreateTimestamp': '最新扫描时间',
        'PasswordExpirationDate': '密码到期时间',
        'LastLoginIp': '上次登录IP',
        'Status': '状态',
        'InstanceId': '实例ID',
        'InstanceName': '实例名称',
        'Ip': 'IP地址',
        'IntranetIp': '内网IP',
        'InternetIp': '公网IP',
        'Uuid': 'UUID',
        
        // 端口类型
        'Port': '端口',
        'Proto': '协议',
        'Ip': 'IP地址',
        'BindIp': '绑定IP',
        'Pid': '进程ID',
        'ProcName': '进程名',
        'InstanceId': '实例ID',
        'InstanceName': '实例名称',
        
        // 进程类型
        'Cmdline': '命令行',
        'Path': '路径',
        'ProcessUser': '进程用户',
        'RuntimeEnvVersion': '运行环境版本',
        
        // 服务器类型
        'Os': '操作系统',
        'Kernel': '内核版本',
        'IntranetIp': '内网IP',
        'InternetIp': '公网IP',
        'RegionName': '地域',
        'VendorName': '厂商',
        
        // 通用字段
        'Name': '名称',
        'Version': '版本',
        'Uuid': 'UUID',
        'Ip': 'IP地址',
      }
      
      // 如果有关键字匹配
      for (const [labelKey, label] of Object.entries(labelMap)) {
        if (key === labelKey || key.includes(labelKey)) {
          return label
        }
      }
      
      // 默认返回原始key，但做一些美化
      return key.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase()).trim()
    }
    
    // 获取详情展示的列数
    const getDetailColumns = (assetType) => {
      // 根据不同资产类型返回不同的列数
      const columnMap = {
        'account': 2,
        'port': 3,
        'process': 2,
        'server': 3,
        'middleware': 2,
        'software': 2,
        'cron_task': 2,
        'startup_item': 2,
        'kernel_module': 2,
        'web_site': 2,
        'ai_component': 2,
        'database': 2,
        'web_service': 2,
        'idc_probe': 3
      }
      return columnMap[assetType] || 3
    }
    
    // 获取内网IP
    const getIntranetIp = (asset) => {
      if (!asset || !asset.data) return null
      return asset.data.IntranetIp || asset.data.Ip || asset.data['内网IP'] || null
    }
    
    // 获取公网IP
    const getInternetIp = (asset) => {
      if (!asset || !asset.data) return null
      return asset.data.InternetIp || asset.data['公网IP'] || null
    }
    
    // 内网IP筛选
    const filterIntranetIp = (value, row) => {
      const ip = getIntranetIp(row)
      if (!value) return true
      if (!ip) return false
      return ip.toString().toLowerCase().includes(value.toString().toLowerCase())
    }
    
    // 公网IP筛选
    const filterInternetIp = (value, row) => {
      const ip = getInternetIp(row)
      if (!value) return true
      if (!ip) return false
      return ip.toString().toLowerCase().includes(value.toString().toLowerCase())
    }
    
    onMounted(() => {
      loadAssets()
    })
    
    // 切换云（AWS/阿里云）时重新加载数据
    watch(() => route.meta.source, () => {
      currentPage.value = 1
      loadAssets()
    })

    return {
      loading,
      assets,
      total,
      currentPage,
      pageSize,
      filters,
      pageTitle,
      detailDialogVisible,
      currentAsset,
      serverInfo,
      tableRef,
      exporting,
      loadAssets,
      handleQuery,
      resetFilters,
      handleExport,
      getAssetTypeName,
      showDetail,
      formatDateTime,
      formatFieldValue,
      getFieldLabel,
      getDetailColumns,
      getIntranetIp,
      getInternetIp,
      tableFilters,
      Search,
      Refresh
    }
  }
}
</script>

<style scoped>
.filter-form {
  margin-bottom: 20px;
}

.asset-detail {
  max-height: 70vh;
  overflow-y: auto;
}

.detail-card {
  margin-bottom: 20px;
}

.detail-card:last-child {
  margin-bottom: 0;
}

:deep(.el-descriptions__label) {
  font-weight: 600;
  width: 150px;
}

:deep(.el-descriptions__content) {
  word-break: break-word;
}
</style>
