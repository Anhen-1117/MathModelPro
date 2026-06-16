<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useTaskStore } from '@/stores/taskStore'
import { useNotify } from '@/composables/useNotify'

const props = defineProps<{
  taskId: string
}>()

const taskStore = useTaskStore()
const notify = useNotify()
const selectedFigure = ref<string | null>(null)
const fullscreenFigure = ref<string | null>(null)

const task = computed(() => taskStore.getTaskById(props.taskId))
const figures = computed(() => task.value?.figures || [])

onMounted(async () => {
  await taskStore.fetchFigures(props.taskId)
})

const handleExport = async (figure: string, format: string) => {
  try {
    await taskStore.exportFigure(props.taskId, figure, format)
    notify.success('导出成功')
  } catch {
    notify.error('导出失败')
  }
}

const handleExportAll = async () => {
  try {
    await taskStore.exportAllFigures(props.taskId)
    notify.success('导出成功')
  } catch {
    notify.error('导出失败')
  }
}
</script>

<template>
  <div class="h-full flex">
    <div class="flex-1 overflow-auto p-4">
      <!-- 空状态 -->
      <div v-if="figures.length === 0" class="h-full flex flex-col items-center justify-center">
        <div class="text-5xl mb-4 opacity-30">📊</div>
        <p class="text-sm text-zinc-500 mb-1">暂无图表</p>
        <p class="text-[10px] text-zinc-600">代码运行后生成的图表将在此显示</p>
      </div>
      
      <!-- 图表网格 -->
      <div v-else>
        <div class="flex items-center justify-between mb-4">
          <span class="text-xs text-zinc-500">{{ figures.length }} 张图表</span>
          <button @click="handleExportAll" class="px-3 py-1.5 text-xs text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg transition-colors">↓ 全部导出</button>
        </div>
        <div class="grid grid-cols-2 lg:grid-cols-3 gap-4">
          <div v-for="figure in figures" :key="figure"
            @click="selectedFigure = figure"
            :class="['relative group cursor-pointer rounded-lg overflow-hidden border transition-all', selectedFigure === figure ? 'border-blue-500/30 ring-1 ring-blue-500/20' : 'border-white/5 hover:border-white/10']">
            <div class="aspect-video bg-zinc-900 flex items-center justify-center p-2">
              <img :src="`/api/v1/preview/${taskId}/figures/${figure}`" :alt="figure" class="max-w-full max-h-full object-contain" loading="lazy" />
            </div>
            
            <div class="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
              <button @click.stop="fullscreenFigure = figure" class="px-3 py-1.5 bg-white/10 hover:bg-white/20 text-white text-xs rounded-lg transition-colors">🔍 放大</button>
              <button @click.stop="handleExport(figure, 'png')" class="px-3 py-1.5 bg-white/10 hover:bg-white/20 text-white text-xs rounded-lg transition-colors">PNG</button>
            </div>
            
            <div class="absolute bottom-0 left-0 right-0 px-3 py-2 bg-gradient-to-t from-black/80 to-transparent">
              <p class="text-white text-xs truncate">{{ figure }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 侧边详情 -->
    <div v-if="selectedFigure" class="w-80 border-l border-white/5 bg-zinc-900/50 p-4 flex flex-col">
      <h3 class="text-sm font-medium text-white mb-4">图表详情</h3>
      <div class="flex-1 flex items-center justify-center bg-zinc-800/50 rounded-lg overflow-hidden mb-4 cursor-pointer" @click="fullscreenFigure = selectedFigure">
        <img :src="`/api/v1/preview/${taskId}/figures/${selectedFigure}`" :alt="selectedFigure" class="max-w-full max-h-full object-contain" />
      </div>
      <div class="space-y-3">
        <div>
          <label class="text-xs text-zinc-500">文件名</label>
          <p class="text-sm text-zinc-300">{{ selectedFigure }}</p>
        </div>
        <div class="flex gap-2">
          <button @click="handleExport(selectedFigure, 'png')" class="flex-1 px-3 py-2 text-xs bg-white text-black rounded-lg hover:bg-zinc-200 transition-colors">PNG</button>
          <button @click="handleExport(selectedFigure, 'svg')" class="flex-1 px-3 py-2 text-xs bg-zinc-800 text-white rounded-lg hover:bg-zinc-700 transition-colors">SVG</button>
        </div>
      </div>
    </div>

    <!-- 全屏查看 -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="fullscreenFigure" class="fixed inset-0 z-[90] flex items-center justify-center bg-black/90 backdrop-blur-sm" @click="fullscreenFigure = null">
          <div class="relative max-w-[90vw] max-h-[90vh] p-4">
            <img :src="`/api/v1/preview/${taskId}/figures/${fullscreenFigure}`" :alt="fullscreenFigure" class="max-w-full max-h-[85vh] object-contain rounded-lg" />
            <div class="absolute top-2 right-2 flex gap-2">
              <button @click.stop="handleExport(fullscreenFigure, 'png')" class="px-3 py-1.5 bg-white/10 hover:bg-white/20 text-white text-xs rounded-lg backdrop-blur-sm">↓ PNG</button>
              <button @click.stop="fullscreenFigure = null" class="px-3 py-1.5 bg-white/10 hover:bg-white/20 text-white text-xs rounded-lg backdrop-blur-sm">✕ 关闭</button>
            </div>
            <p class="text-center text-sm text-zinc-400 mt-2">{{ fullscreenFigure }}</p>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>
