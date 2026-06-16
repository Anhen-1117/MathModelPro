import { ref } from 'vue'

interface ConfirmOptions {
  title: string
  description?: string
  confirmText?: string
  cancelText?: string
  variant?: 'default' | 'danger'
}

const isOpen = ref(false)
const options = ref<ConfirmOptions>({ title: '' })
let resolvePromise: ((value: boolean) => void) | null = null

export function useConfirm() {
  function confirm(opts: ConfirmOptions): Promise<boolean> {
    options.value = {
      confirmText: '确认',
      cancelText: '取消',
      variant: 'default',
      ...opts
    }
    isOpen.value = true

    return new Promise<boolean>((resolve) => {
      resolvePromise = resolve
    })
  }

  function handleConfirm() {
    isOpen.value = false
    resolvePromise?.(true)
    resolvePromise = null
  }

  function handleCancel() {
    isOpen.value = false
    resolvePromise?.(false)
    resolvePromise = null
  }

  return {
    isOpen,
    options,
    confirm,
    handleConfirm,
    handleCancel
  }
}
