<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useTaskStore } from '@/stores/taskStore'
import { useNotify } from '@/composables/useNotify'
import { useApiKeyStore } from '@/stores/apiKeys'
import { checkApiConfig } from '@/utils/api-check'
import service from '@/utils/request'
import DragDropZone from '@/components/DragDropZone.vue'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{
  'update:open': [value: boolean]
  created: [taskId: string]
}>()

const router = useRouter()
const taskStore = useTaskStore()
const notify = useNotify()
const apiKeyStore = useApiKeyStore()
const isCreating = ref(false)
const apiConfigured = ref<boolean | null>(null)
const isExtracting = ref(false)

const form = ref({
  name: '',
  description: '',
  problem_text: '',
  language: 'python',
  template_id: 'cumcm',
  notes: ''
})

/** 拖拽上传的文件列表 */
const uploadedFiles = ref<File[]>([])

/** 文本提取结果信息 */
const extractResult = ref<{
  source: string       // 提取来源文件名
  charCount: number    // 提取字符数
  error?: string       // 提取错误（如有）
} | null>(null)

// ── Typst 模板 ─────────────────────────────────────

const templates = ref<any[]>([])
const loadingTemplates = ref(false)

const costEstimate = ref<any>(null)
const loadingCost = ref(false)

const languages = [
  { id: 'python', label: 'Python', icon: '🐍' },
  // MATLAB 已移除，统一使用 Python (matplotlib/seaborn)
]

const exampleProblems = [
  { name: '2024 国赛 A 题', text: '某城市有 n 个社区，需要建设若干个应急物资配送中心。请建立数学模型，确定配送中心的位置和数量，使得所有社区都能在规定时间内获得物资供应，同时总建设成本最低。' },
  { name: '2024 国赛 B 题', text: '某地区有多种农作物可种植，每种作物的产量、售价、种植成本各不相同。请建立数学模型，制定最优种植方案，使得总利润最大，同时满足轮作约束和市场需求。' },
  { name: '美赛 MCM 示例', text: 'Develop a mathematical model to optimize the placement of charging stations for electric vehicles in a metropolitan area, considering traffic patterns, population density, and grid capacity.' }
]

// ── 判断是否有文档文件（可提取文本的） ──────────────

const TEXT_EXTRACT_EXTENSIONS = ['.pdf', '.doc', '.docx']

const hasDocumentFiles = computed(() =>
  uploadedFiles.value.some(f => {
    const ext = '.' + f.name.split('.').pop()?.toLowerCase()
    return TEXT_EXTRACT_EXTENSIONS.includes(ext)
  })
)

// ── 自动提取文档文本 ───────────────────────────────

watch(() => uploadedFiles.value.length, async () => {
  if (!hasDocumentFiles.value) return

  // 只提取文档文件
  const docFiles = uploadedFiles.value.filter(f => {
    const ext = '.' + f.name.split('.').pop()?.toLowerCase()
    return TEXT_EXTRACT_EXTENSIONS.includes(ext)
  })

  if (docFiles.length === 0) return

  isExtracting.value = true
  extractResult.value = null

  try {
    const formData = new FormData()
    for (const file of docFiles) {
      formData.append('files', file)
    }

    const res = await service.post<{
      combined_text: string
      results: Array<{ filename: string; char_count: number; error?: string }>
    }>('/api/v1/extract-text', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 60000,
    })

    if (res.data?.combined_text) {
      // 如果用户未手动输入题目文本，则自动填充
      if (!form.value.problem_text.trim()) {
        form.value.problem_text = res.data.combined_text
        // 自动生成任务名称
        if (!form.value.name.trim() && res.data.results?.[0]) {
          form.value.name = res.data.results[0].filename.replace(/\.[^.]+$/, '')
        }
      }

      const firstResult = res.data.results?.[0]
      extractResult.value = {
        source: firstResult?.filename || '文档',
        charCount: firstResult?.char_count || res.data.combined_text.length,
        error: firstResult?.error,
      }
    } else if (res.data?.results?.[0]?.error) {
      extractResult.value = {
        source: res.data.results[0].filename,
        charCount: 0,
        error: res.data.results[0].error,
      }
    }
  } catch (e: any) {
    console.error('文档文本提取失败:', e)
    extractResult.value = {
      source: docFiles.map(f => f.name).join(', '),
      charCount: 0,
      error: '提取失败，请手动粘贴题目或检查文件是否损坏',
    }
  } finally {
    isExtracting.value = false
  }
})

