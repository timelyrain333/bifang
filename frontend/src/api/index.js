import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,  // 增加到60秒，给任务启动留出足够时间
  headers: {
    'Content-Type': 'application/json'
  },
  withCredentials: true,  // 支持Session认证和CSRF
  paramsSerializer: (params) => {
    // 自定义参数序列化，确保数组参数被正确转换为多个同名参数
    // 例如: {asset_type: ['a', 'b']} => 'asset_type=a&asset_type=b'
    const searchParams = new URLSearchParams()
    Object.keys(params).forEach(key => {
      const value = params[key]
      if (Array.isArray(value)) {
        // 数组类型：添加多个同名参数
        value.forEach(v => {
          if (v !== null && v !== undefined) {
            searchParams.append(key, v)
          }
        })
      } else if (value !== null && value !== undefined) {
        // 非数组类型：正常添加
        searchParams.append(key, value)
      }
    })
    return searchParams.toString()
  }
})

// 获取CSRF token的函数
const getCsrfToken = () => {
  // 从cookie中获取CSRF token
  const name = 'csrftoken'
  const cookies = document.cookie.split(';')
  for (let cookie of cookies) {
    const [key, value] = cookie.trim().split('=')
    if (key === name) {
      return value
    }
  }
  return null
}

// 请求拦截器
api.interceptors.request.use(
  config => {
    // 添加CSRF token到请求头
    const csrfToken = getCsrfToken()
    if (csrfToken) {
      config.headers['X-CSRFToken'] = csrfToken
    }
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  response => {
    // 如果是blob响应（文件下载），直接返回response对象
    if (response.config.responseType === 'blob' || response.data instanceof Blob) {
      // 为了能在错误处理中读取错误信息，我们需要保存原始的response
      if (!response.headers) {
        response.headers = {}
      }
      // 尝试从response.headers或response的headers中获取
      if (response.response && response.response.headers) {
        Object.assign(response.headers, response.response.headers)
      }
      return response.data || response
    }
    return response.data
  },
  async error => {
    // 401未授权，清除用户信息并跳转到登录页
    if (error.response && error.response.status === 401) {
      try {
        const { useAuthStore } = await import('../stores/auth')
        useAuthStore().clearAuth()
        // 如果不在登录页，则跳转
        if (window.location.pathname !== '/login') {
          window.location.href = '/login'
        }
      } catch (e) {
        console.error('清除认证信息失败:', e)
      }
    }
    // 只在非401错误时记录详细信息
    if (!(error.response && error.response.status === 401)) {
      console.error('API Error:', error)
      if (error.response) {
        console.error('Response status:', error.response.status)
        console.error('Response data:', error.response.data)
      }
    }
    return Promise.reject(error)
  }
)

export default api
