# 前端适配指南 - SSE Streaming

## Vue.js 3 前端适配示例

### 1. API 服务层 (`frontend/src/api/chat.js`)

```javascript
import axios from 'axios'

const API_BASE = '/api'

/**
 * SSE 流式聊天
 * @param {string} message - 用户消息
 * @param {function} onMessage - 接收消息的回调
 * @param {function} onError - 错误回调
 * @param {function} onComplete - 完成回调
 * @returns {EventSource} - EventSource 实例（可手动关闭）
 */
export function streamChat(
  message,
  { onMessage, onError, onComplete }
) {
  const url = `${API_BASE}/chat/stream`
  const params = new URLSearchParams({ message })
  
  const eventSource = new EventSource(`${url}?${params}`)
  
  let fullText = ''
  
  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      
      if (data.type === 'message') {
        const chunk = data.text
        fullText += chunk
        onMessage(chunk, fullText)
      } else if (data.type === 'error') {
        onError(data.error)
      }
    } catch (e) {
      console.error('解析 SSE 数据失败:', e)
    }
  }
  
  eventSource.onerror = (error) => {
    console.error('SSE 连接错误:', error)
    onError(error)
    eventSource.close()
  }
  
  // 监听连接关闭
  eventSource.addEventListener('close', () => {
    if (onComplete) onComplete(fullText)
    eventSource.close()
  })
  
  return eventSource
}

/**
 * POST 方式流式聊天（支持长消息）
 */
export function streamChatPost(
  message,
  conversationHistory = [],
  { onMessage, onError, onComplete }
) {
  const url = `${API_BASE}/chat/stream`
  
  // 使用 fetch 发送 POST 请求
  fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message,
      conversation_history: conversationHistory,
    }),
  })
  .then(response => {
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let fullText = ''
    
    // 读取流式数据
    function read() {
      let buffer = ''
      
      return reader.read().then(({ done, value }) => {
        if (done) {
          if (onComplete) onComplete(fullText)
          return
        }
        
        // 解码并解析 SSE 格式
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              
              if (data.type === 'message') {
                const chunk = data.text
                fullText += chunk
                onMessage(chunk, fullText)
              } else if (data.type === 'error') {
                onError(data.error)
              }
            } catch (e) {
              console.error('解析 SSE 数据失败:', e, line)
            }
          }
        }
        
        return read()
      })
    }
    
    return read()
  })
  .catch(error => {
    console.error('流式请求失败:', error)
    onError(error)
  })
}

/**
 * 查询聊天状态
 */
export function getChatStatus() {
  return axios.get(`${API_BASE}/chat/status`)
}
```

### 2. Vue 组件示例 (`frontend/src/views/ChatSecOps.vue`)

