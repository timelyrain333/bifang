import api from './index'

export const authApi = {
  // 获取CSRF token
  getCsrfToken() {
    return api.get('/auth/login/')
  },
  
  // 登录
  login(username, password) {
    return api.post('/auth/login/', {
      username,
      password
    })
  },
  
  // 登出
  logout() {
    return api.post('/auth/logout/')
  },
  
  // 获取当前用户信息
  getCurrentUser() {
    return api.get('/auth/user/')
  }
}
