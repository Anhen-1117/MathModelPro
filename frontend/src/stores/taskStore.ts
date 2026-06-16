import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import service from '@/utils/request'
import { TaskWebSocket } from '@/utils/websocket'

export interface Task {
  id: string
  name: string
  description?: string
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled'
  language: string
  template_id?: string
  progress: {
    analysis: number
    modeling: number
    coding: number
    paper: number
    overall: number
  }
  agent_status: {
    coordinator: string
    modeler: string
    coder: string
    writer: string
    system?: string  // 系统状态标记（如 real_llm_mode）
  }
  token_usage: Record<string, number>
  tags: string[]
  is_favorite: string
  created_at: string
  updated_at: string
  started_at?: string
  completed_at?: string
  // 详情字段
  problem_text?: string
  problem_pdf_path?: string
  data_files?: any[]
  output_dir?: string
  paper_path?: string
  paper_content?: string
  typst_source?: string
  code?: string
  matlab_code?: string
  figures?: string[]
  literature?: any[]
  notes?: string
}

const API_BASE = '/api/v1'
const V2_API_BASE = '/api/v2'  // 新架构端点

export const useTaskStore = defineStore('task', () => {
  const tasks = ref<Task[]>([])
  const currentTask = ref<Task | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // WebSocket 连接（带自动重连）
  let ws: TaskWebSocket | null = null
  const wsCallbacks: Map<string, (data: any) => void> = new Map()

  // 获取任务列表
  const fetchTasks = async () => {
    loading.value = true
    error.value = null
    try {
      const response = await service.get(`${V2_API_BASE}/tasks`)
      tasks.value = response.data.tasks
    } catch (e: any) {
      error.value = e.message
      console.error('Failed to fetch tasks:', e)
    } finally {
      loading.value = false
    }
  }

  // 获取任务详情
  const fetchTask = async (taskId: string) => {
    loading.value = true
    error.value = null
    try {
      const response = await service.get(`${V2_API_BASE}/tasks/${taskId}`)
      currentTask.value = response.data
      
      // 更新列表中的任务
      const index = tasks.value.findIndex(t => t.id === taskId)
      if (index !== -1) {
        tasks.value[index] = response.data
      }
    } catch (e: any) {
      error.value = e.message
      console.error('Failed to fetch task:', e)
    } finally {
      loading.value = false
    }
  }

  // 创建任务（支持文件上传）
  const createTask = async (data: any, files?: File[]): Promise<string> => {
    loading.value = true
    error.value = null
    try {
      let response: any

      // V2 使用 JSON body
      response = await service.post(`${V2_API_BASE}/tasks`, {
        name: data.name || '',
        description: data.description || '',
        problem_text: data.problem_text || '',
        language: data.language || 'python',
        template_id: data.template_id || 'cumcm',
        notes: data.notes || '',
      }, { timeout: 60000 })

      const newTask = response.data
      tasks.value.unshift(newTask)
      return newTask.id
    } catch (e: any) {
      error.value = e.message
      console.error('Failed to create task:', e)
      throw e
    } finally {
      loading.value = false
    }
  }

  // 更新任务
  const updateTask = async (taskId: string, data: any) => {
    loading.value = true
    error.value = null
    try {
      const response = await service.put(`${API_BASE}/tasks/${taskId}`, data)
      const updatedTask = response.data
      
      // 更新列表
      const index = tasks.value.findIndex(t => t.id === taskId)
      if (index !== -1) {
        tasks.value[index] = updatedTask
      }
      
      // 更新当前任务
      if (currentTask.value?.id === taskId) {
        currentTask.value = { ...currentTask.value, ...updatedTask }
      }
    } catch (e: any) {
      error.value = e.message
      console.error('Failed to update task:', e)
      throw e
    } finally {
      loading.value = false
    }
  }

  // 删除任务
  const deleteTask = async (taskId: string) => {
    loading.value = true
    error.value = null
    try {
      await service.delete(`${V2_API_BASE}/tasks/${taskId}`)
      tasks.value = tasks.value.filter(t => t.id !== taskId)
      
      if (currentTask.value?.id === taskId) {
        currentTask.value = null
      }
    } catch (e: any) {
      error.value = e.message
      console.error('Failed to delete task:', e)
      throw e
    } finally {
      loading.value = false
    }
  }

  // 开始任务
  const startTask = async (taskId: string) => {
    try {
      await service.post(`${V2_API_BASE}/tasks/${taskId}/start`)
      await fetchTask(taskId)
    } catch (e: any) {
      console.error('Failed to start task:', e)
      throw e
    }
  }

  // 暂停任务
  const pauseTask = async (taskId: string) => {
    try {
      await service.post(`${API_BASE}/tasks/${taskId}/pause`)
      await fetchTask(taskId)
    } catch (e: any) {
      console.error('Failed to pause task:', e)
      throw e
    }
  }

  // 恢复任务
  const resumeTask = async (taskId: string) => {
    try {
      await service.post(`${API_BASE}/tasks/${taskId}/resume`)
      await fetchTask(taskId)
    } catch (e: any) {
      console.error('Failed to resume task:', e)
      throw e
    }
  }

  // 取消任务
  const cancelTask = async (taskId: string) => {
    try {
      await service.post(`${API_BASE}/tasks/${taskId}/cancel`)
      await fetchTask(taskId)
    } catch (e: any) {
      console.error('Failed to cancel task:', e)
      throw e
    }
  }

  // 重试任务
  const retryTask = async (taskId: string) => {
    try {
      await service.post(`${API_BASE}/tasks/${taskId}/retry`)
      await fetchTask(taskId)
    } catch (e: any) {
      console.error('Failed to retry task:', e)
      throw e
    }
  }

  // 导出任务
  const exportTask = async (taskId: string) => {
    try {
      const response = await service.post(`${API_BASE}/tasks/${taskId}/export`, null, {
        responseType: 'blob'
      })
      
      // 下载文件
      const url = URL.createObjectURL(response.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `task_${taskId}.zip`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e: any) {
      console.error('Failed to export task:', e)
      throw e
    }
  }

  // 导出论文为 Word (.docx)
  const exportDocx = async (taskId: string, taskName?: string) => {
    try {
      const response = await service.post(`${API_BASE}/tasks/${taskId}/export/docx`, null, {
        responseType: 'blob'
      })
      const url = URL.createObjectURL(response.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `${taskName || '论文'}.docx`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e: any) {
      console.error('Failed to export docx:', e)
      throw e
    }
  }

  // 获取论文预览
  const fetchPaperPreview = async (taskId: string) => {
    try {
      const response = await service.get(`${API_BASE}/preview/${taskId}/paper/content`)
      const index = tasks.value.findIndex(t => t.id === taskId)
      if (index !== -1) {
        tasks.value[index].paper_content = response.data.content
      }
    } catch (e) {
      console.error('Failed to fetch paper preview:', e)
    }
  }

  // 更新论文内容
  const updatePaperContent = async (taskId: string, content: string) => {
    try {
      await service.put(`${API_BASE}/preview/${taskId}/paper/content`, { content })
      const index = tasks.value.findIndex(t => t.id === taskId)
      if (index !== -1) {
        tasks.value[index].paper_content = content
      }
    } catch (e) {
      console.error('Failed to update paper content:', e)
      throw e
    }
  }

  // 获取代码
  const fetchCode = async (taskId: string) => {
    try {
      const response = await service.get(`${API_BASE}/preview/${taskId}/code`)
      const index = tasks.value.findIndex(t => t.id === taskId)
      if (index !== -1) {
        if (response.data.language === 'matlab') {
          tasks.value[index].matlab_code = response.data.content
        } else {
          tasks.value[index].code = response.data.content
        }
      }
    } catch (e) {
      console.error('Failed to fetch code:', e)
    }
  }

  // 更新代码
  const updateCode = async (taskId: string, content: string, language: string) => {
    try {
      await service.put(`${API_BASE}/preview/${taskId}/code`, { content, language })
      const index = tasks.value.findIndex(t => t.id === taskId)
      if (index !== -1) {
        if (language === 'matlab') {
          tasks.value[index].matlab_code = content
        } else {
          tasks.value[index].code = content
        }
      }
    } catch (e) {
      console.error('Failed to update code:', e)
      throw e
    }
  }

  // 运行代码
  const runCode = async (taskId: string, language: string) => {
    try {
      const response = await service.post(`${API_BASE}/preview/${taskId}/code/run`, { language })
      return response.data
    } catch (e) {
      console.error('Failed to run code:', e)
      throw e
    }
  }

  // 获取图表列表
  const fetchFigures = async (taskId: string) => {
    try {
      const response = await service.get(`${API_BASE}/preview/${taskId}/figures`)
      const index = tasks.value.findIndex(t => t.id === taskId)
      if (index !== -1) {
        tasks.value[index].figures = response.data.figures.map((f: any) => f.name)
      }
    } catch (e) {
      console.error('Failed to fetch figures:', e)
    }
  }

  // 导出图表
  const exportFigure = async (taskId: string, filename: string, format: string) => {
    try {
      const response = await service.post(`${API_BASE}/preview/${taskId}/figures/${filename}/export`, { format }, {
        responseType: 'blob'
      })
      
      const url = URL.createObjectURL(response.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `${filename.split('.')[0]}.${format}`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      console.error('Failed to export figure:', e)
      throw e
    }
  }

  // 导出所有图表
  const exportAllFigures = async (taskId: string) => {
    try {
      const response = await service.post(`${API_BASE}/tasks/${taskId}/export`, { type: 'figures' }, {
        responseType: 'blob'
      })
      
      const url = URL.createObjectURL(response.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `figures_${taskId}.zip`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      console.error('Failed to export all figures:', e)
      throw e
    }
  }

  // WebSocket 连接（带自动重连 + 连接状态跟踪）
  const wsConnectionStatus = ref<'connecting' | 'connected' | 'disconnected' | 'reconnecting'>('disconnected')

  // HTTP 轮询降级（当 WebSocket 断开时自动切换）
  let pollingTimer: ReturnType<typeof setInterval> | null = null
  const isPolling = ref(false)

  const startPolling = (taskId: string) => {
    if (pollingTimer) return
    isPolling.value = true
    pollingTimer = setInterval(async () => {
      try {
        const response = await service.get(`${V2_API_BASE}/tasks/${taskId}`)
        const updatedTask = response.data
        if (updatedTask) {
          const index = tasks.value.findIndex(t => t.id === taskId)
          if (index !== -1) {
            tasks.value[index] = { ...tasks.value[index], ...updatedTask }
          }
          // 任务已结束，停止轮询
          if (updatedTask.status === 'completed' || updatedTask.status === 'failed' || updatedTask.status === 'cancelled') {
            stopPolling()
          }
        }
      } catch { /* 静默失败 */ }
    }, 3000)
  }

  const stopPolling = () => {
    if (pollingTimer) {
      clearInterval(pollingTimer)
      pollingTimer = null
    }
    isPolling.value = false
  }

  const connectWebSocket = (taskId: string, callback: (data: any) => void) => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}${API_BASE}/ws/progress/${taskId}`

    // 使用带重连的 TaskWebSocket
    ws = new TaskWebSocket(
      wsUrl,
      (data: any) => {
        // 更新任务进度（从 WebSocket 推送的进度消息）
        if (data.type === 'progress') {
          const index = tasks.value.findIndex(t => t.id === taskId)
          if (index !== -1) {
            // 合并各阶段进度 + 整体进度
            const phases = data.data?.phases || {}
            tasks.value[index].progress = {
              ...tasks.value[index].progress,
              analysis: phases.analysis ?? tasks.value[index].progress.analysis,
              modeling: phases.modeling ?? tasks.value[index].progress.modeling,
              coding: phases.coding ?? tasks.value[index].progress.coding,
              paper: phases.paper ?? tasks.value[index].progress.paper,
              overall: data.data?.overall_progress ?? tasks.value[index].progress.overall,
            }
            tasks.value[index].agent_status = data.data?.agents
              ? { ...tasks.value[index].agent_status, ...data.data.agents }
              : tasks.value[index].agent_status
          }
        }
        callback(data)
      },
      (status) => {
        wsConnectionStatus.value = status
        // WebSocket 断开时启动 HTTP 轮询降级
        if (status === 'disconnected' || status === 'reconnecting') {
          startPolling(taskId)
        } else if (status === 'connected') {
          stopPolling()
        }
      }
    )

    ws.connect()
    wsCallbacks.set(taskId, callback)
  }

  // 断开 WebSocket
  const disconnectWebSocket = (taskId: string) => {
    ws?.close()
    ws = null
    wsCallbacks.delete(taskId)
    stopPolling()
  }

  // 获取任务（带缓存）
  const getTaskById = (taskId: string) => {
    return tasks.value.find(t => t.id === taskId) || null
  }

  return {
    // 状态
    tasks,
    currentTask,
    loading,
    error,
    
    // 方法
    fetchTasks,
    fetchTask,
    createTask,
    updateTask,
    deleteTask,
    startTask,
    pauseTask,
    resumeTask,
    cancelTask,
    retryTask,
    exportTask,
    exportDocx,

    // 论文
    fetchPaperPreview,
    updatePaperContent,
    
    // 代码
    fetchCode,
    updateCode,
    runCode,
    
    // 图表
    fetchFigures,
    exportFigure,
    exportAllFigures,
    
    // WebSocket
    wsConnectionStatus,
    connectWebSocket,
    disconnectWebSocket,

    // 工具
    getTaskById
  }
})
