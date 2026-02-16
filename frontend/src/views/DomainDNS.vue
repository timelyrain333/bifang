<template>
  <div class="domain-dns">
    <el-card>
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <span class="title">域名解析</span>
            <el-select
              v-model="activeDataSource"
              placeholder="选择数据源"
              style="width: 150px; margin-left: 20px;"
              @change="handleDataSourceChange"
            >
              <el-option label="阿里云" value="aliyun_dns" />
              <el-option label="AWS" value="aws_route53" />
            </el-select>
          </div>
          <div class="header-right">
            <el-button type="primary" @click="handleRefresh" :icon="Refresh">刷新</el-button>
            <el-button type="success" @click="handleExport" :loading="exporting">导出Excel</el-button>
          </div>
        </div>
        <el-tabs v-model="activeResourceType" @tab-change="handleResourceTypeChange" class="resource-tabs">
          <el-tab-pane
            :label="activeDataSource === 'aws_route53' ? '托管区域' : '域名'"
            :name="activeDataSource === 'aws_route53' ? 'dns_hosted_zone' : 'dns_domain'"
          />
          <el-tab-pane label="解析记录" name="dns_record" />
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
        <el-form-item label="记录类型">
          <el-select
            v-model="filters.recordType"
            placeholder="请选择类型"
            clearable
            style="width: 150px;"
            @change="handleQuery"
          >
            <el-option
              v-for="rtype in recordTypeOptions"
              :key="rtype.value"
              :label="rtype.label"
              :value="rtype.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="名称/域名">
          <el-input
            v-model="filters.keyword"
            placeholder="输入域名关键词"
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
          prop="name"
          label="名称"
          width="250"
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

        <!-- 域名/托管区域特有列 -->
        <template v-if="activeResourceType === 'dns_domain' || activeResourceType === 'dns_hosted_zone'">
          <el-table-column label="DNS服务器" width="300" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.data?.DnsServersStr || '-' }}
            </template>
          </el-table-column>
          <el-table-column v-if="activeDataSource === 'aliyun_dns'" prop="data.VersionName" label="版本" width="120" />
          <el-table-column v-if="activeDataSource === 'aws_route53'" label="类型" width="120">
            <template #default="{ row }">
              <el-tag :type="row.data?.PrivateZone ? 'warning' : 'success'" size="small">
                {{ row.data?.PrivateZone ? '私有' : '公开' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="记录数" width="100">
            <template #default="{ row }">
              {{ row.data?.ResourceRecordSetCount || '-' }}
            </template>
          </el-table-column>
          <el-table-column v-if="activeDataSource === 'aliyun_dns'" prop="data.CreateTime" label="创建时间" width="180" />
        </template>

        <!-- 解析记录特有列 -->
        <template v-if="activeResourceType === 'dns_record'">
          <el-table-column prop="data.RR" label="主机记录" width="150" show-overflow-tooltip />
          <el-table-column prop="data.Type" label="记录类型" width="120">
            <template #default="{ row }">
              <el-tag :type="getRecordTypeTag(row.data?.Type)" size="small">
                {{ row.data?.Type || '-' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="记录值" width="300" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.data?.Value || '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="data.TTL" label="TTL" width="100" />
          <el-table-column v-if="activeDataSource === 'aliyun_dns'" prop="data.Line" label="解析线路" width="120" />
          <el-table-column label="所属域名" width="200" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.data?.DomainName || '-' }}
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
  name: 'DomainDNS',
  setup() {
    const activeDataSource = ref('aliyun_dns')
    const activeResourceType = ref('dns_domain')
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
      recordType: '',
      keyword: ''
    })

    // 状态选项
    const statusOptions = ref([])

    // 记录类型选项
    const recordTypeOptions = ref([
      { label: 'A', value: 'A' },
      { label: 'AAAA', value: 'AAAA' },
      { label: 'CNAME', value: 'CNAME' },
      { label: 'MX', value: 'MX' },
      { label: 'TXT', value: 'TXT' },
      { label: 'NS', value: 'NS' },
      { label: 'SRV', value: 'SRV' },
      { label: 'PTR', value: 'PTR' },
      { label: 'CAA', value: 'CAA' },
      { label: 'SOA', value: 'SOA' }
    ])

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

        // 添加筛选条件
        if (filters.keyword) {
          params.name = filters.keyword
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
      filters.recordType = ''
      filters.keyword = ''
      currentPage.value = 1
      loadResources()
    }

    const handleResourceTypeChange = () => {
      currentPage.value = 1
      filters.status = ''
      filters.recordType = ''
      filters.keyword = ''
      statusOptions.value = []
      Promise.resolve().then(() => {
        loadResources()
      })
    }

    const handleDataSourceChange = () => {
      currentPage.value = 1
      filters.status = ''
      filters.recordType = ''
      filters.keyword = ''
      statusOptions.value = []
      // 切换数据源时重置为域名类型
      activeResourceType.value = activeDataSource.value === 'aws_route53' ? 'dns_hosted_zone' : 'dns_domain'
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

        let filename = `域名解析${getResourceTypeLabel()}_导出_${new Date().toISOString().slice(0, 19).replace(/[:-]/g, '')}.xlsx`
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
        '正常': 'success',
        '启用': 'success',
        'Active': 'success',
        '暂停': 'warning',
        'DISABLE': 'warning',
        '未实名认证': 'warning',
        '实名认证审核中': 'warning',
        '域名锁定': 'danger',
        '域名过期': 'danger',
      }
      return statusMap[status] || 'info'
    }

    const getRecordTypeTag = (type) => {
      const typeMap = {
        'A': 'primary',
        'AAAA': 'success',
        'CNAME': 'warning',
        'MX': 'info',
        'TXT': '',
        'NS': 'info',
        'SRV': 'warning',
        'PTR': '',
        'CAA': 'danger',
        'SOA': 'info'
      }
      return typeMap[type] || 'info'
    }

    const getResourceTypeLabel = () => {
      const labels = {
        'dns_domain': '域名',
        'dns_hosted_zone': '托管区域',
        'dns_record': '解析记录'
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
      recordTypeOptions,
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
      getRecordTypeTag,
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
