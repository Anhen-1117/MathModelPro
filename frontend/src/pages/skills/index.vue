<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import service from '@/utils/request'
import { useNotify } from '@/composables/useNotify'
import { useConfirm } from '@/composables/useConfirm'

const router = useRouter()
const notify = useNotify()
const { confirm } = useConfirm()
const skills = ref<any[]>([])
const selectedSkill = ref<any>(null)
const loading = ref(false)
const activeTab = ref('coordinator')
const showCreateDialog = ref(false)

const agentTypes = [
  { id: 'coordinator', label: '协调器', icon: '🎯' },
  { id: 'modeler', label: '建模手', icon: '📐' },
  { id: 'coder', label: '代码手', icon: '💻' },
  { id: 'writer', label: '论文手', icon: '📝' },
]

const newSkill = ref({ name: '', description: '', agent_type: 'coordinator', system_prompt: '' })

const filteredSkills = computed(() => skills.value.filter(s => s.agent_type === activeTab.value || s.agent_type === 'all'))

onMounted(async () => { await loadSkills() })

const loadSkills = async () => {
  loading.value = true
  try { const res = await service.get('/api/v1/skills'); skills.value = res.data.skills || [] }
  catch { notify.error('加载失败', '无法获取 Skill 列表') }
  finally { loading.value = false }
}

const selectSkill = (skill: any) => { selectedSkill.value = skill }

const createSkill = async () => {
  if (!newSkill.value.name || !newSkill.value.system_prompt) { notify.warning('请填写名称和系统提示词'); return }
  try {
    await service.post('/api/v1/skills', newSkill.value)
    showCreateDialog.value = false
    newSkill.value = { name: '', description: '', agent_type: 'coordinator', system_prompt: '' }
    await loadSkills()
    notify.success('Skill 创建成功')
  } catch { notify.error('创建失败') }
}

