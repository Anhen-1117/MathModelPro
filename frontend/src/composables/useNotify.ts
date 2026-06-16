import { toast } from '@/components/ui/toast/use-toast'

export function useNotify() {
  function success(title: string, description?: string) {
    toast({
      title: `✅ ${title}`,
      description,
      variant: 'success',
    })
  }

  function error(title: string, description?: string) {
    toast({
      title: `❌ ${title}`,
      description,
      variant: 'destructive',
    })
  }

  function warning(title: string, description?: string) {
    toast({
      title: `⚠️ ${title}`,
      description,
      variant: 'warning',
    })
  }

  function info(title: string, description?: string) {
    toast({
      title: `ℹ️ ${title}`,
      description,
      variant: 'info',
    })
  }

  return { success, error, warning, info }
}
