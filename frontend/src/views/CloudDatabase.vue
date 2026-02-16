<template>
  <div class="cloud-database">
    <el-card>
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <span class="title">云数据库</span>
            <el-select
              v-model="activeDataSource"
              placeholder="选择数据源"
              style="width: 150px; margin-left: 20px;"
              @change="handleDataSourceChange"
            >
              <el-option label="阿里云" value="aliyun_rds" />
              <el-option label="AWS" value="aws_rds" />
            </el-select>
          </div>
          <div class="header-right">
            <el-button type="primary" @click="handleRefresh" :icon="Refresh">刷新</el-button>
            <el-button type="success" @click="handleExport" :loading="exporting">导出Excel</el-button>
          </div>
        </div>
        <el-tabs v-model="activeResourceType" @tab-change="handleResourceTypeChange" class="resource-tabs">
          <el-tab-pane label="RDS实例" name="rds_instance" />
          <el-tab-pane
            :label="activeDataSource === 'aws_rds' ? '只读副本' : '只读实例'"
            :name="activeDataSource === 'aws_rds' ? 'rds_read_replica' : 'rds_readonly_instance'"
          />
          <el-tab-pane v-if="activeDataSource === 'aliyun_rds'" label="数据库" name="rds_database" />
          <el-tab-pane v-if="activeDataSource === 'aliyun_rds'" label="数据库账号" name="rds_account" />
          <el-tab-pane v-if="activeDataSource === 'aws_rds'" label="Aurora集群" name="rds_cluster" />
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
        <el-form-item label="引擎">
          <el-select
            v-model="filters.engine"
            placeholder="请选择引擎"
            clearable
            style="width: 150px;"
            @change="handleQuery"
          >
            <el-option
              v-for="engine in engineOptions"
              :key="engine.value"
              :label="engine.label"
              :value="engine.value"
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

        <!-- RDS实例特有列 (阿里云/AWS通用) -->
        <template v-if="activeResourceType === 'rds_instance'">
          <el-table-column prop="data.Engine" label="引擎" width="120">
            <template #default="{ row }">
              <el-tag :type="getEngineType(row.data?.Engine)" size="small">
                {{ row.data?.Engine || '-' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="data.EngineVersion" label="引擎版本" width="120" />
          <el-table-column prop="data.DBInstanceClass" label="规格" width="180" show-overflow-tooltip />
          <el-table-column prop="data.VpcId" label="VPC ID" width="200" show-overflow-tooltip />
          <el-table-column label="连接地址" width="200" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.data?.Endpoint || row.data?.ConnectionString || '-' }}
            </template>
          </el-table-column>
          <el-table-column label="端口" width="100">
            <template #default="{ row }">
              {{ row.data?.Port || '-' }}
            </template>
          </el-table-column>
          <el-table-column label="存储(GB)" width="100">
            <template #default="{ row }">
              {{ row.data?.AllocatedStorage || row.data?.DBInstanceStorage || '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="data.RegionId" label="地域" width="150" />
        </template>

        <!-- 只读实例/副本特有列 -->
        <template v-if="activeResourceType === 'rds_readonly_instance' || activeResourceType === 'rds_read_replica'">
          <el-table-column prop="data.Engine" label="引擎" width="120">
            <template #default="{ row }">
              <el-tag :type="getEngineType(row.data?.Engine)" size="small">
                {{ row.data?.Engine || '-' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="data.EngineVersion" label="引擎版本" width="120" />
          <el-table-column prop="data.DBInstanceClass" label="规格" width="180" show-overflow-tooltip />
          <el-table-column label="主实例ID" width="220" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.data?.MasterInstanceId || row.data?.ReadReplicaSourceDBInstanceIdentifier || '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="data.VpcId" label="VPC ID" width="200" show-overflow-tooltip />
          <el-table-column label="连接地址" width="200" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.data?.Endpoint || row.data?.ConnectionString || '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="data.RegionId" label="地域" width="150" />
        </template>

        <!-- 数据库特有列 (阿里云) -->
        <template v-if="activeResourceType === 'rds_database'">
          <el-table-column prop="data.Engine" label="引擎" width="120">
            <template #default="{ row }">
              <el-tag :type="getEngineType(row.data?.Engine)" size="small">
                {{ row.data?.Engine || '-' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="data.CharacterSetName" label="字符集" width="150" />
          <el-table-column label="所属实例ID" width="220" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.data?.DBInstanceId || row.host_uuid || '-' }}
            </template>
          </el-table-column>
          <el-table-column label="账号数" width="100">
            <template #default="{ row }">
              {{ getAccountCount(row) }}
            </template>
          </el-table-column>
        </template>

        <!-- 数据库账号特有列 (阿里云) -->
        <template v-if="activeResourceType === 'rds_account'">
          <el-table-column prop="data.AccountType" label="账号类型" width="120" />
          <el-table-column label="所属实例ID" width="220" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.data?.DBInstanceId || row.host_uuid || '-' }}
            </template>
          </el-table-column>
          <el-table-column label="数据库权限数" width="120">
            <template #default="{ row }">
              {{ getDatabasePrivilegeCount(row) }}
            </template>
          </el-table-column>
        </template>

        <!-- Aurora集群特有列 (AWS) -->
        <template v-if="activeResourceType === 'rds_cluster'">
          <el-table-column prop="data.Engine" label="引擎" width="120">
            <template #default="{ row }">
              <el-tag :type="getEngineType(row.data?.Engine)" size="small">
                {{ row.data?.Engine || '-' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="data.EngineVersion" label="引擎版本" width="120" />
          <el-table-column prop="data.EngineMode" label="引擎模式" width="120" />
          <el-table-column prop="data.VpcId" label="VPC ID" width="200" show-overflow-tooltip />
          <el-table-column label="集群端点" width="220" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.data?.Endpoint || '-' }}
            </template>
          </el-table-column>
          <el-table-column label="只读端点" width="220" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.data?.ReaderEndpoint || '-' }}
            </template>
          </el-table-column>
          <el-table-column label="实例数" width="100">
            <template #default="{ row }">
              {{ getClusterMemberCount(row) }}
            </template>
          </el-table-column>
          <el-table-column prop="data.RegionId" label="地域" width="150" />
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
  name: 'CloudDatabase',
  setup() {
    const activeDataSource = ref('aliyun_rds')
    const activeResourceType = ref('rds_instance')
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
      engine: '',
      keyword: ''
    })

    // 状态选项
    const statusOptions = ref([])

    // 引擎选项
    const engineOptions = ref([
      { label: 'MySQL', value: 'MySQL' },
      { label: 'mysql', value: 'mysql' },
      { label: 'PostgreSQL', value: 'PostgreSQL' },
      { label: 'postgres', value: 'postgres' },
      { label: 'SQL Server', value: 'SQLServer' },
      { label: 'sqlserver', value: 'sqlserver' },
      { label: 'MariaDB', value: 'MariaDB' },
      { label: 'mariadb', value: 'mariadb' },
      { label: 'Oracle', value: 'Oracle' },
      { label: 'oracle', value: 'oracle' },
      { label: 'Aurora MySQL', value: 'aurora-mysql' },
      { label: 'Aurora PostgreSQL', value: 'aurora-postgresql' }
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
      filters.engine = ''
      filters.keyword = ''
      currentPage.value = 1
      loadResources()
    }

    const handleResourceTypeChange = () => {
      currentPage.value = 1
      filters.status = ''
      filters.engine = ''
      filters.keyword = ''
      statusOptions.value = []
      Promise.resolve().then(() => {
        loadResources()
      })
    }

    const handleDataSourceChange = () => {
      currentPage.value = 1
      filters.status = ''
      filters.engine = ''
      filters.keyword = ''
      statusOptions.value = []
      // 切换数据源时重置为RDS实例类型
      activeResourceType.value = 'rds_instance'
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

        let filename = `云数据库${getResourceTypeLabel()}_导出_${new Date().toISOString().slice(0, 19).replace(/[:-]/g, '')}.xlsx`
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
        'Available': 'success',
        'Active': 'success',
        'Creating': 'warning',
        'Modifying': 'warning',
        'Rebooting': 'warning',
        'Starting': 'warning',
        'Deleting': 'danger',
        'Failed': 'danger',
        'Stopped': 'info',
        'Stopping': 'info',
        'Inaccessible': 'danger'
      }
      return statusMap[status] || 'info'
    }

    const getEngineType = (engine) => {
      if (!engine) return 'info'
      const engineLower = engine.toLowerCase()
      const engineMap = {
        'mysql': 'primary',
        'aurora-mysql': 'primary',
        'mariadb': 'primary',
        'postgresql': 'success',
        'postgres': 'success',
        'aurora-postgresql': 'success',
        'sqlserver': 'warning',
        'oracle': 'danger'
      }
      return engineMap[engineLower] || 'info'
    }

    const getAccountCount = (row) => {
      const accounts = row.data?.Accounts || []
      return Array.isArray(accounts) ? accounts.length : 0
    }

    const getDatabasePrivilegeCount = (row) => {
      const privileges = row.data?.DatabasePrivileges || []
      return Array.isArray(privileges) ? privileges.length : 0
    }

    const getClusterMemberCount = (row) => {
      const members = row.data?.DBClusterMembers || []
      return Array.isArray(members) ? members.length : 0
    }

    const getResourceTypeLabel = () => {
      const labels = {
        'rds_instance': 'RDS实例',
        'rds_readonly_instance': '只读实例',
        'rds_read_replica': '只读副本',
        'rds_database': '数据库',
        'rds_account': '数据库账号',
        'rds_cluster': 'Aurora集群'
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
      engineOptions,
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
      getEngineType,
      getAccountCount,
      getDatabasePrivilegeCount,
      getClusterMemberCount,
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
  width: 180px;
}

:deep(.el-descriptions__content) {
  word-break: break-word;
}
</style>
