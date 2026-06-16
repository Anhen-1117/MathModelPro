<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import service from '@/utils/request'
import { useNotify } from '@/composables/useNotify'

const notify = useNotify()
const checkpoints = ref<any[]>([])
const polling = ref(false)
let timer: ReturnType<typeof setInterval> | null = null

const actionLabels: Record<string, { label: string; icon: string; color: string }> = {
  confirm: { label: '确认继续', icon: '✅', color: 'bg-green-600 hover:bg-green-700' },
  regenerate: { label: '重新生成', icon: '🔄', color: 'bg-blue-600 hover:bg-blue-700' },
  edit: { label: '编辑后继续', icon: '✏️', color: 'bg-yellow-600 hover:bg-yellow-700' },
  skip: { label: '跳过', icon: '⏭️', color: 'bg-zinc-600 hover:bg-zinc-700' },
  ask: { label: '追问', icon: '❓', color: 'bg-purple-600 hover:bg-purple-700' },
  abort: { label: '中止', icon: '🛑', color: 'bg-red-600 hover:bg-red-700' },
}

const fetchPending = async () => {
  try {
    const res = await service.get('/api/v1/hil/pending')
    checkpoints.value = res.data.checkpoints || []
  } catch {}
}

const decide = async (cpId: string, action: string, userInput?: string) => {
  try {
    await service.post(`/api/v1/hil/decide/${cpId}`, { action, user_input: userInput })
    notify.success('已决策', actionLabels[action]?.label || action)
    await fetchPending()
  } catch {
    notify.error('决策失败')
  }
}

const startPolling = () => {
  polling.value = true
  timer = setInterval(fetchPending, 3000)
}

const stopPolling = () => {
  polling.value = false
  if (timer) clearInterval(timer)
}

onMounted(() => { fetchPending(); startPolling() })
onUnmounted(() => stopPolling())
</script>

<template>
  <div v-if="checkpoints.length > 0" class="mb-4">
    <div v-for="cp in checkpoints" :key="cp.id" class="p-4 bg-amber-950/20 border border-amber-500/20 rounded-lg mb-2">
      <div class="flex items-center gap-2 mb-2">
        <span class="text-amber-400">⏸️</span>
        <span class="text-xs text-amber-300 font-medium">{{ cp.agent }} 需要你的决策</span>
        <span class="text-[10px] text-zinc-500 ml-auto">{{ cp.phase }}</span>
      </div>
      
      <p class="text-sm text-zinc-300 mb-3">{{ cp.question }}</p>
      
      <!-- 预览内容 -->
      <div v-if="cp.preview" class="p-3 bg-zinc-900/50 rounded-lg mb-3 max-h-32 overflow-y-auto">
        <pre class="text-xs text-zinc-400 whitespace-pre-wrap font-mono">{{ cp.preview }}</pre>
      </div>
      
      <!-- 决策按钮 -->
      <div class="flex flex-wrap gap-2">
        <button v-for="opt in cp.options" :key="opt" @click="decide(cp.id, opt)"
          :class="['px-3 py-1.5 text-xs text-white rounded-lg transition-colors', actionLabels[opt]?.color || 'bg-zinc-600']">
          {{ actionLabels[opt]?.icon || '•' }} {{ actionLabels[opt]?.label || opt }}
        </button>
      </div>
    </div>
  </div>
</template>
