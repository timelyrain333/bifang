import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { useAuthStore } from './stores/auth'

// 全局处理 ResizeObserver 错误
const debounce = (fn, delay) => {
  let timer = null
  return function (...args) {
    clearTimeout(timer)
    timer = setTimeout(() => fn.apply(this, args), delay)
  }
}

const _ResizeObserver = window.ResizeObserver
window.ResizeObserver = class ResizeObserver extends _ResizeObserver {
  constructor(callback) {
    const debouncedCallback = debounce(callback, 16)
    super(debouncedCallback)
  }
}

// 抑制 ResizeObserver 相关错误（这些通常是良性的）
const suppressResizeObserverErrors = () => {
  // 处理 window.onerror
  const originalOnError = window.onerror
  window.onerror = (message, ...args) => {
    if (typeof message === 'string' && message.includes('ResizeObserver')) {
      return true
    }
    return originalOnError?.(message, ...args)
  }

  // 处理 unhandledrejection
  window.addEventListener('unhandledrejection', (event) => {
    if (event.reason?.message?.includes('ResizeObserver') ||
        String(event.reason).includes('ResizeObserver')) {
      event.preventDefault()
    }
  })

  // 处理 error 事件
  window.addEventListener('error', (event) => {
    if (event.message?.includes('ResizeObserver') ||
        event.error?.message?.includes('ResizeObserver')) {
      event.preventDefault()
      event.stopPropagation()
    }
  }, true)
}
suppressResizeObserverErrors()

const app = createApp(App)

// 注册所有图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// 初始化认证状态
const authStore = useAuthStore()
authStore.init()

app.use(router)
app.use(ElementPlus, { locale: zhCn })
app.mount('#app')
