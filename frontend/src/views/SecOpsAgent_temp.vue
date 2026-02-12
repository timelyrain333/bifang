// 使用建议
const useSuggestion = (text) => {
  inputMessage.value = text
  sendMessage()
}

// 切换思考过程展开状态
const toggleThinkingExpand = (msg) => {
  if (msg.expandable !== undefined) {
    msg.expandable = !msg.expandable
  }
}

// 发送消息