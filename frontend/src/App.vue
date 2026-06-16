<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { Toaster } from '@/components/ui/toast'
import ConfirmDialog from '@/components/ConfirmDialog.vue'

const router = useRouter()

// 全局快捷键
const handleKeydown = (e: KeyboardEvent) => {
  // Ctrl+K: 搜索（跳转到对话页）
  if (e.ctrlKey && e.key === 'k') {
    e.preventDefault()
    router.push('/chat')
  }
  // Ctrl+N: 新建任务
  if (e.ctrlKey && e.key === 'n') {
    e.preventDefault()
    router.push('/tasks')
  }
  // Esc: 返回首页
  if (e.key === 'Escape') {
    router.push('/')
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <router-view v-slot="{ Component }">
    <Transition name="page" mode="out-in">
      <component :is="Component" />
    </Transition>
  </router-view>
  <Toaster />
  <ConfirmDialog />
</template>

<style>
/* 页面切换动画 */
.page-enter-active,
.page-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.page-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.page-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

/* 通用过渡 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* 滚动条样式 */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}
</style>
