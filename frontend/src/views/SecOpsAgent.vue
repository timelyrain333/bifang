<template>
  <div class="secops-agent">
    <el-card class="agent-card">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <span class="title">🤖 SecOps智能体</span>
            <el-tag type="info" size="small" effect="plain">基于通义千问大模型</el-tag>
          </div>
          <div class="header-right">
            <ChatHistoryDropdown />
            <el-tag
              v-if="chatStore.hexstrikeStatus.checked"
              :type="chatStore.hexstrikeStatus.connected ? 'success' : 'warning'"
              size="small"
              effect="plain"
            >
              {{ chatStore.hexstrikeStatus.connected ? '✓ 资产安全评估已连接' : '⚠ 资产安全评估未连接' }}
            </el-tag>
          </div>
        </div>
      </template>

      <!-- 对话区域 -->
      <div class="chat-container" ref="chatContainerRef" @scroll="handleScroll">
        <div class="messages" v-if="chatStore.messages.length > 0">
          <TransitionGroup name="message-fade">
            <div
              v-for="(msg, index) in chatStore.messages"
              :key="msg.id || index"
              :class="['message', msg.role]"
            >
              <div class="message-header">
                <span class="role-name">
                  {{ msg.role === 'user' ? '👤 您' : '🤖 SecOps 智能体' }}
                </span>
                <span class="message-time">{{ formatTime(msg.timestamp) }}</span>
              </div>
              <div :class="['message-content', { 'streaming': msg.isStreaming }]">
                <div v-html="formatMessage(msg.content || '')"></div>
              </div>
            </div>
          </TransitionGroup>
        </div>

        <!-- 空状态 -->
        <div v-else class="empty-state">
          <div class="empty-content">
            <div class="empty-icon">🤖</div>
            <h3>开始与智能体对话</h3>
            <p>让它帮您执行安全运营任务，获得专业的安全建议</p>
            <div class="suggestions">
              <div
                v-for="(suggestion, idx) in suggestions"
                :key="idx"
                class="suggestion-card"
                @click="useSuggestion(suggestion.text)"
              >
                <div class="suggestion-icon">{{ suggestion.icon }}</div>
                <div class="suggestion-text">{{ suggestion.text }}</div>
                <div class="suggestion-arrow">→</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 思考中指示器 -->
        <Transition name="fade">
          <div v-if="chatStore.isLoading" class="thinking-indicator">
            <div class="thinking-dots">
              <span class="dot"></span>
              <span class="dot"></span>
              <span class="dot"></span>
            </div>
            <span class="thinking-text">智能体正在思考</span>
          </div>
        </Transition>
      </div>

      <!-- 输入区域 -->
      <div class="input-area">
        <div class="input-wrapper">
          <el-input
            v-model="inputMessage"
            type="textarea"
            :rows="inputRows"
            placeholder="输入您的指令，例如：请捕获最新的漏洞并检查我的资产是否受影响"
            @keydown.ctrl.enter="sendMessage"
            @keydown.meta.enter="sendMessage"
            @input="handleInput"
            :disabled="chatStore.isLoading"
            class="message-input"
            ref="inputRef"
          />
          <div class="input-actions">
            <div class="input-hint">
              <span>Ctrl + Enter 发送</span>
            </div>
            <el-button
              @click="sendMessage"
              :loading="chatStore.isLoading"
              :disabled="!inputMessage.trim() || chatStore.isLoading"
              size="default"
              class="send-button"
            >
              <el-icon v-if="!chatStore.isLoading" class="send-icon"><Promotion /></el-icon>
              <span v-else class="loading-text">发送中</span>
            </el-button>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Promotion } from '@element-plus/icons-vue'
import { secopsAgentApi } from '../api/secopsAgent'
import { useChatStore } from '../stores/chat'
import ChatHistoryDropdown from '../components/ChatHistoryDropdown.vue'

// 使用聊天 store
const chatStore = useChatStore()

// 本地状态
const inputMessage = ref('')
const chatContainerRef = ref(null)
const inputRef = ref(null)
const inputRows = ref(3)
const userScrolled = ref(false)

// 建议列表
const suggestions = [
  { icon: '🔍', text: '请捕获最新的漏洞并检查我的资产是否受影响' },
  { icon: '📊', text: '采集最近7天的漏洞信息' },
  { icon: '🛡️', text: '检查哪些资产可能受到最新漏洞的影响' },
  { icon: '⚡', text: '对资产做一次安全评估' }
]

// 格式化时间
const formatTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

