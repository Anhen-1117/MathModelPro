<script setup lang="ts">
import { computed, ref } from 'vue'
import { useTaskStore } from '@/stores/taskStore'

const props = defineProps<{
  selectedTaskId: string | null
}>()

const emit = defineEmits<{
  select: [taskId: string]
}>()

const taskStore = useTaskStore()
const filterStatus = ref<string>('all')
const sortBy = ref<'date' | 'status'>('date')
const searchQuery = ref('')

const statusConfigs: Record<string, { color: string; bg: string; text: string }> = {
  pending: { color: 'text-zinc-400', bg: 'bg-zinc-500', text: '待处理' },
  running: { color: 'text-blue-400', bg: 'bg-blue-500', text: '运行中' },
  paused: { color: 'text-yellow-400', bg: 'bg-yellow-500', text: '已暂停' },
  completed: { color: 'text-green-400', bg: 'bg-green-500', text: '已完成' },
  failed: { color: 'text-red-400', bg: 'bg-red-500', text: '失败' },
  cancelled: { color: 'text-zinc-500', bg: 'bg-zinc-600', text: '已取消' }
}

const filteredTasks = computed(() => {
  let list = [...taskStore.tasks]
  // 搜索过滤
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.trim().toLowerCase()
    list = list.filter(t =>
      t.name.toLowerCase().includes(q) ||
      t.description?.toLowerCase().includes(q) ||
      t.id.toLowerCase().includes(q)
    )
  }
  if (filterStatus.value !== 'all') {
    list = list.filter(t => t.status === filterStatus.value)
  }
  if (sortBy.value === 'date') {
    list.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
  }
  return list
})

const formatDate = (date: string) => {
  const d = new Date(date)
  const now = new Date()
  const isToday = d.toDateString() === now.toDateString()
  if (isToday) return `今天 ${d.getHours()}:${d.getMinutes().toString().padStart(2, '0')}`
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:${d.getMinutes().toString().padStart(2, '0')}`
}

const getProgressWidth = (task: any) => {
  return task.progress?.overall || 0
}
</script>

<template>
  <div class="flex-1 flex flex-col overflow-hidden">
    <!-- 筛选栏 -->
    <div class="px-3 py-2 border-b border-white/5 space-y-2">
      <input v-model="searchQuery" type="text" placeholder="搜索任务名称、描述或 ID..."
        class="w-full px-2 py-1.5 bg-zinc-800 border border-white/5 rounded text-[11px] text-zinc-300 placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-blue-500/30" />
      <select v-model="filterStatus" class="w-full px-2 py-1 bg-zinc-800 border border-white/5 rounded text-[10px] text-zinc-400 focus:outline-none">
        <option value="all">全部状态</option>
        <option value="running">运行中</option>
        <option value="completed">已完成</option>
        <option value="pending">待处理</option>
        <option value="failed">失败</option>
      </select>
    </div>

    <!-- 任务列表 -->
    <div class="flex-1 overflow-y-auto p-2">
      <!-- 骨架屏 -->
      <div v-if="taskStore.loading && taskStore.tasks.length === 0" class="space-y-2">
        <div v-for="i in 3" :key="i" class="p-3 rounded-lg bg-zinc-900/50 animate-pulse">
          <div class="h-3 bg-zinc-800 rounded w-3/4 mb-2"></div>
          <div class="h-2 bg-zinc-800 rounded w-1/2 mb-2"></div>
          <div class="h-1 bg-zinc-800 rounded-full"></div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else-if="filteredTasks.length === 0" class="flex flex-col items-center justify-center py-12 px-4">
        <div class="text-4xl mb-3 opacity-50">📋</div>
        <p class="text-sm text-zinc-500 mb-1">{{ filterStatus === 'all' ? '暂无任务' : '没有匹配的任务' }}</p>
        <p class="text-[10px] text-zinc-600">{{ filterStatus === 'all' ? '点击左侧「新建」开始第一个建模任务' : '尝试切换筛选条件' }}</p>
      </div>

      <!-- 任务卡片 -->
      <div v-for="task in filteredTasks" :key="task.id"
        @click="emit('select', task.id)"
        :class="['group p-3 rounded-lg cursor-pointer transition-all mb-1 border', selectedTaskId === task.id ? 'bg-white/10 border-white/10' : 'border-transparent hover:bg-white/5 hover:border-white/5']">
        
        <div class="flex items-center justify-between mb-2">
          <h3 class="text-sm font-medium text-white truncate flex-1">{{ task.name }}</h3>
          <span :class="['w-2 h-2 rounded-full shrink-0 ml-2', task.status === 'running' ? 'bg-blue-500 animate-pulse' : statusConfigs[task.status]?.bg || 'bg-zinc-500']"></span>
        </div>
        
        <div class="flex items-center gap-2 mb-2">
          <span :class="['text-[10px] px-1.5 py-0.5 rounded', statusConfigs[task.status]?.color || 'text-zinc-400', 'bg-zinc-800/50']">
            {{ statusConfigs[task.status]?.text || task.status }}
          </span>
          <span class="text-[10px] text-zinc-600">{{ formatDate(task.created_at) }}</span>
        </div>
        
        <!-- 进度条 -->
        <div class="h-1 bg-zinc-800 rounded-full overflow-hidden">
          <div :class="['h-full rounded-full transition-all duration-500', task.status === 'completed' ? 'bg-green-500' : task.status === 'failed' ? 'bg-red-500' : 'bg-gradient-to-r from-blue-500 to-purple-500']"
            :style="{ width: `${getProgressWidth(task)}%` }"></div>
        </div>
        
        <div v-if="task.status === 'running'" class="mt-1.5 text-[10px] text-blue-400">
          {{ getProgressWidth(task) }}% 完成
        </div>
      </div>
    </div>
  </div>
</template>
