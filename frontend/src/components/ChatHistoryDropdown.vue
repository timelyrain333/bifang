<template>
  <el-dropdown
    trigger="click"
    placement="bottom-end"
    @command="handleCommand"
    :hide-timeout="0"
  >
    <template #default>
      <!-- 当前会话标题 + 图标 -->
      <div class="session-selector">
        <el-icon class="selector-icon"><Clock /></el-icon>
        <span class="session-title">{{ currentSessionTitle }}</span>
        <el-icon class="dropdown-icon"><ArrowDown /></el-icon>
      </div>
    </template>

    <template #dropdown>
      <el-dropdown-menu>
        <!-- 新建对话按钮 -->
        <el-dropdown-item command="new" divided>
          <el-icon><Plus /></el-icon>
          <span>新建对话</span>
        </el-dropdown-item>

        <!-- 会话列表 -->
        <el-dropdown-item
          v-for="session in sessionList"
          :key="session.id"
          :command="`switch-${session.id}`"
          :divided="false"
          :class="{ 'is-active': session.id === currentSessionId }"
        >
          <div class="session-item">
            <div class="session-info">
              <el-icon v-if="session.id === currentSessionId" class="check-icon">
                <Check />
              </el-icon>
              <span class="session-title-text">{{ session.title }}</span>
            </div>
            <div class="session-meta">
              <span class="message-count">{{ session.messages_count || 0 }} 条消息</span>
              <span class="update-time">{{ formatTime(session.updated_at) }}</span>
            </div>
            <!-- 操作菜单 -->
            <el-dropdown
              trigger="click"
              placement="right-start"
              @command="(cmd) => handleSessionAction(cmd, session.id)"
              @click.stop
            >
              <template #reference>
                <el-icon class="more-icon" @click.stop><MoreFilled /></el-icon>
              </template>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="rename">
                    <el-icon><Edit /></el-icon>
                    <span>重命名</span>
                  </el-dropdown-item>
                  <el-dropdown-item command="delete" divided>
                    <el-icon><Delete /></el-icon>
                    <span>删除</span>
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </el-dropdown-item>

        <!-- 空状态 -->
        <el-dropdown-item v-if="sessionList.length === 0" disabled>
          <span class="empty-text">暂无历史对话</span>
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup>
import { computed } from 'vue'
import { Clock, ArrowDown, Plus, Check, MoreFilled, Edit, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useChatStore } from '../stores/chat'

const chatStore = useChatStore()

// 本地会话列表 computed（避免直接使用 store 导致递归更新）
const sessionList = computed(() => chatStore.sessions || [])

// 当前会话标题
const currentSessionTitle = computed(() => {
  if (!chatStore.sessions || chatStore.sessions.length === 0) {
    return '选择会话'
  }
  const session = chatStore.sessions.find(s => s.id === chatStore.currentSessionId)
  return session ? session.title : '选择会话'
})

// 当前会话ID（直接使用）
const currentSessionId = computed(() => chatStore.currentSessionId)

// 处理下拉菜单命令
const handleCommand = async (command) => {
  if (typeof command === 'string' && command.startsWith('switch-')) {
    const sessionId = parseInt(command.replace('switch-', ''))
    await handleSwitch(sessionId)
  } else if (command === 'new') {
    await handleNewSession()
  }
}

// 切换会话
const handleSwitch = async (sessionId) => {
  try {
    await chatStore.switchSession(sessionId)
    ElMessage.success('已切换会话')
  } catch (error) {
    ElMessage.error('切换会话失败')
    console.error(error)
  }
}

// 创建新会话
const handleNewSession = async () => {
  try {
    await chatStore.createSession()
    ElMessage.success('已创建新对话')
  } catch (error) {
    ElMessage.error('创建会话失败')
    console.error(error)
  }
}

// 会话操作
const handleSessionAction = async (action, sessionId) => {
  switch (action) {
    case 'rename':
      await handleRename(sessionId)
      break
    case 'delete':
      await handleDelete(sessionId)
      break
  }
}

// 重命名会话
const handleRename = async (sessionId) => {
  try {
    const session = chatStore.sessions.find(s => s.id === sessionId)
    if (!session) return

    const { value } = await ElMessageBox.prompt(
      '重命名会话',
      '请输入新的会话标题',
      {
        inputValue: session.title,
        inputPattern: /^.{1,50}$/,
        inputErrorMessage: '标题长度应为 1-50 个字符'
      }
    )

    if (value) {
      await chatStore.renameSession(sessionId, value)
      ElMessage.success('重命名成功')
    }
  } catch (error) {
    // 用户取消或输入无效
    if (error !== 'cancel') {
      ElMessage.error('重命名失败')
      console.error(error)
    }
  }
}

// 删除会话
const handleDelete = async (sessionId) => {
  try {
    await ElMessageBox.confirm(
      '确定要删除这个会话吗？',
      '删除会话后，所有消息将无法恢复。',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    await chatStore.deleteSession(sessionId)
    ElMessage.success('会话已删除')
  } catch (error) {
    // 用户取消
    if (error !== 'cancel') {
      ElMessage.error('删除会话失败')
      console.error(error)
    }
  }
}

// 格式化时间
const formatTime = (timestamp) => {
  if (!timestamp) return ''

  const date = new Date(timestamp)
  const now = new Date()
  const diff = now - date

  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 86400000)} 天前`

  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}
</script>

<style scoped>
.session-selector {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: #f3f4f6;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  user-select: none;
  border: 1px solid transparent;
}

.session-selector:hover {
  background: #e5e7eb;
  border-color: #d1d5db;
}

.selector-icon {
  font-size: 16px;
  color: #10a37f;
}

.session-title {
  font-size: 13px;
  font-weight: 500;
  color: #1f2937;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dropdown-icon {
  font-size: 12px;
  color: #6b7280;
}

.session-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  min-width: 300px;
  max-width: 450px;
  padding: 0;
}

.session-info {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.check-icon {
  font-size: 14px;
  color: #10a37f;
  flex-shrink: 0;
}

.session-title-text {
  font-size: 13px;
  color: #1f2937;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
}

.session-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  font-size: 11px;
  color: #9ca3af;
  margin-right: 8px;
}

.message-count {
  background: #f3f4f6;
  color: #6b7280;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 500;
}

.update-time {
  color: #9ca3af;
  font-size: 10px;
}

.more-icon {
  font-size: 14px;
  color: #9ca3af;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: all 0.2s;
}

.more-icon:hover {
  color: #10a37f;
  background: #f3f4f6;
}

.is-active {
  background: #f0fdf4;
}

.empty-text {
  color: #9ca3af;
  font-size: 13px;
  text-align: center;
  padding: 24px 16px;
}
</style>
