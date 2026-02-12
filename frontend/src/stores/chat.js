/**
 * 聊天状态管理（多会话版本）
 * 支持数据库持久化和会话切换
 */
import { reactive, watch } from 'vue'
import { chatApi } from '../api/chat'

const STORAGE_KEY = 'secops_chat_history'

// 创建响应式状态
const state = reactive({
  // 会话相关
  sessions: [],
  currentSessionId: null,
  sessionsLoading: false,

  // 当前会话的消息
  messages: [],
  messageUpdateLock: false,  // 防止并发更新消息

  // 其他状态
  isLoading: false,
  hexstrikeStatus: {
    checked: false,
    connected: false
  }
})

// ========== 初始化 ==========

/**
 * 从 localStorage 迁移旧数据到数据库
 */
const migrateFromLocalStorage = async () => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (!saved) return

    const data = JSON.parse(saved)
    if (!data.messages || data.messages.length === 0) return

    console.log('开始迁移旧聊天记录到数据库...')

    // 创建新会话
    const session = await chatApi.createSession({
      title: '历史对话导入'
    })

    // 批量导入消息
    const promises = data.messages.map(msg =>
      chatApi.addMessage(session.id, {
        role: msg.role,
        content: msg.content,
        timestamp: msg.timestamp
      })
    )

    await Promise.all(promises)

    // 清除 localStorage
    localStorage.removeItem(STORAGE_KEY)
    console.log('迁移完成，已清除 localStorage')

    // 刷新会话列表
    await loadSessionsInternal()
    await switchSession(session.id)

    return session
  } catch (error) {
    console.error('迁移失败:', error)
  }
}

// ========== 内部方法 ==========

/**
 * 从数据库加载会话列表（内部方法，不触发加载锁）
 */
const loadSessionsInternal = async () => {
  console.log('开始加载会话列表')
  state.sessionsLoading = true
  try {
    const response = await chatApi.getSessions()
    console.log('会话列表 API 响应:', response)

    // 处理可能的响应包装
    let sessions = response
    if (response && typeof response === 'object' && !Array.isArray(response)) {
      // 如果是 DRF 的分页响应，提取 results
      sessions = response.results || response.data || []
    }

    // 确保 sessions 是数组
    if (!Array.isArray(sessions)) {
      console.warn('API 返回的会话数据不是数组:', sessions)
      sessions = []
    }

    console.log('解析后的会话数组:', sessions)

    // 使用 reactive 数组方法更新，保持响应性
    state.sessions.length = 0
    sessions.forEach(s => state.sessions.push(s))

    console.log('更新后的 state.sessions:', state.sessions)

    // 如果有活跃会话，自动加载
    const activeSession = sessions.find(s => s.is_active)
    if (activeSession && !state.currentSessionId) {
      console.log('找到活跃会话，自动切换:', activeSession)
      await switchSession(activeSession.id)
    }
  } catch (error) {
    console.error('加载会话列表失败:', error)
  } finally {
    state.sessionsLoading = false
  }
}

/**
 * 创建新会话
 */
const createSession = async (title) => {
  try {
    const defaultTitle = title || `新对话 ${new Date().toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })}`

    // 先创建会话
    const session = await chatApi.createSession({
      title: defaultTitle
    })

    // 添加到本地状态
    state.sessions.unshift(session)

    // 立即切换到新会话
    state.currentSessionId = session.id
    state.messages.length = 0

    return session
  } catch (error) {
    console.error('创建会话失败:', error)
    throw error
  }
}

/**
 * 切换会话
 */
const switchSession = async (sessionId) => {
  console.log('开始切换会话:', sessionId)
  try {
    state.currentSessionId = sessionId
    console.log('设置 currentSessionId:', state.currentSessionId)

    // 加载会话的消息
    const response = await chatApi.getSessionMessages(sessionId)
    console.log('API 返回的原始响应:', response)

    // 处理可能的响应包装
    let messages = response
    if (response && typeof response === 'object' && !Array.isArray(response)) {
      // 如果是 DRF 的分页响应，提取 results
      messages = response.results || response.data || []
    }

    // 确保 messages 是数组
    if (!Array.isArray(messages)) {
      console.warn('API 返回的消息数据不是数组:', messages)
      messages = []
    }

    console.log('解析后的消息数组:', messages)

    // 使用 reactive 数组方法更新，保持响应性
    state.messages.length = 0
    messages.forEach(msg => state.messages.push(msg))

    console.log('更新后的 state.messages:', state.messages)

    // 更新会话的活跃状态（使用 reactive 方法）
    state.sessions.forEach(s => {
      s.is_active = s.id === sessionId
    })
  } catch (error) {
    console.error('切换会话失败:', error)
  }
}

/**
 * 删除会话
 */
const deleteSession = async (sessionId) => {
  try {
    await chatApi.deleteSession(sessionId)

    // 从列表中移除（使用 reactive 数组方法）
    const index = state.sessions.findIndex(s => s.id === sessionId)
    if (index !== -1) {
      state.sessions.splice(index, 1)
    }

    // 如果删除的是当前会话，清空消息并切换
    if (state.currentSessionId === sessionId) {
      state.messages.length = 0
      state.currentSessionId = null

      // 如果还有其他会话，切换到第一个
      if (state.sessions.length > 0) {
        await switchSession(state.sessions[0].id)
      }
    }
  } catch (error) {
    console.error('删除会话失败:', error)
  }
}

