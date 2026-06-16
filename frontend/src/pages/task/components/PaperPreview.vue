<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useTaskStore } from '@/stores/taskStore'
import { useNotify } from '@/composables/useNotify'
import { renderMarkdown as renderMd } from '@/utils/markdown'
import service from '@/utils/request'

const props = defineProps<{
  taskId: string
}>()

const taskStore = useTaskStore()
const notify = useNotify()
const viewMode = ref<'preview' | 'edit'>('preview')
const isEditing = ref(false)
const editedContent = ref('')
const renderedHtml = ref('')

const task = computed(() => taskStore.getTaskById(props.taskId))

// Markdown 渲染
const renderMarkdown = async (content: string) => {
  if (!content) { renderedHtml.value = ''; return }
  try {
    renderedHtml.value = await renderMd(content, props.taskId)
  } catch {
    renderedHtml.value = content
  }
}

watch(() => task.value?.paper_content, (content) => {
  if (content && viewMode.value === 'preview') renderMarkdown(content)
}, { immediate: true })

onMounted(async () => {
  await taskStore.fetchPaperPreview(props.taskId)
})

const handleEdit = () => {
  editedContent.value = task.value?.paper_content || ''
  isEditing.value = true
  viewMode.value = 'edit'
}

const handleSave = async () => {
  try {
    await taskStore.updatePaperContent(props.taskId, editedContent.value)
    isEditing.value = false
    viewMode.value = 'preview'
    notify.success('已保存')
  } catch {
    notify.error('保存失败')
  }
}

const handleCancel = () => {
  isEditing.value = false
  viewMode.value = 'preview'
}

// PDF 编译（iframe + KaTeX，按 CUMCM 模板规范排版）
const compiling = ref(false)
const handleCompilePdf = async () => {
  compiling.value = true
  try {
    await printPdf()
  } finally {
    compiling.value = false
  }
}

// Word 导出
const handleExportDocx = async () => {
  if (!task.value?.paper_content) {
    notify.error('论文尚未生成，无法导出')
    return
  }
  try {
    await taskStore.exportDocx(props.taskId, task.value?.name)
    notify.success('Word 导出成功', '文件已开始下载')
  } catch {
    notify.error('Word 导出失败', '请稍后重试')
  }
}

// 浏览器打印 PDF（从后端获取模板样式，与 Word 导出共享同一套配置）
const printPdf = async () => {
  const content = task.value?.paper_content || ''
  const title = task.value?.name || '数学建模论文'
  if (!content) { notify.error('论文内容为空'); return }

  notify.info('正在渲染论文...')
  let bodyHtml: string, templateCss: string
  try {
    bodyHtml = await renderMd(content)
  } catch {
    notify.error('论文渲染失败')
    return
  }

  // 从后端获取统一样式（与 Word 导出共享配置）
  try {
    const res = await service.get('/api/v1/template/styles', { params: { template_id: 'cumcm' } })
    templateCss = res.data.css
  } catch {
    // 兜底：使用内联默认样式
    templateCss = `@page{size:A4;margin:2.5cm}body{font-family:'Times New Roman','SimSun',serif;font-size:12pt;line-height:1.8;margin:0;padding:0}p{text-indent:2em;margin:.35em 0;text-align:justify}h1{text-align:center;font-size:17pt;font-weight:bold;text-indent:0}h2{font-size:14pt;font-weight:bold;text-indent:0;page-break-before:always}h3{font-size:12pt;font-weight:bold;text-indent:0}table{border-collapse:collapse;width:100%;margin:.6em 0;font-size:10.5pt;page-break-inside:avoid}th,td{padding:.45em;text-align:center}th{font-weight:bold}pre{background:#f2f2f2;border:.8pt solid #b3b3b3;padding:.7em;font-size:10pt;overflow-x:auto;white-space:pre-wrap;font-family:'Courier New',monospace;text-indent:0}code{font-family:'Courier New',monospace;font-size:10pt}img{max-width:100%}.katex{font-size:1.05em}.katex-display{margin:.7em 0;text-align:center}@media print{body{padding:0}h2{page-break-before:always}h3,table,pre{page-break-inside:avoid}}`
  }

  // 移除旧 iframe
  const oldFrame = document.getElementById('print-frame')
  if (oldFrame) oldFrame.remove()

  const iframe = document.createElement('iframe')
  iframe.id = 'print-frame'
  iframe.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;border:none;z-index:9999;background:#fff'
  document.body.appendChild(iframe)

  const doc = iframe.contentDocument || iframe.contentWindow!.document
  doc.open()
  doc.write(`<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>${title.replace(/</g, '&lt;')}</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
<style>${templateCss}</style>
</head>
<body>${bodyHtml}</body>
</html>`)
  doc.close()

  const doPrint = () => {
    iframe.contentWindow!.focus()
    iframe.contentWindow!.print()
    setTimeout(() => {
      if (iframe.parentNode) iframe.parentNode.removeChild(iframe)
    }, 1000)
  }

  const linkEl = doc.querySelector('link')
  if (linkEl) {
    linkEl.addEventListener('load', () => setTimeout(doPrint, 300))
  }
  setTimeout(() => {
    if (document.getElementById('print-frame')) doPrint()
  }, 5000)
}
</script>

