<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import service from '@/utils/request'
import { useNotify } from '@/composables/useNotify'

const router = useRouter()
const notify = useNotify()
const activeTab = ref('models')

// ── 建模方法库 ──
const models = ref<any[]>([])
const selectedModel = ref<any>(null)
const categoryFilter = ref('all')
const searchQuery = ref('')
const categories = ['评价类', '预测类', '优化类', '模拟类']
const categoryIcons: Record<string, string> = { '评价类': '⚖️', '预测类': '📈', '优化类': '🎯', '模拟类': '🎲' }
const difficultyColors: Record<string, string> = { '初级': 'text-green-400 bg-green-900/30', '中级': 'text-yellow-400 bg-yellow-900/30', '高级': 'text-red-400 bg-red-900/30' }
const filteredModels = computed(() => {
  let list = models.value
  if (categoryFilter.value !== 'all') list = list.filter(m => m.category === categoryFilter.value)
  if (searchQuery.value) { const q = searchQuery.value.toLowerCase(); list = list.filter(m => m.name.toLowerCase().includes(q) || m.name_en.toLowerCase().includes(q)) }
  return list
})

// ── 决策树 ──
const decisionTree = ref<any>(null)
const treePath = ref<string[]>([])
const currentNode = ref<any>(null)
const recommendations = ref<any[]>([])

// ── 竞赛日历 ──
const competitions = ref<any[]>([])
const selectedComp = ref<any>(null)

// ── Web 搜索 ──
const searchInput = ref('')
const searchResults = ref<any>(null)
const searching = ref(false)

// ── 获奖论文 ──
const paperPatterns = ref<any[]>([])
const paperComp = ref('CUMCM')

// ── 易错点 ──
const mistakes = ref<string[]>([])
const mistakesComp = ref('CUMCM')

// ── 写作规范 ──
const guidelines = ref<any>(null)

onMounted(async () => {
  await Promise.all([loadModels(), loadCompetitions(), loadDecisionTree(), loadPatterns(), loadMistakes(), loadGuidelines()])
})

const loadModels = async () => { try { const r = await service.get('/api/v1/knowledge/models'); models.value = r.data.models } catch {} }
const loadModelDetail = async (id: string) => { try { const r = await service.get(`/api/v1/knowledge/models/${id}`); selectedModel.value = r.data } catch {} }
const loadCompetitions = async () => { try { const r = await service.get('/api/v1/competitions'); competitions.value = r.data.competitions } catch {} }
const loadCompDetail = async (id: string) => { try { const r = await service.get(`/api/v1/competitions/${id}`); selectedComp.value = r.data } catch {} }
const loadDecisionTree = async () => { try { const r = await service.get('/api/v1/knowledge/decision-tree'); decisionTree.value = r.data; currentNode.value = r.data.root } catch {} }
const loadPatterns = async () => { try { const r = await service.get('/api/v1/papers/patterns', { params: { competition: paperComp.value } }); paperPatterns.value = r.data.patterns } catch {} }
const loadMistakes = async () => { try { const r = await service.get('/api/v1/papers/mistakes', { params: { competition: mistakesComp.value } }); mistakes.value = r.data.mistakes } catch {} }
const loadGuidelines = async () => { try { const r = await service.get('/api/v1/papers/guidelines'); guidelines.value = r.data.guidelines } catch {} }

const selectOption = async (option: any) => {
  treePath.value.push(option.label)
  if (option.models) {
    try { const r = await service.post('/api/v1/knowledge/recommend', { keywords: option.models }); recommendations.value = r.data.recommendations; currentNode.value = null } catch {}
  } else if (option.next && decisionTree.value[option.next]) { currentNode.value = decisionTree.value[option.next] }
}
const resetTree = () => { treePath.value = []; recommendations.value = []; currentNode.value = decisionTree.value?.root || null }

const doSearch = async () => {
  if (!searchInput.value.trim()) return
  searching.value = true
  try { const r = await service.get('/api/v1/search', { params: { q: searchInput.value, max_results: 5 } }); searchResults.value = r.data } catch { notify.error('搜索失败') } finally { searching.value = false }
}
const getMonthLabel = (m: number) => `${m}月`
</script>