/**
 * 重命名会话
 */
const renameSession = async (sessionId, newTitle) => {
  try {
    await chatApi.updateSession(sessionId, { title: newTitle })

    // 更新本地状态
    const session = state.sessions.find(s => s.id === sessionId)
    if (session) {
      session.title = newTitle
    }
  } catch (error) {
    console.error('重命名会话失败:', error)
  }
}

// ========== 消息管理方法 ==========

/**
 * 发送消息（保存到数据库）
 */
const addMessage = async (message, saveToDb = true) => {
  // 如果没有当前会话，先创建一个
  if (!state.currentSessionId) {
    await createSession()
  }

  try {
    // 乐观更新：立即添加到 UI
    const tempMessage = {
      ...message,
      id: Date.now(),
      timestamp: new Date(),
      isStreaming: message.role === 'assistant'
    }

    state.messages.push(tempMessage)

    // 如果内容为空或不需要保存到数据库，跳过 API 调用
    if (!saveToDb || !message.content) {
      return tempMessage
    }

    // 异步保存到数据库
    const newMessage = await chatApi.addMessage(state.currentSessionId, {
      role: message.role,
      content: message.content,
      metadata: message.metadata || {}
    })

    // 更新消息ID（用服务器返回的真实ID）
    const msgIndex = state.messages.findIndex(m => m.id === tempMessage.id)
    if (msgIndex !== -1) {
      state.messages[msgIndex] = {
        ...state.messages[msgIndex],
        id: newMessage.id,
        timestamp: newMessage.timestamp
      }
    }

    // 更新会话的 updated_at 时间
    const session = state.sessions.find(s => s.id === state.currentSessionId)
    if (session) {
      session.updated_at = new Date().toISOString()
    }

    return newMessage
  } catch (error) {
    console.error('发送消息失败:', error)
    throw error
  }
}

/**
 * 更新消息内容
 */
const updateLastMessage = (content) => {
  if (state.messages.length === 0) return

  // 防止并发更新（流式输出时频繁更新）
  if (state.messageUpdateLock) return

  const lastIndex = state.messages.length - 1
  state.messages[lastIndex].content = content

  // 不立即同步到数据库，等待流式结束后再同步
}

/**
 * 同步最后一条消息到数据库（流式结束后调用）
 */
const syncLastMessage = async () => {
  if (state.messages.length === 0) return

  const lastIndex = state.messages.length - 1
  const lastMsg = state.messages[lastIndex]

  // 如果内容为空，不保存
  if (!lastMsg.content || lastMsg.content.trim() === '') {
    return
  }

  // 如果消息ID小于10000000，说明是数据库ID，需要更新
  // 否则是临时ID，需要创建新消息
  const isPersisted = lastMsg.id && lastMsg.id < 10000000

  try {
    if (isPersisted) {
      // 更新现有消息（需要后端支持）
      // 暂时跳过，因为后端没有 updateMessage 端点
      console.log('消息已存在数据库中，跳过更新')
    } else {
      // 保存为新消息
      const newMessage = await chatApi.addMessage(state.currentSessionId, {
        role: lastMsg.role,
        content: lastMsg.content,
        metadata: lastMsg.metadata || {}
      })

      // 更新消息ID
      state.messages[lastIndex] = {
        ...state.messages[lastIndex],
        id: newMessage.id,
        timestamp: newMessage.timestamp
      }
    }
  } catch (error) {
    console.error('同步消息失败:', error)
  }
}

/**
 * 设置消息流式状态
 */
const setMessageStreaming = (isStreaming) => {
  if (state.messages.length === 0) return

  const lastIndex = state.messages.length - 1
  state.messages[lastIndex].isStreaming = isStreaming
}

/**
 * 清空当前会话的消息（不删除会话）
 */
const clearHistory = () => {
  state.messages.length = 0
}

/**
 * 设置加载状态
 */
const setLoading = (loading) => {
  state.isLoading = loading
}

/**
 * 更新 HexStrike 状态
 */
const updateHexstrikeStatus = (status) => {
  Object.assign(state.hexstrikeStatus, status)
}

// ========== 导出 ==========

export const useChatStore = () => {
  return {
    // 状态
    sessions: state.sessions,
    currentSessionId: state.currentSessionId,
    messages: state.messages,
    isLoading: state.isLoading,
    sessionsLoading: state.sessionsLoading,
    hexstrikeStatus: state.hexstrikeStatus,

    // 会话方法
    loadSessions: loadSessionsInternal,
    createSession,
    switchSession,
    deleteSession,
    renameSession,

    // 消息方法
    addMessage,
    updateLastMessage,
    syncLastMessage,
    setMessageStreaming,
    clearHistory,

    // 其他方法
    setLoading,
    updateHexstrikeStatus,

    // 初始化
    init: async () => {
      // 确保不触发重复加载
      if (state.sessions.length > 0) return

      // 加载会话列表和迁移
      await loadSessionsInternal()

      // 如果有活跃会话，自动切换
      const activeSession = state.sessions.find(s => s.is_active)
      if (activeSession && !state.currentSessionId) {
        await switchSession(activeSession.id)
      }
    }
  }
}
