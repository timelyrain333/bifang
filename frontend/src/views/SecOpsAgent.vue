<template>
  <div class="secops-agent">
    <el-card class="agent-card">
      <template #header>
        <div class="card-header">
          <span>🤖 SecOps智能体</span>
          <el-tag type="info">基于通义千问大模型</el-tag>
          <el-tag v-if="hexstrikeStatus.checked" :type="hexstrikeStatus.connected ? 'success' : 'warning'" size="small" style="margin-left: 8px;">
            {{ hexstrikeStatus.connected ? '资产安全评估已连接' : '资产安全评估未连接' }}
          </el-tag>
        </div>
      </template>
      
      <!-- 对话区域 -->
      <div class="chat-container" ref="chatContainer">
        <div class="messages" v-if="messages.length > 0">
          <div
            v-for="(msg, index) in messages"
            :key="index"
            :class="['message', msg.role]"
          >
            <div class="message-header">
              <span class="role-name">
                {{ msg.role === 'user' ? '👤 您' : '🤖 智能体' }}
              </span>
              <span class="message-time">{{ formatTime(msg.timestamp) }}</span>
            </div>
            <div class="message-content" v-html="formatMessage(msg.content)"></div>
          </div>
        </div>
        
        <!-- 空状态 -->
        <div v-else class="empty-state">
          <el-empty description="开始与智能体对话，让它帮您执行安全运营任务">
            <template #image>
              <div class="empty-icon">🤖</div>
            </template>
            <div class="suggestions">
              <p>您可以尝试：</p>
              <ul>
                <li>请捕获最新的漏洞并检查我的资产是否受影响</li>
                <li>采集最近7天的漏洞信息</li>
                <li>检查哪些资产可能受到最新漏洞的影响</li>
                <li v-if="hexstrikeStatus.connected">对资产做一次安全评估（需 HexStrike 已启动）</li>
              </ul>
            </div>
          </el-empty>
        </div>
        
        <!-- 加载提示 -->
        <div v-if="isLoading" class="loading-indicator">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>智能体正在思考...</span>
        </div>
      </div>
      
      <!-- 输入区域 -->
      <div class="input-area">
        <el-input
          v-model="inputMessage"
          type="textarea"
          :rows="3"
          placeholder="输入您的指令，例如：请捕获最新的漏洞并检查我的资产是否受影响"
          @keydown.ctrl.enter="sendMessage"
          @keydown.meta.enter="sendMessage"
          :disabled="isLoading"
        />
        <div class="input-actions">
          <span class="hint">Ctrl/Cmd + Enter 发送</span>
          <el-button
            type="primary"
            @click="sendMessage"
            :loading="isLoading"
            :disabled="!inputMessage.trim() || isLoading"
          >
            发送
          </el-button>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script>