// ── 生命周期 ───────────────────────────────────────

const loadTemplates = async () => {
  loadingTemplates.value = true
  try {
    const res = await service.get('/api/v1/typst/templates')
    templates.value = res.data.templates || []
  } catch {
    templates.value = [
      { id: 'cumcm', name: '国赛 (CUMCM)', lang: 'zh', description: '全国大学生数学建模竞赛' },
      { id: 'mcm', name: 'MCM/ICM (美赛)', lang: 'en', description: '美国大学生数学建模竞赛' },
    ]
  } finally {
    loadingTemplates.value = false
  }
}

const estimateCost = async () => {
  loadingCost.value = true
  try {
    const res = await service.post('/api/v1/estimate/cost', { model: 'deepseek-chat' })
    costEstimate.value = res.data
  } catch {} finally {
    loadingCost.value = false
  }
}

watch(() => props.open, async (val) => {
  if (val) {
    const status = await checkApiConfig()
    apiConfigured.value = status.configured
    await Promise.all([loadTemplates(), estimateCost()])
  }
})

// ── 提交校验 ───────────────────────────────────────

const canSubmit = computed(() => {
  const hasText = form.value.problem_text.trim().length > 0
  const hasFiles = uploadedFiles.value.length > 0
  return form.value.name.trim() && (hasText || hasFiles)  // 有文件或有文本均可
})

// ── 操作 ───────────────────────────────────────────

const handleClose = () => {
  emit('update:open', false)
  form.value = { name: '', description: '', problem_text: '', language: 'python', template_id: 'cumcm', notes: '' }
  uploadedFiles.value = []
  extractResult.value = null
}

const fillExample = (example: typeof exampleProblems[0]) => {
  form.value.name = example.name
  form.value.problem_text = example.text
  uploadedFiles.value = []
  extractResult.value = null
}

const handleSubmit = async () => {
  if (!canSubmit.value) return
  if (!apiConfigured.value) {
    // 未配置有效 API Key → 阻止提交，引导用户去设置
    notify.warning(
      '未配置有效 API Key',
      '请先在「设置 → API Key」中配置有效的 API Key 后再提交任务。'
    )
    return
  }
  // 同步保存 API 配置到后端（确保 apiKeyStore → config.json）
  try {
    const { saveApiConfig } = await import('@/apis/apiKeyApi')
    await saveApiConfig({
      coordinator: apiKeyStore.coordinatorConfig,
      modeler: apiKeyStore.modelerConfig,
      coder: apiKeyStore.coderConfig,
      writer: apiKeyStore.writerConfig,
      openalex_email: apiKeyStore.openalexEmail,
    })
  } catch { /* 保存失败不阻塞提交流程 */ }

  isCreating.value = true
  try {
    const taskId = await taskStore.createTask(form.value, uploadedFiles.value)
    notify.success('任务已创建', form.value.name)
    emit('created', taskId)
    handleClose()
  } catch {
    notify.error('创建失败', '请检查后端连接')
  } finally {
    isCreating.value = false
  }
}

