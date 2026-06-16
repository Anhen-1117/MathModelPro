<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useTaskStore } from '@/stores/taskStore'
import { useNotify } from '@/composables/useNotify'
import { useConfirm } from '@/composables/useConfirm'
import { playSuccessSound, playErrorSound, sendBrowserNotification } from '@/utils/notify'
import PaperPreview from './PaperPreview.vue'
import CodeEditor from './CodeEditor.vue'
import FiguresGallery from './FiguresGallery.vue'
import AgentStatus from './AgentStatus.vue'
import ValidationReport from './ValidationReport.vue'
import HILPanel from './HILPanel.vue'
import service from '@/utils/request'

const props = defineProps<{
  taskId: string
}>()

const taskStore = useTaskStore()
const notify = useNotify()
const { confirm } = useConfirm()
const activeTab = ref('paper')
const wsMessages = ref<any[]>([])
const showValidation = ref(false)

const task = computed(() => taskStore.getTaskById(props.taskId))


const tabs = [
  { id: 'paper', label: '论文', icon: '📄' },
  { id: 'code', label: '代码', icon: '💻' },
  { id: 'figures', label: '图表', icon: '📊' },
  { id: 'literature', label: '文献', icon: '📚' },
  { id: 'logs', label: '日志', icon: '📋' }
]

// 监听任务状态变化
watch(() => task.value?.status, (newStatus, oldStatus) => {
  if (newStatus === 'completed' && oldStatus !== 'completed') {
    playSuccessSound()
    sendBrowserNotification('建模完成', `${task.value?.name} 已完成！`)
    notify.success('建模完成', task.value?.name)
  }
  if (newStatus === 'failed' && oldStatus !== 'failed') {
    playErrorSound()
    sendBrowserNotification('建模失败', `${task.value?.name} 执行失败`)
    notify.error('建模失败', task.value?.name)
  }
})

onMounted(() => {
  taskStore.connectWebSocket(props.taskId, (data) => {
    wsMessages.value.push(data)
    // 自动滚动到最新日志
    const logsEl = document.getElementById('logs-container')
    if (logsEl) {
      setTimeout(() => logsEl.scrollTop = logsEl.scrollHeight, 50)
    }
  })
})

onUnmounted(() => {
  taskStore.disconnectWebSocket(props.taskId)
})

const handleExport = async () => {
  try {
    await taskStore.exportTask(props.taskId)
    notify.success('导出成功', 'ZIP 文件已开始下载')
  } catch {
    notify.error('导出失败', '请稍后重试')
  }
}

const handleExportDocx = async () => {
  if (!task.value?.paper_content) {
    notify.error('论文尚未生成，无法导出 Word')
    return
  }
  try {
    await taskStore.exportDocx(props.taskId, task.value?.name)
    notify.success('Word 导出成功', '文件已开始下载')
  } catch {
    notify.error('Word 导出失败', '请稍后重试')
  }
}

const handleRetry = async () => {
  const ok = await confirm({
    title: '重新生成',
    description: '将重新运行整个建模流程，当前结果会被覆盖。',
    confirmText: '重新生成',
    variant: 'default'
  })
  if (ok) {
    try {
      await taskStore.retryTask(props.taskId)
      notify.info('已重新开始', '建模流程重新启动')
    } catch {
      notify.error('重试失败', '请检查后端连接')
    }
  }
}

const handleDelete = async () => {
  const ok = await confirm({
    title: '删除任务',
    description: '删除后不可恢复，确定要删除吗？',
    confirmText: '删除',
    variant: 'danger'
  })
  if (ok) {
    try {
      await taskStore.deleteTask(props.taskId)
      notify.success('已删除')
    } catch {
      notify.error('删除失败')
    }
  }
}

const handleStart = async () => {
  try {
    await taskStore.startTask(props.taskId)
    notify.info('任务已启动')
  } catch {
    notify.error('启动失败', '请检查 API 配置')
  }
}

// 文献检索
const searchingLit = ref(false)
const searchLiterature = async () => {
  searchingLit.value = true
  try {
    const res = await service.get('/api/v1/search', { params: { q: task.value?.name || 'mathematical modeling', max_results: 5 } })
    if (res.data.papers?.length) {
      // 更新任务的文献数据
      if (task.value) task.value.literature = res.data.papers
      notify.success('检索完成', `找到 ${res.data.papers.length} 篇文献`)
    } else {
      notify.info('未找到相关文献')
    }
  } catch {
    notify.error('检索失败')
  } finally {
    searchingLit.value = false
  }
}

const formatTime = (date: string) => {
  const d = new Date(date)
  return `${d.getHours()}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`
}
</script>

