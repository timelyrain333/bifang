import api from './index'

export const pluginApi = {
  // 获取插件列表
  getPlugins() {
    return api.get('/plugins/')
  },
  
  // 获取插件详情
  getPlugin(id) {
    return api.get(`/plugins/${id}/`)
  },
  
  // 获取插件关联的任务
  getPluginTasks(id) {
    return api.get(`/plugins/${id}/tasks/`)
  }
}








