<script setup lang="ts">
import { computed } from 'vue'
import type { Task } from '@/stores/taskStore'

const props = defineProps<{ task: Task }>()

const agents = computed(() => [
  { id: 'coordinator', name: '协调器', icon: '🎯', status: props.task.agent_status?.coordinator || 'idle', progress: props.task.progress?.analysis || 0 },
  { id: 'modeler', name: '建模手', icon: '📐', status: props.task.agent_status?.modeler || 'idle', progress: props.task.progress?.modeling || 0 },
  { id: 'coder', name: '代码手', icon: '💻', status: props.task.agent_status?.coder || 'idle', progress: props.task.progress?.coding || 0 },
  { id: 'writer', name: '论文手', icon: '📝', status: props.task.agent_status?.writer || 'idle', progress: props.task.progress?.paper || 0 }
])

const statusLabels: Record<string, { text: string; color: string }> = {
  idle: { text: '待命', color: 'text-zinc-500' },
  thinking: { text: '思考中...', color: 'text-yellow-400' },
  working: { text: '工作中', color: 'text-blue-400' },
  completed: { text: '已完成', color: 'text-green-400' },
  error: { text: '出错', color: 'text-red-400' }
}

const overallProgress = computed(() => props.task.progress?.overall || 0)
</script>

<template>
  <div class="px-6 py-3 border-b border-white/5 bg-zinc-900/30 shrink-0">
    <!-- 整体进度 -->
    <div class="flex items-center gap-3 mb-2.5">
      <span class="text-[10px] text-zinc-500 shrink-0">整体进度</span>
      <div class="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
        <div class="h-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-full transition-all duration-700 relative"
          :style="{ width: `${overallProgress}%` }">
          <div v-if="task.status === 'running'" class="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer"></div>
        </div>
      </div>
      <span class="text-[10px] font-mono text-zinc-400 shrink-0 w-8 text-right">{{ overallProgress }}%</span>
    </div>

    <!-- 各 Agent 状态 -->
    <div class="flex items-center gap-3">
      <div v-for="agent in agents" :key="agent.id" class="flex-1 flex items-center gap-2 px-2 py-1.5 rounded-md bg-zinc-800/30">
        <span class="text-sm">{{ agent.icon }}</span>
        <div class="flex-1 min-w-0">
          <div class="flex items-center justify-between">
            <span class="text-[10px] text-zinc-400">{{ agent.name }}</span>
            <span :class="['text-[9px]', statusLabels[agent.status]?.color || 'text-zinc-500']">
              <span v-if="agent.status === 'working' || agent.status === 'thinking'" class="inline-block w-1 h-1 rounded-full bg-current animate-pulse mr-0.5"></span>
              {{ statusLabels[agent.status]?.text || agent.status }}
            </span>
          </div>
          <div v-if="agent.progress > 0" class="h-0.5 bg-zinc-700 rounded-full mt-1 overflow-hidden">
            <div class="h-full rounded-full transition-all duration-500" :class="agent.status === 'completed' ? 'bg-green-500' : 'bg-blue-500'" :style="{ width: `${agent.progress}%` }"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}
.animate-shimmer { animation: shimmer 2s infinite; }
</style>
