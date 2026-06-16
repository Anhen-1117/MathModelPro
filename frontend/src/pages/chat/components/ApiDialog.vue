<script setup lang="ts">
import { ref, watch } from 'vue'
import { saveApiConfig, validateApiKey } from '@/apis/apiKeyApi'
import { useToast } from '@/components/ui/toast'
import { useApiKeyStore } from '@/stores/apiKeys'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
}>()

const { toast } = useToast()
const apiKeyStore = useApiKeyStore()
const activeTab = ref('coordinator')
const validating = ref(false)
const saving = ref(false)

const configs = ref({
  coordinator: {
    apiKey: '',
    baseUrl: 'https://api.deepseek.com',
    modelId: 'deepseek-chat',
    apiType: 'openai'
  },
  modeler: {
    apiKey: '',
    baseUrl: 'https://api.deepseek.com',
    modelId: 'deepseek-chat',
    apiType: 'openai'
  },
  coder: {
    apiKey: '',
    baseUrl: 'https://api.deepseek.com',
    modelId: 'deepseek-chat',
    apiType: 'openai'
  },
  writer: {
    apiKey: '',
    baseUrl: 'https://api.deepseek.com',
    modelId: 'deepseek-chat',
    apiType: 'openai'
  }
})

const tabs = [
  { id: 'coordinator', label: '协调器', icon: '🎯' },
  { id: 'modeler', label: '建模手', icon: '📐' },
  { id: 'coder', label: '代码手', icon: '💻' },
  { id: 'writer', label: '论文手', icon: '📝' }
]

const apiTypes = [
  { id: 'openai', label: 'OpenAI 兼容 (DeepSeek/通义等)' },
  { id: 'anthropic', label: 'Anthropic' }
]

const handleClose = () => {
  emit('update:open', false)
}

const handleValidate = async () => {
  const cfg = (configs as any)[activeTab.value]
  if (!cfg.apiKey?.trim()) {
    toast({
      title: '请输入 API Key',
      description: '验证前需要先填写 API Key',
      variant: 'destructive',
    })
    return
  }
  validating.value = true
  try {
    const res = await validateApiKey({
      api_key: cfg.apiKey,
      base_url: cfg.baseUrl,
      model_id: cfg.modelId,
      api_type: cfg.apiType,
    })
    if (res.data.valid) {
      toast({ title: '✅ 验证成功', description: res.data.message })
    } else {
      toast({ title: '❌ 验证失败', description: res.data.message, variant: 'destructive' })
    }
  } catch {
    toast({ title: '验证失败', description: '无法连接后端，请确认后端已启动', variant: 'destructive' })
  } finally {
    validating.value = false
  }
}

const handleSave = async () => {
  // 清除脱敏 Key（阻止将 sk-c****xxxx 保存到后端）
  let clearedMasked = false
  for (const agent of Object.keys(configs.value)) {
    const key = (configs.value as any)[agent]?.apiKey || ''
    if (key.includes('****')) {
      (configs.value as any)[agent].apiKey = ''
      clearedMasked = true
    }
  }
  if (clearedMasked) {
    toast({ title: '⚠️ 检测到无效 Key', description: '脱敏 Key 已自动清除，请重新输入真实 API Key', variant: 'destructive' })
    return  // 阻止保存，让用户重新输入
  }

  saving.value = true
  // 统一写入 apiKeyStore（Pinia 自动持久化到 localStorage）
  apiKeyStore.setCoordinatorConfig({ ...configs.value.coordinator })
  apiKeyStore.setModelerConfig({ ...configs.value.modeler })
  apiKeyStore.setCoderConfig({ ...configs.value.coder })
  apiKeyStore.setWriterConfig({ ...configs.value.writer })
  try {
    const res = await saveApiConfig({
      coordinator: configs.value.coordinator,
      modeler: configs.value.modeler,
      coder: configs.value.coder,
      writer: configs.value.writer,
      openalex_email: '',
    })
    if (res.data.success) {
      toast({ title: '✅ 已保存到后端', description: res.data.message })
    } else {
      toast({ title: '⚠️ 保存失败', description: res.data.message, variant: 'destructive' })
    }
  } catch {
    toast({
      title: '已保存到本地',
      description: '无法连接后端，配置已保存到本地存储。后端启动后请重新保存。',
      variant: 'destructive',
    })
  } finally {
    saving.value = false
    handleClose()
  }
}

const handleReset = () => {
  configs.value = {
    coordinator: { apiKey: '', baseUrl: 'https://api.deepseek.com', modelId: 'deepseek-chat', apiType: 'openai' },
    modeler: { apiKey: '', baseUrl: 'https://api.deepseek.com', modelId: 'deepseek-chat', apiType: 'openai' },
    coder: { apiKey: '', baseUrl: 'https://api.deepseek.com', modelId: 'deepseek-chat', apiType: 'openai' },
    writer: { apiKey: '', baseUrl: 'https://api.deepseek.com', modelId: 'deepseek-chat', apiType: 'openai' }
  }
}

