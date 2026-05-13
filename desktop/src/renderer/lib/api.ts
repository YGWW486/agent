import type {
  StartWorkflowResponse,
  WorkflowState,
  HealthResponse,
  SkillsResponse,
  IndexStats,
} from '../../shared/types'

const REQUEST_TIMEOUT_MS = 30_000

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)

  try {
    const res = await fetch(url, { ...options, signal: controller.signal })
    if (!res.ok) {
      const text = await res.text().catch(() => '').then(t => t.slice(0, 200))
      console.error(`[API] ${res.status} from ${url}:`, text)
      throw new Error(`请求失败 (${res.status})`)
    }
    return res.json().catch(() => ({} as T))
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('请求超时 — 后端可能未响应')
    }
    if ((err as Error).message?.startsWith('Request failed')) throw err
    console.error('[API] 网络错误:', url, err)
    throw new Error(`无法连接后端 (${url}) — 确认 Sidebar 后端为绿灯`)
  } finally {
    clearTimeout(timer)
  }
}

export function createApi(baseUrl: string) {
  const u = (path: string) => `${baseUrl}${path}`

  return {
    listWorkflows() {
      return request<Array<{ thread_id: string; spec: string; status: string; suspended: boolean; error: string }>>(u('/api/workflows'))
    },

    startWorkflow(spec: string, context = '') {
      return request<StartWorkflowResponse>(u('/api/workflow'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ spec, context }),
      })
    },

    getWorkflowStatus(threadId: string) {
      return request<WorkflowState>(u(`/api/workflow/${threadId}`))
    },

    approveWorkflow(threadId: string, approved: boolean, comment = '') {
      return request<{ status: string; message: string }>(
        u(`/api/workflow/${threadId}/approve`),
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ approved, comment }),
        },
      )
    },

    resumeWorkflow(threadId: string, targetNode = 'coder') {
      return request<{ status: string; message: string }>(
        u(`/api/workflow/${threadId}/resume`),
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ target_node: targetNode }),
        },
      )
    },

    async restoreWorkflow(threadId: string) {
      return request<{ restored: string[]; backup_dir: string }>(
        u(`/api/workflow/${threadId}/restore`),
        { method: 'POST' },
      )
    },

    async deleteWorkflow(threadId: string) {
      return request<{ deleted: boolean }>(u(`/api/workflow/${threadId}`), { method: 'DELETE' })
    },

    getStreamUrl(threadId: string) {
      return u(`/api/workflow/${threadId}/stream`)
    },

    getSkills() {
      return request<SkillsResponse>(u('/api/skills'))
    },

    healthCheck() {
      return request<HealthResponse>(u('/api/health'))
    },

    rebuildIndex(graphPath: string) {
      return request<IndexStats>(u('/api/index/rebuild'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ graph_path: graphPath }),
      })
    },

    getContext(files: string[], depth = 2) {
      const qs = `files=${files.map(encodeURIComponent).join(',')}&depth=${depth}`
      return request<{ nodes: unknown[]; edges: unknown[]; file_summaries: Record<string, string> }>(
        u(`/api/context?${qs}`),
      )
    },
  }
}

export type Api = ReturnType<typeof createApi>
