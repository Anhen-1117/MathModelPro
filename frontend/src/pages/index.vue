<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ref, onMounted } from 'vue'
import { checkApiConfig } from '@/utils/api-check'
import service from '@/utils/request'

const router = useRouter()
const needsSetup = ref(false)
const upcomingComps = ref<any[]>([])

onMounted(async () => {
  const status = await checkApiConfig()
  needsSetup.value = !status.configured
  try { const r = await service.get('/api/v1/competitions/upcoming/list'); upcomingComps.value = (r.data.competitions || []).slice(0, 4) } catch {}
})

const features = [
  { icon: '⚡', title: '极速建模', desc: '3天→1小时，AI全自动完成从分析到论文的全流程' },
  { icon: '🤖', title: '多Agent协作', desc: '协调器 + 建模手 + 代码手 + 论文手，分工明确' },
  { icon: '📝', title: '自动生成论文', desc: 'Typst 模板，支持国赛、华数杯、美赛等' },
  { icon: '💻', title: '多语言代码', desc: 'Python / MATLAB 双语言支持' },
  { icon: '📊', title: '实时进度追踪', desc: 'WebSocket 实时推送，随时掌握建模进度' },
  { icon: '🎨', title: '现代UI设计', desc: '深色主题，流畅动画，专业级界面' },
]

const steps = [
  { num: '01', title: '分析问题', desc: 'AI 理解题目，提取关键信息' },
  { num: '02', title: '建立模型', desc: '自动选择建模方法，推导公式' },
  { num: '03', title: '编写代码', desc: '生成 Python / MATLAB 代码' },
  { num: '04', title: '撰写论文', desc: '生成可直接提交的建模论文' },
]
</script>

