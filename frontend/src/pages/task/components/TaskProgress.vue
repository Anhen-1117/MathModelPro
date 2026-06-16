<script setup lang="ts">
import { computed } from 'vue'
import { useTaskStore } from '@/stores/taskStore'

const props = defineProps<{
  taskId: string
}>()

const taskStore = useTaskStore()
const task = computed(() => taskStore.getTaskById(props.taskId))

const progress = computed(() => task.value?.progress?.overall || 0)

const phases = computed(() => [
  { 
    id: 'analysis', 
    name: '问题分析', 
    icon: '🔍',
    progress: task.value?.progress?.analysis || 0,
    status: task.value?.agent_status?.coordinator || 'idle'
  },
  { 
    id: 'modeling', 
    name: '数学建模', 
    icon: '📐',
    progress: task.value?.progress?.modeling || 0,
    status: task.value?.agent_status?.modeler || 'idle'
  },
  { 
    id: 'coding', 
    name: '代码实现', 
    icon: '💻',
    progress: task.value?.progress?.coding || 0,
    status: task.value?.agent_status?.coder || 'idle'
  },
  { 
    id: 'paper', 
    name: '论文撰写', 
    icon: '📝',
    progress: task.value?.progress?.paper || 0,
    status: task.value?.agent_status?.writer || 'idle'
  }
])

const getPhaseColor = (status: string) => {
  const colors: Record<string, string> = {
    idle: 'bg-slate-200 dark:bg-slate-700',
    thinking: 'bg-yellow-400',
    working: 'bg-blue-500',
    completed: 'bg-green-500',
    error: 'bg-red-500'
  }
  return colors[status] || colors.idle
}
</script>

<template>
  <div class="px-6 py-4 border-b border-slate-200 dark:border-slate-700 bg-white/50 dark:bg-slate-900/50">
    <!-- 整体进度 -->
    <div class="mb-4">
      <div class="flex items-center justify-between mb-2">
        <span class="text-sm font-medium text-slate-700 dark:text-slate-300">整体进度</span>
        <span class="text-sm font-bold text-blue-600 dark:text-blue-400">{{ progress }}%</span>
      </div>
      <div class="h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
        <div 
          class="h-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-full transition-all duration-500 relative"
          :style="{ width: `${progress}%` }"
        >
          <div class="absolute inset-0 bg-gradient-to-r from-transparent via-white/30 to-transparent animate-shimmer"></div>
        </div>
      </div>
    </div>

    <!-- 阶段进度 -->
    <div class="flex items-center gap-4">
      <div 
        v-for="(phase, index) in phases" 
        :key="phase.id"
        class="flex-1"
      >
        <div class="flex items-center gap-2 mb-1">
          <span class="text-sm">{{ phase.icon }}</span>
          <span class="text-xs text-slate-600 dark:text-slate-400">{{ phase.name }}</span>
        </div>
        <div class="h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
          <div 
            :class="['h-full rounded-full transition-all duration-500', getPhaseColor(phase.status)]"
            :style="{ width: `${phase.progress}%` }"
          ></div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes shimmer {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(100%);
  }
}

.animate-shimmer {
  animation: shimmer 2s infinite;
}
</style>
