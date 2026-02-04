import api from './index'

export const aliyunConfigApi = {
  // 获取配置列表
  getConfigs() {
    return api.get('/aliyun-configs/')
  },
  
  // 获取配置详情
  getConfig(id) {
    return api.get(`/aliyun-configs/${id}/`)
  },
  
  // 创建配置
  createConfig(data) {
    return api.post('/aliyun-configs/', data)
  },
  
  // 更新配置
  updateConfig(id, data) {
    return api.put(`/aliyun-configs/${id}/`, data)
  },
  
  // 删除配置
  deleteConfig(id) {
    return api.delete(`/aliyun-configs/${id}/`)
  },
  
  // 设置默认配置
  setDefault(id) {
    return api.post(`/aliyun-configs/${id}/set_default/`)
  },
  
  // 获取默认配置
  getDefault() {
    return api.get('/aliyun-configs/default/')
  },
  
  // 测试钉钉配置
  testDingtalk(id) {
    return api.post(`/aliyun-configs/${id}/test_dingtalk/`)
  },
  
  // 测试通义千问配置
  testQianwen(id) {
    return api.post(`/aliyun-configs/${id}/test_qianwen/`)
  },
  
  // 测试AI解析功能
  testAiParsing(id) {
    return api.post(`/aliyun-configs/${id}/test_ai_parsing/`)
  }
}