// Markdown 渲染（简化版，可后续集成 marked 或 markdown-it）
const formatMessage = (content) => {
  if (!content) return ''

  // 预处理：转义 HTML
  let html = content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  // Markdown 基本语法
  .replace(/\n/g, '<br>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/~~(.+?)~~/g, '<del>$1</del>')

  // 表情符号颜色
  .replace(/✅/g, '<span class="emoji-success">✅</span>')
  .replace(/❌/g, '<span class="emoji-error">❌</span>')
    .replace(/⚠️/g, '<span class="emoji-warning">⚠️</span>')
    .replace(/ℹ️/g, '<span class="emoji-info">ℹ️</span>')

  // 代码块
  .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code class="language-$1">$2</code></pre>')

  // 报告下载按钮
  .replace(
      /\[点击下载 HTML 报告\]\((\/api\/reports\/hexstrike\/[^)]+)\)/g,
      '<div class="report-download"><el-button type="primary" size="small" onclick="window.open(\'$1\', \'_blank\')">📄 下载完整 HTML 报告</el-button></div>'
    )

  // 普通链接
  .replace(
      /\[([^\]]+)\]\((\/api\/[^)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
    )

  // URL 自动链接
  .replace(
      /(https?:\/\/[^\s<]+)/g,
      '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>'
    )

  return html
}

// 自动滚动
const handleScroll = () => {
  if (!chatContainerRef.value) return
  const container = chatContainerRef.value
  const threshold = 100
  const distanceToBottom = container.scrollHeight - container.scrollTop - container.clientHeight
  userScrolled.value = distanceToBottom > threshold
}

// 自动滚动到底部
const scrollToBottom = (force = false) => {
  if (!chatContainerRef.value) return
  if (force && userScrolled.value) return

  nextTick(() => {
    if (chatContainerRef.value) {
      chatContainerRef.value.scrollTo({
        top: chatContainerRef.value.scrollHeight,
        behavior: 'smooth'
      })
    }
  })
}

// 使用建议
const useSuggestion = (text) => {
  inputMessage.value = text
  sendMessage()
}

// 发送消息
const sendMessage = async () => {
  const message = inputMessage.value.trim()
  if (!message || chatStore.isLoading) return

  // 重置滚动锁定
  userScrolled.value = false

  // 添加用户消息到 store
  chatStore.addMessage({
    role: 'user',
    content: message,
    timestamp: new Date(),
    isStreaming: false
  })

  // 清空输入框
  inputMessage.value = ''
  inputRows.value = 3

  // 创建助手思考过程消息占位（不保存到数据库）
  chatStore.addMessage({
    role: 'assistant',
    type: 'thinking',
    content: '正在思考...',
    timestamp: new Date(),
    isStreaming: true
  }, false)

  scrollToBottom(true)
  chatStore.setLoading(true)

  try {
    // 构建对话历史（排除当前正在流式输出的消息）
    const history = chatStore.messages
      .slice(0, -1)
      .filter(msg => msg.role === 'user' || msg.role === 'assistant')
      .map(msg => ({
        role: msg.role,
        content: msg.content
      }))

    // 调用流式 API
    const response = await secopsAgentApi.chat(message, history)

    // 创建读取器
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const rawData = line.substring(6)

            // 尝试解析为 JSON（新格式：{"type": "thinking", "content": "..."}）
            let data
            try {
              data = JSON.parse(rawData)
            } catch (e) {
              // 不是 JSON 格式，当作普通文本处理
              data = { content: rawData }
            }

            // 处理不同类型的消息
            if (data.error) {
              ElMessage.error(data.error)
              chatStore.updateLastMessage(
                chatStore.messages[chatStore.messages.length - 1].content + `\n\n❌ 错误: ${data.error}\n`
              )
            } else if (data.done) {
              // 流式结束，保存消息到数据库
              await chatStore.syncLastMessage()
              chatStore.setMessageStreaming(false)
            } else if (data.type === 'thinking') {
              // 思考过程消息（灰色，可展开）
              chatStore.addMessage({
                role: 'assistant',
                type: 'thinking',
                content: data.content || '正在思考...',
                timestamp: new Date(),
                isStreaming: false,
                expandable: true
              }, false)
            } else if (data.type === 'final' && data.content) {
              // 最终答复内容（黑色，追加到当前 final 消息）
              chatStore.updateLastMessage(
                chatStore.messages[chatStore.messages.length - 1].content + data.content
              )
              scrollToBottom()
            } else if (data.content) {
              // 兼容旧格式：普通文本内容（追加到最后一条消息）
              chatStore.updateLastMessage(
                chatStore.messages[chatStore.messages.length - 1].content + data.content
              )
              scrollToBottom()
            }
          } catch (e) {
            console.error('解析SSE失败:', e, line)
          }
        }
      }
    }

    // 处理剩余 buffer
    if (buffer.startsWith('data: ')) {
      try {
        const data = JSON.parse(buffer.substring(6))
        if (data.content) {
          const currentContent = chatStore.messages[chatStore.messages.length - 1].content
          chatStore.updateLastMessage(currentContent + data.content)
        }
      } catch (e) {
        // ignore
      }
    }

    // 流式结束，保存消息到数据库
    await chatStore.syncLastMessage()
    chatStore.setMessageStreaming(false)
    scrollToBottom()
    chatStore.setLoading(false)

  } catch (error) {
    console.error('发送消息失败:', error)
    ElMessage.error(error.message || '发送消息失败，请检查网络连接')
    const currentContent = chatStore.messages[chatStore.messages.length - 1]?.content || ''
    chatStore.updateLastMessage(currentContent + `\n\n❌ 错误: ${error.message}\n`)
    chatStore.setMessageStreaming(false)
    // 即使出错也尝试保存（可能已接收部分内容）
    await chatStore.syncLastMessage()
  } finally {
    chatStore.setLoading(false)
    scrollToBottom()
  }
}

