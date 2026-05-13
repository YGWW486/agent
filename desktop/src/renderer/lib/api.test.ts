import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createApi } from './api'

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

function mockResponse(data: unknown, ok = true, status = 200) {
  return {
    ok,
    status,
    json: async () => data,
  }
}

describe('createApi', () => {
  let api: ReturnType<typeof createApi>

  beforeEach(() => {
    vi.clearAllMocks()
    api = createApi('http://127.0.0.1:8000')
  })

  describe('startWorkflow', () => {
    it('POSTs spec to /api/workflow and returns thread_id', async () => {
      mockFetch.mockResolvedValueOnce(
        mockResponse({ thread_id: 'abc12345', status: 'started', stream_url: '/api/workflow/abc12345/stream' }),
      )

      const result = await api.startWorkflow('build a login page', 'context here')

      expect(mockFetch).toHaveBeenCalledWith(
        'http://127.0.0.1:8000/api/workflow',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ spec: 'build a login page', context: 'context here' }),
        }),
      )
      expect(result.thread_id).toBe('abc12345')
    })

    it('throws on non-ok response', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse({ detail: 'error' }, false, 500))

      await expect(api.startWorkflow('spec')).rejects.toThrow()
    })
  })

  describe('getWorkflowStatus', () => {
    it('fetches status and returns parsed state', async () => {
      mockFetch.mockResolvedValueOnce(
        mockResponse({ thread_id: 'x', status: 'running', code: '', revision_count: 0 }),
      )

      const state = await api.getWorkflowStatus('x')

      expect(state.status).toBe('running')
      expect(mockFetch).toHaveBeenCalledWith(
        'http://127.0.0.1:8000/api/workflow/x',
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      )
    })
  })

  describe('approveWorkflow', () => {
    it('POSTs approval', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse({ status: 'merged' }))

      await api.approveWorkflow('x', true, 'lgtm')

      const call = mockFetch.mock.calls[0]
      expect(call[0]).toContain('/api/workflow/x/approve')
      expect(JSON.parse((call[1] as RequestInit).body as string)).toEqual({
        approved: true,
        comment: 'lgtm',
      })
    })
  })

  describe('resumeWorkflow', () => {
    it('POSTs resume with target node', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse({ status: 'coding' }))

      await api.resumeWorkflow('x', 'coder')

      expect(mockFetch).toHaveBeenCalledWith(
        'http://127.0.0.1:8000/api/workflow/x/resume',
        expect.objectContaining({
          body: JSON.stringify({ target_node: 'coder' }),
        }),
      )
    })
  })

  describe('healthCheck', () => {
    it('returns health status', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse({ status: 'ok', model: 'claude-sonnet-4-6' }))

      const health = await api.healthCheck()

      expect(health.status).toBe('ok')
      expect(health.model).toBe('claude-sonnet-4-6')
    })

    it('throws when backend is down', async () => {
      mockFetch.mockRejectedValueOnce(new Error('ECONNREFUSED'))

      await expect(api.healthCheck()).rejects.toThrow('无法连接后端')
    })
  })

  describe('getStreamUrl', () => {
    it('returns the SSE stream URL for a thread', () => {
      const url = api.getStreamUrl('abc123')

      expect(url).toContain('/api/workflow/abc123/stream')
      expect(url).toContain('http://127.0.0.1:8000')
    })
  })

  describe('getSkills', () => {
    it('fetches skills list', async () => {
      mockFetch.mockResolvedValueOnce(
        mockResponse({ workflow: 'planner→coder→reviewer→merge', features: ['a', 'b'] }),
      )

      const skills = await api.getSkills()

      expect(skills.workflow).toContain('planner')
    })
  })

  describe('rebuildIndex', () => {
    it('POSTs graph path to rebuild index', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse({ node_count: 42, edge_count: 100, files_indexed: 15, loaded_at: '' }))

      const stats = await api.rebuildIndex('/path/to/graph.json')

      expect(stats.node_count).toBe(42)
      expect(mockFetch).toHaveBeenCalledWith(
        'http://127.0.0.1:8000/api/index/rebuild',
        expect.objectContaining({
          body: JSON.stringify({ graph_path: '/path/to/graph.json' }),
        }),
      )
    })
  })

  describe('getContext', () => {
    it('fetches context for file list', async () => {
      mockFetch.mockResolvedValueOnce(mockResponse({ nodes: [], edges: [], file_summaries: {} }))

      const ctx = await api.getContext(['a.py', 'b.py'], 3)

      expect(ctx.nodes).toEqual([])
      const url = mockFetch.mock.calls[0][0] as string
      expect(url).toContain('files=a.py')
      expect(url).toContain('depth=3')
    })
  })
})
