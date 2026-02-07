/**
 * 用户认证状态管理
 */
import { ref, reactive } from 'vue'

// 全局状态
const user = ref(null)
const isAuthenticated = ref(false)

// 从localStorage恢复状态
const loadFromStorage = () => {
  try {
    const savedUser = localStorage.getItem('user')
    if (savedUser) {
      user.value = JSON.parse(savedUser)
      isAuthenticated.value = true
    }
  } catch (e) {
    console.error('加载用户信息失败:', e)
    clearAuth()
  }
}

// 清除认证信息
const clearAuth = () => {
  user.value = null
  isAuthenticated.value = false
  localStorage.removeItem('user')
}

// 导出store对象
export const useAuthStore = () => {
  return {
    user,
    isAuthenticated,
    setUser: (userData) => {
      user.value = userData
      isAuthenticated.value = true
      localStorage.setItem('user', JSON.stringify(userData))
    },
    clearAuth,
    // 初始化：从localStorage加载
    init: () => {
      loadFromStorage()
    }
  }
}

// 初始化
loadFromStorage()







