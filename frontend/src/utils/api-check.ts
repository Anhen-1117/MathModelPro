import service from '@/utils/request'

/** API 配置状态 */
export interface ApiConfigStatus {
  configured: boolean
  agents: {
    coordinator: boolean
    modeler: boolean
    coder: boolean
    writer: boolean
  }
  message: string
}

/** 检查 API 是否已配置（识别脱敏 Key） */
export async function checkApiConfig(): Promise<ApiConfigStatus> {
  try {
    const res = await service.get('/api/v2/settings')
    const api = res.data?.api

    if (!api) {
      return {
        configured: false,
        agents: { coordinator: false, modeler: false, coder: false, writer: false },
        message: '未找到 API 配置'
      }
    }

    // 识别脱敏 Key（含 **** 表示后端返回的是脱敏版本，真实 Key 在 localStorage）
    const isRealKey = (key: string) => !!(key && key.length > 0 && !key.includes('****'))

    const agents = {
      coordinator: isRealKey(api.coordinator?.apiKey),
      modeler: isRealKey(api.modeler?.apiKey),
      coder: isRealKey(api.coder?.apiKey),
      writer: isRealKey(api.writer?.apiKey)
    }

    const configuredCount = Object.values(agents).filter(Boolean).length
    const configured = configuredCount > 0

    return {
      configured,
      agents,
      message: configured
        ? `已配置 ${configuredCount}/4 个 Agent`
        : '请先配置至少一个 Agent 的 API Key（当前 Key 无效或未配置）'
    }
  } catch {
    return {
      configured: false,
      agents: { coordinator: false, modeler: false, coder: false, writer: false },
      message: '无法连接后端服务'
    }
  }
}