<template>
  <div class="h-screen flex bg-[#0a0a0b] text-white">
    <!-- 侧边栏 -->
    <aside class="w-64 border-r border-white/5 flex flex-col">
      <div class="h-14 px-4 border-b border-white/5 flex items-center">
        <button @click="router.push('/')" class="flex items-center gap-2 text-zinc-400 hover:text-white transition-colors">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
          <span class="text-sm">返回</span>
        </button>
      </div>
      <div class="flex-1 p-3 space-y-1 overflow-y-auto">
        <button v-for="tab in [
          { id: 'models', icon: '📚', label: '建模方法库' },
          { id: 'tree', icon: '🌳', label: '模型选择' },
          { id: 'calendar', icon: '📅', label: '竞赛日历' },
          { id: 'search', icon: '🔍', label: '搜索' },
          { id: 'papers', icon: '🏆', label: '获奖论文' },
          { id: 'mistakes', icon: '⚠️', label: '常见易错' },
          { id: 'guide', icon: '📖', label: '写作规范' },
        ]" :key="tab.id" @click="activeTab = tab.id"
          :class="['w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors', activeTab === tab.id ? 'bg-white/10 text-white' : 'text-zinc-400 hover:bg-white/5']">
          {{ tab.icon }} {{ tab.label }}
        </button>
      </div>
    </aside>

    <!-- 主内容 -->
    <main class="flex-1 overflow-y-auto">

      <!-- 建模方法库 -->
      <div v-if="activeTab === 'models'" class="p-8">
        <div class="max-w-5xl mx-auto">
          <div class="flex items-center justify-between mb-6">
            <div><h1 class="text-xl font-bold">建模方法库</h1><p class="text-xs text-zinc-500 mt-1">内置 {{ models.length }} 种常见建模方法</p></div>
            <input v-model="searchQuery" type="text" placeholder="搜索模型..." class="px-3 py-2 bg-zinc-900 border border-white/10 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-blue-500/30 w-60" />
          </div>
          <div class="flex gap-2 mb-6">
            <button @click="categoryFilter = 'all'" :class="['px-3 py-1.5 text-xs rounded-lg transition-colors', categoryFilter === 'all' ? 'bg-white/10 text-white' : 'text-zinc-500 hover:text-zinc-300']">全部</button>
            <button v-for="cat in categories" :key="cat" @click="categoryFilter = cat" :class="['px-3 py-1.5 text-xs rounded-lg transition-colors', categoryFilter === cat ? 'bg-white/10 text-white' : 'text-zinc-500 hover:text-zinc-300']">{{ categoryIcons[cat] }} {{ cat }}</button>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div v-for="model in filteredModels" :key="model.id" @click="loadModelDetail(model.id); activeTab = 'model-detail'" class="p-4 bg-zinc-900/50 border border-white/5 rounded-lg hover:border-white/10 cursor-pointer transition-all group">
              <div class="flex items-center justify-between mb-2">
                <span class="text-lg">{{ categoryIcons[model.category] || '📐' }}</span>
                <span :class="['text-[10px] px-2 py-0.5 rounded-full', difficultyColors[model.complexity]]">{{ model.complexity }}</span>
              </div>
              <h3 class="text-sm font-medium text-white mb-1 group-hover:text-blue-400 transition-colors">{{ model.name }}</h3>
              <p class="text-[10px] text-zinc-500 mb-2">{{ model.name_en }}</p>
              <p class="text-xs text-zinc-400 line-clamp-2">{{ model.description }}</p>
              <div class="flex flex-wrap gap-1 mt-2"><span v-for="s in model.scenarios?.slice(0,3)" :key="s" class="text-[9px] px-1.5 py-0.5 bg-zinc-800 text-zinc-500 rounded">{{ s }}</span></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 模型详情 -->
      <div v-if="activeTab === 'model-detail' && selectedModel" class="p-8">
        <div class="max-w-3xl mx-auto">
          <button @click="activeTab = 'models'" class="text-sm text-zinc-400 hover:text-white mb-4">← 返回列表</button>
          <div class="p-6 bg-zinc-900/50 border border-white/5 rounded-lg">
            <div class="flex items-center gap-3 mb-4">
              <span class="text-2xl">{{ categoryIcons[selectedModel.category] || '📐' }}</span>
              <div><h1 class="text-lg font-bold">{{ selectedModel.name }}</h1><p class="text-xs text-zinc-500">{{ selectedModel.name_en }}</p></div>
              <span :class="['text-[10px] px-2 py-0.5 rounded-full ml-auto', difficultyColors[selectedModel.complexity]]">{{ selectedModel.complexity }}</span>
            </div>
            <p class="text-sm text-zinc-300 mb-6">{{ selectedModel.description }}</p>
            <div class="grid grid-cols-2 gap-6 mb-4">
              <div><h3 class="text-xs text-zinc-500 mb-2">✅ 优点</h3><ul class="space-y-1"><li v-for="p in selectedModel.pros" :key="p" class="text-xs text-green-400">• {{ p }}</li></ul></div>
              <div><h3 class="text-xs text-zinc-500 mb-2">❌ 缺点</h3><ul class="space-y-1"><li v-for="c in selectedModel.cons" :key="c" class="text-xs text-red-400">• {{ c }}</li></ul></div>
            </div>
            <div class="mb-4"><h3 class="text-xs text-zinc-500 mb-2">🎯 适用场景</h3><div class="flex flex-wrap gap-1"><span v-for="s in selectedModel.applicable_scenarios" :key="s" class="text-xs px-2 py-1 bg-blue-900/30 text-blue-400 rounded">{{ s }}</span></div></div>
            <div v-if="selectedModel.example_code" class="mb-4"><h3 class="text-xs text-zinc-500 mb-2">💻 示例代码</h3><pre class="p-4 bg-zinc-800 rounded-lg text-xs text-zinc-300 overflow-x-auto font-mono">{{ selectedModel.example_code }}</pre></div>
            <div v-if="selectedModel.references?.length"><h3 class="text-xs text-zinc-500 mb-2">📖 参考文献</h3><ul class="space-y-1"><li v-for="r in selectedModel.references" :key="r" class="text-xs text-zinc-400">• {{ r }}</li></ul></div>
          </div>
        </div>
      </div>

      <!-- 模型选择决策树 -->
      <div v-if="activeTab === 'tree'" class="p-8">
        <div class="max-w-3xl mx-auto">
          <h1 class="text-xl font-bold mb-2">模型选择助手</h1>
          <p class="text-xs text-zinc-500 mb-6">回答几个问题，帮你找到最合适的建模方法</p>
          <div v-if="treePath.length" class="flex items-center gap-2 mb-4 flex-wrap">
            <span v-for="(step, i) in treePath" :key="i" class="text-xs text-zinc-400">{{ step }} <span v-if="i < treePath.length-1" class="text-zinc-600 mx-1">→</span></span>
            <button @click="resetTree" class="text-[10px] text-zinc-500 hover:text-white ml-2">↻ 重新选择</button>
          </div>
          <div v-if="currentNode" class="p-6 bg-zinc-900/50 border border-white/5 rounded-lg mb-4">
            <h3 class="text-sm font-medium text-white mb-4">{{ currentNode.question }}</h3>
            <div class="space-y-2">
              <button v-for="option in currentNode.options" :key="option.label" @click="selectOption(option)" class="w-full text-left px-4 py-3 bg-zinc-800 border border-white/5 rounded-lg text-sm text-zinc-300 hover:border-white/10 hover:bg-zinc-700 transition-all">{{ option.label }}</button>
            </div>
            <div v-if="currentNode.suggestions" class="mt-4 p-4 bg-blue-950/20 border border-blue-500/10 rounded-lg">
              <p class="text-xs text-blue-400 mb-2">💡 建议：</p>
              <ul class="space-y-1"><li v-for="s in currentNode.suggestions" :key="s" class="text-xs text-zinc-400">• {{ s }}</li></ul>
            </div>
          </div>
          <div v-if="recommendations.length" class="space-y-3">
            <h3 class="text-sm font-medium text-white">🎯 推荐模型</h3>
            <div v-for="rec in recommendations" :key="rec.id" @click="loadModelDetail(rec.id); activeTab = 'model-detail'" class="p-4 bg-zinc-900/50 border border-white/5 rounded-lg hover:border-white/10 cursor-pointer transition-all">
              <div class="flex items-center justify-between mb-2"><span class="text-sm font-medium text-white">{{ rec.name }}</span><span :class="['text-[10px] px-2 py-0.5 rounded-full', difficultyColors[rec.complexity]]">{{ rec.complexity }}</span></div>
              <p class="text-xs text-zinc-400">{{ rec.description }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- 竞赛日历 -->
      <div v-if="activeTab === 'calendar'" class="p-8">
        <div class="max-w-4xl mx-auto">
          <h1 class="text-xl font-bold mb-2">建模竞赛日历</h1>
          <p class="text-xs text-zinc-500 mb-6">全年 {{ competitions.length }} 场主流建模竞赛</p>
          <div class="space-y-3">
            <div v-for="comp in competitions" :key="comp.id" @click="loadCompDetail(comp.id); activeTab = 'comp-detail'" class="flex items-start gap-4 p-4 bg-zinc-900/50 border border-white/5 rounded-lg hover:border-white/10 cursor-pointer transition-all group">
              <div class="shrink-0 w-12 text-center"><div class="text-lg font-bold text-white">{{ comp.month }}</div><div class="text-[10px] text-zinc-500">月</div></div>
              <div class="flex-1">
                <div class="flex items-center gap-2 mb-1"><h3 class="text-sm font-medium text-white group-hover:text-blue-400 transition-colors">{{ comp.name }}</h3><span :class="['text-[10px] px-1.5 py-0.5 rounded', difficultyColors[comp.difficulty]]">{{ comp.difficulty }}</span></div>
                <p class="text-xs text-zinc-400 mb-2">{{ comp.description }}</p>
                <div class="flex items-center gap-3 text-[10px] text-zinc-500"><span>⏱ {{ comp.duration_hours }}h</span><span>👥 {{ comp.team_size }}</span><span>🌐 {{ comp.language }}</span><span>🏆 {{ comp.level }}</span></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 竞赛详情 -->
      <div v-if="activeTab === 'comp-detail' && selectedComp" class="p-8">
        <div class="max-w-3xl mx-auto">
          <button @click="activeTab = 'calendar'" class="text-sm text-zinc-400 hover:text-white mb-4">← 返回列表</button>
          <div class="p-6 bg-zinc-900/50 border border-white/5 rounded-lg">
            <h1 class="text-lg font-bold mb-2">{{ selectedComp.name }}</h1>
            <p class="text-xs text-zinc-500 mb-4">{{ selectedComp.name_en }} · {{ selectedComp.organizer }}</p>
            <p class="text-sm text-zinc-300 mb-6">{{ selectedComp.description }}</p>
            <div class="grid grid-cols-2 gap-4 mb-6">
              <div class="p-3 bg-zinc-800/50 rounded-lg"><p class="text-[10px] text-zinc-500">比赛时间</p><p class="text-sm text-white">{{ selectedComp.month }} 月</p></div>
              <div class="p-3 bg-zinc-800/50 rounded-lg"><p class="text-[10px] text-zinc-500">比赛时长</p><p class="text-sm text-white">{{ selectedComp.duration_hours }} 小时</p></div>
              <div class="p-3 bg-zinc-800/50 rounded-lg"><p class="text-[10px] text-zinc-500">队伍规模</p><p class="text-sm text-white">{{ selectedComp.team_size }}</p></div>
              <div class="p-3 bg-zinc-800/50 rounded-lg"><p class="text-[10px] text-zinc-500">语言</p><p class="text-sm text-white">{{ selectedComp.language }}</p></div>
            </div>
            <div v-if="selectedComp.prizes" class="mb-4"><h3 class="text-xs text-zinc-500 mb-2">🏆 奖项设置</h3><p class="text-sm text-zinc-300">{{ selectedComp.prizes }}</p></div>
            <div v-if="selectedComp.tips?.length"><h3 class="text-xs text-zinc-500 mb-2">💡 参赛建议</h3><ul class="space-y-1"><li v-for="tip in selectedComp.tips" :key="tip" class="text-xs text-zinc-400">• {{ tip }}</li></ul></div>
          </div>
        </div>
      </div>

      <!-- 🔍 Web 搜索 -->
      <div v-if="activeTab === 'search'" class="p-8">
        <div class="max-w-3xl mx-auto">
          <h1 class="text-xl font-bold mb-2">🔍 Web 搜索</h1>
          <p class="text-xs text-zinc-500 mb-6">搜索网页 + 学术论文，获取真实数据和参考文献</p>
          <div class="flex gap-2 mb-6">
            <input v-model="searchInput" @keydown.enter="doSearch" type="text" placeholder="输入关键词，如：物流优化 数学模型" class="flex-1 px-4 py-3 bg-zinc-900 border border-white/10 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-blue-500/30" />
            <button @click="doSearch" :disabled="searching" :class="['px-6 py-3 rounded-lg text-sm font-medium transition-colors', searching ? 'bg-zinc-800 text-zinc-500' : 'bg-white text-black hover:bg-zinc-200']">
              {{ searching ? '搜索中...' : '搜索' }}
            </button>
          </div>

          <div v-if="searchResults">
            <!-- 网页结果 -->
            <div v-if="searchResults.web?.length" class="mb-8">
              <h3 class="text-sm font-medium text-white mb-3">🌐 网页结果</h3>
              <div class="space-y-3">
                <div v-for="(r, i) in searchResults.web" :key="i" class="p-4 bg-zinc-900/50 border border-white/5 rounded-lg hover:border-white/10 transition-all">
                  <a :href="r.url" target="_blank" class="text-sm font-medium text-blue-400 hover:underline">{{ r.title }}</a>
                  <p class="text-xs text-zinc-400 mt-1 line-clamp-2">{{ r.snippet }}</p>
                  <p class="text-[10px] text-zinc-600 mt-1 truncate">{{ r.url }}</p>
                </div>
              </div>
            </div>
            <!-- 学术论文 -->
            <div v-if="searchResults.papers?.length">
              <h3 class="text-sm font-medium text-white mb-3">📄 学术论文</h3>
              <div class="space-y-3">
                <div v-for="(p, i) in searchResults.papers" :key="i" class="p-4 bg-zinc-900/50 border border-white/5 rounded-lg">
                  <div class="flex items-center justify-between mb-1">
                    <a v-if="p.url" :href="p.url" target="_blank" class="text-sm font-medium text-blue-400 hover:underline">{{ p.title }}</a>
                    <span v-else class="text-sm font-medium text-white">{{ p.title }}</span>
                    <span class="text-[10px] text-zinc-500 shrink-0 ml-2">引用 {{ p.citations }}</span>
                  </div>
                  <p class="text-[10px] text-zinc-500 mb-1">{{ p.authors?.join(', ') }} · {{ p.year }} · {{ p.venue }}</p>
                  <p class="text-xs text-zinc-400 line-clamp-2">{{ p.abstract }}</p>
                </div>
              </div>
            </div>
            <div v-if="!searchResults.web?.length && !searchResults.papers?.length" class="text-center py-12"><p class="text-sm text-zinc-500">没有找到结果</p></div>
          </div>
        </div>
      </div>

      <!-- 🏆 获奖论文 -->
      <div v-if="activeTab === 'papers'" class="p-8">
        <div class="max-w-3xl mx-auto">
          <h1 class="text-xl font-bold mb-2">🏆 获奖论文模式</h1>
          <p class="text-xs text-zinc-500 mb-6">参考获奖论文的写作特点，提升自己的论文质量</p>
          <div class="flex gap-2 mb-6">
            <button @click="paperComp = 'CUMCM'; loadPatterns()" :class="['px-3 py-1.5 text-xs rounded-lg', paperComp === 'CUMCM' ? 'bg-white/10 text-white' : 'text-zinc-500']">国赛 CUMCM</button>
            <button @click="paperComp = 'MCM'; loadPatterns()" :class="['px-3 py-1.5 text-xs rounded-lg', paperComp === 'MCM' ? 'bg-white/10 text-white' : 'text-zinc-500']">美赛 MCM</button>
          </div>
          <div class="space-y-4">
            <div v-for="p in paperPatterns" :key="`${p.competition}-${p.year}-${p.award}-${p.problem}`" class="p-5 bg-zinc-900/50 border border-white/5 rounded-lg">
              <div class="flex items-center gap-2 mb-3">
                <span class="text-sm font-medium text-white">{{ p.title }}</span>
                <span class="text-[10px] px-2 py-0.5 rounded bg-yellow-900/30 text-yellow-400">{{ p.award }}</span>
                <span class="text-[10px] px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">{{ p.problem }}题</span>
              </div>
              <div class="grid grid-cols-2 gap-4 mb-3">
                <div>
                  <p class="text-[10px] text-zinc-500 mb-1">核心特征</p>
                  <div class="flex flex-wrap gap-1"><span v-for="f in p.key_features" :key="f" class="text-[10px] px-1.5 py-0.5 bg-blue-900/30 text-blue-400 rounded">{{ f }}</span></div>
                </div>
                <div>
                  <p class="text-[10px] text-zinc-500 mb-1">常用模型</p>
                  <div class="flex flex-wrap gap-1"><span v-for="m in p.model_types" :key="m" class="text-[10px] px-1.5 py-0.5 bg-green-900/30 text-green-400 rounded">{{ m }}</span></div>
                </div>
              </div>
              <div class="p-3 bg-zinc-800/50 rounded-lg">
                <p class="text-[10px] text-zinc-500 mb-1">写作风格</p>
                <div class="flex flex-wrap gap-3 text-[10px] text-zinc-400"><span v-for="(v, k) in p.writing_style" :key="k">{{ k }}: {{ v }}</span></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ⚠️ 常见易错 -->
      <div v-if="activeTab === 'mistakes'" class="p-8">
        <div class="max-w-3xl mx-auto">
          <h1 class="text-xl font-bold mb-2">⚠️ 常见易错点</h1>
          <p class="text-xs text-zinc-500 mb-6">避免这些常见错误，减少返工</p>
          <div class="flex gap-2 mb-6">
            <button @click="mistakesComp = 'CUMCM'; loadMistakes()" :class="['px-3 py-1.5 text-xs rounded-lg', mistakesComp === 'CUMCM' ? 'bg-white/10 text-white' : 'text-zinc-500']">国赛 CUMCM</button>
            <button @click="mistakesComp = 'MCM'; loadMistakes()" :class="['px-3 py-1.5 text-xs rounded-lg', mistakesComp === 'MCM' ? 'bg-white/10 text-white' : 'text-zinc-500']">美赛 MCM</button>
          </div>
          <div class="space-y-2">
            <div v-for="(m, i) in mistakes" :key="i" class="flex items-start gap-3 p-3 bg-zinc-900/50 border border-white/5 rounded-lg">
              <span class="text-red-400 shrink-0 mt-0.5">❌</span>
              <p class="text-sm text-zinc-300">{{ m }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- 📖 写作规范 -->
      <div v-if="activeTab === 'guide'" class="p-8">
        <div class="max-w-3xl mx-auto">
          <h1 class="text-xl font-bold mb-2">📖 写作规范指南</h1>
          <p class="text-xs text-zinc-500 mb-6">按照标准规范撰写论文，避免格式扣分</p>
          <div v-if="guidelines" class="space-y-6">
            <div v-for="(section, title) in guidelines" :key="title" class="p-5 bg-zinc-900/50 border border-white/5 rounded-lg">
              <h3 class="text-sm font-medium text-white mb-3">{{ title }}</h3>
              <div class="space-y-2">
                <div v-for="(content, key) in section" :key="key" class="flex items-start gap-2">
                  <span class="text-[10px] text-zinc-500 shrink-0 w-20 text-right mt-0.5">{{ key }}</span>
                  <p class="text-xs text-zinc-300">{{ content }}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

    </main>
  </div>
</template>
