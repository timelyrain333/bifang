<template>
  <div class="load-balancer">
    <el-card>
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <span class="title">负载均衡</span>
            <el-select
              v-model="activeDataSource"
              placeholder="选择数据源"
              style="width: 150px; margin-left: 20px;"
              @change="handleDataSourceChange"
            >
              <el-option label="阿里云" value="aliyun_slb" />
              <el-option label="AWS" value="aws_elb" />
            </el-select>
          </div>
          <div class="header-right">
            <el-button type="primary" @click="handleRefresh" :icon="Refresh">刷新</el-button>
            <el-button type="success" @click="handleExport" :loading="exporting">导出Excel</el-button>
          </div>
        </div>
        <el-tabs v-model="activeResourceType" @tab-change="handleResourceTypeChange" class="resource-tabs">
          <el-tab-pane :label="activeDataSource === 'aws_elb' ? '负载均衡器' : 'CLB实例'" :name="activeDataSource === 'aws_elb' ? 'load_balancer' : 'clb'" />
          <el-tab-pane :label="activeDataSource === 'aws_elb' ? '目标组' : '监听器'" :name="activeDataSource === 'aws_elb' ? 'target_group' : 'listener'" />
          <el-tab-pane :label="activeDataSource === 'aws_elb' ? '目标' : '后端服务器'" :name="activeDataSource === 'aws_elb' ? 'target' : 'backend_server'" />
        </el-tabs>
      </template>

      <!-- 筛选表单 -->
      <el-form :inline="true" :model="filters" class="filter-form">
        <el-form-item label="状态">
          <el-select
            v-model="filters.status"
            placeholder="请选择状态"
            clearable
            style="width: 150px;"
            @change="handleQuery"
          >
            <el-option
              v-for="status in statusOptions"
              :key="status.value"
              :label="status.label"
              :value="status.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="名称/ID">
          <el-input
            v-model="filters.keyword"
            placeholder="输入名称或ID关键词"
            clearable
            style="width: 200px;"
            @keyup.enter="handleQuery"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleQuery" :icon="Search">查询</el-button>
          <el-button @click="resetFilters" :icon="Refresh">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 数据表格 -->
      <el-table
        :data="resources"
        v-loading="loading"
        stripe
        ref="tableRef"
      >
        <el-table-column
          prop="uuid"
          label="资源ID/ARN"
          width="300"
          show-overflow-tooltip
        />
        <el-table-column
          prop="name"
          label="名称"
          width="200"
          show-overflow-tooltip
        />
        <el-table-column
          prop="data.Status"
          label="状态"
          width="120"
        >
          <template #default="{ row }">
            <el-tag v-if="row.data" :type="getStatusType(row.data.Status)">
              {{ row.data.Status || '-' }}
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>

        <!-- 负载均衡器/CLB实例特有列 -->
        <template v-if="activeResourceType === 'load_balancer' || activeResourceType === 'clb'">
          <el-table-column :prop="activeDataSource === 'aws_elb' ? 'data.DNSName' : 'data.Address'" label="地址/DNS" width="280" show-overflow-tooltip />
          <el-table-column :prop="activeDataSource === 'aws_elb' ? 'data.Type' : 'data.LoadBalancerSpec'" label="类型/规格" width="120" />
          <el-table-column prop="data.VpcId" label="VPC ID" width="220" show-overflow-tooltip />
          <el-table-column :prop="activeDataSource === 'aws_elb' ? 'data.Scheme' : 'data.AddressType'" label="网络类型" width="120">
            <template #default="{ row }">
              {{ row.data?.Scheme || row.data?.AddressType || '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="data.RegionId" label="地域" width="150" />
        </template>

        <!-- 监听器特有列 -->
        <template v-if="activeResourceType === 'listener'">
          <el-table-column prop="data.ListenerProtocol" label="协议" width="100" />
          <el-table-column prop="data.ListenerPort" label="端口" width="100" />
          <el-table-column prop="data.Scheduler" label="调度算法" width="120" />
          <el-table-column label="健康检查" width="120">
            <template #default="{ row }">
              <el-tag v-if="row.data?.HealthCheck" type="success">已配置</el-tag>
              <el-tag v-else type="info">未配置</el-tag>
            </template>
          </el-table-column>
          <el-table-column :prop="activeDataSource === 'aws_elb' ? 'data.LoadBalancerArn' : 'data.LoadBalancerId'" label="负载均衡器" width="250" show-overflow-tooltip />
        </template>

        <!-- 目标组特有列 (AWS) -->
        <template v-if="activeResourceType === 'target_group'">
          <el-table-column prop="data.Protocol" label="协议" width="100" />
          <el-table-column prop="data.Port" label="端口" width="100" />
          <el-table-column prop="data.TargetType" label="目标类型" width="120" />
          <el-table-column prop="data.VpcId" label="VPC ID" width="220" show-overflow-tooltip />
          <el-table-column prop="data.HealthCheckPath" label="健康检查路径" width="150" show-overflow-tooltip />
          <el-table-column prop="data.RegionId" label="地域" width="150" />
        </template>

        <!-- 目标/后端服务器特有列 -->
        <template v-if="activeResourceType === 'target' || activeResourceType === 'backend_server'">
          <el-table-column :prop="activeDataSource === 'aws_elb' ? 'data.TargetId' : 'data.ServerId'" label="实例ID" width="200" />
          <el-table-column :prop="activeDataSource === 'aws_elb' ? 'data.TargetPort' : 'data.Port'" label="端口" width="100" />
          <el-table-column :prop="activeDataSource === 'aws_elb' ? 'data.HealthStatus' : 'data.Status'" label="健康状态" width="120">
            <template #default="{ row }">
              <el-tag :type="getHealthStatusType(row.data?.HealthStatus || row.data?.Status)">
                {{ row.data?.HealthStatus || row.data?.Status || '-' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column v-if="activeDataSource === 'aliyun_slb'" prop="data.Weight" label="权重" width="80" />
          <el-table-column :prop="activeDataSource === 'aws_elb' ? 'data.TargetGroupName' : 'data.LoadBalancerName'" label="关联资源" width="200" show-overflow-tooltip />
        </template>

        <el-table-column prop="collected_at" label="采集时间" width="180" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="showDetail(row)">
              查看详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50, 100]"
        :total="total"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadResources"
        @current-change="loadResources"
        style="margin-top: 20px;"
      />
    </el-card>

    <!-- 详情对话框 -->
    <el-dialog
      v-model="detailDialogVisible"
      :title="`${getResourceTypeLabel()}详情`"
      width="80%"
      :close-on-click-modal="false"
    >
      <div v-if="currentResource" class="resource-detail">
        <!-- 基本信息 -->
        <el-card class="detail-card" shadow="never">
          <template #header>
            <span>基本信息</span>
          </template>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="资源ID">
              {{ currentResource.uuid }}
            </el-descriptions-item>
            <el-descriptions-item label="名称">
              {{ currentResource.name || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag v-if="currentResource.data" :type="getStatusType(currentResource.data.Status)">
                {{ currentResource.data.Status || '-' }}
              </el-tag>
              <span v-else>-</span>
            </el-descriptions-item>
            <el-descriptions-item label="采集时间">
              {{ formatDateTime(currentResource.collected_at) }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>

        <!-- 详细数据 -->
        <el-card class="detail-card" shadow="never">
          <template #header>
            <span>详细信息</span>
          </template>
          <el-descriptions :column="2" border>
            <template v-for="(value, key) in currentResource.data" :key="key">
              <el-descriptions-item :label="key">
                {{ formatFieldValue(key, value) }}
              </el-descriptions-item>
            </template>
          </el-descriptions>
        </el-card>
      </div>

      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, reactive, onMounted } from 'vue'
import { Search, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '../api'

export default {
  name: 'LoadBalancer',
  setup() {
    const activeDataSource = ref('aliyun_slb')
    const activeResourceType = ref('clb')
    const loading = ref(false)
    const resources = ref([])
    const total = ref(0)
    const currentPage = ref(1)
    const pageSize = ref(20)
    const detailDialogVisible = ref(false)
    const currentResource = ref(null)
    const tableRef = ref(null)
    const exporting = ref(false)

    const filters = reactive({
      status: '',
      keyword: ''
    })

    const statusOptions = ref([])

    const loadResources = async () => {
      loading.value = true
      resources.value = []
      total.value = 0

      try {
        const params = {
          source: activeDataSource.value,
          asset_type: activeResourceType.value,
          page: currentPage.value,
          page_size: pageSize.value
        }

        if (filters.status) {
          params.name = filters.status
        }
        if (filters.keyword) {
          params.name = filters.keyword
        }

        const response = await api.get('/assets/', { params })
        resources.value = response.results || (Array.isArray(response) ? response : [])
        total.value = response.count || resources.value.length

        extractStatusOptions()
      } catch (error) {
        console.error('加载资源失败:', error)
        ElMessage.error('加载资源失败')
        resources.value = []
        total.value = 0
      } finally {
        loading.value = false
      }
    }

    const extractStatusOptions = () => {
      const statusSet = new Set()
      resources.value.forEach(resource => {
        if (resource.data && resource.data.Status) {
          statusSet.add(resource.data.Status)
        }
        if (resource.data && resource.data.HealthStatus) {
          statusSet.add(resource.data.HealthStatus)
        }
        if (resource.data && resource.data.LoadBalancerStatus) {
          statusSet.add(resource.data.LoadBalancerStatus)
        }
        if (resource.data && resource.data.State) {
          statusSet.add(resource.data.State)
        }
      })
      statusOptions.value = Array.from(statusSet).map(status => ({
        label: status,
        value: status
      }))
    }

    const handleQuery = () => {
      currentPage.value = 1
      loadResources()
    }

    const resetFilters = () => {
      filters.status = ''
      filters.keyword = ''
      currentPage.value = 1
      loadResources()
    }

    const handleResourceTypeChange = () => {
      currentPage.value = 1
      filters.status = ''
      filters.keyword = ''
      statusOptions.value = []
      Promise.resolve().then(() => {
        loadResources()
      })
    }

    const handleDataSourceChange = () => {
      currentPage.value = 1
      filters.status = ''
      filters.keyword = ''
      statusOptions.value = []
      // 切换数据源时重置资源类型
      activeResourceType.value = activeDataSource.value === 'aws_elb' ? 'load_balancer' : 'clb'
      Promise.resolve().then(() => {
        loadResources()
      })
    }

    const handleRefresh = () => {
      loadResources()
      ElMessage.success('刷新成功')
    }

    const handleExport = async () => {
      exporting.value = true
      try {
        const params = {
          source: activeDataSource.value,
          asset_type: activeResourceType.value
        }

        const axios = (await import('axios')).default
        const response = await axios.get('/api/assets/export/', {
          params,
          responseType: 'blob',
          withCredentials: true
        })

        const blob = new Blob([response.data], {
          type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })
        const url = window.URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url

        let filename = `负载均衡${getResourceTypeLabel()}_导出_${new Date().toISOString().slice(0, 19).replace(/[:-]/g, '')}.xlsx`
        const contentDisposition = response.headers['content-disposition'] || ''
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

        ElMessage.success('导出成功！')
      } catch (error) {
        console.error('导出失败:', error)
        ElMessage.error('导出失败，请稍后重试')
      } finally {
        exporting.value = false
      }
    }

    const getStatusType = (status) => {
      const statusMap = {
        'Active': 'success',
        'Available': 'success',
        'InService': 'success',
        'Healthy': 'success',
        'Pending': 'warning',
        'Provisioning': 'warning',
        'Adding': 'warning',
        'Removing': 'warning',
        'Failed': 'danger',
        'Unhealthy': 'danger',
        'OutOfService': 'danger',
        'Draining': 'warning',
        'Disabled': 'info',
        'Inactive': 'info',
      }
      return statusMap[status] || 'info'
    }

    const getHealthStatusType = (status) => {
      const statusMap = {
        'healthy': 'success',
        'Healthy': 'success',
        'unhealthy': 'danger',
        'Unhealthy': 'danger',
        'draining': 'warning',
        'Draining': 'warning',
        'unavailable': 'info',
        'Unavailable': 'info',
        'unused': 'info',
        'Unused': 'info',
        'initializing': 'warning',
        'Active': 'success',
        'InService': 'success',
      }
      return statusMap[status] || 'info'
    }

    const getResourceTypeLabel = () => {
      const labels = {
        'clb': 'CLB实例',
        'load_balancer': '负载均衡器',
        'listener': '监听器',
        'target_group': '目标组',
        'backend_server': '后端服务器',
        'target': '目标',
      }
      return labels[activeResourceType.value] || activeResourceType.value
    }

    const showDetail = (resource) => {
      currentResource.value = resource
      detailDialogVisible.value = true
    }

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

    const formatFieldValue = (key, value) => {
      if (value === null || value === undefined || value === '') {
        return '-'
      }

      if (typeof value === 'object') {
        return JSON.stringify(value, null, 2)
      }

      if (Array.isArray(value)) {
        return value.join(', ') || '-'
      }

      return String(value)
    }

    onMounted(() => {
      loadResources()
    })

    return {
      activeDataSource,
      activeResourceType,
      loading,
      resources,
      total,
      currentPage,
      pageSize,
      filters,
      statusOptions,
      detailDialogVisible,
      currentResource,
      tableRef,
      exporting,
      loadResources,
      handleQuery,
      resetFilters,
      handleResourceTypeChange,
      handleDataSourceChange,
      handleRefresh,
      handleExport,
      getStatusType,
      getHealthStatusType,
      getResourceTypeLabel,
      showDetail,
      formatDateTime,
      formatFieldValue,
      Search,
      Refresh
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

.header-left {
  display: flex;
  align-items: center;
}

.header-left .title {
  font-size: 16px;
  font-weight: 600;
}

.header-right {
  display: flex;
  gap: 10px;
}

.resource-tabs {
  margin-top: 15px;
}

.filter-form {
  margin-bottom: 20px;
}

.resource-detail {
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