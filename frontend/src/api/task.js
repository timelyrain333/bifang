import api from './index'

export const taskApi = {
  // 获取任务列表
  getTasks(params) {
    return api.get('/tasks/', { params })
  },
  
  // 获取任务详情
  getTask(id) {
    return api.get(`/tasks/${id}/`)
  },
  
  // 创建任务
  createTask(data) {
    return api.post('/tasks/', data)
  },
  
  // 更新任务
  updateTask(id, data) {
    return api.put(`/tasks/${id}/`, data)
  },
  
  // 删除任务
  deleteTask(id) {
    return api.delete(`/tasks/${id}/`)
  },
  
  // 执行任务
  executeTask(id) {
    return api.post(`/tasks/${id}/execute/`)
  },
  
  // 获取任务执行历史
  getTaskExecutions(id) {
    return api.get(`/tasks/${id}/executions/`)
  }
}







