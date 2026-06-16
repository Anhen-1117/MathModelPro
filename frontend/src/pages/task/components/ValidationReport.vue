<script setup lang="ts">
import { ref, computed } from 'vue'
import service from '@/utils/request'
import { useNotify } from '@/composables/useNotify'

const props = defineProps<{ taskId: string; content: string }>()
const emit = defineEmits<{ close: [] }>()

const notify = useNotify()
const loading = ref(false)
const report = ref<any>(null)

const severityIcons: Record<string, string> = { error: '❌', warning: '⚠️', info: 'ℹ️' }
const severityColors: Record<string, string> = {
  error: 'border-red-500/20 bg-red-950/20',
  warning: 'border-yellow-500/20 bg-yellow-950/20',
  info: 'border-blue-500/20 bg-blue-950/20',
}

const scoreColor = computed(() => {
  if (!report.value) return 'text-zinc-400'
  if (report.value.score >= 90) return 'text-green-400'
  if (report.value.score >= 70) return 'text-yellow-400'
  return 'text-red-400'
})

const runValidation = async () => {
  loading.value = true
  try {
    const res = await service.post('/api/v1/validate/paper', {
      content: props.content,
      problem_text: '',
    })
    report.value = res.data
  } catch {
    notify.error('验收失败', '请检查后端连接')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div class="fixed inset-0 z-[80] flex items-center justify-center">
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="emit('close')"></div>
        <div class="relative w-full max-w-2xl mx-4 max-h-[80vh] bg-[#111111] border border-white/10 rounded-xl shadow-2xl overflow-hidden flex flex-col">
          <!-- 标题 -->
          <div class="px-6 py-4 border-b border-white/5 flex items-center justify-between shrink-0">
            <div>
              <h2 class="text-sm font-medium text-white">📋 论文验收报告</h2>
              <p class="text-[10px] text-zinc-500">检测文本泄漏、数值一致性、格式规范</p>
            </div>
            <button @click="emit('close')" class="w-6 h-6 rounded-md hover:bg-white/10 flex items-center justify-center text-zinc-400 hover:text-white transition-colors">✕</button>
          </div>

          <!-- 内容 -->
          <div class="flex-1 overflow-y-auto p-6">
            <!-- 未运行 -->
            <div v-if="!report && !loading" class="text-center py-12">
              <div class="text-4xl mb-4 opacity-30">🔍</div>
              <p class="text-sm text-zinc-400 mb-4">点击下方按钮开始验收</p>
              <button @click="runValidation" class="px-6 py-2 bg-white text-black text-sm font-medium rounded-lg hover:bg-zinc-200 transition-colors">开始验收</button>
            </div>

            <!-- 加载中 -->
            <div v-if="loading" class="text-center py-12">
              <div class="w-8 h-8 border-2 border-white/20 border-t-white rounded-full animate-spin mx-auto mb-4"></div>
              <p class="text-sm text-zinc-400">正在验收...</p>
            </div>

            <!-- 结果 -->
            <div v-if="report && !loading">
              <!-- 分数 -->
              <div class="text-center mb-6">
                <div :class="['text-5xl font-bold', scoreColor]">{{ report.score }}</div>
                <p class="text-sm text-zinc-400 mt-1">/ 100 分</p>
                <p class="text-xs text-zinc-500 mt-2">{{ report.summary }}</p>
              </div>

              <!-- 统计 -->
              <div class="flex items-center justify-center gap-6 mb-6">
                <div class="text-center">
                  <div class="text-lg font-bold text-red-400">{{ report.error_count }}</div>
                  <div class="text-[10px] text-zinc-500">错误</div>
                </div>
                <div class="text-center">
                  <div class="text-lg font-bold text-yellow-400">{{ report.warning_count }}</div>
                  <div class="text-[10px] text-zinc-500">警告</div>
                </div>
                <div class="text-center">
                  <div class="text-lg font-bold text-zinc-400">{{ report.issues.length - report.error_count - report.warning_count }}</div>
                  <div class="text-[10px] text-zinc-500">建议</div>
                </div>
              </div>

              <!-- 问题列表 -->
              <div class="space-y-2">
                <div v-for="(issue, i) in report.issues" :key="i"
                  :class="['p-3 rounded-lg border', severityColors[issue.severity] || 'border-white/5']">
                  <div class="flex items-start gap-2">
                    <span class="shrink-0">{{ severityIcons[issue.severity] || '•' }}</span>
                    <div class="flex-1">
                      <p class="text-xs text-zinc-300">{{ issue.message }}</p>
                      <p v-if="issue.suggestion" class="text-[10px] text-zinc-500 mt-1">💡 {{ issue.suggestion }}</p>
                    </div>
                    <span class="text-[9px] text-zinc-600 shrink-0">{{ issue.category }}</span>
                  </div>
                </div>
              </div>

              <!-- 重新验收 -->
              <div class="text-center mt-6">
                <button @click="runValidation" class="px-4 py-2 text-xs text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg transition-colors">↻ 重新验收</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
