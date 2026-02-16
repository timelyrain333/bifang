import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import Home from '../views/Home.vue'
import Login from '../views/Login.vue'
import TaskList from '../views/TaskList.vue'
import TaskForm from '../views/TaskForm.vue'
import PluginList from '../views/PluginList.vue'
import AssetList from '../views/AssetList.vue'
import CloudServer from '../views/CloudServer.vue'
import VPCNetwork from '../views/VPCNetwork.vue'
import LoadBalancer from '../views/LoadBalancer.vue'
import CloudDatabase from '../views/CloudDatabase.vue'
import DomainDNS from '../views/DomainDNS.vue'
import VulnerabilityList from '../views/VulnerabilityList.vue'
import SystemConfig from '../views/SystemConfig.vue'
import AliyunConfig from '../views/AliyunConfig.vue'
import AWSConfig from '../views/AWSConfig.vue'
import SecOpsAgent from '../views/SecOpsAgent.vue'
import HexStrike from '../views/HexStrike.vue'
import HexStrikeReports from '../views/HexStrikeReports.vue'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    name: 'Home',
    component: Home,
    meta: { requiresAuth: true }
  },
  {
    path: '/tasks',
    name: 'TaskList',
    component: TaskList,
    meta: { requiresAuth: true }
  },
  {
    path: '/tasks/new',
    name: 'TaskNew',
    component: TaskForm,
    meta: { requiresAuth: true }
  },
  {
    path: '/tasks/:id/edit',
    name: 'TaskEdit',
    component: TaskForm,
    meta: { requiresAuth: true }
  },
  {
    path: '/plugins',
    name: 'PluginList',
    component: PluginList,
    meta: { requiresAuth: true }
  },
  {
    path: '/assets',
    redirect: '/assets/fingerprints'
  },
  {
    path: '/assets/fingerprints',
    name: 'AssetFingerprints',
    component: AssetList,
    meta: { requiresAuth: true, title: '主机指纹' }
  },
  {
    path: '/assets/cloud-servers',
    name: 'CloudServer',
    component: CloudServer,
    meta: { requiresAuth: true, title: '云服务器' }
  },
  {
    path: '/assets/vpc-network',
    name: 'VPCNetwork',
    component: VPCNetwork,
    meta: { requiresAuth: true, title: 'VPC专有网络' }
  },
  {
    path: '/assets/load-balancer',
    name: 'LoadBalancer',
    component: LoadBalancer,
    meta: { requiresAuth: true, title: '负载均衡' }
  },
  {
    path: '/assets/cloud-database',
    name: 'CloudDatabase',
    component: CloudDatabase,
    meta: { requiresAuth: true, title: '云数据库' }
  },
  {
    path: '/assets/domain-dns',
    name: 'DomainDNS',
    component: DomainDNS,
    meta: { requiresAuth: true, title: '域名解析' }
  },
  {
    path: '/vulnerabilities',
    name: 'VulnerabilityList',
    component: VulnerabilityList,
    meta: { requiresAuth: true, title: '开源软件安全漏洞情报', source: 'oss_security' }
  },
  {
    path: '/vulnerabilities/cnvd',
    name: 'VulnerabilityListCNVD',
    component: VulnerabilityList,
    meta: { requiresAuth: true, title: '国家信息安全漏洞共享平台情报', source: 'cnvd' }
  },
  {
    path: '/system-config',
    name: 'SystemConfig',
    component: SystemConfig,
    meta: { requiresAuth: true, title: '系统配置' }
  },
  {
    path: '/aliyun-config',
    redirect: '/system-config'
  },
  {
    path: '/aws-config',
    name: 'AWSConfig',
    component: AWSConfig,
    meta: { requiresAuth: true, title: 'AWS配置管理' }
  },
  {
    path: '/secops-agent',
    name: 'SecOpsAgent',
    component: SecOpsAgent,
    meta: { requiresAuth: true, title: 'SecOps智能体' }
  },
  {
    path: '/hexstrike',
    name: 'HexStrike',
    component: HexStrike,
    meta: { requiresAuth: true, title: 'HexStrike AI 控制台' }
  },
  {
    path: '/hexstrike/reports',
    name: 'HexStrikeReports',
    component: HexStrikeReports,
    meta: { requiresAuth: true, title: 'HexStrike 安全评估报告' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()
  
  // 如果路由需要认证
  if (to.meta.requiresAuth) {
    // 检查是否已登录
    if (authStore.isAuthenticated.value) {
      next()
    } else {
      // 尝试从API获取用户信息（验证Session是否有效）
      try {
        const { authApi } = await import('../api/auth')
        const user = await authApi.getCurrentUser()
        // Session有效，更新用户信息
        authStore.setUser(user)
        next()
      } catch {
        // Session无效，跳转到登录页
        next({
          path: '/login',
          query: { redirect: to.fullPath }
        })
      }
    }
  } else {
    // 不需要认证的路由（如登录页）
    if (to.path === '/login' && authStore.isAuthenticated.value) {
      // 已登录用户访问登录页，跳转到首页
      next('/')
    } else {
      next()
    }
  }
})

export default router
