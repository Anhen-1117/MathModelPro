<script setup lang="ts">
import { ref, nextTick, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import service from '@/utils/request'
import { renderMarkdown } from '@/utils/markdown'
import { useApiKeyStore } from '@/stores/apiKeys'

const router = useRouter()
const apiKeyStore = useApiKeyStore()
const message = ref('')
const messages = ref<Array<{ role: 'user' | 'assistant'; content: string; time: Date; rendered?: string }>>([])
const isTyping = ref(false)
const chatContainer = ref<HTMLElement>()
const searchQuery = ref('')
const showSearch = ref(false)

// 检查 API Key 状态
const hasValidApiKey = computed(() => {
  const key = apiKeyStore.coordinatorConfig.apiKey || ''
  return key.length > 8 && !key.includes('****')
})

const filteredMessages = computed(() => {
  if (!searchQuery.value) return messages.value
  const q = searchQuery.value.toLowerCase()
  return messages.value.filter(m => m.content.toLowerCase().includes(q))
})

const scrollToBottom = async () => {
  await nextTick()
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}

const sendMessage = async () => {
  if (!message.value.trim() || isTyping.value) return

  const userMessage = message.value.trim()
  messages.value.push({ role: 'user', content: userMessage, time: new Date() })
  message.value = ''
  isTyping.value = true
  await scrollToBottom()

  // 流式消息占位
  const streamMsg = { role: 'assistant' as const, content: '', time: new Date(), rendered: '' }
  messages.value.push(streamMsg)

  try {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || window.location.origin
    const response = await fetch(`${baseUrl}/api/v1/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: userMessage }),
    })

    if (!response.ok) throw new Error(`HTTP ${response.status}`)

    const reader = response.body?.getReader()
    if (!reader) throw new Error('No reader')

    const decoder = new TextDecoder()
    let buffer = ''
    let fullContent = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (data === '[DONE]') continue
          try {
            const parsed = JSON.parse(data)
            if (parsed.token) {
              fullContent += parsed.token
              streamMsg.content = fullContent
              streamMsg.rendered = await renderMarkdown(fullContent)
              scrollToBottom()
            }
            if (parsed.error) {
              streamMsg.content = parsed.error
              streamMsg.rendered = `<p class="text-red-400">${parsed.error}</p>`
            }
          } catch { /* skip unparseable lines */ }
        }
      }
    }

    if (!fullContent) {
      streamMsg.content = '（空响应）'
      streamMsg.rendered = '<p>（空响应）</p>'
    }
  } catch {
    streamMsg.content = '抱歉，服务暂时不可用。请检查后端是否启动。'
    streamMsg.rendered = '<p>抱歉，服务暂时不可用。请检查后端是否启动。</p>'
  } finally {
    isTyping.value = false
    scrollToBottom()
  }
}

const formatTime = (date: Date) => {
  return `${date.getHours()}:${date.getMinutes().toString().padStart(2, '0')}`
}

const quickActions = [
  { icon: '📄', label: '上传赛题', action: () => router.push('/tasks') },
  { icon: '🚀', label: '开始建模', action: () => router.push('/tasks') },
  { icon: '⚙️', label: 'API 设置', action: () => router.push('/settings') },
  { icon: '📊', label: '结果对比', action: () => router.push('/compare') },
  { icon: '📚', label: '知识库', action: () => router.push('/knowledge') }
]
</script>

<template>
  <div class="h-screen flex bg-[#0a0a0b] text-white">
    <!-- 左侧边栏 -->
    <aside class="w-64 border-r border-white/5 flex flex-col">
      <div class="h-14 px-4 border-b border-white/5 flex items-center">
        <button @click="router.push('/')" class="flex items-center gap-2 text-zinc-400 hover:text-white transition-colors">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
          <span class="text-sm">返回</span>
        </button>
      </div>

      <div class="p-3 space-y-1">
        <button v-for="action in quickActions" :key="action.label" @click="action.action()"
          class="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-zinc-400 hover:bg-white/5 hover:text-white transition-colors">
          <span>{{ action.icon }}</span>
          <span>{{ action.label }}</span>
        </button>
      </div>

      <!-- 搜索 -->
      <div class="px-3 mb-2">
        <input v-model="searchQuery" type="text" placeholder="搜索对话..."
          class="w-full px-3 py-1.5 bg-zinc-800 border border-white/5 rounded-lg text-xs text-white placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-blue-500/30" />
      </div>

      <div class="mt-auto p-3 border-t border-white/5">
        <button @click="router.push('/settings')" class="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-zinc-400 hover:bg-white/5 hover:text-white transition-colors">
          <span>⚙️</span><span>设置</span>
        </button>
      </div>
    </aside>

    <!-- 主聊天区 -->
    <main class="flex-1 flex flex-col">
      <!-- API Key 未配置提示 -->
      <div v-if="!hasValidApiKey" class="px-6 py-2 bg-amber-950/20 border-b border-amber-500/20 flex items-center gap-2 shrink-0">
        <span class="text-amber-400 text-xs">⚠️</span>
        <span class="text-[11px] text-amber-300 flex-1">未检测到有效 API Key，聊天将使用离线模式。</span>
        <router-link to="/settings" class="text-[10px] text-amber-400 underline hover:text-amber-300 shrink-0">配置 API Key →</router-link>
      </div>

      <div ref="chatContainer" class="flex-1 overflow-y-auto p-6 space-y-6">
        <!-- 欢迎页 -->
        <div v-if="messages.length === 0" class="h-full flex items-center justify-center">
          <div class="text-center max-w-md">
            <div class="w-16 h-16 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-500 flex items-center justify-center">
              <span class="text-3xl">🧮</span>
            </div>
            <h2 class="text-2xl font-bold text-white mb-2">MathModelPro</h2>
            <p class="text-zinc-400 mb-8">上传赛题或描述你的建模需求</p>
            <div class="grid grid-cols-2 gap-2">
              <button v-for="action in quickActions" :key="action.label" @click="action.action()"
                class="p-3 bg-zinc-900 border border-white/5 rounded-lg text-left hover:border-white/10 transition-colors">
                <span class="block text-lg mb-1">{{ action.icon }}</span>
                <span class="text-xs text-zinc-400">{{ action.label }}</span>
              </button>
            </div>
          </div>
        </div>

        <!-- 消息列表 -->
        <template v-for="(msg, index) in filteredMessages" :key="index">
          <div :class="['flex gap-4 max-w-3xl mx-auto', msg.role === 'user' ? 'justify-end' : 'justify-start']">
            <div v-if="msg.role === 'assistant'" class="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-500 flex items-center justify-center shrink-0">
              <span class="text-sm">🤖</span>
            </div>
            
            <div class="max-w-[70%]">
              <div :class="['px-4 py-3 rounded-2xl', msg.role === 'user' ? 'bg-white text-black' : 'bg-zinc-800 text-zinc-200']">
                <!-- 用户消息 -->
                <p v-if="msg.role === 'user'" class="text-sm whitespace-pre-wrap">{{ msg.content }}</p>
                <!-- Agent 消息（Markdown 渲染） -->
                <div v-else class="text-sm prose prose-invert prose-sm max-w-none prose-p:my-1 prose-headings:my-2 prose-pre:bg-zinc-900 prose-pre:border prose-pre:border-white/10 prose-code:text-blue-300" v-html="msg.rendered || msg.content"></div>
              </div>
              <p class="text-[10px] text-zinc-600 mt-1" :class="msg.role === 'user' ? 'text-right' : 'text-left'">{{ formatTime(msg.time) }}</p>
            </div>
            
            <div v-if="msg.role === 'user'" class="w-8 h-8 rounded-lg bg-zinc-700 flex items-center justify-center shrink-0">
              <span class="text-sm">👤</span>
            </div>
          </div>
        </template>

        <!-- 打字指示器 -->
        <div v-if="isTyping" class="flex gap-4 max-w-3xl mx-auto">
          <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-500 flex items-center justify-center shrink-0">
            <span class="text-sm">🤖</span>
          </div>
          <div class="px-4 py-3 rounded-2xl bg-zinc-800">
            <div class="flex gap-1">
              <div class="w-2 h-2 bg-zinc-500 rounded-full animate-bounce"></div>
              <div class="w-2 h-2 bg-zinc-500 rounded-full animate-bounce" style="animation-delay: 0.1s"></div>
              <div class="w-2 h-2 bg-zinc-500 rounded-full animate-bounce" style="animation-delay: 0.2s"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区 -->
      <div class="p-4 border-t border-white/5">
        <div class="max-w-3xl mx-auto flex gap-3">
          <input v-model="message" @keydown.enter="sendMessage" type="text" placeholder="输入你的建模需求..."
            class="flex-1 px-4 py-3 bg-zinc-900 border border-white/10 rounded-xl text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-blue-500/30 focus:border-blue-500/30 transition-all" />
          <button @click="sendMessage" :disabled="!message.trim() || isTyping"
            :class="['px-4 py-3 rounded-xl transition-colors', message.trim() && !isTyping ? 'bg-white text-black hover:bg-zinc-200' : 'bg-zinc-800 text-zinc-500 cursor-not-allowed']">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" /></svg>
          </button>
        </div>
      </div>
    </main>
  </div>
</template>
