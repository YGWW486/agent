import { useCallback, useRef } from 'react'
import { useSSE } from './useSSE'
import { useApi } from './useApi'
import { useWorkflowStore } from '@/stores/workflow.store'
import type { SSEEvent, TimelineNode, NodeStatus } from '../../shared/types'

const NODE_LABELS: Record<string, string> = {
  planner: 'Planner',
  coder: 'Coder',
  reviewer: 'Reviewer',
  merge: 'Merge',
}

function createInitialNodes(): TimelineNode[] {
  return ['planner', 'coder', 'reviewer', 'merge'].map((name) => ({
    name,
    label: NODE_LABELS[name] ?? name,
    status: 'pending' as NodeStatus,
    summary: null,
    started_at: null,
    completed_at: null,
    suspended: false,
    failure_reason: '',
  }))
}

export function useWorkflow(threadId: string | null) {
  const api = useApi()
  const updateWorkflow = useWorkflowStore((s) => s.updateWorkflow)
  const nodesRef = useRef<TimelineNode[]>([])

  const handleEvent = useCallback(
    (event: SSEEvent) => {
      if (!threadId) return

      switch (event.event) {
        case 'node_start': {
          const nodeName = event.node ?? ''
          nodesRef.current = nodesRef.current.map((n) =>
            n.name === nodeName
              ? { ...n, status: 'running' as const, started_at: event.timestamp ?? null }
              : n,
          )
          updateWorkflow(threadId, { nodes: [...nodesRef.current] })
          break
        }
        case 'node_complete': {
          const nodeName = event.node ?? ''
          const nodeStatus: NodeStatus = event.suspended
            ? event.failure_reason
              ? 'failed'
              : 'suspended'
            : 'success'
          nodesRef.current = nodesRef.current.map((n) =>
            n.name === nodeName
              ? {
                  ...n,
                  status: nodeStatus,
                  completed_at: event.timestamp ?? null,
                  summary: event.summary ?? null,
                  suspended: event.suspended ?? false,
                  failure_reason: event.failure_reason ?? '',
                }
              : n,
          )
          updateWorkflow(threadId, { nodes: [...nodesRef.current] })
          break
        }
        case 'interrupt': {
          updateWorkflow(threadId, { interrupt: true })
          break
        }
        case 'workflow_complete': {
          updateWorkflow(threadId, { error: '' })
          break
        }
        case 'workflow_error': {
          updateWorkflow(threadId, { error: event.error ?? 'Unknown error' })
          break
        }
      }
    },
    [threadId, updateWorkflow],
  )

  // Initialize nodes when threadId changes
  if (threadId) {
    const existing = useWorkflowStore.getState().getWorkflow(threadId)
    if (existing && existing.nodes.length === 0) {
      nodesRef.current = createInitialNodes()
      updateWorkflow(threadId, { nodes: [...nodesRef.current] })
    } else if (existing) {
      nodesRef.current = existing.nodes
    }
  }

  const streamUrl = threadId ? api.getStreamUrl(threadId) : ''

  const onStatusRefresh = useCallback(async () => {
    if (!threadId) return
    try {
      const state = await api.getWorkflowStatus(threadId)
      updateWorkflow(threadId, {
        error: state.error,
        result: state.code,
      })
    } catch (err) {
      if ((err as Error).message?.includes('404')) {
        updateWorkflow(threadId, { error: '工作流已过期' })
        throw err // 阻止 SSE 重连循环
      }
      console.error('[useWorkflow] 状态刷新失败:', err)
    }
  }, [threadId, api, updateWorkflow])

  const { connected, error } = useSSE({
    threadId,
    streamUrl,
    onEvent: handleEvent,
    onStatusRefresh,
  })

  return { connected, error }
}
