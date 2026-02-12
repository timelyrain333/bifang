import api from './index'

/**
 * 聊天会话管理 API 客户端
 */
export const chatApi = {
  /**
   * 获取所有会话列表
   */
  getSessions() {
    return api.get('/chat/sessions/')
  },

  /**
   * 获取单个会话详情
   */
  getSession(sessionId) {
    return api.get(`/chat/sessions/${sessionId}/`)
  },

  /**
   * 创建新会话
   * @param {Object} data - { title: string }
   */
  createSession(data) {
    return api.post('/chat/sessions/', data)
  },

  /**
   * 更新会话（重命名）
   * @param {number} sessionId
   * @param {Object} data - { title: string }
   */
  updateSession(sessionId, data) {
    return api.put(`/chat/sessions/${sessionId}/`, data)
  },

  /**
   * 删除会话（级联删除所有消息）
   * @param {number} sessionId
   */
  deleteSession(sessionId) {
    return api.delete(`/chat/sessions/${sessionId}/`)
  },

  /**
   * 设置活跃会话
   * @param {number} sessionId
   */
  setActive(sessionId) {
    return api.post(`/chat/sessions/${sessionId}/set_active/`)
  },

  /**
   * 获取会话的所有消息
   * @param {number} sessionId
   */
  getSessionMessages(sessionId) {
    return api.get(`/chat/sessions/${sessionId}/messages/`)
  },

  /**
   * 向会话添加消息
   * @param {number} sessionId
   * @param {Object} data - { role: 'user'|'assistant', content: string, metadata: {} }
   */
  addMessage(sessionId, data) {
    return api.post(`/chat/sessions/${sessionId}/add_message/`, data)
  }
}
