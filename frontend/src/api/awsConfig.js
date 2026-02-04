import api from './index'

export const awsConfigApi = {
  // 获取配置列表
  getConfigs() {
    return api.get('/aws-configs/')
  },
  
  // 获取配置详情
  getConfig(id) {
    return api.get(`/aws-configs/${id}/`)
  },
  
  // 创建配置
  createConfig(data) {
    return api.post('/aws-configs/', data)
  },
  
  // 更新配置
  updateConfig(id, data) {
    return api.put(`/aws-configs/${id}/`, data)
  },
  
  // 删除配置
  deleteConfig(id) {
    return api.delete(`/aws-configs/${id}/`)
  },
  
  // 设置默认配置
  setDefault(id) {
    return api.post(`/aws-configs/${id}/set_default/`)
  },
  
  // 获取默认配置
  getDefault() {
    return api.get('/aws-configs/default/')
  }
}
