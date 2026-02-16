<template>
  <div class="vpc-network">
    <el-card>
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <span class="title">专有网络VPC</span>
            <el-select
              v-model="activeDataSource"
              placeholder="选择数据源"
              style="width: 150px; margin-left: 20px;"
              @change="handleDataSourceChange"
            >
              <el-option label="阿里云" value="aliyun_vpc" />
              <el-option label="AWS" value="aws_vpc" />
            </el-select>
          </div>
          <div class="header-right">
            <el-button type="primary" @click="handleRefresh" :icon="Refresh">刷新</el-button>
            <el-button type="success" @click="handleExport" :loading="exporting">导出Excel</el-button>
          </div>
        </div>
        <el-tabs v-model="activeResourceType" @tab-change="handleResourceTypeChange" class="resource-tabs">
          <el-tab-pane label="VPC实例" name="vpc" />
          <el-tab-pane :label="activeDataSource === 'aws_vpc' ? '子网' : '交换机'" :name="activeDataSource === 'aws_vpc' ? 'subnet' : 'vswitch'" />
          <el-tab-pane label="路由表" name="route_table" />
          <el-tab-pane label="NAT网关" name="nat_gateway" />
          <el-tab-pane v-if="activeDataSource === 'aws_vpc'" label="Internet网关" name="internet_gateway" />
          <el-tab-pane v-if="activeDataSource === 'aliyun_vpc'" label="IPv4网关" name="ipv4_gateway" />
          <el-tab-pane label="VPC对等连接" name="vpc_peer_connection" />
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
        <el-form-item v-if="activeResourceType !== 'vpc'" label="VPC ID">
          <el-input
            v-model="filters.vpcId"
            placeholder="输入VPC ID"
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

        <!-- VPC实例特有列 -->
        <template v-if="activeResourceType === 'vpc'">
          <el-table-column prop="data.CidrBlock" label="IPv4网段" width="180" />
          <el-table-column prop="data.RegionId" label="地域" width="150" />
          <el-table-column prop="data.IsDefault" label="是否默认VPC" width="120">
            <template #default="{ row }">
              {{ row.data?.IsDefault ? '是' : '否' }}
            </template>
          </el-table-column>
          <el-table-column label="交换机数量" width="120">
            <template #default="{ row }">
              {{ getVSwitchCount(row) }}
            </template>
          </el-table-column>
        </template>

        <!-- 交换机/子网特有列 -->
        <template v-if="activeResourceType === 'vswitch' || activeResourceType === 'subnet'">
          <el-table-column prop="data.VpcId" label="VPC ID" width="220" />
          <el-table-column prop="data.CidrBlock" label="网段" width="180" />
          <el-table-column :prop="activeDataSource === 'aws_vpc' ? 'data.AvailabilityZone' : 'data.ZoneId'" label="可用区" width="150" />
          <el-table-column prop="data.AvailableIpAddressCount" label="可用IP数" width="120" />
          <el-table-column prop="data.RegionId" label="地域" width="150" />
        </template>

        <!-- 路由表特有列 -->
        <template v-if="activeResourceType === 'route_table'">
          <el-table-column prop="data.VpcId" label="VPC ID" width="220" />
          <el-table-column prop="data.RouteTableType" label="路由表类型" width="150" />
          <el-table-column prop="data.RegionId" label="地域" width="150" />
          <el-table-column label="路由条目数" width="120">
            <template #default="{ row }">
              {{ getRouteEntryCount(row) }}
            </template>
          </el-table-column>
        </template>

        <!-- NAT网关特有列 -->
        <template v-if="activeResourceType === 'nat_gateway'">
          <el-table-column prop="data.VpcId" label="VPC ID" width="220" />
          <el-table-column prop="data.Spec" label="规格" width="120" />
          <el-table-column prop="data.RegionId" label="地域" width="150" />
          <el-table-column label="公网IP" width="200">
            <template #default="{ row }">
              {{ getNatIpList(row) }}
            </template>
          </el-table-column>
          <el-table-column label="SNAT/DNAT条目" width="150">
            <template #default="{ row }">
              {{ getNatEntryCount(row) }}
            </template>
          </el-table-column>
        </template>

        <!-- IPv4网关特有列 (阿里云) -->
        <template v-if="activeResourceType === 'ipv4_gateway'">
          <el-table-column prop="data.VpcId" label="VPC ID" width="220" />
          <el-table-column prop="data.RegionId" label="地域" width="150" />
          <el-table-column prop="data.Enabled" label="是否启用" width="100">
            <template #default="{ row }">
              <el-tag :type="row.data?.Enabled ? 'success' : 'info'">
                {{ row.data?.Enabled ? '是' : '否' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="data.IpCount" label="IP数量" width="120" />
        </template>

        <!-- Internet网关特有列 (AWS) -->
        <template v-if="activeResourceType === 'internet_gateway'">
          <el-table-column prop="data.VpcId" label="VPC ID" width="220" />
          <el-table-column prop="data.RegionId" label="地域" width="150" />
          <el-table-column prop="data.Status" label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="row.data?.Attachments?.length > 0 ? 'success' : 'info'">
                {{ row.data?.Attachments?.length > 0 ? '已挂载' : '未挂载' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="挂载VPC数" width="120">
            <template #default="{ row }">
              {{ row.data?.Attachments?.length || 0 }}
            </template>
          </el-table-column>
        </template>

        <!-- VPC对等连接特有列 -->
        <template v-if="activeResourceType === 'vpc_peer_connection'">
          <el-table-column prop="data.AccepterVpcId" label="接受端VPC ID" width="220" />
          <el-table-column prop="data.RequesterVpcId" label="发起端VPC ID" width="220" />
          <el-table-column prop="data.Bandwidth" label="带宽(Mbps)" width="120" />
          <el-table-column prop="data.AccepterRegionId" label="接受端地域" width="150" />
          <el-table-column prop="data.RequesterRegionId" label="发起端地域" width="150" />
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
  name: 'VPCNetwork',
  setup() {
    const activeDataSource = ref('aliyun_vpc')
    const activeResourceType = ref('vpc')
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
      keyword: '',
      vpcId: ''
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

        // 添加筛选条件
        if (filters.status) {
          params.name = filters.status  // 使用后端的name字段筛选status
        }
        if (filters.keyword) {
          params.name = filters.keyword
        }
        if (filters.vpcId) {
          params.vpc_id = filters.vpcId
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
      filters.vpcId = ''
      currentPage.value = 1
      loadResources()
    }

    const handleResourceTypeChange = () => {
      currentPage.value = 1
      filters.status = ''
      filters.keyword = ''
      filters.vpcId = ''
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
      filters.vpcId = ''
      statusOptions.value = []
      // 切换数据源时重置为VPC类型
      activeResourceType.value = 'vpc'
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

        let filename = `VPC网络${getResourceTypeLabel()}_导出_${new Date().toISOString().slice(0, 19).replace(/[:-]/g, '')}.xlsx`
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
        'Available': 'success',
        'Pending': 'warning',
        'Modifying': 'warning',
        'Creating': 'warning',
        'Deleting': 'danger',
        'Deleted': 'info',
        'Active': 'success',
        'Inactive': 'info',
        'Unavailable': 'danger',
        'Idle': 'info',
        'InUse': 'success'
      }
      return statusMap[status] || 'info'
    }

    const getVSwitchCount = (row) => {
      const vswitchIds = row.data?.VSwitchIds || []
      return Array.isArray(vswitchIds) ? vswitchIds.length : 0
    }

    const getRouteEntryCount = (row) => {
      // AWS使用Routes，阿里云使用RouteEntrys
      const routeEntries = row.data?.Routes || row.data?.RouteEntrys || []
      return Array.isArray(routeEntries) ? routeEntries.length : 0
    }

    const getNatIpList = (row) => {
      // 阿里云使用IpList，AWS使用NatGatewayAddresses
      const ipList = row.data?.IpList || row.data?.NatGatewayAddresses || []
      if (Array.isArray(ipList) && ipList.length > 0) {
        return ipList.map(ip => ip.IpAddress || ip.PublicIp || ip).join(', ')
      }
      return '-'
    }

    const getNatEntryCount = (row) => {
      const snatCount = Array.isArray(row.data?.SnatTableIds) ? row.data.SnatTableIds.length : 0
      const dnatCount = Array.isArray(row.data?.ForwardTableIds) ? row.data.ForwardTableIds.length : 0
      return `SNAT: ${snatCount}, DNAT: ${dnatCount}`
    }

    const getResourceTypeLabel = () => {
      const labels = {
        'vpc': 'VPC实例',
        'vswitch': '交换机',
        'subnet': '子网',
        'route_table': '路由表',
        'nat_gateway': 'NAT网关',
        'ipv4_gateway': 'IPv4网关',
        'internet_gateway': 'Internet网关',
        'vpc_peer_connection': 'VPC对等连接'
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
      getVSwitchCount,
      getRouteEntryCount,
      getNatIpList,
      getNatEntryCount,
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
