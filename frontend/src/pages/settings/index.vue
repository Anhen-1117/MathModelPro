<script setup lang="ts">
import { ref, onMounted, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import service from '@/utils/request'
import { useNotify } from '@/composables/useNotify'
import { useApiKeyStore } from '@/stores/apiKeys'

const router = useRouter()
const notify = useNotify()
const apiKeyStore = useApiKeyStore()
const activeTab = ref('api')
const saving = ref(false)
const showKeys = reactive<Record<string, boolean>>({})

const tabs = [
  { id: 'api', label: 'API 设置', icon: '🔑' },
  { id: 'model', label: '模型配置', icon: '⚙️' },
  { id: 'general', label: '通用', icon: '🎛️' }
]

const settings = reactive({
  general: { language: 'zh-CN', theme: 'dark' },
  api: {
    coordinator: { apiKey: '', baseUrl: 'https://api.deepseek.com', modelId: 'deepseek-chat', apiType: 'openai' },
    modeler: { apiKey: '', baseUrl: 'https://api.deepseek.com', modelId: 'deepseek-chat', apiType: 'openai' },
    coder: { apiKey: '', baseUrl: 'https://api.deepseek.com', modelId: 'deepseek-chat', apiType: 'openai' },
    writer: { apiKey: '', baseUrl: 'https://api.deepseek.com', modelId: 'deepseek-chat', apiType: 'openai' }
  },
  model: { defaultLanguage: 'python', defaultTemplate: 'cumcm' }
})

const agentLabels: Record<string, { name: string; icon: string; desc: string }> = {
  coordinator: { name: '协调器', icon: '🎯', desc: '负责任务分解和调度' },
  modeler: { name: '建模手', icon: '📐', desc: '负责数学模型构建' },
  coder: { name: '代码手', icon: '💻', desc: '负责代码生成和调试' },
  writer: { name: '论文手', icon: '📝', desc: '负责论文撰写和排版' }
}

const configuredCount = computed(() => {
  return Object.values(settings.api).filter(a => !!a.apiKey).length
})

onMounted(async () => {
  // 步骤1：从 localStorage 加载非 API 的设置（model、general）
  const local = localStorage.getItem('settings')
  if (local) {
    try {
      const parsed = JSON.parse(local)
      if (parsed.model) Object.assign(settings.model, parsed.model)
      if (parsed.general) Object.assign(settings.general, parsed.general)
    } catch {}
  }

  // 步骤2：从 apiKeyStore（Pinia，单一数据源）加载 API Key
  const agentKeys = ['coordinator', 'modeler', 'coder', 'writer'] as const
  const storeConfigs = apiKeyStore.getAllAgentConfigs()
  for (const agent of agentKeys) {
    const storeCfg = storeConfigs[agent]
    if (storeCfg) {
      // 只使用有效的 Key（排除空字符串和脱敏 Key）
      const key = storeCfg.apiKey || ''
      ;(settings.api as any)[agent] = {
        apiKey: (key && !key.includes('****')) ? key : '',
        baseUrl: storeCfg.baseUrl || 'https://api.deepseek.com',
        modelId: storeCfg.modelId || 'deepseek-chat',
        apiType: storeCfg.apiType || 'openai',
      }
    }
  }

  // 步骤3：从后端补充（非敏感字段兜底，不覆盖本地已有 Key）
  try {
    const res = await service.get('/api/v2/settings')
    if (res.data.api) {
      for (const agent of Object.keys(res.data.api)) {
        const backendCfg = res.data.api[agent]
        const localCfg = (settings.api as any)[agent]
        if (!localCfg) {
          // 本地无此 Agent → 用后端数据，但清除脱敏 Key
          (settings.api as any)[agent] = { ...backendCfg, apiKey: '' }
        } else {
          // 后端 Key 仅在本地为空时补充（且后端 Key 非脱敏）
          if (!localCfg.apiKey && backendCfg.apiKey && !backendCfg.apiKey.includes('****')) {
            localCfg.apiKey = backendCfg.apiKey
          }
          // 兜底字段：保留本地值，空时取后端
          localCfg.baseUrl = localCfg.baseUrl || backendCfg.baseUrl || 'https://api.deepseek.com'
          localCfg.modelId = localCfg.modelId || backendCfg.modelId || 'deepseek-chat'
          localCfg.apiType = localCfg.apiType || backendCfg.apiType || 'openai'
        }
      }
    }
    if (res.data.model) {
      settings.model = { ...settings.model, ...res.data.model }
    }
  } catch {}
})

const maskKey = (key: string) => {
  if (!key) return ''
  if (key.length <= 8) return '****'
  return key.slice(0, 4) + '****' + key.slice(-4)
}

const toggleShowKey = (agent: string) => {
  showKeys[agent] = !showKeys[agent]
}

const handleSave = async () => {
  // 检查是否有脱敏 Key（阻止将脱敏 Key 保存到后端）
  let hasMaskedKey = false
  for (const agent of Object.keys(settings.api)) {
    const key = (settings.api as any)[agent]?.apiKey || ''
    if (key.includes('****')) {
      (settings.api as any)[agent].apiKey = ''  // 清除脱敏 Key
      hasMaskedKey = true
    }
  }
  if (hasMaskedKey) {
    notify.warning('检测到无效 Key', '脱敏 Key 已自动清除，请重新输入真实 API Key')
  }

  saving.value = true
  // 保存非 API 设置到 localStorage（API Key 由 Pinia store 统一管理）
  localStorage.setItem('settings', JSON.stringify({
    model: settings.model,
    general: settings.general
  }))
  // API Key 统一写入 apiKeyStore（Pinia 自动持久化到 localStorage）
  apiKeyStore.setCoordinatorConfig({ ...settings.api.coordinator })
  apiKeyStore.setModelerConfig({ ...settings.api.modeler })
  apiKeyStore.setCoderConfig({ ...settings.api.coder })
  apiKeyStore.setWriterConfig({ ...settings.api.writer })
  try {
    const res = await service.put('/api/v2/settings', {
      api: settings.api,
      model: settings.model
    })
    // 验证后端保存成功
    // 后端返回脱敏 Key（如 sk-c****71b6），非空即已配置
    const savedConfigured = Object.values(res.data?.api || {}).filter((a: any) => a?.apiKey).length
    notify.success('已保存到后端', `${savedConfigured}/4 个 Agent 已配置`)
  } catch (e) {
    notify.error('无法连接后端', '配置已保存到本地，后端启动后将自动同步')
  } finally {
    saving.value = false
  }
}

const fillPreset = (agent: string, provider: string) => {
  const presets: Record<string, any> = {
    deepseek: { baseUrl: 'https://api.deepseek.com', modelId: 'deepseek-chat' },
    openai: { baseUrl: 'https://api.openai.com/v1', modelId: 'gpt-4o' },
    dashscope: { baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1', modelId: 'deepseek-v3' }
  }
  const preset = presets[provider]
  if (preset) {
    (settings.api as any)[agent].baseUrl = preset.baseUrl
    ;(settings.api as any)[agent].modelId = preset.modelId
  }
}
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
      
      <div class="flex-1 p-3 space-y-1">
        <button v-for="tab in tabs" :key="tab.id" @click="activeTab = tab.id"
          :class="['w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors', activeTab === tab.id ? 'bg-white/10 text-white' : 'text-zinc-400 hover:bg-white/5 hover:text-white']">
          <span>{{ tab.icon }}</span>
          <span>{{ tab.label }}</span>
        </button>
      </div>

      <!-- 配置状态 -->
      <div class="p-3 border-t border-white/5">
        <div class="mb-3 px-2">
          <div class="flex items-center justify-between text-xs mb-1.5">
            <span class="text-zinc-500">配置进度</span>
            <span :class="configuredCount > 0 ? 'text-green-400' : 'text-zinc-500'">{{ configuredCount }}/4</span>
          </div>
          <div class="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
            <div class="h-full bg-gradient-to-r from-green-500 to-emerald-400 rounded-full transition-all duration-500" :style="{ width: `${configuredCount * 25}%` }"></div>
          </div>
        </div>
        <button @click="handleSave" :disabled="saving"
          :class="['w-full py-2 text-sm font-medium rounded-lg transition-all flex items-center justify-center gap-2', saving ? 'bg-zinc-700 text-zinc-400 cursor-wait' : 'bg-white text-black hover:bg-zinc-200']">
          <svg v-if="saving" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>
          {{ saving ? '保存中...' : '保存设置' }}
        </button>
      </div>
    </aside>

    <!-- 主内容 -->
    <main class="flex-1 overflow-y-auto">
      <div class="max-w-2xl mx-auto p-8">
        <!-- API 设置 -->
        <div v-if="activeTab === 'api'" class="space-y-6">
          <div>
            <h2 class="text-lg font-semibold text-white">API 设置</h2>
            <p class="text-xs text-zinc-500 mt-1">为每个 Agent 配置 LLM API。至少配置一个即可使用。</p>
          </div>

          <!-- 快捷预设 -->
          <div class="p-4 bg-blue-950/20 border border-blue-500/10 rounded-lg">
            <p class="text-xs text-blue-400 mb-2">💡 快捷预设（点击自动填充 Base URL 和 Model ID）</p>
            <div class="flex gap-2">
              <button @click="Object.keys(settings.api).forEach(k => fillPreset(k, 'deepseek'))" class="px-3 py-1.5 text-xs bg-zinc-800 hover:bg-zinc-700 border border-white/10 rounded-lg text-zinc-300 transition-colors">DeepSeek</button>
              <button @click="Object.keys(settings.api).forEach(k => fillPreset(k, 'dashscope'))" class="px-3 py-1.5 text-xs bg-zinc-800 hover:bg-zinc-700 border border-white/10 rounded-lg text-zinc-300 transition-colors">阿里百炼</button>
              <button @click="Object.keys(settings.api).forEach(k => fillPreset(k, 'openai'))" class="px-3 py-1.5 text-xs bg-zinc-800 hover:bg-zinc-700 border border-white/10 rounded-lg text-zinc-300 transition-colors">OpenAI</button>
            </div>
          </div>

          <div v-for="(info, key) in agentLabels" :key="key" class="p-4 bg-zinc-900/50 border border-white/5 rounded-lg transition-colors hover:border-white/10">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center gap-2">
                <span class="text-lg">{{ info.icon }}</span>
                <div>
                  <h3 class="text-sm font-medium text-white">{{ info.name }}</h3>
                  <p class="text-[10px] text-zinc-500">{{ info.desc }}</p>
                </div>
              </div>
              <span v-if="(settings.api as any)[key].apiKey" class="text-[10px] px-2 py-0.5 rounded-full bg-green-900/30 text-green-400 border border-green-500/20">✓ 已配置</span>
              <span v-else class="text-[10px] px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-500">未配置</span>
            </div>
            <div class="space-y-3">
              <div>
                <label class="block text-xs text-zinc-500 mb-1">API Key</label>
                <div class="flex gap-2">
                  <input :type="showKeys[key] ? 'text' : 'password'" v-model="(settings.api as any)[key].apiKey" placeholder="sk-..."
                    class="flex-1 px-3 py-2 bg-zinc-800 border border-white/10 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-blue-500/30 focus:border-blue-500/30 transition-all" />
                  <button @click="toggleShowKey(key)" class="px-3 py-2 bg-zinc-800 border border-white/10 rounded-lg text-xs text-zinc-400 hover:text-white hover:bg-zinc-700 transition-colors">
                    {{ showKeys[key] ? '🙈' : '👁️' }}
                  </button>
                </div>
                <p v-if="(settings.api as any)[key].apiKey" class="text-[10px] text-zinc-600 mt-1">当前: {{ maskKey((settings.api as any)[key].apiKey) }}</p>
              </div>
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-xs text-zinc-500 mb-1">Base URL</label>
                  <input v-model="(settings.api as any)[key].baseUrl" type="text" placeholder="https://api.deepseek.com"
                    class="w-full px-3 py-2 bg-zinc-800 border border-white/10 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-blue-500/30 focus:border-blue-500/30 transition-all" />
                </div>
                <div>
                  <label class="block text-xs text-zinc-500 mb-1">Model ID</label>
                  <input v-model="(settings.api as any)[key].modelId" type="text" placeholder="deepseek-chat"
                    class="w-full px-3 py-2 bg-zinc-800 border border-white/10 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-blue-500/30 focus:border-blue-500/30 transition-all" />
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 模型配置 -->
        <div v-if="activeTab === 'model'" class="space-y-6">
          <h2 class="text-lg font-semibold text-white">模型配置</h2>
          <div class="space-y-4">
            <div>
              <label class="block text-sm text-zinc-400 mb-1.5">默认代码语言</label>
              <div class="flex gap-2">
                <button v-for="lang in [{ id: 'python', label: 'Python', icon: '🐍' }]" :key="lang.id"
                  @click="settings.model.defaultLanguage = lang.id"
                  :class="['flex-1 px-4 py-3 rounded-lg border text-sm text-center transition-all', settings.model.defaultLanguage === lang.id ? 'border-blue-500/30 bg-blue-500/10 text-white' : 'border-white/5 text-zinc-400 hover:border-white/10']">
                  <span class="block text-lg mb-1">{{ lang.icon }}</span>
                  {{ lang.label }}
                </button>
              </div>
            </div>
            <div>
              <label class="block text-sm text-zinc-400 mb-1.5">默认论文模板</label>
              <select v-model="settings.model.defaultTemplate" class="w-full px-3 py-2 bg-zinc-900 border border-white/10 rounded-lg text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500/30">
                <option value="cumcm">国赛 (CUMCM)</option>
                <option value="huashu">华数杯</option>
                <option value="mcm">MCM/ICM (美赛)</option>
              </select>
            </div>
          </div>
        </div>

        <!-- 通用设置 -->
        <div v-if="activeTab === 'general'" class="space-y-6">
          <h2 class="text-lg font-semibold text-white">通用设置</h2>
          <div class="space-y-4">
            <div>
              <label class="block text-sm text-zinc-400 mb-1.5">界面语言</label>
              <select v-model="settings.general.language" class="w-full px-3 py-2 bg-zinc-900 border border-white/10 rounded-lg text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500/30">
                <option value="zh-CN">简体中文</option>
                <option value="en-US">English</option>
              </select>
            </div>
            <div>
              <label class="block text-sm text-zinc-400 mb-1.5">主题</label>
              <div class="flex gap-2">
                <button v-for="theme in [{ id: 'dark', label: '深色', icon: '🌙' }, { id: 'light', label: '浅色', icon: '☀️' }]" :key="theme.id"
                  @click="settings.general.theme = theme.id"
                  :class="['flex-1 px-4 py-3 rounded-lg border text-sm text-center transition-all', settings.general.theme === theme.id ? 'border-blue-500/30 bg-blue-500/10 text-white' : 'border-white/5 text-zinc-400 hover:border-white/10']">
                  <span class="block text-lg mb-1">{{ theme.icon }}</span>
                  {{ theme.label }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>