import { ref, reactive, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { secopsAgentApi } from '../api/secopsAgent'

export default {
  name: 'SecOpsAgent',
  components: {
    Loading
  },
  setup() {
    const messages = ref([])
    const inputMessage = ref('')
    const isLoading = ref(false)
    const chatContainer = ref(null)
    const hexstrikeStatus = reactive({ checked: false, connected: false })
    
    const formatTime = (timestamp) => {
      if (!timestamp) return ''
      const date = new Date(timestamp)
      return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    }
    
    const formatMessage = (content) => {
      if (!content) return ''
      // 简单的Markdown转换
      return content
        .replace(/\n/g, '<br>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/`(.+?)`/g, '<code>$1</code>')
        .replace(/✅/g, '<span style="color: #67c23a;">✅</span>')
        .replace(/❌/g, '<span style="color: #f56c6c;">❌</span>')
        .replace(/⚠️/g, '<span style="color: #e6a23c;">⚠️</span>')
    }
    
    const scrollToBottom = () => {
      nextTick(() => {
        if (chatContainer.value) {
          chatContainer.value.scrollTop = chatContainer.value.scrollHeight
        }
      })
    }
    
    const sendMessage = async () => {
      const message = inputMessage.value.trim()
      if (!message || isLoading.value) return
      
      // 添加用户消息
      messages.value.push({
        role: 'user',
        content: message,
        timestamp: new Date()
      })
      
      // 清空输入框
      inputMessage.value = ''
      isLoading.value = true
      
      // 创建助手消息
      const assistantMessageIndex = messages.value.length
      messages.value.push({
        role: 'assistant',
        content: '',
        timestamp: new Date()
      })
      
      scrollToBottom()
      
      try {
        // 构建对话历史（只包含user和assistant角色的消息）
        const history = messages.value.slice(0, -1).filter(msg => msg.role === 'user' || msg.role === 'assistant').map(msg => ({
          role: msg.role,
          content: msg.content
        }))
        
        // 调用API（流式）
        const response = await secopsAgentApi.chat(message, history)
        
        if (!response.ok) {
          let errorText = `HTTP错误: ${response.status}`
          try {
            const errBody = await response.json()
            if (errBody && errBody.error) {
              errorText = errBody.error
            }
          } catch (_) {
            // 忽略解析失败，使用默认错误文案
          }
          throw new Error(errorText)
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
                const data = JSON.parse(line.substring(6))
                
                if (data.error) {
                  ElMessage.error(data.error)
                  messages.value[assistantMessageIndex].content += `\n❌ 错误: ${data.error}\n`
                } else if (data.done) {
                  // 流式响应结束
                  break
                } else if (data.content) {
                  // 追加内容
                  messages.value[assistantMessageIndex].content += data.content
                  scrollToBottom()
                }
              } catch (e) {
                console.error('解析SSE数据失败:', e, line)
              }
            }
          }
        }
        
        // 处理剩余的buffer
        if (buffer.startsWith('data: ')) {
          try {
            const data = JSON.parse(buffer.substring(6))
            if (data.content) {
              messages.value[assistantMessageIndex].content += data.content
            }
          } catch (e) {
            // 忽略解析错误
          }
        }
        
      } catch (error) {
        console.error('发送消息失败:', error)
        const msg = error.message || '发送消息失败，请检查网络连接'
        ElMessage.error(msg.includes('HTTP错误') ? '请求失败，请查看下方错误详情' : msg)
        messages.value[assistantMessageIndex].content += `\n❌ 错误: ${error.message}\n`
      } finally {
        isLoading.value = false
        scrollToBottom()
      }
    }
    
    onMounted(() => {
      secopsAgentApi.hexstrikeStatus().then(data => {
        hexstrikeStatus.checked = true
        hexstrikeStatus.connected = !!data.connected
      }).catch(() => {
        hexstrikeStatus.checked = true
        hexstrikeStatus.connected = false
      })
    })
    
    return {
      messages,
      inputMessage,
      isLoading,
      chatContainer,
      hexstrikeStatus,
      formatTime,
      formatMessage,
      sendMessage
    }
  }
}
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
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 16px;
  font-weight: bold;
}

.chat-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 20px;
}

.messages {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.message {
  max-width: 80%;
  animation: fadeIn 0.3s;
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
}

.role-name {
  font-weight: 500;
}

.message-content {
  padding: 12px 16px;
  border-radius: 8px;
  line-height: 1.6;
  word-wrap: break-word;
}

.message.user .message-content {
  background: #409eff;
  color: white;
}

.message.assistant .message-content {
  background: white;
  color: #303133;
  border: 1px solid #e4e7ed;
  white-space: pre-wrap;
}

.message.assistant .message-content :deep(code) {
  background: #f5f7fa;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Courier New', monospace;
  font-size: 0.9em;
}

.empty-state {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 20px;
}

.suggestions {
  text-align: left;
  margin-top: 20px;
}

.suggestions ul {
  list-style: none;
  padding: 0;
  margin: 10px 0;
}

.suggestions li {
  padding: 8px;
  margin: 5px 0;
  background: #f5f7fa;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.3s;
}

.suggestions li:hover {
  background: #e4e7ed;
}

.loading-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #909399;
  padding: 10px;
}

.input-area {
  border-top: 1px solid #e4e7ed;
  padding-top: 16px;
}

.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
}

.hint {
  font-size: 12px;
  color: #909399;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>

