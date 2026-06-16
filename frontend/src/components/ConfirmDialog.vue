<script setup lang="ts">
import { useConfirm } from '@/composables/useConfirm'

const { isOpen, options, handleConfirm, handleCancel } = useConfirm()
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="isOpen" class="fixed inset-0 z-[100] flex items-center justify-center">
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="handleCancel"></div>
        
        <div class="relative w-full max-w-sm mx-4 bg-[#111111] border border-white/10 rounded-xl shadow-2xl overflow-hidden">
          <div class="p-6">
            <h3 class="text-base font-medium text-white mb-2">{{ options.title }}</h3>
            <p v-if="options.description" class="text-sm text-zinc-400">{{ options.description }}</p>
          </div>
          
          <div class="px-6 py-4 border-t border-white/5 flex justify-end gap-3">
            <button 
              @click="handleCancel"
              class="px-4 py-2 text-sm text-zinc-400 hover:text-white transition-colors rounded-lg hover:bg-white/5"
            >
              {{ options.cancelText }}
            </button>
            <button 
              @click="handleConfirm"
              :class="[
                'px-4 py-2 text-sm font-medium rounded-lg transition-colors',
                options.variant === 'danger'
                  ? 'bg-red-600 text-white hover:bg-red-700'
                  : 'bg-white text-black hover:bg-zinc-200'
              ]"
            >
              {{ options.confirmText }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
