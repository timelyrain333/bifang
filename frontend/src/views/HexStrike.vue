<template>
  <div class="hexstrike-container">
    <el-card class="hexstrike-card">
      <template #header>
        <div class="card-header">
          <span>HexStrike AI 安全评估服务</span>
        </div>
      </template>

      <el-tabs v-model="activeTab" type="border-card" @tab-change="handleTabChange">
        <!-- 控制台标签页 -->
        <el-tab-pane label="📊 控制台" name="console">
          <template #label>
            <span>
              <el-icon><Monitor /></el-icon>
              控制台
            </span>
          </template>

          <!-- 原有的控制台内容 -->
          <div v-if="loading && !status" class="loading-container">
            <el-icon class="is-loading loading-icon"><Loading /></el-icon>
            <p>正在加载 HexStrike 服务状态...</p>
          </div>

          <div v-else-if="error" class="error-container">
            <el-alert
              :title="error"
              type="error"
              :closable="false"
              show-icon
            >
              <template #default>
                <p>{{ error }}</p>
                <p style="margin-top: 10px;">
                  请确认：
                  <ul style="margin-left: 20px; margin-top: 5px;">
                    <li>HexStrike 服务已启动（默认端口 8888）</li>
                    <li>服务地址配置正确</li>
                    <li>网络连接正常</li>
                  </ul>
                </p>
                <el-button
                  type="primary"
                  @click="loadStatus"
                  style="margin-top: 15px;"
                >
                  重试
                </el-button>
              </template>
            </el-alert>
          </div>

          <div v-else-if="status" class="status-container">
            <!-- 操作按钮 -->
            <div style="margin-bottom: 20px;">
              <el-button
                type="success"
                size="small"
                @click="showExportDialog = true"
                :disabled="!status || status.status !== 'healthy'"
              >
                <el-icon><Download /></el-icon>
                导出报告
              </el-button>
              <el-button
                type="primary"
                size="small"
                @click="loadStatus"
                :loading="loading"
                style="margin-left: 10px;"
              >
                <el-icon><Refresh /></el-icon>
                刷新状态
              </el-button>
            </div>

            <!-- 服务状态 -->
            <el-card shadow="never" class="status-card">
              <template #header>
                <div class="status-header">
                  <el-icon :class="status.status === 'healthy' ? 'status-icon success' : 'status-icon error'">
                    <CircleCheck v-if="status.status === 'healthy'" />
                    <CircleClose v-else />
                  </el-icon>
                  <span class="status-title">服务状态</span>
                </div>
              </template>
              <div class="status-content">
                <el-descriptions :column="2" border>
                  <el-descriptions-item label="状态">
                    <el-tag :type="status.status === 'healthy' ? 'success' : 'danger'">
                      {{ status.status === 'healthy' ? '正常运行' : '异常' }}
                    </el-tag>
                  </el-descriptions-item>
                  <el-descriptions-item label="版本">
                    {{ status.version || '未知' }}
                  </el-descriptions-item>
                  <el-descriptions-item label="运行时间">
                    {{ formatUptime(status.uptime) }}
                  </el-descriptions-item>
                  <el-descriptions-item label="消息">
                    {{ status.message || '-' }}
                  </el-descriptions-item>
                </el-descriptions>
              </div>
            </el-card>

            <!-- 工具统计 -->
            <el-card shadow="never" class="status-card" style="margin-top: 20px;">
              <template #header>
                <span class="status-title">工具统计</span>
              </template>
              <div class="status-content">
                <el-descriptions :column="2" border>
                  <el-descriptions-item label="总工具数">
                    <el-tag>{{ status.total_tools_count || 0 }}</el-tag>
                  </el-descriptions-item>
                  <el-descriptions-item label="可用工具数">
                    <el-tag type="success">{{ status.total_tools_available || 0 }}</el-tag>
                  </el-descriptions-item>
                  <el-descriptions-item label="必需工具">
                    <el-tag :type="status.all_essential_tools_available ? 'success' : 'warning'">
                      {{ status.all_essential_tools_available ? '全部可用' : '部分缺失' }}
                    </el-tag>
                  </el-descriptions-item>
                  <el-descriptions-item label="成功率">
                    {{ status.telemetry?.success_rate || '0%' }}
                  </el-descriptions-item>
                </el-descriptions>

                <!-- 工具分类统计 -->
                <div v-if="status.category_stats" style="margin-top: 20px;">
                  <h4>工具分类统计</h4>
                  <el-row :gutter="20">
                    <el-col :span="6" v-for="(count, category) in status.category_stats" :key="category">
                      <el-statistic :value="count.available" :title="getCategoryName(category)">
                        <template #suffix>
                          <span style="font-size: 14px;">/ {{ count.total }}</span>
                        </template>
                      </el-statistic>
                    </el-col>
                  </el-row>
                </div>
              </div>
            </el-card>

            <!-- 系统指标 -->
            <el-card shadow="never" class="status-card" style="margin-top: 20px;" v-if="status.telemetry?.system_metrics">
              <template #header>
                <span class="status-title">系统指标</span>
              </template>
              <div class="status-content">
                <el-descriptions :column="2" border>
                  <el-descriptions-item label="CPU 使用率">
                    {{ status.telemetry.system_metrics.cpu_percent }}%
                  </el-descriptions-item>
                  <el-descriptions-item label="内存使用率">
                    {{ status.telemetry.system_metrics.memory_percent }}%
                  </el-descriptions-item>
                  <el-descriptions-item label="磁盘使用率">
                    {{ status.telemetry.system_metrics.disk_usage }}%
                  </el-descriptions-item>
                  <el-descriptions-item label="平均执行时间">
                    {{ status.telemetry.average_execution_time }}
                  </el-descriptions-item>
                </el-descriptions>
              </div>
            </el-card>

            <!-- API 访问 -->
            <el-card shadow="never" class="status-card" style="margin-top: 20px;">
              <template #header>
                <span class="status-title">API 访问</span>
              </template>
              <div class="status-content">
                <el-alert
                  type="info"
                  :closable="false"
                  show-icon
                >
                  <template #default>
                    <p>HexStrike 是一个 API 服务，主要用于安全评估和扫描工具调用。</p>
                    <p style="margin-top: 10px;">
                      <strong>服务地址：</strong>
                      <el-link :href="hexstrikeApiUrl" target="_blank" type="primary">
                        {{ hexstrikeApiUrl }}
                      </el-link>
                    </p>
                    <p style="margin-top: 10px;">
                      <strong>主要 API 端点：</strong>
                    </p>
                    <ul style="margin-left: 20px; margin-top: 5px;">
                      <li><code>GET /health</code> - 健康检查</li>
                      <li><code>POST /api/intelligence/analyze-target</code> - 分析目标</li>
                      <li><code>POST /api/intelligence/select-tools</code> - 选择工具</li>
                      <li><code>POST /api/command</code> - 执行命令</li>
                    </ul>
                    <p style="margin-top: 10px;">
                      您可以通过 <strong>SecOps 智能体</strong> 或 <strong>钉钉机器人</strong> 与 HexStrike 交互。
                    </p>
                  </template>
                </el-alert>
              </div>
            </el-card>

            <!-- 执行记录 -->
            <el-card shadow="never" class="status-card" style="margin-top: 20px;">
              <template #header>
                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <span class="status-title">执行记录</span>
                  <el-button
                    type="text"
                    size="small"
                    @click="loadExecutions"
                    :loading="executionsLoading"
                  >
                    <el-icon><Refresh /></el-icon>
                    刷新
                  </el-button>
                </div>
              </template>
              <div class="status-content">
                <el-table
                  :data="executions"
                  style="width: 100%"
                  v-loading="executionsLoading"
                  empty-text="暂无执行记录"
                >
                  <el-table-column prop="id" label="ID" width="80" />
                  <el-table-column prop="target" label="评估目标" min-width="150" />
                  <el-table-column prop="tool_name" label="工具名称" width="120">
                    <template #default="scope">
                      {{ scope.row.tool_name || '综合分析' }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="status" label="状态" width="100">
                    <template #default="scope">
                      <el-tag
                        :type="scope.row.status === 'success' ? 'success' : scope.row.status === 'failed' ? 'danger' : 'warning'"
                      >
                        {{ scope.row.status === 'success' ? '成功' : scope.row.status === 'failed' ? '失败' : '执行中' }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="started_at" label="开始时间" width="180">
                    <template #default="scope">
                      {{ formatDateTime(scope.row.started_at) }}
                    </template>
                  </el-table-column>
                  <el-table-column prop="execution_time" label="耗时" width="100">
                    <template #default="scope">
                      {{ scope.row.execution_time ? Number(scope.row.execution_time).toFixed(2) + 's' : '-' }}
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="120" fixed="right">
                    <template #default="scope">
                      <el-button
                        type="text"
                        size="small"
                        @click="exportSingleExecution(scope.row.id)"
                      >
                        导出
                      </el-button>
                    </template>
                  </el-table-column>
                </el-table>

                <el-pagination
                  v-model:current-page="executionsPage"
                  v-model:page-size="executionsPageSize"
                  :page-sizes="[10, 20, 50, 100]"
                  :total="executionsTotal"
                  layout="total, sizes, prev, pager, next"
                  @size-change="loadExecutions"
                  @current-change="loadExecutions"
                  style="margin-top: 20px;"
                />
              </div>
            </el-card>
          </div>
        </el-tab-pane>

        <!-- 安全评估报告标签页 -->
        <el-tab-pane label="📄 安全评估报告" name="reports">
          <template #label>
            <span>
              <el-icon><Document /></el-icon>
              安全评估报告
            </span>
          </template>

          <div class="reports-content">
            <!-- 搜索栏 -->
            <div class="search-bar">
              <el-input
                v-model="searchTarget"
                placeholder="搜索目标 IP 或域名"
                prefix-icon="Search"
                clearable
                style="width: 300px; margin-right: 10px;"
                @clear="loadReports"
                @keyup.enter="loadReports"
              >
              </el-input>
              <el-button type="primary" @click="loadReports" :loading="reportsLoading">搜索</el-button>
              <el-button @click="searchTarget = ''; loadReports()">重置</el-button>
              <el-button type="primary" size="small" @click="loadReports" :loading="reportsLoading" style="margin-left: auto;">
                <el-icon><Refresh /></el-icon> 刷新
              </el-button>
            </div>

            <!-- 报告列表 -->
            <div v-loading="reportsLoading">
              <div v-if="reports.length === 0" class="empty-state">
                <el-icon class="empty-icon"><Document /></el-icon>
                <p>暂无报告</p>
                <p class="hint">完成安全评估后，报告将自动生成并显示在这里</p>
              </div>

              <div v-else class="report-grid">
                <el-card
                  v-for="report in reports"
                  :key="report.filename"
                  class="report-card"
                  shadow="hover"
                >
                  <div slot="header" class="card-header">
                    <span class="target">
                      <el-icon><Monitor /></el-icon>
                      {{ report.target }}
                    </span>
                    <el-tag size="mini" type="info">HTML 报告</el-tag>
                  </div>

                  <div class="report-info">
                    <div class="info-item">
                      <el-icon><Clock /></el-icon>
                      <span>{{ report.created_time }}</span>
                    </div>
                    <div class="info-item">
                      <el-icon><Document /></el-icon>
                      <span>{{ formatFileSize(report.size) }}</span>
                    </div>
                  </div>

                  <div class="report-actions">
                    <el-button
                      type="primary"
                      size="small"
                      @click="downloadReport(report)"
                    >
                      <el-icon><Download /></el-icon>
                      下载报告
                    </el-button>
                    <el-button
                      type="success"
                      size="small"
                      @click="viewReport(report)"
                    >
                      <el-icon><View /></el-icon>
                      在线查看
                    </el-button>
                  </div>
                </el-card>
              </div>

              <!-- 分页 -->
              <div class="pagination" v-if="reports.length > 0">
                <el-pagination
                  @size-change="handleSizeChange"
                  @current-change="handleCurrentChange"
                  :current-page="currentPage"
                  :page-sizes="[20, 50, 100]"
                  :page-size="pageSize"
                  layout="total, sizes, prev, pager, next, jumper"
                  :total="totalReports"
                >
                </el-pagination>
              </div>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 导出对话框 -->
    <el-dialog
      v-model="showExportDialog"
      title="导出报告"
      width="500px"
    >
      <el-form :model="exportForm" label-width="100px">
        <el-form-item label="导出格式">
          <el-radio-group v-model="exportForm.format">
            <el-radio label="excel">Excel 表格</el-radio>
            <el-radio label="pdf">PDF 报告</el-radio>
            <el-radio label="html">HTML 报告</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="评估目标">
          <el-input
            v-model="exportForm.target"
            placeholder="留空则导出所有记录"
            clearable
          />
        </el-form-item>
        <el-form-item label="开始日期">
          <el-date-picker
            v-model="exportForm.startDate"
            type="date"
            placeholder="选择开始日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker
            v-model="exportForm.endDate"
            type="date"
            placeholder="选择结束日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showExportDialog = false">取消</el-button>
        <el-button type="primary" @click="handleExport" :loading="exporting">
          导出
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Refresh, Loading, CircleCheck, CircleClose, Download,
  Monitor, Document, Clock, View
} from '@element-plus/icons-vue'
import api from '../api/index'
import axios from 'axios'

export default {
  name: 'HexStrike',
  components: {
    Refresh,
    Loading,
    CircleCheck,
    CircleClose,
    Download,
    Monitor,
    Document,
    Clock,
    View
  },
  setup() {
    // 标签页状态
    const activeTab = ref('console')

    // 控制台相关状态
    const loading = ref(false)
    const error = ref(null)
    const status = ref(null)
    const showExportDialog = ref(false)
    const exporting = ref(false)
    const executions = ref([])
    const executionsLoading = ref(false)
    const executionsPage = ref(1)
    const executionsPageSize = ref(20)
    const executionsTotal = ref(0)

    // 报告列表相关状态
    const reports = ref([])
    const reportsLoading = ref(false)
    const searchTarget = ref('')
    const currentPage = ref(1)
    const pageSize = ref(20)
    const totalReports = ref(0)

    const exportForm = ref({
      format: 'excel',
      target: '',
      startDate: '',
      endDate: ''
    })

    // 根据环境确定 hexstrike API URL
    const hexstrikeApiUrl = ref('')

    const initUrl = () => {
      hexstrikeApiUrl.value = window.location.origin + '/hexstrike'
    }

    // 标签页切换处理
    const handleTabChange = (tabName) => {
      if (tabName === 'reports' && reports.value.length === 0) {
        loadReports()
      }
    }

    // ========== 控制台相关方法 ==========

    // 加载 HexStrike 服务状态
    const loadStatus = async () => {
      loading.value = true
      error.value = null

      try {
        let url = '/hexstrike/health'

        let response
        try {
          response = await fetch(url, {
            method: 'GET',
            mode: 'cors',
            credentials: 'omit'
          })

          if ((!response || !response.ok) && process.env.NODE_ENV !== 'production') {
            url = 'http://localhost:8888/health'
            response = await fetch(url, {
              method: 'GET',
              mode: 'cors',
              credentials: 'omit'
            })
          }
        } catch (proxyError) {
          if (process.env.NODE_ENV !== 'production') {
            url = 'http://localhost:8888/health'
            response = await fetch(url, {
              method: 'GET',
              mode: 'cors',
              credentials: 'omit'
            })
          } else {
            throw proxyError
          }
        }

        if (!response || !response.ok) {
          throw new Error(`服务不可用: ${response ? response.status : '无响应'}`)
        }

        const data = await response.json()
        status.value = data
        ElMessage.success('HexStrike 服务状态加载成功')
      } catch (e) {
        console.error('HexStrike service check failed:', e)
        error.value = `无法连接到 HexStrike 服务: ${e.message}。请确认：1) HexStrike 服务已启动（端口 8888）；2) 网络连接正常`
        status.value = null
        ElMessage.error('无法连接到 HexStrike 服务，请检查服务是否启动')
      } finally {
        loading.value = false
      }
    }

    // 格式化运行时间
    const formatUptime = (seconds) => {
      if (!seconds) return '-'
      const days = Math.floor(seconds / 86400)
      const hours = Math.floor((seconds % 86400) / 3600)
      const minutes = Math.floor((seconds % 3600) / 60)
      const secs = Math.floor(seconds % 60)

      if (days > 0) {
        return `${days}天 ${hours}小时 ${minutes}分钟`
      } else if (hours > 0) {
        return `${hours}小时 ${minutes}分钟`
      } else if (minutes > 0) {
        return `${minutes}分钟 ${secs}秒`
      } else {
        return `${secs}秒`
      }
    }

    // 获取分类名称（中文）
    const getCategoryName = (category) => {
      const names = {
        'essential': '必需工具',
        'network': '网络工具',
        'web_security': 'Web安全',
        'vuln_scanning': '漏洞扫描',
        'cloud': '云安全',
        'osint': 'OSINT',
        'forensics': '取证',
        'binary': '二进制',
        'password': '密码',
        'exploitation': '漏洞利用',
        'wireless': '无线',
        'api': 'API',
        'additional': '其他'
      }
      return names[category] || category
    }

    // 格式化日期时间
    const formatDateTime = (dateTime) => {
      if (!dateTime) return '-'
      try {
        const date = new Date(dateTime)
        if (isNaN(date.getTime())) return dateTime
        return date.toLocaleString('zh-CN', {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit'
        })
      } catch (e) {
        return dateTime
      }
    }

    // 加载执行记录
    const loadExecutions = async () => {
      executionsLoading.value = true
      try {
        const response = await api.get('/secops-agent/hexstrike_executions/', {
          params: {
            page: executionsPage.value,
            page_size: executionsPageSize.value
          }
        })
        executions.value = response.results || []
        executionsTotal.value = response.total || 0
      } catch (e) {
        console.error('加载执行记录失败:', e)
        ElMessage.error('加载执行记录失败')
      } finally {
        executionsLoading.value = false
      }
    }

    // 导出单个执行记录
    const exportSingleExecution = async (executionId) => {
      try {
        exporting.value = true
        const response = await api.get('/secops-agent/hexstrike_export/', {
          params: {
            format: 'excel',
            execution_ids: executionId.toString()
          },
          responseType: 'blob'
        })

        const url = window.URL.createObjectURL(new Blob([response]))
        const link = document.createElement('a')
        link.href = url
        link.setAttribute('download', `hexstrike_execution_${executionId}_${new Date().getTime()}.xlsx`)
        document.body.appendChild(link)
        link.click()
        link.remove()
        window.URL.revokeObjectURL(url)

        ElMessage.success('导出成功')
      } catch (e) {
        console.error('导出失败:', e)
        ElMessage.error('导出失败')
      } finally {
        exporting.value = false
      }
    }

    // 处理导出
    const handleExport = async () => {
      try {
        exporting.value = true

        const params = {
          format: exportForm.value.format
        }

        if (exportForm.value.target) {
          params.target = exportForm.value.target
        }
        if (exportForm.value.startDate) {
          params.start_date = exportForm.value.startDate
        }
        if (exportForm.value.endDate) {
          params.end_date = exportForm.value.endDate
        }

        const response = await api.get('/secops-agent/hexstrike_export/', {
          params,
          responseType: 'blob'
        })

        const extensions = {
          excel: 'xlsx',
          pdf: 'pdf',
          html: 'html'
        }
        const ext = extensions[exportForm.value.format] || 'xlsx'

        const url = window.URL.createObjectURL(new Blob([response]))
        const link = document.createElement('a')
        link.href = url
        const filename = `hexstrike_report_${new Date().getTime()}.${ext}`
        link.setAttribute('download', filename)
        document.body.appendChild(link)
        link.click()
        link.remove()
        window.URL.revokeObjectURL(url)

        ElMessage.success('导出成功')
        showExportDialog.value = false
      } catch (e) {
        console.error('导出失败:', e)
        ElMessage.error('导出失败: ' + (e.response?.data?.error || e.message))
      } finally {
        exporting.value = false
      }
    }

    // ========== 报告列表相关方法 ==========

    // 加载报告列表
    const loadReports = async () => {
      reportsLoading.value = true
      try {
        const response = await axios.get('/api/secops-agent/hexstrike_reports/', {
          params: {
            target: searchTarget.value,
            limit: pageSize.value
          }
        })

        if (response.data && response.data.reports) {
          reports.value = response.data.reports
          totalReports.value = response.data.total || reports.value.length
        }
      } catch (error) {
        console.error('加载报告列表失败:', error)
        ElMessage.error('加载报告列表失败: ' + (error.response?.data?.error || error.message))
      } finally {
        reportsLoading.value = false
      }
    }

    // 下载报告
    const downloadReport = (report) => {
      const url = report.download_url
      const link = document.createElement('a')
      link.href = url
      link.download = report.filename
      link.target = '_blank'
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)

      ElMessage.success('正在下载报告: ' + report.filename)
    }

    // 查看报告
    const viewReport = (report) => {
      window.open(report.download_url, '_blank')
    }

    // 格式化文件大小
    const formatFileSize = (bytes) => {
      if (bytes === 0) return '0 B'
      const k = 1024
      const sizes = ['B', 'KB', 'MB', 'GB']
      const i = Math.floor(Math.log(bytes) / Math.log(k))
      return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
    }

    const handleSizeChange = (val) => {
      pageSize.value = val
      loadReports()
    }

    const handleCurrentChange = (val) => {
      currentPage.value = val
      loadReports()
    }

    onMounted(() => {
      initUrl()
      loadStatus()
      loadExecutions()
    })

    return {
      activeTab,
      loading,
      error,
      status,
      hexstrikeApiUrl,
      loadStatus,
      formatUptime,
      getCategoryName,
      formatDateTime,
      showExportDialog,
      exporting,
      exportForm,
      handleExport,
      executions,
      executionsLoading,
      executionsPage,
      executionsPageSize,
      executionsTotal,
      loadExecutions,
      exportSingleExecution,
      // 报告列表
      reports,
      reportsLoading,
      searchTarget,
      currentPage,
      pageSize,
      totalReports,
      loadReports,
      downloadReport,
      viewReport,
      formatFileSize,
      handleSizeChange,
      handleCurrentChange,
      handleTabChange
    }
  }
}
</script>

