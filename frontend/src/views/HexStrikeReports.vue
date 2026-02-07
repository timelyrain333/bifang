<template>
  <div class="hexstrike-reports">
    <div class="page-header">
      <h1>
        <i class="el-icon-document"></i>
        HexStrike 安全评估报告
      </h1>
      <el-button type="primary" size="small" @click="loadReports" :loading="loading">
        <i class="el-icon-refresh"></i> 刷新
      </el-button>
    </div>

    <!-- 搜索栏 -->
    <div class="search-bar">
      <el-input
        v-model="searchTarget"
        placeholder="搜索目标 IP 或域名"
        prefix-icon="el-icon-search"
        clearable
        style="width: 300px; margin-right: 10px;"
        @clear="loadReports"
        @keyup.enter.native="loadReports"
      >
      </el-input>
      <el-button type="primary" @click="loadReports">搜索</el-button>
      <el-button @click="searchTarget = ''; loadReports()">重置</el-button>
    </div>

    <!-- 报告列表 -->
    <el-card class="report-list" v-loading="loading">
      <div v-if="reports.length === 0" class="empty-state">
        <i class="el-icon-document"></i>
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
              <i class="el-icon-monitor"></i>
              {{ report.target }}
            </span>
            <el-tag size="mini" type="info">HTML 报告</el-tag>
          </div>

          <div class="report-info">
            <div class="info-item">
              <i class="el-icon-time"></i>
              <span>{{ report.created_time }}</span>
            </div>
            <div class="info-item">
              <i class="el-icon-document"></i>
              <span>{{ formatFileSize(report.size) }}</span>
            </div>
          </div>

          <div class="report-actions">
            <el-button
              type="primary"
              size="small"
              icon="el-icon-download"
              @click="downloadReport(report)"
            >
              下载报告
            </el-button>
            <el-button
              type="success"
              size="small"
              icon="el-icon-view"
              @click="viewReport(report)"
            >
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
    </el-card>
  </div>
</template>

<script>
import axios from 'axios'

export default {
  name: 'HexStrikeReports',
  data() {
    return {
      reports: [],
      loading: false,
      searchTarget: '',
      currentPage: 1,
      pageSize: 20,
      totalReports: 0
    }
  },
  mounted() {
    this.loadReports()
  },
  methods: {
    async loadReports() {
      this.loading = true
      try {
        const response = await axios.get('/api/secops-agent/hexstrike_reports/', {
          params: {
            target: this.searchTarget,
            limit: this.pageSize
          }
        })

        if (response.data && response.data.reports) {
          this.reports = response.data.reports
          this.totalReports = response.data.total || this.reports.length
        }
      } catch (error) {
        console.error('加载报告列表失败:', error)
        this.$message.error('加载报告列表失败: ' + (error.response?.data?.error || error.message))
      } finally {
        this.loading = false
      }
    },

    downloadReport(report) {
      // 在新窗口中打开报告（触发下载）
      const url = report.download_url
      const link = document.createElement('a')
      link.href = url
      link.download = report.filename
      link.target = '_blank'
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)

      this.$message.success('正在下载报告: ' + report.filename)
    },

    viewReport(report) {
      // 在新标签页中打开报告
      window.open(report.download_url, '_blank')
    },

    formatFileSize(bytes) {
      if (bytes === 0) return '0 B'
      const k = 1024
      const sizes = ['B', 'KB', 'MB', 'GB']
      const i = Math.floor(Math.log(bytes) / Math.log(k))
      return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
    },

    handleSizeChange(val) {
      this.pageSize = val
      this.loadReports()
    },

    handleCurrentChange(val) {
      this.currentPage = val
      this.loadReports()
    }
  }
}
</script>

<style scoped>
.hexstrike-reports {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0;
  font-size: 24px;
  color: #303133;
}

.page-header h1 i {
  margin-right: 10px;
  color: #409EFF;
}

.search-bar {
  margin-bottom: 20px;
  padding: 20px;
  background: #fff;
  border-radius: 4px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.report-list {
  min-height: 400px;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #909399;
}

.empty-state i {
  font-size: 64px;
  margin-bottom: 20px;
  display: block;
}

.empty-state p {
  font-size: 16px;
  margin: 10px 0;
}

.empty-state .hint {
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

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header .target {
  font-size: 16px;
  font-weight: bold;
  color: #303133;
}

.card-header .target i {
  margin-right: 5px;
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

.info-item i {
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