<template>
  <div class="h-full flex flex-col">
    <!-- 工具栏 -->
    <div class="px-4 py-2 border-b border-white/5 flex items-center justify-between shrink-0">
      <div class="flex items-center gap-1">
        <button @click="viewMode = 'preview'; isEditing = false"
          :class="['px-3 py-1.5 text-xs rounded-lg transition-colors', viewMode === 'preview' ? 'bg-white/10 text-white' : 'text-zinc-500 hover:text-zinc-300']">
          📖 预览
        </button>
        <button @click="handleEdit"
          :class="['px-3 py-1.5 text-xs rounded-lg transition-colors', viewMode === 'edit' ? 'bg-white/10 text-white' : 'text-zinc-500 hover:text-zinc-300']">
          ✏️ 编辑
        </button>
        <button @click="handleCompilePdf" :disabled="compiling"
          :class="['px-3 py-1.5 text-xs rounded-lg transition-colors flex items-center gap-1', compiling ? 'text-zinc-500 cursor-wait' : 'text-zinc-500 hover:text-zinc-300']">
          <span v-if="compiling" class="w-3 h-3 border border-zinc-500 border-t-transparent rounded-full animate-spin"></span>
          📄 编译 PDF
        </button>
        <button @click="handleExportDocx" :disabled="!task?.paper_content"
          :class="['px-3 py-1.5 text-xs rounded-lg transition-colors flex items-center gap-1', task?.paper_content ? 'text-zinc-500 hover:text-zinc-300' : 'text-zinc-600 cursor-not-allowed']">
          📝 导出 Word
        </button>
      </div>
      
      <div v-if="isEditing" class="flex items-center gap-2">
        <button @click="handleSave" class="px-3 py-1.5 text-xs bg-white text-black rounded-lg hover:bg-zinc-200 transition-colors">保存</button>
        <button @click="handleCancel" class="px-3 py-1.5 text-xs text-zinc-400 hover:text-white rounded-lg transition-colors">取消</button>
      </div>
    </div>

    <!-- 内容 -->
    <div class="flex-1 overflow-hidden">
      <!-- 预览模式 -->
      <div v-if="viewMode === 'preview'" class="h-full overflow-y-auto">
        <!-- PDF 嵌入 -->
        <iframe v-if="task?.paper_path" :src="`/api/v1/preview/${taskId}/paper`" class="w-full h-full border-0 bg-white"></iframe>
        
        <!-- Markdown 渲染 -->
        <div v-else-if="renderedHtml" class="p-8 max-w-3xl mx-auto prose prose-invert prose-sm prose-headings:text-white prose-p:text-zinc-300 prose-strong:text-white prose-code:text-blue-300 prose-pre:bg-zinc-900 prose-pre:border prose-pre:border-white/10" v-html="renderedHtml"></div>
        
        <!-- 空状态 -->
        <div v-else class="h-full flex flex-col items-center justify-center">
          <div class="text-5xl mb-4 opacity-30">📄</div>
          <p class="text-sm text-zinc-500 mb-1">论文尚未生成</p>
          <p class="text-[10px] text-zinc-600">任务运行后，论文内容将在此显示</p>
        </div>
      </div>

      <!-- 编辑模式 -->
      <div v-else class="h-full p-4">
        <textarea v-model="editedContent"
          class="w-full h-full p-4 bg-zinc-900 border border-white/10 rounded-lg text-sm text-zinc-300 font-mono resize-none focus:outline-none focus:ring-1 focus:ring-blue-500/30"
          placeholder="输入 Markdown 内容..."></textarea>
      </div>
    </div>
  </div>
</template>