const zhTemplates = computed(() => templates.value.filter(t => t.lang === 'zh'))
const enTemplates = computed(() => templates.value.filter(t => t.lang === 'en'))
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center">
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="handleClose"></div>

        <div class="relative w-full max-w-xl mx-4 bg-[#111111] border border-white/10 rounded-xl shadow-2xl overflow-hidden max-h-[90vh] flex flex-col">
          <!-- 标题 -->
          <div class="px-6 py-4 border-b border-white/5 flex items-center justify-between shrink-0">
            <div>
              <h2 class="text-sm font-medium text-white">新建建模任务</h2>
              <p class="text-[10px] text-zinc-500 mt-0.5">拖拽上传赛题 PDF/Word，或粘贴题目文本</p>
            </div>
            <button @click="handleClose" class="w-6 h-6 rounded-md hover:bg-white/10 flex items-center justify-center text-zinc-400 hover:text-white transition-colors">✕</button>
          </div>

          <!-- API 未配置提示 -->
          <div v-if="apiConfigured === false" class="mx-6 mt-4 p-3 rounded-lg border bg-red-950/20 border-red-500/20 flex items-center gap-3">
            <span class="text-lg">🔴</span>
            <div class="flex-1">
              <p class="text-xs text-red-300">未配置有效 API Key</p>
              <p class="text-[10px] text-zinc-500 mt-0.5">请先配置 API Key 后才能提交任务。可在「设置」中配置。</p>
            </div>
            <button @click="handleClose(); router.push('/settings')" class="px-3 py-1 text-xs bg-red-500/20 text-red-300 rounded-lg hover:bg-red-500/30 transition-colors shrink-0">去配置</button>
          </div>

          <!-- 表单 -->
          <div class="flex-1 overflow-y-auto p-6 space-y-4">
            <!-- 拖拽上传区域 -->
            <div>
              <label class="block text-xs text-zinc-400 mb-1.5">📎 上传赛题文件</label>
              <DragDropZone v-model="uploadedFiles" @error="(msg) => notify.warning('文件问题', msg)" />

              <!-- 提取状态 -->
              <div v-if="isExtracting" class="mt-2 flex items-center gap-2 text-xs text-blue-400">
                <svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                </svg>
                正在从文档中提取题目文本...
              </div>

              <!-- 提取结果提示 -->
              <div v-else-if="extractResult && !extractResult.error"
                class="mt-2 flex items-center gap-2 text-xs text-green-400">
                <span>✅</span>
                已从「{{ extractResult.source }}」提取 {{ extractResult.charCount }} 字，已自动填入下方文本框
              </div>

              <div v-else-if="extractResult?.error"
                class="mt-2 flex items-center gap-2 text-xs text-amber-400">
                <span>⚠️</span>
                {{ extractResult.error }}
              </div>
            </div>

            <!-- 任务名称 -->
            <div>
              <label class="block text-xs text-zinc-400 mb-1.5">任务名称 *</label>
              <input v-model="form.name" type="text" placeholder="例如：2024 国赛 A 题"
                class="w-full px-3 py-2 bg-zinc-900 border border-white/10 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-blue-500/30 focus:border-blue-500/30 transition-all" />
            </div>

            <!-- 题目内容 -->
            <div>
              <div class="flex items-center justify-between mb-1.5">
                <label class="text-xs text-zinc-400">题目内容 *</label>
                <div class="flex gap-1">
                  <button v-for="(ex, i) in exampleProblems" :key="i" @click="fillExample(ex)"
                    class="px-2 py-0.5 text-[10px] bg-zinc-800 hover:bg-zinc-700 border border-white/5 rounded text-zinc-400 hover:text-white transition-colors">
                    示例{{ i + 1 }}
                  </button>
                </div>
              </div>
              <textarea v-model="form.problem_text" rows="4" placeholder="拖拽 PDF/Word 自动提取，或在此手动粘贴题目内容..."
                class="w-full px-3 py-2 bg-zinc-900 border border-white/10 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-blue-500/30 focus:border-blue-500/30 resize-y transition-all"></textarea>
              <p class="text-[10px] text-zinc-600 mt-1">{{ form.problem_text.length }} 字</p>
            </div>

            <!-- 特殊要求 -->
            <div>
              <label class="block text-xs text-zinc-400 mb-1.5">📝 特殊要求（可选）</label>
              <textarea v-model="form.notes" rows="2"
                placeholder="如：必须使用层次分析法、程序需输出中间结果、论文需包含灵敏度分析..."
                class="w-full px-3 py-2 bg-zinc-900 border border-white/10 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-blue-500/30 focus:border-blue-500/30 resize-y transition-all"></textarea>
            </div>

            <!-- 代码语言 -->
            <div>
              <label class="block text-xs text-zinc-400 mb-1.5">代码语言</label>
              <div class="flex gap-2">
                <label v-for="lang in languages" :key="lang.id"
                  :class="['flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg border cursor-pointer transition-all text-sm', form.language === lang.id ? 'border-blue-500/30 bg-blue-500/10 text-white' : 'border-white/5 text-zinc-400 hover:border-white/10']">
                  <input v-model="form.language" type="radio" :value="lang.id" class="sr-only" />
                  <span>{{ lang.icon }}</span>
                  {{ lang.label }}
                </label>
              </div>
            </div>

            <!-- Typst 模板选择器 -->
            <div>
              <label class="block text-xs text-zinc-400 mb-1.5">📄 论文模板（Typst）</label>
              <div v-if="loadingTemplates" class="text-xs text-zinc-500 py-2">加载模板中...</div>
              <div v-else>
                <p class="text-[10px] text-zinc-600 mb-1.5">中文赛事</p>
                <div class="grid grid-cols-3 gap-1.5 mb-3">
                  <button v-for="tpl in zhTemplates" :key="tpl.id" @click="form.template_id = tpl.id"
                    :class="['px-2 py-1.5 rounded-lg border text-left transition-all text-[11px]', form.template_id === tpl.id ? 'border-blue-500/30 bg-blue-500/10 text-white' : 'border-white/5 text-zinc-400 hover:border-white/10']">
                    {{ tpl.name }}
                  </button>
                </div>
                <p class="text-[10px] text-zinc-600 mb-1.5">英文赛事</p>
                <div class="grid grid-cols-3 gap-1.5">
                  <button v-for="tpl in enTemplates" :key="tpl.id" @click="form.template_id = tpl.id"
                    :class="['px-2 py-1.5 rounded-lg border text-left transition-all text-[11px]', form.template_id === tpl.id ? 'border-blue-500/30 bg-blue-500/10 text-white' : 'border-white/5 text-zinc-400 hover:border-white/10']">
                    {{ tpl.name }}
                  </button>
                </div>
              </div>
            </div>

            <!-- 费用预估 -->
            <div v-if="costEstimate" class="p-3 bg-zinc-900/50 border border-white/5 rounded-lg">
              <div class="flex items-center justify-between mb-2">
                <span class="text-xs text-zinc-400">💰 费用预估</span>
                <span class="text-xs text-zinc-500">{{ costEstimate.model }}</span>
              </div>
              <div class="flex items-center gap-4">
                <div>
                  <p class="text-lg font-bold text-white">¥{{ costEstimate.total_cost_cny }}</p>
                  <p class="text-[10px] text-zinc-500">${{ costEstimate.total_cost_usd }}</p>
                </div>
                <div class="flex-1 text-[10px] text-zinc-500">
                  <p>输入: {{ costEstimate.total_input_tokens?.toLocaleString() }} tokens</p>
                  <p>输出: {{ costEstimate.total_output_tokens?.toLocaleString() }} tokens</p>
                </div>
              </div>
            </div>
          </div>

          <!-- 底部按钮 -->
          <div class="px-6 py-4 border-t border-white/5 flex justify-between items-center shrink-0">
            <p class="text-[10px] text-zinc-600">创建后将自动开始 AI 建模</p>
            <div class="flex gap-3">
              <button @click="handleClose" class="px-4 py-2 text-sm text-zinc-400 hover:text-white transition-colors">取消</button>
              <button @click="handleSubmit" :disabled="isCreating || isExtracting || !canSubmit"
                :class="['px-5 py-2 text-sm font-medium rounded-lg transition-all flex items-center gap-2', isCreating || isExtracting || !canSubmit ? 'bg-zinc-800 text-zinc-500 cursor-not-allowed' : 'bg-white text-black hover:bg-zinc-200']">
                <svg v-if="isCreating" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>
                {{ isExtracting ? '提取文本中...' : isCreating ? '创建中...' : '开始建模' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