<template>
  <div class="min-h-screen bg-[#0a0a0b] text-white">
    <!-- 导航栏 -->
    <nav class="fixed top-0 left-0 right-0 z-50 border-b border-white/5 bg-[#0a0a0b]/80 backdrop-blur-xl">
      <div class="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-500 flex items-center justify-center">
            <span class="text-sm font-bold">M</span>
          </div>
          <span class="font-semibold text-white">MathModelPro</span>
        </div>
        
        <div class="flex items-center gap-6">
          <button @click="router.push('/chat')" class="text-sm text-zinc-400 hover:text-white transition-colors">对话</button>
          <button @click="router.push('/tasks')" class="text-sm text-zinc-400 hover:text-white transition-colors">任务</button>
          <button @click="router.push('/skills')" class="text-sm text-zinc-400 hover:text-white transition-colors">Skill</button>
          <button @click="router.push('/knowledge')" class="text-sm text-zinc-400 hover:text-white transition-colors">知识库</button>
          <button @click="router.push('/settings')" class="text-sm text-zinc-400 hover:text-white transition-colors">设置</button>
          <button @click="router.push('/tasks')" class="px-4 py-2 bg-white text-black text-sm font-medium rounded-lg hover:bg-zinc-200 transition-colors">开始使用</button>
        </div>
      </div>
    </nav>

    <!-- 首次使用引导 -->
    <div v-if="needsSetup" class="fixed top-16 left-0 right-0 z-40 bg-amber-950/80 border-b border-amber-500/20 backdrop-blur-sm">
      <div class="max-w-6xl mx-auto px-6 py-3 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <span class="text-amber-400">👋</span>
          <p class="text-sm text-amber-200">首次使用？请先配置 API Key 才能开始建模</p>
        </div>
        <div class="flex items-center gap-2">
          <button @click="router.push('/settings')" class="px-4 py-1.5 text-xs bg-amber-500/20 text-amber-200 rounded-lg hover:bg-amber-500/30 transition-colors">去配置</button>
          <button @click="needsSetup = false" class="text-amber-400/60 hover:text-amber-400 transition-colors">✕</button>
        </div>
      </div>
    </div>

    <!-- Hero -->
    <section class="pt-32 pb-20 px-6">
      <div class="max-w-4xl mx-auto text-center">
        <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-white/10 bg-white/5 text-sm text-zinc-400 mb-8">
          <span class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
          AI 驱动的数学建模助手
        </div>
        
        <h1 class="text-5xl md:text-7xl font-bold mb-6 tracking-tight">
          数学建模
          <span class="bg-gradient-to-r from-violet-400 via-indigo-400 to-cyan-400 bg-clip-text text-transparent">新范式</span>
        </h1>
        
        <p class="text-lg text-zinc-400 mb-10 max-w-2xl mx-auto leading-relaxed">
          从问题分析到论文生成，AI 全自动完成。
        </p>
        
        <div class="flex items-center justify-center gap-4">
          <button @click="router.push('/tasks')" class="px-8 py-3 bg-white text-black font-medium rounded-lg hover:bg-zinc-200 transition-colors flex items-center gap-2">
            立即开始
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6" /></svg>
          </button>
          <button @click="router.push('/chat')" class="px-8 py-3 bg-zinc-800 text-white font-medium rounded-lg hover:bg-zinc-700 transition-colors">对话模式</button>
        </div>

        <!-- 快捷键提示 -->
        <div class="mt-8 flex items-center justify-center gap-6 text-[10px] text-zinc-600">
          <span><kbd class="px-1.5 py-0.5 bg-zinc-800 border border-white/10 rounded text-zinc-400">Ctrl+K</kbd> 对话</span>
          <span><kbd class="px-1.5 py-0.5 bg-zinc-800 border border-white/10 rounded text-zinc-400">Ctrl+N</kbd> 新建任务</span>
          <span><kbd class="px-1.5 py-0.5 bg-zinc-800 border border-white/10 rounded text-zinc-400">Esc</kbd> 返回首页</span>
        </div>
      </div>
    </section>

    <!-- 核心功能 -->
    <section class="py-20 px-6 border-t border-white/5">
      <div class="max-w-6xl mx-auto">
        <h2 class="text-2xl font-bold text-center text-white mb-12">核心功能</h2>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div v-for="feature in features" :key="feature.title"
            class="p-6 rounded-2xl bg-zinc-900/50 border border-white/5 hover:border-white/10 transition-colors">
            <div class="text-3xl mb-4">{{ feature.icon }}</div>
            <h3 class="font-semibold text-white mb-2">{{ feature.title }}</h3>
            <p class="text-sm text-zinc-400">{{ feature.desc }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- 工作流程 -->
    <section class="py-20 px-6 border-t border-white/5">
      <div class="max-w-4xl mx-auto">
        <h2 class="text-2xl font-bold text-center text-white mb-12">工作流程</h2>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-6">
          <div v-for="step in steps" :key="step.num" class="text-center">
            <div class="w-12 h-12 mx-auto mb-4 rounded-full bg-white/5 border border-white/10 flex items-center justify-center">
              <span class="text-sm font-mono text-zinc-400">{{ step.num }}</span>
            </div>
            <h3 class="font-semibold text-white mb-1">{{ step.title }}</h3>
            <p class="text-xs text-zinc-500">{{ step.desc }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- 竞赛倒计时 -->
    <section class="py-16 px-6 border-t border-white/5">
      <div class="max-w-4xl mx-auto">
        <h2 class="text-2xl font-bold text-center text-white mb-4">📅 竞赛倒计时</h2>
        <p class="text-xs text-zinc-500 text-center mb-8">全年建模竞赛，把握每一个节点</p>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div v-for="comp in upcomingComps" :key="comp.id" class="p-4 bg-zinc-900/50 border border-white/5 rounded-lg text-center">
            <p class="text-lg font-bold text-white">{{ comp.month }} 月</p>
            <p class="text-xs text-zinc-400 mt-1 truncate">{{ comp.name }}</p>
            <p class="text-[10px] text-zinc-500 mt-2">{{ comp.months_away === 0 ? '本月' : comp.months_away + ' 个月后' }}</p>
          </div>
        </div>
        <div class="text-center mt-6">
          <button @click="router.push('/knowledge')" class="text-sm text-zinc-400 hover:text-white transition-colors">查看完整日历 →</button>
        </div>
      </div>
    </section>

    <!-- 底部 -->
    <footer class="py-8 px-6 border-t border-white/5">
      <div class="max-w-6xl mx-auto flex items-center justify-between text-sm text-zinc-500">
        <span>© 2026 MathModelPro</span>
        <span>Built with AI</span>
      </div>
    </footer>
  </div>
</template>
