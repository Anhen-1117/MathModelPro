<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const isLogin = ref(true)
const email = ref('')
const password = ref('')

const handleSubmit = () => {
  router.push('/')
}
</script>

<template>
  <div class="min-h-screen bg-[#0a0a0b] flex items-center justify-center p-8">
    <div class="w-full max-w-sm">
      <div class="text-center mb-8">
        <div class="w-12 h-12 mx-auto mb-4 rounded-xl bg-gradient-to-br from-violet-500 to-indigo-500 flex items-center justify-center">
          <span class="text-xl font-bold">M</span>
        </div>
        <h1 class="text-xl font-semibold text-white">MathModelPro</h1>
        <p class="text-sm text-zinc-500 mt-1">{{ isLogin ? '登录你的账号' : '创建新账号' }}</p>
      </div>

      <div class="bg-zinc-900/50 border border-white/5 rounded-xl p-6">
        <div class="flex bg-zinc-800 rounded-lg p-0.5 mb-6">
          <button 
            @click="isLogin = true"
            :class="[
              'flex-1 py-2 text-sm font-medium rounded-md transition-colors',
              isLogin ? 'bg-zinc-700 text-white' : 'text-zinc-400 hover:text-white'
            ]"
          >
            登录
          </button>
          <button 
            @click="isLogin = false"
            :class="[
              'flex-1 py-2 text-sm font-medium rounded-md transition-colors',
              !isLogin ? 'bg-zinc-700 text-white' : 'text-zinc-400 hover:text-white'
            ]"
          >
            注册
          </button>
        </div>

        <div class="space-y-4">
          <div>
            <label class="block text-xs text-zinc-400 mb-1.5">邮箱</label>
            <input 
              v-model="email"
              type="email"
              placeholder="your@email.com"
              class="w-full px-3 py-2 bg-zinc-800 border border-white/10 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-white/20"
            />
          </div>
          
          <div>
            <label class="block text-xs text-zinc-400 mb-1.5">密码</label>
            <input 
              v-model="password"
              type="password"
              placeholder="••••••••"
              class="w-full px-3 py-2 bg-zinc-800 border border-white/10 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-white/20"
            />
          </div>

          <button 
            @click="handleSubmit"
            class="w-full py-2.5 bg-white text-black text-sm font-medium rounded-lg hover:bg-zinc-200 transition-colors"
          >
            {{ isLogin ? '登录' : '注册' }}
          </button>
        </div>

        <div class="flex items-center gap-4 my-6">
          <div class="flex-1 h-px bg-white/10"></div>
          <span class="text-xs text-zinc-500">或者</span>
          <div class="flex-1 h-px bg-white/10"></div>
        </div>

        <button 
          @click="router.push('/')"
          class="w-full py-2.5 bg-zinc-800 hover:bg-zinc-700 text-white text-sm font-medium rounded-lg transition-colors"
        >
          跳过，直接使用
        </button>
      </div>
    </div>
  </div>
</template>
