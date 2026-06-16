<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useTaskStore } from '@/stores/taskStore'
import { useNotify } from '@/composables/useNotify'

const router = useRouter()
const taskStore = useTaskStore()
const notify = useNotify()
const selectedTasks = ref<string[]>([])
const showResult = ref(false)

const tasks = computed(() => taskStore.tasks)
const canCompare = computed(() => selectedTasks.value.length >= 2)
const selectedTaskData = computed(() => tasks.value.filter(t => selectedTasks.value.includes(t.id)))

onMounted(async () => { await taskStore.fetchTasks() })

const handleSelectTask = (taskId: string) => {
  const i = selectedTasks.value.indexOf(taskId)
  if (i === -1) selectedTasks.value.push(taskId)
  else selectedTasks.value.splice(i, 1)
}

const handleCompare = () => {
  if (!canCompare.value) { notify.warning('请选择至少 2 个任务'); return }
  showResult.value = true
}

const handleClear = () => { selectedTasks.value = []; showResult.value = false }

const statusColors: Record<string, string> = {
  completed: 'text-green-400', running: 'text-blue-400', failed: 'text-red-400', pending: 'text-zinc-400'
}
</script>

<template>
  <div class="h-screen flex bg-[#0a0a0b] text-white">
    <aside class="w-72 border-r border-white/5 flex flex-col">
      <div class="h-14 px-4 border-b border-white/5 flex items-center justify-between">
        <button @click="router.push('/')" class="flex items-center gap-2 text-zinc-400 hover:text-white transition-colors">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
          <span class="text-sm">返回</span>
        </button>
        <span class="text-xs text-zinc-500">{{ selectedTasks.length }} 个已选</span>
      </div>

      <div class="p-3 border-b border-white/5">
        <button @click="handleCompare" :disabled="!canCompare"
          :class="['w-full py-2 rounded-lg text-sm font-medium transition-colors', canCompare ? 'bg-white text-black hover:bg-zinc-200' : 'bg-zinc-800 text-zinc-500 cursor-not-allowed']">
          开始对比
        </button>
      </div>

      <div class="flex-1 overflow-y-auto p-2">
        <div v-if="tasks.length === 0" class="text-center py-12">
          <div class="text-3xl mb-2 opacity-30">📋</div>
          <p class="text-sm text-zinc-500">暂无任务</p>
        </div>
        <div v-for="task in tasks" :key="task.id" @click="handleSelectTask(task.id)"
          :class="['p-3 rounded-lg cursor-pointer mb-1 border transition-all', selectedTasks.includes(task.id) ? 'bg-white/10 border-white/20' : 'border-transparent hover:bg-white/5']">
          <div class="flex items-center gap-3">
            <div :class="['w-4 h-4 rounded border flex items-center justify-center shrink-0', selectedTasks.includes(task.id) ? 'bg-white border-white' : 'border-zinc-600']">
              <svg v-if="selectedTasks.includes(task.id)" class="w-3 h-3 text-black" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" /></svg>
            </div>
            <div class="flex-1 min-w-0">
              <h3 class="text-sm font-medium text-white truncate">{{ task.name }}</h3>
              <p class="text-xs text-zinc-500">{{ task.language }} · {{ task.created_at?.slice(0, 10) }}</p>
            </div>
            <span :class="['w-2 h-2 rounded-full shrink-0', task.status === 'completed' ? 'bg-green-500' : task.status === 'running' ? 'bg-blue-500 animate-pulse' : task.status === 'failed' ? 'bg-red-500' : 'bg-zinc-500']"></span>
          </div>
        </div>
      </div>
    </aside>

    <main class="flex-1 flex flex-col overflow-hidden">
      <template v-if="showResult && selectedTaskData.length >= 2">
        <div class="h-14 px-6 border-b border-white/5 flex items-center justify-between shrink-0">
          <h2 class="text-sm font-medium text-white">对比结果 · {{ selectedTaskData.length }} 个任务</h2>
          <button @click="handleClear" class="px-3 py-1.5 text-xs text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg transition-colors">清空</button>
        </div>
        <div class="flex-1 overflow-auto p-6">
          <div class="max-w-4xl mx-auto space-y-6">
            <!-- 进度对比 -->
            <div class="bg-zinc-900/50 border border-white/5 rounded-xl p-6">
              <h3 class="text-sm font-medium text-white mb-4">📊 进度对比</h3>
              <div class="space-y-3">
                <div v-for="task in selectedTaskData" :key="task.id">
                  <div class="flex items-center justify-between mb-1">
                    <span class="text-xs text-zinc-400">{{ task.name }}</span>
                    <span class="text-xs font-mono" :class="statusColors[task.status] || 'text-zinc-400'">{{ task.progress?.overall || 0 }}%</span>
                  </div>
                  <div class="h-2 bg-zinc-800 rounded-full overflow-hidden">
                    <div :class="['h-full rounded-full transition-all duration-500', task.status === 'completed' ? 'bg-green-500' : 'bg-gradient-to-r from-blue-500 to-purple-500']" :style="{ width: `${task.progress?.overall || 0}%` }"></div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 详细对比表 -->
            <div class="bg-zinc-900/50 border border-white/5 rounded-xl p-6">
              <h3 class="text-sm font-medium text-white mb-4">📋 详细对比</h3>
              <div class="overflow-x-auto">
                <table class="w-full text-xs">
                  <thead><tr class="border-b border-white/5">
                    <th class="text-left py-2 pr-4 text-zinc-500 font-normal">指标</th>
                    <th v-for="task in selectedTaskData" :key="task.id" class="text-left py-2 px-4 text-zinc-400 font-medium">{{ task.name }}</th>
                  </tr></thead>
                  <tbody class="divide-y divide-white/5">
                    <tr><td class="py-2 pr-4 text-zinc-500">状态</td><td v-for="task in selectedTaskData" :key="task.id" :class="['py-2 px-4', statusColors[task.status]]">{{ task.status }}</td></tr>
                    <tr><td class="py-2 pr-4 text-zinc-500">语言</td><td v-for="task in selectedTaskData" :key="task.id" class="py-2 px-4 text-zinc-300">{{ task.language }}</td></tr>
                    <tr><td class="py-2 pr-4 text-zinc-500">模板</td><td v-for="task in selectedTaskData" :key="task.id" class="py-2 px-4 text-zinc-300">{{ task.template_id || '-' }}</td></tr>
                    <tr><td class="py-2 pr-4 text-zinc-500">创建时间</td><td v-for="task in selectedTaskData" :key="task.id" class="py-2 px-4 text-zinc-300">{{ task.created_at?.slice(0, 16) }}</td></tr>
                    <tr><td class="py-2 pr-4 text-zinc-500">完成时间</td><td v-for="task in selectedTaskData" :key="task.id" class="py-2 px-4 text-zinc-300">{{ task.completed_at?.slice(0, 16) || '-' }}</td></tr>
                  </tbody>
                </table>
              </div>
            </div>

            <!-- 论文预览 -->
            <div class="bg-zinc-900/50 border border-white/5 rounded-xl p-6">
              <h3 class="text-sm font-medium text-white mb-4">📄 论文对比</h3>
              <div class="grid gap-4" :class="selectedTaskData.length === 2 ? 'grid-cols-2' : 'grid-cols-1'">
                <div v-for="task in selectedTaskData" :key="task.id" class="p-4 bg-zinc-800/50 rounded-lg">
                  <h4 class="text-sm font-medium text-white mb-2 truncate">{{ task.name }}</h4>
                  <div class="max-h-64 overflow-auto text-xs text-zinc-400 whitespace-pre-wrap leading-relaxed">{{ task.paper_content || '暂无论文内容' }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>

      <div v-else class="flex-1 flex items-center justify-center">
        <div class="text-center">
          <div class="text-5xl mb-6 opacity-30">📊</div>
          <h3 class="text-lg font-medium text-white mb-2">选择任务进行对比</h3>
          <p class="text-sm text-zinc-500 mb-4">从左侧选择 2 个以上任务，点击"开始对比"</p>
          <p class="text-[10px] text-zinc-600">支持对比进度、状态、论文内容等</p>
        </div>
      </div>
    </main>
  </div>
</template>