<style scoped>
.hexstrike-container {
  max-width: 1200px;
}

.hexstrike-card {
  min-height: 600px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.loading-container {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 60px 20px;
  text-align: center;
}

.loading-icon {
  font-size: 48px;
  color: #409EFF;
  margin-bottom: 20px;
}

.error-container {
  padding: 20px;
}

.status-container {
  padding: 0;
}

.status-card {
  margin-bottom: 0;
}

.status-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.status-icon {
  font-size: 20px;
}

.status-icon.success {
  color: #67C23A;
}

.status-icon.error {
  color: #F56C6C;
}

.status-title {
  font-weight: 500;
  font-size: 16px;
}

.status-content {
  padding: 10px 0;
}

:deep(.el-descriptions__label) {
  font-weight: 500;
}

:deep(.el-statistic__head) {
  font-size: 14px;
  color: #606266;
}

/* 报告列表样式 */
.reports-content {
  padding: 20px 0;
}

.search-bar {
  display: flex;
  align-items: center;
  padding: 15px;
  background: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 20px;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #909399;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 20px;
}

.empty-state p {
  font-size: 16px;
  margin: 10px 0;
}

.hint {
  font-size: 14px;
  color: #C0C4CC;
}

.report-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 20px;
  margin-bottom: 20px;
}

.report-card {
  transition: transform 0.3s, box-shadow 0.3s;
}

.report-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}

.report-card .card-header {
  font-size: 16px;
  font-weight: bold;
  color: #303133;
}

.report-card .card-header .target {
  display: flex;
  align-items: center;
  gap: 5px;
}

.report-card .card-header .target .el-icon {
  color: #67C23A;
}

.report-info {
  margin: 15px 0;
}

.info-item {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
  color: #606266;
  font-size: 14px;
}

.info-item .el-icon {
  margin-right: 8px;
  color: #909399;
}

.report-actions {
  display: flex;
  gap: 10px;
}

.report-actions .el-button {
  flex: 1;
}

.pagination {
  margin-top: 20px;
  text-align: center;
}
</style>