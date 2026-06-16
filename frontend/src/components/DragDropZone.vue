<script setup lang="ts">
/**
 * DragDropZone — 拖拽上传组件
 * 支持拖拽 + 点击上传、文件类型识别、大小校验、多文件管理
 */
import { ref, computed, watch } from 'vue'

// ── Props ──────────────────────────────────────────

const props = withDefaults(defineProps<{
  /** v-model 绑定的文件列表 */
  modelValue?: File[]
  /** 允许的文件扩展名，逗号分隔 */
  accept?: string
  /** 单文件最大大小（字节），默认 20MB */
  maxSize?: number
  /** 是否禁用 */
  disabled?: boolean
}>(), {
  modelValue: () => [],
  accept: '.pdf,.doc,.docx,.txt,.csv,.xlsx',
  maxSize: 20 * 1024 * 1024, // 20MB
  disabled: false,
})

// ── Emits ──────────────────────────────────────────

const emit = defineEmits<{
  'update:modelValue': [files: File[]]
  'error': [message: string]
}>()

// ── 状态 ───────────────────────────────────────────

const isDragOver = ref(false)
const errorMessage = ref<string | null>(null)

// ── 计算属性 ───────────────────────────────────────

const acceptExtensions = computed(() => props.accept.split(',').map(s => s.trim().toLowerCase()))

const acceptLabels: Record<string, string> = {
  '.pdf': 'PDF',
  '.doc': 'DOC',
  '.docx': 'DOCX',
  '.txt': 'TXT',
  '.csv': 'CSV',
  '.xlsx': 'XLSX',
  '.xls': 'XLS',
}

// ── 文件类型图标 ───────────────────────────────────

function getFileIcon(file: File): string {
  const ext = '.' + file.name.split('.').pop()?.toLowerCase()
  switch (ext) {
    case '.pdf': return '📄'
    case '.doc':
    case '.docx': return '📝'
    case '.xlsx':
    case '.xls':
    case '.csv': return '📊'
    case '.txt': return '📃'
    default: return '📎'
  }
}

function getFileTypeLabel(file: File): string {
  const ext = '.' + file.name.split('.').pop()?.toLowerCase()
  return acceptLabels[ext] || ext.toUpperCase()
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

// ── 文件校验 ───────────────────────────────────────

function validateFiles(newFiles: File[]): File[] {
  const valid: File[] = []
  for (const file of newFiles) {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase()
    if (!acceptExtensions.value.includes(ext)) {
      emit('error', `不支持的文件类型: ${file.name}`)
      continue
    }
    if (file.size > props.maxSize) {
      emit('error', `文件过大: ${file.name} (${formatFileSize(file.size)}，限制 ${formatFileSize(props.maxSize)})`)
      continue
    }
    if (file.size === 0) {
      emit('error', `空文件: ${file.name}`)
      continue
    }
    valid.push(file)
  }
  return valid
}

// ── 事件处理 ───────────────────────────────────────

function onDragEnter(e: DragEvent) {
  if (props.disabled) return
  e.preventDefault()
  isDragOver.value = true
}

function onDragLeave(e: DragEvent) {
  e.preventDefault()
  isDragOver.value = false
}

function onDragOver(e: DragEvent) {
  if (props.disabled) return
  e.preventDefault()
  if (e.dataTransfer) {
    e.dataTransfer.dropEffect = 'copy'
  }
}

function onDrop(e: DragEvent) {
  if (props.disabled) return
  e.preventDefault()
  isDragOver.value = false
  errorMessage.value = null

  const droppedFiles = e.dataTransfer?.files
  if (!droppedFiles || droppedFiles.length === 0) return

  const valid = validateFiles(Array.from(droppedFiles))
  if (valid.length > 0) {
    const merged = [...props.modelValue, ...valid]
    emit('update:modelValue', merged)
  }
}

function onClickBrowse() {
  if (props.disabled) return
  // 创建隐藏的 input 并触发点击
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = props.accept
  input.multiple = true
  input.onchange = () => {
    if (input.files && input.files.length > 0) {
      const valid = validateFiles(Array.from(input.files))
      if (valid.length > 0) {
        const merged = [...props.modelValue, ...valid]
        emit('update:modelValue', merged)
      }
    }
  }
  input.click()
}

function removeFile(index: number) {
  const updated = [...props.modelValue]
  updated.splice(index, 1)
  emit('update:modelValue', updated)
}

// 监听模型值变化，清除错误
watch(() => props.modelValue, () => {
  errorMessage.value = null
})
</script>

<template>
  <div class="drag-drop-zone">
    <!-- 拖拽区域 -->
    <div
      :class="[
        'relative border-2 border-dashed rounded-xl p-8 text-center transition-all duration-200 cursor-pointer select-none',
        isDragOver
          ? 'border-blue-400/60 bg-blue-500/10 scale-[1.01]'
          : 'border-white/10 hover:border-white/20 bg-zinc-900/30',
        disabled ? 'opacity-50 cursor-not-allowed' : ''
      ]"
      @dragenter="onDragEnter"
      @dragleave="onDragLeave"
      @dragover="onDragOver"
      @drop="onDrop"
      @click="onClickBrowse"
    >
      <!-- 拖拽图标 -->
      <div class="mx-auto w-14 h-14 rounded-2xl bg-white/5 border border-white/5 flex items-center justify-center mb-4 transition-transform duration-200"
        :class="{ 'scale-110': isDragOver }">
        <svg class="w-7 h-7 text-zinc-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
            d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
        </svg>
      </div>

      <!-- 提示文字 -->
      <p class="text-sm font-medium text-zinc-300">
        <template v-if="isDragOver">释放文件以添加</template>
        <template v-else>拖拽赛题文件到此处，或<span class="text-blue-400">点击上传</span></template>
      </p>
      <p class="text-xs text-zinc-500 mt-2">
        支持 PDF / DOC / DOCX / TXT / CSV / XLSX（单文件最大 {{ formatFileSize(maxSize) }}）
      </p>
    </div>

    <!-- 已上传文件列表 -->
    <div v-if="modelValue.length > 0" class="mt-4 space-y-2">
      <p class="text-xs text-zinc-500 mb-2">已选择 {{ modelValue.length }} 个文件</p>
      <div
        v-for="(file, index) in modelValue"
        :key="file.name + file.size + index"
        class="flex items-center gap-3 px-4 py-3 bg-zinc-900/60 border border-white/5 rounded-lg group hover:border-white/10 transition-all"
      >
        <!-- 文件图标 -->
        <span class="text-xl flex-shrink-0">{{ getFileIcon(file) }}</span>

        <!-- 文件信息 -->
        <div class="flex-1 min-w-0">
          <p class="text-sm text-zinc-200 truncate" :title="file.name">{{ file.name }}</p>
          <p class="text-[11px] text-zinc-500 mt-0.5">
            {{ getFileTypeLabel(file) }} · {{ formatFileSize(file.size) }}
          </p>
        </div>

        <!-- 删除按钮 -->
        <button
          @click.stop="removeFile(index)"
          class="w-7 h-7 rounded-md flex items-center justify-center text-zinc-500 hover:text-red-400 hover:bg-red-500/10 transition-colors opacity-0 group-hover:opacity-100 flex-shrink-0"
          title="移除文件"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>