<template>
  <div class="flex-1 flex flex-col overflow-hidden">
    <!-- 顶部工具栏 -->
    <div class="h-14 px-6 border-b border-white/5 flex items-center justify-between shrink-0">
      <div class="flex items-center gap-3">
        <h2 class="text-sm font-medium text-white">{{ task?.name || '任务详情' }}</h2>
        <span class="text-[10px] px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">{{ task?.language || 'python' }}</span>
        <span v-if="task?.status === 'running'" class="text-[10px] px-2 py-0.5 rounded bg-blue-900/30 text-blue-400 flex items-center gap-1">
          <span class="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse"></span>
          运行中 {{ task?.progress?.overall || 0 }}%
        </span>
        <span v-else-if="task?.status === 'completed'" class="text-[10px] px-2 py-0.5 rounded bg-green-900/30 text-green-400">✓ 已完成</span>
        <span v-else-if="task?.status === 'failed'" class="text-[10px] px-2 py-0.5 rounded bg-red-900/30 text-red-400">✗ 失败</span>
        <span v-if="task?.status === 'failed'" class="text-[10px] text-red-400/60">
          {{ task?.token_usage?.total ? '执行过程中出错' : '请检查 API Key 是否有效' }}
        </span>
      </div>
      
      <div class="flex items-center gap-2">
        <button v-if="task?.status === 'pending'" @click="handleStart"
          class="px-3 py-1.5 text-xs bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center gap-1">
          ▶ 启动
        </button>
        <button @click="handleRetry" class="px-3 py-1.5 text-xs text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg transition-colors">↻ 重新生成</button>
        <button @click="showValidation = true" class="px-3 py-1.5 text-xs text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg transition-colors">📋 验收</button>
        <button @click="handleExport" class="px-3 py-1.5 text-xs text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg transition-colors">↓ 导出 ZIP</button>
        <button v-if="task?.status === 'completed'" @click="handleExportDocx" class="px-3 py-1.5 text-xs text-blue-400 hover:text-blue-300 hover:bg-blue-900/20 rounded-lg transition-colors">📝 Word</button>
        <button @click="handleDelete" class="px-3 py-1.5 text-xs text-red-400 hover:text-red-300 hover:bg-red-900/20 rounded-lg transition-colors">删除</button>
      </div>
    </div>


    <!-- 任务失败恢复引导 -->
    <div v-if="task?.status === 'failed'" class="px-6 py-2 bg-red-950/10 border-b border-red-500/20 flex items-center gap-3 shrink-0">
      <span class="text-red-400 text-xs">✗</span>
      <span class="text-[11px] text-red-300 flex-1">
        {{ task?.token_usage?.total ? '任务执行过程中出错' : 'API Key 可能无效或未配置，任务无法访问 AI 服务。' }}
      </span>
      <button @click="handleRetry" class="px-3 py-1 text-[10px] bg-red-500/20 text-red-300 rounded-lg hover:bg-red-500/30 transition-colors">↻ 重试</button>
      <router-link to="/settings" class="px-3 py-1 text-[10px] bg-blue-500/20 text-blue-300 rounded-lg hover:bg-blue-500/30 transition-colors">配置 API</router-link>
    </div>

    <!-- Agent 状态条 -->
    <AgentStatus v-if="task" :task="task" />

    <!-- 标签页 -->
    <div class="flex items-center gap-0 px-6 border-b border-white/5 shrink-0">
      <button v-for="tab in tabs" :key="tab.id" @click="activeTab = tab.id"
        :class="['px-4 py-2.5 text-xs transition-colors border-b-2', activeTab === tab.id ? 'text-white border-white' : 'text-zinc-500 border-transparent hover:text-zinc-300']">
        <span class="mr-1">{{ tab.icon }}</span>{{ tab.label }}
      </button>
    </div>

    <!-- HIL 决策面板 -->
    <div class="px-6 shrink-0">
      <HILPanel />
    </div>

    <!-- 内容区 -->
    <div class="flex-1 overflow-hidden">
      <PaperPreview v-if="activeTab === 'paper'" :task-id="taskId" />
      <CodeEditor v-else-if="activeTab === 'code'" :task-id="taskId" />
      <FiguresGallery v-else-if="activeTab === 'figures'" :task-id="taskId" />
      
      <!-- 文献检索 -->
      <div v-else-if="activeTab === 'literature'" class="h-full overflow-y-auto p-6">
        <div class="max-w-3xl mx-auto">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-sm font-medium text-white">📚 文献检索结果</h3>
            <button @click="searchLiterature" :disabled="searchingLit" :class="['px-3 py-1.5 text-xs rounded-lg transition-colors', searchingLit ? 'bg-zinc-800 text-zinc-500' : 'bg-white/10 text-white hover:bg-white/20']">
              {{ searchingLit ? '搜索中...' : '🔍 搜索文献' }}
            </button>
          </div>
          <div v-if="task?.literature?.length" class="space-y-3">
            <div v-for="(paper, i) in task.literature" :key="i" class="p-4 bg-zinc-900/50 border border-white/5 rounded-lg">
              <p class="text-sm font-medium text-white mb-1">{{ paper.title }}</p>
              <p class="text-[10px] text-zinc-500 mb-1">{{ paper.authors?.join(', ') }} · {{ paper.year }}</p>
              <div class="flex items-center gap-2"><span class="text-[10px] text-zinc-400">引用 {{ paper.citations }}</span></div>
            </div>
          </div>
          <div v-else class="text-center py-12">
            <div class="text-4xl mb-3 opacity-30">📚</div>
            <p class="text-sm text-zinc-500">暂无文献</p>
            <p class="text-[10px] text-zinc-600">点击搜索或在建模过程中自动检索</p>
          </div>
        </div>
      </div>

      <!-- 日志 -->
      <div v-else-if="activeTab === 'logs'" id="logs-container" class="h-full overflow-y-auto p-4 font-mono text-xs">
        <div v-if="wsMessages.length === 0" class="text-center py-12 text-zinc-600">
          <p>暂无日志</p>
          <p class="text-[10px] mt-1">任务运行后将显示实时日志</p>
        </div>
        <div v-for="(msg, i) in wsMessages" :key="i" class="mb-1 flex gap-2">
          <span class="text-zinc-600 shrink-0">{{ msg.timestamp ? formatTime(msg.timestamp) : '' }}</span>
          <span :class="[
            msg.type === 'error' ? 'text-red-400' : 
            msg.type === 'success' ? 'text-green-400' : 
            msg.type === 'progress' ? 'text-blue-400' : 'text-zinc-400'
          ]">{{ msg.message || msg.content || JSON.stringify(msg) }}</span>
        </div>
      </div>
    </div>

    <!-- 论文验收弹窗 -->
    <ValidationReport v-if="showValidation" :task-id="taskId" :content="task?.paper_content || ''" @close="showValidation = false" />
  </div>
</template>