const deleteSkill = async (id: string) => {
  const ok = await confirm({ title: '删除 Skill', description: '确定要删除这个 Skill 吗？', confirmText: '删除', variant: 'danger' })
  if (!ok) return
  try {
    await service.delete(`/api/v1/skills/${id}`)
    if (selectedSkill.value?.id === id) selectedSkill.value = null
    await loadSkills()
    notify.success('已删除')
  } catch { notify.error('删除失败') }
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
        <button @click="showCreateDialog = true" class="px-3 py-1.5 bg-white text-black text-xs font-medium rounded-lg hover:bg-zinc-200">+ 新建</button>
      </div>

      <div class="p-2 border-b border-white/5 grid grid-cols-4 gap-1">
        <button v-for="a in agentTypes" :key="a.id" @click="activeTab = a.id"
          :class="['p-2 rounded-lg text-center text-xs transition-colors', activeTab === a.id ? 'bg-white/10 text-white' : 'text-zinc-500 hover:text-white']">
          <div class="text-lg">{{ a.icon }}</div><div>{{ a.label }}</div>
        </button>
      </div>

      <div class="flex-1 overflow-y-auto p-2">
        <div v-if="loading" class="text-center py-12"><div class="w-6 h-6 border-2 border-zinc-600 border-t-white rounded-full animate-spin mx-auto"></div></div>
        <div v-else-if="filteredSkills.length === 0" class="text-center py-12">
          <div class="text-3xl mb-2 opacity-30">🧩</div><p class="text-sm text-zinc-500">暂无 Skill</p>
        </div>
        <div v-for="skill in filteredSkills" :key="skill.id" @click="selectSkill(skill)"
          :class="['p-3 rounded-lg cursor-pointer mb-1 transition-colors border', selectedSkill?.id === skill.id ? 'bg-white/10 border-white/10' : 'border-transparent hover:bg-white/5']">
          <h3 class="text-sm font-medium text-white">{{ skill.name }}</h3>
          <p class="text-xs text-zinc-500 mt-1 line-clamp-2">{{ skill.description }}</p>
          <div class="flex items-center gap-2 mt-2">
            <span class="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400">{{ skill.agent_type }}</span>
            <span v-if="skill.is_builtin" class="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-500">内置</span>
          </div>
        </div>
      </div>
    </aside>

    <main class="flex-1 flex flex-col overflow-hidden">
      <template v-if="selectedSkill">
        <div class="h-14 px-6 border-b border-white/5 flex items-center justify-between shrink-0">
          <div class="flex items-center gap-3">
            <h2 class="text-sm font-medium text-white">{{ selectedSkill.name }}</h2>
            <span class="text-xs px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">{{ selectedSkill.agent_type }}</span>
          </div>
          <button v-if="!selectedSkill.is_builtin" @click="deleteSkill(selectedSkill.id)" class="px-3 py-1.5 text-xs text-red-400 hover:bg-red-900/20 rounded-lg transition-colors">删除</button>
        </div>
        <div class="flex-1 overflow-auto p-6">
          <div class="max-w-3xl space-y-6">
            <div><label class="block text-xs text-zinc-500 mb-2">描述</label><p class="text-sm text-zinc-300">{{ selectedSkill.description || '无描述' }}</p></div>
            <div><label class="block text-xs text-zinc-500 mb-2">系统提示词</label>
              <div class="p-4 bg-zinc-900 border border-white/5 rounded-lg"><pre class="text-sm text-zinc-300 whitespace-pre-wrap font-mono leading-relaxed">{{ selectedSkill.system_prompt }}</pre></div>
            </div>
          </div>
        </div>
      </template>
      <div v-else class="flex-1 flex items-center justify-center">
        <div class="text-center">
          <div class="text-5xl mb-4 opacity-30">🧩</div>
          <h3 class="text-lg font-medium text-white mb-2">Skill 库</h3>
          <p class="text-sm text-zinc-500 mb-4">选择左侧 Skill 查看详情，或点击"新建"创建</p>
          <p class="text-[10px] text-zinc-600">Skill 定义了每个 Agent 的行为方式</p>
        </div>
      </div>
    </main>

    <Teleport to="body">
      <Transition name="fade">
        <div v-if="showCreateDialog" class="fixed inset-0 z-50 flex items-center justify-center">
          <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="showCreateDialog = false"></div>
          <div class="relative w-full max-w-lg mx-4 bg-[#111] border border-white/10 rounded-xl shadow-2xl">
            <div class="px-6 py-4 border-b border-white/5 flex justify-between items-center">
              <h2 class="text-sm font-medium text-white">新建 Skill</h2>
              <button @click="showCreateDialog = false" class="text-zinc-400 hover:text-white transition-colors">✕</button>
            </div>
            <div class="p-6 space-y-4">
              <div><label class="block text-xs text-zinc-400 mb-1">名称 *</label>
                <input v-model="newSkill.name" placeholder="例如：国赛建模专家" class="w-full px-3 py-2 bg-zinc-900 border border-white/10 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-blue-500/30" /></div>
              <div><label class="block text-xs text-zinc-400 mb-1">描述</label>
                <input v-model="newSkill.description" placeholder="简要描述这个 Skill 的用途" class="w-full px-3 py-2 bg-zinc-900 border border-white/10 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-blue-500/30" /></div>
              <div><label class="block text-xs text-zinc-400 mb-1">适用 Agent</label>
                <select v-model="newSkill.agent_type" class="w-full px-3 py-2 bg-zinc-900 border border-white/10 rounded-lg text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500/30">
                  <option v-for="a in agentTypes" :key="a.id" :value="a.id">{{ a.icon }} {{ a.label }}</option>
                </select></div>
              <div><label class="block text-xs text-zinc-400 mb-1">系统提示词 *</label>
                <textarea v-model="newSkill.system_prompt" rows="6" placeholder="定义 Agent 的角色和行为规则..." class="w-full px-3 py-2 bg-zinc-900 border border-white/10 rounded-lg text-sm text-white font-mono placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-blue-500/30 resize-y"></textarea></div>
            </div>
            <div class="px-6 py-4 border-t border-white/5 flex justify-end gap-3">
              <button @click="showCreateDialog = false" class="px-4 py-2 text-sm text-zinc-400 hover:text-white transition-colors">取消</button>
              <button @click="createSkill" class="px-4 py-2 text-sm bg-white text-black rounded-lg hover:bg-zinc-200 transition-colors">创建</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>