```vue
<template>
  <div class="chat-container">
    <!-- 消息列表 -->
    <div class="messages" ref="messagesContainer">
      <div
        v-for="(msg, index) in messages"
        :key="index"
        :class="['message', msg.role]"
      >
        <div class="message-content">
          <!-- Markdown 渲染 -->
          <div v-html="renderMarkdown(msg.content)"></div>
          
          <!-- 流式输出指示器 -->
          <span v-if="msg.streaming" class="streaming-indicator">▊</span>
        </div>
        
        <div class="message-time">
          {{ formatTime(msg.timestamp) }}
        </div>
      </div>
    </div>
    
    <!-- 输入区域 -->
    <div class="input-area">
      <textarea
        v-model="userInput"
        @keydown.enter.exact.prevent="sendMessage"
        placeholder="输入消息..."
        rows="3"
        :disabled="isProcessing"
      ></textarea>
      
      <button
        @click="sendMessage"
        :disabled="isProcessing || !userInput.trim()"
        class="send-button"
      >
        {{ isProcessing ? '处理中...' : '发送' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { streamChat } from '@/api/chat'
import { marked } from 'marked'

// 状态
const messages = ref([
  {
    role: 'assistant',
    content: '你好！我是 SecOps 智能助手，可以帮您进行安全评估、漏洞扫描等任务。',
    timestamp: new Date(),
  }
])
const userInput = ref('')
const isProcessing = ref(false)
const eventSource = ref(null)

// DOM 引用
const messagesContainer = ref(null)

// 渲染 Markdown
const renderMarkdown = (text) => {
  return marked.parse(text)
}

// 格式化时间
const formatTime = (timestamp) => {
  return new Date(timestamp).toLocaleTimeString()
}

// 滚动到底部
const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

// 发送消息
const sendMessage = async () => {
  const message = userInput.value.trim()
  if (!message || isProcessing.value) return
  
  // 添加用户消息
  messages.value.push({
    role: 'user',
    content: message,
    timestamp: new Date(),
  })
  
  userInput.value = ''
  isProcessing.value = true
  scrollToBottom()
  
  // 创建助手消息（流式填充）
  const assistantMessage = {
    role: 'assistant',
    content: '',
    timestamp: new Date(),
    streaming: true,
  }
  messages.value.push(assistantMessage)
  
  try {
    // 调用 SSE 流式聊天
    eventSource.value = streamChat(message, {
      onMessage: (chunk, fullText) => {
        // 更新消息内容（流式）
        assistantMessage.content = fullText
        scrollToBottom()
      },
      onError: (error) => {
        console.error('聊天错误:', error)
        assistantMessage.content += `\n\n❌ 错误: ${error}`
        assistantMessage.streaming = false
        isProcessing.value = false
      },
      onComplete: (fullText) => {
        assistantMessage.streaming = false
        isProcessing.value = false
        console.log('聊天完成')
      },
    })
  } catch (error) {
    console.error('发送消息失败:', error)
    assistantMessage.content = `❌ 发送失败: ${error.message}`
    assistantMessage.streaming = false
    isProcessing.value = false
  }
}

// 组件挂载
onMounted(() => {
  scrollToBottom()
})
</script>

<style scoped>
.chat-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: #f5f5f5;
  border-radius: 8px;
}

.message {
  margin-bottom: 20px;
  padding: 12px 16px;
  border-radius: 8px;
  max-width: 80%;
}

.message.user {
  background: #1890ff;
  color: white;
  margin-left: auto;
}

.message.assistant {
  background: white;
  color: #333;
  border: 1px solid #e0e0e0;
}

.message-content {
  line-height: 1.6;
}

.streaming-indicator {
  animation: blink 1s infinite;
  margin-left: 4px;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

.message-time {
  font-size: 12px;
  opacity: 0.6;
  margin-top: 8px;
}

.input-area {
  display: flex;
  gap: 12px;
  padding: 20px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.1);
}

textarea {
  flex: 1;
  padding: 12px;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  resize: none;
  font-family: inherit;
}

.send-button {
  padding: 12px 32px;
  background: #1890ff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.send-button:disabled {
  background: #d9d9d9;
  cursor: not-allowed;
}
</style>
```

### 3. Pinia Store (状态管理)

```javascript
// frontend/src/stores/chat.js
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useChatStore = defineStore('chat', () => {
  const messages = ref([])
  const isProcessing = ref(false)
  
  async function sendMessage(message) {
    // ... 发送逻辑
  }
  
  function clearHistory() {
    messages.value = []
  }
  
  return {
    messages,
    isProcessing,
    sendMessage,
    clearHistory,
  }
})
```

### 4. 路由配置 (`frontend/src/router/index.js`)

```javascript
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/chat/secops',
    name: 'ChatSecOps',
    component: () => import('@/views/ChatSecOps.vue'),
    meta: { title: 'SecOps 智能助手' }
  },
  // ... 其他路由
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
```

### 5. 使用示例

```vue
<script setup>
import { useChatStore } from '@/stores/chat'

const chatStore = useChatStore()

function handleSend() {
  chatStore.sendMessage('对 example.com 进行安全评估')
}
</script>

<template>
  <button @click="handleSend">开始扫描</button>
</template>
```

---

## 功能特性

### ✅ 已实现
1. **实时流式输出** - 打字机效果
2. **Markdown 渲染** - 支持富文本
3. **状态指示器** - 显示处理中
4. **错误处理** - 友好的错误提示
5. **自动滚动** - 始终显示最新消息

### 🎯 优化建议
1. 添加消息重试机制
2. 支持停止生成
3. 导出对话记录
4. 语音输入支持
5. 多语言支持

---

## 测试

### 浏览器测试
1. 打开开发者工具 → Network
2. 发送消息
3. 查看事件流（EventStream）

### 单元测试
```javascript
import { describe, it, expect, vi } from 'vitest'
import { streamChat } from '@/api/chat'

describe('SSE Chat', () => {
  it('should receive messages', async () => {
    const onMessage = vi.fn()
    const eventSource = streamChat('测试消息', { onMessage })
    
    // 等待消息
    await new Promise(resolve => setTimeout(resolve, 1000))
    
    expect(onMessage).toHaveBeenCalled()
    eventSource.close()
  })
})
```

---

## 故障排查

### 问题 1: SSE 连接断开
**原因**: Nginx/Gunicorn 超时
**解决**: 增加超时配置
```nginx
# nginx.conf
proxy_read_timeout 600s;
proxy_send_timeout 600s;
```

### 问题 2: 消息重复
**原因**: EventSource 自动重连
**解决**: 添加消息去重
```javascript
const lastMessageId = ref(null)
```

### 问题 3: 中文乱码
**解决**: 确保 `ensure_ascii=False`
```python
json.dumps(data, ensure_ascii=False)
```
