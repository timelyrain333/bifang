import api from './index'

export const secopsAgentApi = {
  // HexStrike 集成状态（资产安全评估能力是否可用）
  hexstrikeStatus() {
    return fetch('/api/secops-agent/hexstrike_status/', {
      method: 'GET',
      credentials: 'include'
    }).then(res => res.json())
  },
  // 与智能体对话（流式）
  chat(message, history = []) {
    return fetch('/api/secops-agent/chat/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': this.getCsrfToken()
      },
      credentials: 'include',
      body: JSON.stringify({
        message,
        conversation_history: history
      })
    })
  },
  
  // 获取CSRF Token
  getCsrfToken() {
    const name = 'csrftoken'
    let cookieValue = null
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';')
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim()
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1))
          break
        }
      }
    }
    return cookieValue || ''
  }
}

