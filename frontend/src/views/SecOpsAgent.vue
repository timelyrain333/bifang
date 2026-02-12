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
              :class="['message', msg.role, { 'message-thinking': msg.type === 'thinking', 'message-final': msg.type === 'final' }]"
            >
              <div class="message-header">
                <span class="role-name">
                  {{ msg.role === 'user' ? '👤 您' : '🤖 SecOps 智能体' }}
                </span>
                <span class="message-time">{{ formatTime(msg.timestamp) }}</span>
              </div>
              <div
                :class="['message-content', { 'streaming': msg.isStreaming, 'content-thinking': msg.type === 'thinking', 'content-final': msg.type === 'final' }]"
              >
                <div v-if="msg.type === 'thinking'" class="thinking-expand" @click="toggleThinkingExpand(msg)">
                </div>
                <div v-html="formatMessage(msg.content)"></div>
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
              type="primary"
              @click="sendMessage"
              :loading="chatStore.isLoading"
              :disabled="!inputMessage.trim() || chatStore.isLoading"
              circle
              size="large"
              class="send-button"
            >
              <el-icon v-if="!chatStore.isLoading"><Promotion /></el-icon>
            </el-button>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
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
      /\[([^\]]+)\]\(([^)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
    )

  // URL 自动链接
    .replace(
      /(https?:\/\/[^\s<]+)/g,
      '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>'
    )

  return html
}

// 滚动处理
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
  if (!force && userScrolled.value) return

  nextTick(() => {
    if (chatContainerRef.value) {
      chatContainerRef.value.scrollTo({
        top: chatContainerRef.value.scrollHeight,
        behavior: 'smooth'
      })
    }
  })
}

// 处理输入
const handleInput = () => {
  // 自动调整文本框高度
  const lines = inputMessage.value.split('\n').length
  inputRows.value = Math.min(Math.max(lines, 3), 10)
}

// 切换思考过程展开状态
const toggleThinkingExpand = (msg) => {
  if (msg.expandable !== undefined) {
    msg.expandable = !msg.expandable
  }
}

// 使用建议
const useSuggestion = (text) => {
  inputMessage.value = text
  sendMessage()
}

// 发送消息
const sendMessage = async () => {
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
  chatStore.setLoading(true)

  // 创建助手思考过程消息占位（不保存到数据库）
  chatStore.addMessage({
    role: 'assistant',
    type: 'thinking',  // 新增：消息类型
    content: '正在思考...',
    timestamp: new Date(),
    isStreaming: true
  }, false)

  scrollToBottom(true)
}

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

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

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
            } else if (data.content !== undefined) {
              // 处理内容（可能是 JSON 对象或普通文本）
              const currentContent = chatStore.messages[chatStore.messages.length - 1].content

              if (data.type === 'thinking') {
                // 思考过程消息（灰色，可展开）
                chatStore.addMessage({
                  role: 'assistant',
                  type: 'thinking',
                  content: data.content || '正在思考...',
                  timestamp: new Date(),
                  isStreaming: false,
                  expandable: true
                }, false)
              } else if (typeof data.content === 'string') {
                // 普通文本内容（可能是思考过程的一部分）
                chatStore.updateLastMessage(currentContent + data.content)
                scrollToBottom()
              } else if (data.content && data.content.content) {
                // JSON 格式的最终答复内容
                await chatStore.addMessage({
                  role: 'assistant',
                  type: 'final',
                  content: data.content.content,
                  timestamp: new Date(),
                  isStreaming: false
                }, false)
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

  // 聚焦输入框
  nextTick(() => {
    if (inputRef.value) {
      inputRef.value.focus()
    }
  })

  // 滚动到底部显示最新消息
  scrollToBottom(true)
})

onUnmounted(() => {
  // 组件卸载时的清理工作（如有需要）
  console.log('SecOps Agent 组件已卸载')
})
</script>

<style scoped>
.secops-agent {
  padding: 20px;
  height: calc(100vh - 100px);
  display: flex;
  flex-direction: column;
}

.agent-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
}

:deep(.el-card__header) {
  padding: 16px 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
}

:deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title {
  font-size: 16px;
  font-weight: 600;
  color: white;
}

.header-right {
  display: flex;
  gap: 8px;
}

.chat-container {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  background: linear-gradient(180deg, #f8f9fa 0%, #ffffff 100%);
  scroll-behavior: smooth;
  position: relative;
}

.chat-container::-webkit-scrollbar {
  width: 6px;
}

.chat-container::-webkit-scrollbar-track {
  background: transparent;
}

.chat-container::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.15);
  border-radius: 3px;
}

.chat-container::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.25);
}

.messages {
  display: flex;
  flex-direction: column;
  gap: 24px;
  max-width: 900px;
  margin: 0 auto;
  padding-bottom: 60px;
}

