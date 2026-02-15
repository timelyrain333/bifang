<template>
  <div class="cloud-server">
    <el-card>
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <span class="title">云服务器</span>
            <el-select
              v-model="activeDataSource"
              placeholder="选择数据源"
              style="width: 150px; margin-left: 20px;"
              @change="handleDataSourceChange"
            >
              <el-option label="阿里云" value="aliyun_ecs" />
              <el-option label="AWS" value="aws_ecs" />
            </el-select>
          </div>
          <div class="header-right">
            <el-button type="primary" @click="handleRefresh" :icon="Refresh">刷新</el-button>
            <el-button type="success" @click="handleExport" :loading="exporting">导出Excel</el-button>
          </div>
        </div>
        <el-tabs v-model="activeResourceType" @tab-change="handleResourceTypeChange" class="resource-tabs">
          <el-tab-pane label="ECS实例" name="ecs_instance" />
          <el-tab-pane label="镜像" name="ecs_image" />
          <el-tab-pane label="磁盘" name="ecs_disk" />
          <el-tab-pane label="快照" name="ecs_snapshot" />
          <el-tab-pane label="安全组" name="ecs_security_group" />
          <el-tab-pane label="弹性网卡" name="ecs_network_interface" />
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
          label="资源ID"
          width="220"
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

        <!-- 动态列：根据资源类型显示不同字段 -->
        <template v-if="activeResourceType === 'ecs_instance'">
          <el-table-column prop="data.InstanceType" label="规格" width="150" />
          <el-table-column prop="data.RegionId" label="地域" width="150" />
          <el-table-column prop="data.ZoneId" label="可用区" width="150" />
          <el-table-column label="公网IP" width="180">
            <template #default="{ row }">
              {{ getPublicIp(row) || '-' }}
            </template>
          </el-table-column>
          <el-table-column label="内网IP" width="180">
            <template #default="{ row }">
              {{ getPrivateIp(row) || '-' }}
            </template>
          </el-table-column>
        </template>

        <template v-if="activeResourceType === 'ecs_image'">
          <el-table-column prop="data.OSName" label="操作系统" width="200" />
          <el-table-column prop="data.Architecture" label="架构" width="120" />
          <el-table-column prop="data.ImageSize" label="大小(GB)" width="120" />
          <el-table-column prop="data.Platform" label="平台" width="120" />
        </template>

        <template v-if="activeResourceType === 'ecs_disk'">
          <el-table-column prop="data.DiskType" label="磁盘类型" width="120" />
          <el-table-column prop="data.Category" label="分类" width="120" />
          <el-table-column prop="data.Size" label="大小(GB)" width="120" />
          <el-table-column label="挂载实例" width="200">
            <template #default="{ row }">
              {{ getInstanceId(row) || '-' }}
            </template>
          </el-table-column>
        </template>

        <template v-if="activeResourceType === 'ecs_snapshot'">
          <el-table-column prop="data.SourceDiskId" label="源磁盘ID" width="220" />
          <el-table-column prop="data.SourceDiskSize" label="源磁盘大小" width="120" />
          <el-table-column prop="data.RetentionDays" label="保留天数" width="120" />
          <el-table-column prop="data.Progress" label="进度" width="120" />
        </template>

        <template v-if="activeResourceType === 'ecs_security_group'">
          <el-table-column prop="data.Description" label="描述" width="200" show-overflow-tooltip />
          <el-table-column prop="data.VpcId" label="VPC ID" width="220" />
          <el-table-column label="规则数量" width="120">
            <template #default="{ row }">
              {{ getRulesCount(row) }}
            </template>
          </el-table-column>
        </template>

        <template v-if="activeResourceType === 'ecs_network_interface'">
          <el-table-column prop="data.Type" label="类型" width="120" />
          <el-table-column prop="data.VpcId" label="VPC ID" width="220" />
          <el-table-column prop="data.PrivateIpAddress" label="私网IP" width="150" />
          <el-table-column prop="data.PublicIpAddress" label="公网IP" width="150" />
          <el-table-column label="挂载实例" width="200">
            <template #default="{ row }">
              {{ row.data.InstanceId || '-' }}
            </template>
          </el-table-column>
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
              <el-tag :type="getStatusType(currentResource.data.Status)">
                {{ currentResource.data.Status || '-' }}
              </el-tag>
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
  name: 'CloudServer',
  setup() {
    const activeDataSource = ref('aliyun_ecs')
    const activeResourceType = ref('ecs_instance')
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

    // 状态选项（根据不同资源类型动态生成）
    const statusOptions = ref([])

    const loadResources = async () => {
      loading.value = true
      // 先清空数据，避免切换标签时渲染旧数据
      resources.value = []
      total.value = 0

      try {
        const params = {
          source: activeDataSource.value,
          asset_type: activeResourceType.value,
          page: currentPage.value,
          page_size: pageSize.value
        }

        const response = await api.get('/assets/', { params })
        resources.value = response.results || (Array.isArray(response) ? response : [])
        total.value = response.count || resources.value.length

        // 提取状态选项
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
      // 使用nextTick确保DOM更新后再加载数据
      Promise.resolve().then(() => {
        loadResources()
      })
    }

    const handleDataSourceChange = () => {
      currentPage.value = 1
      filters.status = ''
      filters.keyword = ''
      statusOptions.value = []
      // 使用nextTick确保DOM更新后再加载数据
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

        const dataSourceLabel = activeDataSource.value === 'aliyun_ecs' ? '阿里云' : 'AWS'
        let filename = `云服务器${getResourceTypeLabel()}_${dataSourceLabel}_导出_${new Date().toISOString().slice(0, 19).replace(/[:-]/g, '')}.xlsx`
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
        'Running': 'success',
        'Stopped': 'info',
        'Starting': 'warning',
        'Stopping': 'warning',
        'Available': 'success',
        'UnAvailable': 'danger',
        'In_use': 'success',
        'Available': 'info',
        'Creating': 'warning',
        'Deleting': 'danger',
        'ReIniting': 'warning'
      }
      return statusMap[status] || 'info'
    }

    const getPublicIp = (row) => {
      const ips = row.data?.PublicIpAddress || row.data?.InnerIpAddress || []
      if (Array.isArray(ips)) {
        return ips.join(', ')
      }
      return ips
    }

    const getPrivateIp = (row) => {
      const vpc = row.data?.VpcAttributes || {}
      const privateIp = vpc.PrivateIpAddress?.IpAddress || []
      if (Array.isArray(privateIp)) {
        return privateIp.join(', ')
      }
      return privateIp || row.data?.InnerIpAddress || ''
    }

    const getInstanceId = (row) => {
      const instanceIds = row.data?.InstanceIds || []
      if (Array.isArray(instanceIds)) {
        return instanceIds.join(', ')
      }
      return instanceIds
    }

    const getRulesCount = (row) => {
      const rules = row.data?.Rules || {}
      const inbound = rules.inbound?.length || 0
      const outbound = rules.outbound?.length || 0
      return `入: ${inbound}, 出: ${outbound}`
    }

    const getResourceTypeLabel = () => {
      const labels = {
        'ecs_instance': 'ECS实例',
        'ecs_image': '镜像',
        'ecs_disk': '磁盘',
        'ecs_snapshot': '快照',
        'ecs_security_group': '安全组',
        'ecs_network_interface': '弹性网卡'
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
      getPublicIp,
      getPrivateIp,
      getInstanceId,
      getRulesCount,
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