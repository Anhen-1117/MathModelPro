<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useTaskStore } from '@/stores/taskStore'
import { useNotify } from '@/composables/useNotify'
import hljs from 'highlight.js/lib/core'
import python from 'highlight.js/lib/languages/python'

hljs.registerLanguage('python', python)

const props = defineProps<{
  taskId: string
}>()

const taskStore = useTaskStore()
const notify = useNotify()
const isRunning = ref(false)
const runOutput = ref('')
const codeRef = ref<HTMLElement>()
const isEditing = ref(false)
const editedCode = ref('')

const task = computed(() => taskStore.getTaskById(props.taskId))
const code = computed(() => task.value?.code || '')

const highlightedCode = computed(() => {
  if (!code.value) return ''
  try {
    return hljs.highlight(code.value, { language: 'python' }).value
  } catch {
    return code.value
  }
})

onMounted(async () => {
  await taskStore.fetchCode(props.taskId)
})

const handleRun = async () => {
  isRunning.value = true
  runOutput.value = '运行中...'
  try {
    const result = await taskStore.runCode(props.taskId, 'python')
    runOutput.value = result.output || '运行完成'
    notify.success('运行完成')
  } catch (error: any) {
    runOutput.value = `错误: ${error.message}`
    notify.error('运行失败', error.message)
  } finally {
    isRunning.value = false
  }
}

const handleCopy = () => {
  navigator.clipboard.writeText(code.value)
  notify.success('已复制到剪贴板')
}

const handleDownload = () => {
  const blob = new Blob([code.value], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `code.${'py'}`
  a.click()
  URL.revokeObjectURL(url)
}

const handleEdit = () => {
  editedCode.value = code.value
  isEditing.value = true
}

const handleSave = async () => {
  try {
    await taskStore.updateCode(props.taskId, editedCode.value, 'python')
    isEditing.value = false
    notify.success('代码已保存')
  } catch {
    notify.error('保存失败')
  }
}

const handleCancelEdit = () => {
  isEditing.value = false
}
</script>

<template>
  <div class="h-full flex flex-col">
    <!-- 工具栏 -->
    <div class="px-4 py-2 border-b border-white/5 flex items-center justify-between shrink-0">
      <div class="flex items-center gap-1">
        <span class="px-3 py-1.5 text-xs text-zinc-400">🐍 Python</span>
        <span class="w-px h-4 bg-white/10 mx-1"></span>
        <button v-if="!isEditing" @click="handleEdit"
          class="px-3 py-1.5 text-xs text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg transition-colors">
          ✏️ 编辑
        </button>
        <template v-else>
          <button @click="handleSave" class="px-3 py-1.5 text-xs bg-white text-black rounded-lg hover:bg-zinc-200 transition-colors">保存</button>
          <button @click="handleCancelEdit" class="px-3 py-1.5 text-xs text-zinc-400 hover:text-white rounded-lg transition-colors">取消</button>
        </template>
      </div>

      <div class="flex items-center gap-2">
        <button @click="handleCopy" class="px-3 py-1.5 text-xs text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg transition-colors">📋 复制</button>
        <button @click="handleDownload" class="px-3 py-1.5 text-xs text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg transition-colors">↓ 下载</button>
        <button @click="handleRun" :disabled="isRunning"
          :class="['px-4 py-1.5 text-xs rounded-lg transition-colors flex items-center gap-1.5', isRunning ? 'bg-zinc-800 text-zinc-500 cursor-not-allowed' : 'bg-white text-black hover:bg-zinc-200']">
          <span v-if="isRunning" class="w-3 h-3 border-2 border-zinc-500 border-t-transparent rounded-full animate-spin"></span>
          {{ isRunning ? '运行中...' : '▶ 运行' }}
        </button>
      </div>
    </div>

    <!-- 编辑器 -->
    <div class="flex-1 flex overflow-hidden">
      <div class="flex-1 overflow-auto bg-[#0d1117]">
        <!-- 编辑模式 -->
        <div v-if="isEditing" class="h-full p-4">
          <textarea v-model="editedCode"
            class="w-full h-full p-4 bg-zinc-900 border border-white/10 rounded-lg text-sm text-zinc-300 font-mono resize-none focus:outline-none focus:ring-1 focus:ring-yellow-500/30"
            placeholder="输入 Python 代码..."></textarea>
        </div>
        <!-- 预览模式 -->
        <div v-else-if="code" class="relative">
          <pre class="p-4 text-sm leading-relaxed"><code ref="codeRef" class="font-mono" v-html="highlightedCode"></code></pre>
        </div>
        <div v-else class="h-full flex flex-col items-center justify-center">
          <div class="text-4xl mb-3 opacity-30">💻</div>
          <p class="text-sm text-zinc-500">代码尚未生成</p>
        </div>
      </div>

      <!-- 输出面板 -->
      <div class="w-80 border-l border-white/5 bg-[#0d1117] flex flex-col">
        <div class="px-4 py-2 border-b border-white/5 text-xs text-zinc-500 flex items-center justify-between">
          <span>输出</span>
          <span v-if="isRunning" class="text-blue-400 flex items-center gap-1">
            <span class="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse"></span>
            运行中
          </span>
        </div>
        <div class="flex-1 overflow-auto p-4 font-mono text-xs">
          <pre v-if="runOutput" class="text-zinc-300 whitespace-pre-wrap leading-relaxed">{{ runOutput }}</pre>
          <p v-else class="text-zinc-600">点击 ▶ 运行 查看输出</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style>
/* GitHub Dark 风格高亮 */
.hljs-keyword { color: #ff7b72; }
.hljs-built_in { color: #d2a8ff; }
.hljs-string { color: #a5d6ff; }
.hljs-number { color: #79c0ff; }
.hljs-comment { color: #8b949e; font-style: italic; }
.hljs-function { color: #d2a8ff; }
.hljs-title { color: #d2a8ff; }
.hljs-params { color: #c9d1d9; }
.hljs-attr { color: #79c0ff; }
.hljs-literal { color: #79c0ff; }
.hljs-meta { color: #8b949e; }
</style>