/* 消息动画 */
.message-fade-enter-active {
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.message-fade-enter-from {
  opacity: 0;
  transform: translateY(20px);
}

.message-fade-enter-to {
  opacity: 1;
  transform: translateY(0);
}

.message {
  animation: messageSlideIn 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

@keyframes messageSlideIn {
  from {
    opacity: 0;
    transform: translateY(20px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.message.user {
  align-self: flex-end;
}

.message.assistant {
  align-self: flex-start;
}

.message-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 12px;
  color: #909399;
  padding: 0 4px;
}

.role-name {
  font-weight: 500;
}

.message-content {
  padding: 14px 18px;
  border-radius: 16px;
  line-height: 1.7;
  word-wrap: break-word;
  position: relative;
  transition: all 0.3s ease;
}

.message.user .message-content {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-bottom-right-radius: 4px;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
}

.message.assistant .message-content {
  background: white;
  color: #303133;
  border: 1px solid #e4e7ed;
  border-bottom-left-radius: 4px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

/* 流式输出时的光标效果 */
.message.assistant .message-content.streaming::after {
  content: '';
  display: inline-block;
  width: 8px;
  height: 18px;
  margin-left: 4px;
  vertical-align: middle;
  animation: blink 1s infinite;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 2px;
}

@keyframes blink {
  0%, 49% { opacity: 1; }
  50%, 100% { opacity: 0; }
}

.message.assistant .message-content :deep(code) {
  background: #f5f7fa;
  padding: 3px 8px;
  border-radius: 4px;
  font-family: 'Fira Code', 'Monaco', 'Consolas', monospace;
  font-size: 0.9em;
  color: #e83e8c;
  border: 1px solid #e4e7ed;
}

.message.assistant .message-content :deep(pre) {
  background: #282c34;
  color: #abb2bf;
  padding: 16px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 12px 0;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.message.assistant .message-content :deep(pre code) {
  background: transparent;
  padding: 0;
  border: none;
  color: inherit;
}

.message.assistant .message-content :deep(a) {
  color: #409eff;
  text-decoration: none;
  border-bottom: 1px dashed #409eff;
  transition: all 0.2s;
}

.message.assistant .message-content :deep(a:hover) {
  color: #66b1ff;
  border-bottom-style: solid;
}

.emoji-success { color: #67c23a; }
.emoji-error { color: #f56c6c; }
.emoji-warning { color: #e6a23c; }
.emoji-info { color: #909399; }

.report-download {
  margin-top: 16px;
  padding: 12px;
  background: #f0f9ff;
  border-radius: 8px;
  border-left: 3px solid #409eff;
}

.empty-state {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  min-height: 400px;
}

.empty-content {
  text-align: center;
  max-width: 600px;
}

.empty-icon {
  font-size: 72px;
  margin-bottom: 20px;
  animation: float 3s ease-in-out infinite;
}

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-15px); }
}

.empty-content h3 {
  font-size: 24px;
  color: #303133;
  margin-bottom: 12px;
}

.empty-content > p {
  color: #909399;
  font-size: 14px;
  margin-bottom: 32px;
}

.suggestions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-top: 24px;
}

.suggestion-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: white;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.suggestion-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(102, 126, 234, 0.2);
  border-color: #667eea;
}

.suggestion-icon {
  font-size: 24px;
  flex-shrink: 0;
}

.suggestion-text {
  flex: 1;
  font-size: 14px;
  color: #606266;
  text-align: left;
}

.suggestion-arrow {
  font-size: 18px;
  color: #667eea;
  opacity: 0;
  transform: translateX(-8px);
  transition: all 0.3s;
}

.suggestion-card:hover .suggestion-arrow {
  opacity: 1;
  transform: translateX(0);
}

.thinking-indicator {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 24px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  max-width: 200px;
  margin: 0 auto;
}

.thinking-dots {
  display: flex;
  gap: 6px;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  animation: dotPulse 1.4s infinite ease-in-out;
}

.dot:nth-child(1) { animation-delay: 0s; }
.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes dotPulse {
  0%, 80%, 100% {
    transform: scale(0.6);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

.thinking-text {
  font-size: 14px;
  color: #909399;
  font-weight: 500;
}

.clear-history-wrapper {
  position: absolute;
  top: 20px;
  right: 20px;
  z-index: 10;
}

.clear-history-btn {
  opacity: 0.6;
  transition: all 0.3s;
}

.clear-history-btn:hover {
  opacity: 1;
}

/* 淡入淡出动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.input-area {
  border-top: 1px solid #e4e7ed;
  padding: 20px 24px;
  background: white;
}

.input-wrapper {
  max-width: 900px;
  margin: 0 auto;
}

.message-input :deep(textarea) {
  border-radius: 12px;
  border: 2px solid #e4e7ed;
  padding: 14px 16px;
  font-size: 14px;
  line-height: 1.6;
  transition: all 0.3s;
  resize: none;
}

.message-input :deep(textarea):focus {
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
}

.input-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #909399;
}

.hint-icon {
  font-size: 16px;
}

.send-button {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
  transition: all 0.3s;
}

.send-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.5);
}

.send-button:active {
  transform: translateY(0);
}

@media (max-width: 768px) {
  .suggestions {
    grid-template-columns: 1fr;
  }

  .message-content {
    padding: 12px 14px;
  }

  .chat-container {
    padding: 16px;
  }
}
</style>