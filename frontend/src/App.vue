<template>
  <div v-if="showLayout">
    <el-container class="app-container">
      <el-header class="app-header">
        <div class="header-content">
          <h1>Bifang - 云端网络安全威胁感知系统</h1>
          <div class="header-right">
            <el-dropdown @command="handleCommand">
              <span class="user-info">
                <el-icon><User /></el-icon>
                {{ userInfo?.username || '用户' }}
                <el-icon class="el-icon--right"><arrow-down /></el-icon>
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="logout">退出登录</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
      </el-header>
      <el-container>
        <el-aside width="200px" class="app-aside">
          <el-menu
            :default-active="activeMenu"
            router
            class="sidebar-menu"
          >
            <el-menu-item index="/">
              <el-icon><Menu /></el-icon>
              <span>首页</span>
            </el-menu-item>
            <el-menu-item index="/tasks">
              <el-icon><List /></el-icon>
              <span>任务管理</span>
            </el-menu-item>
            <el-menu-item index="/plugins">
              <el-icon><Setting /></el-icon>
              <span>插件管理</span>
            </el-menu-item>
            <el-sub-menu index="assets">
              <template #title>
                <el-icon><DataBoard /></el-icon>
                <span>资产数据</span>
              </template>
              <el-menu-item index="/assets/aws">
                <el-icon><List /></el-icon>
                <span>AWS</span>
              </el-menu-item>
              <el-menu-item index="/assets/aliyun">
                <el-icon><List /></el-icon>
                <span>阿里云</span>
              </el-menu-item>
            </el-sub-menu>
            <el-sub-menu index="vulnerability">
              <template #title>
                <el-icon><Warning /></el-icon>
                <span>漏洞情报库</span>
              </template>
              <el-menu-item index="/vulnerabilities">
                <el-icon><List /></el-icon>
                <span>开源软件安全漏洞情报</span>
              </el-menu-item>
              <el-menu-item index="/vulnerabilities/cnvd">
                <el-icon><List /></el-icon>
                <span>国家信息安全漏洞共享平台情报</span>
              </el-menu-item>
            </el-sub-menu>
            <el-menu-item index="/system-config">
              <el-icon><Setting /></el-icon>
              <span>系统配置</span>
            </el-menu-item>
            <el-menu-item index="/secops-agent">
              <el-icon><ChatDotRound /></el-icon>
              <span>SecOps智能体</span>
            </el-menu-item>
          </el-menu>
        </el-aside>
        <el-main class="app-main">
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </div>
  <div v-else>
    <router-view />
  </div>
</template>

<script>
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown, User, ChatDotRound } from '@element-plus/icons-vue'
import { useAuthStore } from './stores/auth'
import { authApi } from './api/auth'

export default {
  name: 'App',
  components: {
    ArrowDown,
    User,
    ChatDotRound
  },
  setup() {
    const route = useRoute()
    const router = useRouter()
    const authStore = useAuthStore()
    
    // 初始化认证状态
    onMounted(() => {
      authStore.init()
      // 验证Session是否有效
      if (authStore.isAuthenticated.value) {
        authApi.getCurrentUser()
          .then(user => {
            authStore.setUser(user)
          })
          .catch(() => {
            authStore.clearAuth()
          })
      }
    })
    
    const activeMenu = computed(() => route.path)
    const showLayout = computed(() => route.path !== '/login')
    const userInfo = computed(() => authStore.user.value)
    
    const handleCommand = async (command) => {
      if (command === 'logout') {
        try {
          await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning'
          })
          
          await authApi.logout()
          authStore.clearAuth()
          ElMessage.success('已退出登录')
          router.push('/login')
        } catch (error) {
          if (error !== 'cancel') {
            // 即使API失败也清除本地状态
            authStore.clearAuth()
            router.push('/login')
          }
        }
      }
    }
    
    return {
      activeMenu,
      showLayout,
      userInfo,
      handleCommand
    }
  }
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

#app {
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB',
    'Microsoft YaHei', '微软雅黑', Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.app-container {
  height: 100vh;
}

.app-header {
  background-color: #409EFF;
  color: white;
  display: flex;
  align-items: center;
  padding: 0 20px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.header-content h1 {
  font-size: 20px;
  font-weight: normal;
  margin: 0;
}

.header-right {
  display: flex;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  color: white;
  cursor: pointer;
  padding: 0 10px;
}

.user-info:hover {
  opacity: 0.8;
}

.user-info .el-icon {
  margin-right: 5px;
}

.app-aside {
  background-color: #304156;
}

.sidebar-menu {
  border-right: none;
  background-color: #304156;
}

.sidebar-menu .el-menu-item {
  color: #bfcbd9;
}

.sidebar-menu .el-menu-item:hover {
  background-color: #263445;
  color: #409EFF;
}

.sidebar-menu .el-menu-item.is-active {
  background-color: #409EFF;
  color: white;
}

.app-main {
  background-color: #f0f2f5;
  padding: 20px;
}
</style>
