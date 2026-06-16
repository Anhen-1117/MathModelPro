<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useTaskStore } from '@/stores/taskStore'
import TaskList from './components/TaskList.vue'
import TaskDetail from './components/TaskDetail.vue'
import CreateTaskDialog from './components/CreateTaskDialog.vue'

const router = useRouter()
const taskStore = useTaskStore()
const showCreateDialog = ref(false)
const selectedTaskId = ref<string | null>(null)

onMounted(async () => {
  await taskStore.fetchTasks()
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})

const handleKeydown = (e: KeyboardEvent) => {
  // Ctrl+N: 新建任务
  if (e.ctrlKey && e.key === 'n') {
    e.preventDefault()
    showCreateDialog.value = true
  }
}

const handleSelectTask = (taskId: string) => {
  selectedTaskId.value = taskId
}

const handleTaskCreated = (taskId: string) => {
  showCreateDialog.value = false
  selectedTaskId.value = taskId
  taskStore.fetchTasks()
}
</script>

<template>
  <div class="h-screen flex bg-[#0a0a0b] text-white">
    <!-- 左侧边栏 -->
    <aside class="w-72 border-r border-white/5 flex flex-col">
      <div class="h-14 px-4 border-b border-white/5 flex items-center justify-between shrink-0">
        <button @click="router.push('/')" class="flex items-center gap-2 text-zinc-400 hover:text-white transition-colors">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
          <span class="text-sm">返回</span>
        </button>
        <button @click="showCreateDialog = true"
          class="px-3 py-1.5 bg-white text-black text-sm font-medium rounded-lg hover:bg-zinc-200 transition-colors flex items-center gap-1">
          <span>+</span> 新建
        </button>
      </div>

      <TaskList :selected-task-id="selectedTaskId" @select="handleSelectTask" />
    </aside>

    <!-- 主内容区 -->
    <main class="flex-1 flex flex-col overflow-hidden">
      <TaskDetail v-if="selectedTaskId" :task-id="selectedTaskId" />
      
      <!-- 空状态 -->
      <div v-else class="flex-1 flex items-center justify-center">
        <div class="text-center">
          <div class="w-16 h-16 mx-auto mb-6 rounded-2xl bg-zinc-900 border border-white/5 flex items-center justify-center">
            <span class="text-3xl">📝</span>
          </div>
          <h3 class="text-lg font-medium text-white mb-2">选择或创建任务</h3>
          <p class="text-sm text-zinc-500 mb-6">从左侧选择任务，或点击"新建"开始</p>
          <button @click="showCreateDialog = true" class="px-4 py-2 bg-white text-black text-sm font-medium rounded-lg hover:bg-zinc-200 transition-colors">
            新建任务
          </button>
          <p class="text-[10px] text-zinc-600 mt-4">快捷键 <kbd class="px-1 py-0.5 bg-zinc-800 border border-white/10 rounded text-zinc-400">Ctrl+N</kbd></p>
        </div>
      </div>
    </main>

    <CreateTaskDialog v-model:open="showCreateDialog" @created="handleTaskCreated" />
  </div>
</template>