// 处理输入
const handleInput = () => {
  // 自动调整文本框高度
  const lines = inputMessage.value.split('\n').length
  inputRows.value = Math.min(Math.max(lines, 3), 10)
}

// 聚焦输入框
nextTick(() => {
  if (inputRef.value) {
    inputRef.value.focus()
  }
})

// 组件卸载时的清理工作（如有需要）
onUnmounted(() => {
  console.log('SecOps Agent 组件已卸载')
})

onMounted(async () => {
  // 初始化聊天 store（加载会话列表和消息）
  await chatStore.init()

  // 检查 HexStrike 状态
  secopsAgentApi.hexstrikeStatus().then(data => {
    chatStore.updateHexstrikeStatus({
      checked: true,
      connected: !!data.connected
    })
  }).catch(() => {
    chatStore.updateHexstrikeStatus({
      checked: true,
      connected: false
    })
  })

  // 自动聚焦输入框
  nextTick(() => {
    if (inputRef.value) {
      inputRef.value.focus()
    }
  })
})
</script>

<style scoped>
/* Open WebUI 风格设计 */
.secops-agent {
  padding: 0;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f7f7f8;
}

.agent-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: 0;
  box-shadow: none;
  border: none;
  background: transparent;
}

/* 覆盖 el-card 默认样式 */
.agent-card :deep(.el-card__header) {
  border-bottom: 1px solid #e5e7eb;
  background: #ffffff;
  padding: 12px 16px;
}

.agent-card :deep(.el-card__body) {
  padding: 0;
  background: #ffffff;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.title {
  font-size: 14px;
  font-weight: 600;
  color: #111827;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.chat-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: #ffffff;
  scroll-behavior: smooth;
  position: relative;
}

.chat-container::-webkit-scrollbar {
  width: 8px;
}

.chat-container::-webkit-scrollbar-track {
  background: transparent;
}

.chat-container::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.1);
  border-radius: 4px;
  border: 2px solid transparent;
  background-clip: content-box;
}

.chat-container::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.2);
  background-clip: content-box;
}

.messages {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 800px;
  margin: 0 auto;
  padding-bottom: 80px;
}

.message-fade-enter-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.message-fade-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.message-fade-enter-to {
  opacity: 1;
  transform: translateY(0);
}

.message.user {
  align-self: flex-end;
  max-width: 80%;
}

.message.assistant {
  align-self: flex-start;
  max-width: 85%;
}

.message-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
  font-size: 13px;
  padding: 0 4px;
}

.role-name {
  font-weight: 600;
  color: #374151;
}

.message-time {
  font-size: 12px;
  color: #9ca3af;
}

.message-content {
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.6;
  word-wrap: break-word;
  position: relative;
  font-size: 14px;
}

/* 用户消息样式 */
.message.user .message-content {
  background: #f3f4f6;
  color: #1f2937;
  border-bottom-right-radius: 4px;
  border: 1px solid #e5e7eb;
}

/* AI 消息样式 */
.message.assistant .message-content {
  background: #f3f4f6;
  color: #1f2937;
  border-bottom-left-radius: 4px;
  border: 1px solid #e5e7eb;
}

.message-content.streaming::after {
  content: '';
  display: inline-block;
  width: 6px;
  height: 16px;
  margin-left: 4px;
  vertical-align: middle;
  animation: blink 1s infinite;
  background: #1f2937;
  border-radius: 2px;
}

@keyframes blink {
  0%, 49% { opacity: 1; }
  50%, 100% { opacity: 0; }
}

/* Markdown 样式优化 */
.message-content :deep(code) {
  background: rgba(0, 0, 0, 0.08);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
  font-family: 'Monaco', 'Menlo', monospace;
  color: #1f2937;
}

.message-content :deep(pre) {
  background: #1f2937;
  color: #f9fafb;
  padding: 16px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 12px 0;
  border: 1px solid #e5e7eb;
}