// 加载保存的配置（单一数据源：apiKeyStore）
watch(() => props.open, (val) => {
  if (val) {
    // 从 apiKeyStore（Pinia 持久化）读取，这是 API Key 的唯一权威来源
    const defaults = { apiKey: '', baseUrl: 'https://api.deepseek.com', modelId: 'deepseek-chat', apiType: 'openai' }
    configs.value.coordinator = { ...defaults, ...apiKeyStore.coordinatorConfig }
    configs.value.modeler   = { ...defaults, ...apiKeyStore.modelerConfig }
    configs.value.coder     = { ...defaults, ...apiKeyStore.coderConfig }
    configs.value.writer    = { ...defaults, ...apiKeyStore.writerConfig }
    // 清除可能存在的脱敏 Key
    for (const agent of Object.keys(configs.value)) {
      if ((configs.value as any)[agent].apiKey?.includes('****')) {
        (configs.value as any)[agent].apiKey = ''
      }
    }
  }
})
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="open" class="fixed inset-0 z-50 flex items-center justify-center">
        <!-- 遮罩 -->
        <div 
          class="absolute inset-0 bg-black/70 backdrop-blur-sm"
          @click="handleClose"
        ></div>
        
        <!-- 弹窗 -->
        <div class="relative w-full max-w-2xl mx-4 bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden">
          <!-- 头部 -->
          <div class="px-6 py-4 border-b border-slate-800">
            <div class="flex items-center justify-between">
              <h2 class="text-lg font-semibold text-white">API 设置</h2>
              <button 
                @click="handleClose"
                class="w-8 h-8 rounded-lg hover:bg-slate-800 flex items-center justify-center transition-colors text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>
          </div>
          
          <!-- Tab 导航 -->
          <div class="px-6 border-b border-slate-800 flex items-center gap-1">
            <button 
              v-for="tab in tabs"
              :key="tab.id"
              @click="activeTab = tab.id"
              :class="[
                'px-4 py-3 text-sm font-medium transition-all relative',
                activeTab === tab.id
                  ? 'text-white'
                  : 'text-slate-500 hover:text-slate-300'
              ]"
            >
              <span class="mr-1.5">{{ tab.icon }}</span>
              {{ tab.label }}
              <div 
                v-if="activeTab === tab.id"
                class="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-purple-500 to-blue-500"
              ></div>
            </button>
          </div>
          
          <!-- 配置表单 -->
          <div class="p-6 space-y-4 max-h-[50vh] overflow-y-auto">
            <!-- API 类型 -->
            <div>
              <label class="block text-sm text-slate-400 mb-1.5">API 类型</label>
              <select 
                v-model="(configs as any)[activeTab].apiType"
                class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-sm text-white focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
              >
                <option v-for="type in apiTypes" :key="type.id" :value="type.id">{{ type.label }}</option>
              </select>
            </div>
            
            <!-- API Key -->
            <div>
              <label class="block text-sm text-slate-400 mb-1.5">API Key</label>
              <input 
                v-model="(configs as any)[activeTab].apiKey"
                type="password"
                placeholder="sk-..."
                class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-sm text-white placeholder-slate-500 focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
              />
            </div>
            
            <!-- Base URL -->
            <div>
              <label class="block text-sm text-slate-400 mb-1.5">Base URL</label>
              <input 
                v-model="(configs as any)[activeTab].baseUrl"
                type="text"
                placeholder="https://api.openai.com/v1"
                class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-sm text-white placeholder-slate-500 focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
              />
            </div>
            
            <!-- Model ID -->
            <div>
              <label class="block text-sm text-slate-400 mb-1.5">Model ID</label>
              <input 
                v-model="(configs as any)[activeTab].modelId"
                type="text"
                placeholder="gpt-4o / claude-sonnet-4-20250514"
                class="w-full px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-sm text-white placeholder-slate-500 focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
              />
            </div>
          </div>
          
          <!-- 底部按钮 -->
          <div class="px-6 py-4 border-t border-slate-800 flex items-center justify-between">
            <button
              @click="handleReset"
              class="px-4 py-2 text-sm text-slate-400 hover:text-white hover:bg-slate-800 rounded-xl transition-colors"
            >
              重置默认
            </button>
            <div class="flex gap-3">
              <button
                @click="handleClose"
                class="px-4 py-2 text-sm text-slate-400 hover:text-white hover:bg-slate-800 rounded-xl transition-colors"
              >
                取消
              </button>
              <button
                @click="handleValidate"
                :disabled="validating"
                class="px-4 py-2 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 rounded-xl transition-all"
              >
                {{ validating ? '验证中...' : '验证' }}
              </button>
              <button
                @click="handleSave"
                :disabled="saving"
                class="px-6 py-2 text-sm font-medium text-white bg-gradient-to-r from-purple-600 to-blue-600 hover:opacity-90 disabled:opacity-50 rounded-xl transition-all"
              >
                {{ saving ? '保存中...' : '保存' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
</style>