.message-content :deep(pre code) {
  background: transparent;
  padding: 0;
  color: inherit;
}

.message-content :deep(a) {
  color: #10a37f;
  text-decoration: none;
  border-bottom: 1px solid transparent;
  transition: border-color 0.2s;
}

.message-content :deep(a:hover) {
  border-bottom-color: #10a37f;
}

.message.user .message-content :deep(a) {
  color: #1f2937;
  text-decoration: underline;
  font-weight: 500;
}

/* 用户消息中的代码块 */
.message.user .message-content :deep(pre) {
  background: #1f2937;
  color: #f9fafb;
  border: 1px solid #d1d5db;
}

/* 表情符号颜色 */
.message-content :deep(.emoji-success) {
  color: #10b981;
}

.message-content :deep(.emoji-error) {
  color: #ef4444;
}

.message-content :deep(.emoji-warning) {
  color: #f59e0b;
}

.message-content :deep(.emoji-info) {
  color: #3b82f6;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  padding: 40px 20px;
  text-align: center;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 24px;
  opacity: 0.8;
}

.empty-content h3 {
  margin: 0 0 8px 0;
  font-size: 20px;
  color: #111827;
  font-weight: 600;
}

.empty-content p {
  margin: 0;
  font-size: 14px;
  color: #6b7280;
}

.suggestions {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-top: 32px;
  width: 100%;
  max-width: 600px;
}

.suggestion-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  text-align: left;
}

.suggestion-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  border-color: #10a37f;
}

.suggestion-icon {
  font-size: 24px;
  flex-shrink: 0;
}

.suggestion-text {
  font-size: 13px;
  color: #374151;
  font-weight: 500;
  flex: 1;
}

.suggestion-arrow {
  font-size: 14px;
  color: #9ca3af;
  flex-shrink: 0;
}

.thinking-indicator {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  max-width: fit-content;
}

.thinking-dots {
  display: flex;
  gap: 6px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #10a37f;
}

.dot:nth-child(1) {
  animation: pulse 1.4s infinite ease-in-out;
}

.dot:nth-child(2) {
  animation: pulse 1.4s infinite ease-in-out 0.16s;
}

.dot:nth-child(3) {
  animation: pulse 1.4s infinite ease-in-out 0.32s;
}

@keyframes pulse {
  0%, 100% {
    opacity: 0.4;
    transform: scale(0.8);
  }
  50% {
    opacity: 1;
    transform: scale(1);
  }
}

.thinking-text {
  font-size: 13px;
  color: #6b7280;
  font-weight: 500;
}

.input-area {
  border-top: 1px solid #e5e7eb;
  padding: 16px 20px;
  background: #ffffff;
}

.input-wrapper {
  max-width: 800px;
  margin: 0 auto;
}

.message-input {
  width: 100%;
}

/* 覆盖 el-input 样式 */
.message-input :deep(.el-textarea__inner) {
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  background: #f9fafb;
  padding: 12px 16px;
  font-size: 14px;
  line-height: 1.6;
  transition: all 0.2s;
}

.message-input :deep(.el-textarea__inner):focus {
  border-color: #374151;
  background: #ffffff;
  box-shadow: 0 0 0 3px rgba(0, 0, 0, 0.1);
}

/* 覆盖 el-tag 样式 */
.header-right :deep(.el-tag) {
  border-radius: 6px;
  border: none;
  font-weight: 500;
  font-size: 12px;
  padding: 4px 10px;
}

.header-right :deep(.el-tag--success) {
  background: #dcfce7;
  color: #16a34a;
}

.header-right :deep(.el-tag--warning) {
  background: #fef3c7;
  color: #b45309;
}

.header-right :deep(.el-tag--info) {
  background: #dbeafe;
  color: #1e40af;
}

.input-hint {
  font-size: 12px;
  color: #9ca3af;
}

.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
}

.send-button {
  min-width: 100px;
  background: #1f2937;
  color: #ffffff;
  border: none;
  font-weight: 500;
  padding: 10px 20px;
  border-radius: 8px;
  transition: all 0.2s;
}

.send-button:hover:not(:disabled) {
  background: #111827;
  transform: translateY(-1px);
}

.send-button:disabled {
  background: #d1d5db;
  color: #9ca3af;
  cursor: not-allowed;
}

.send-icon {
  font-size: 16px;
  color: #ffffff;
}

.loading-text {
  font-size: 13px;
  color: #ffffff;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .suggestions {
    grid-template-columns: 1fr;
  }

  .message.user,
  .message.assistant {
    max-width: 90%;
  }

  .card-header {
    padding: 10px 12px;
  }

  .chat-container {
    padding: 16px;
  }
}
</style>