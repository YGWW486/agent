import { useCallback, useRef } from 'react'
import { useSSE } from './useSSE'
import { useApi } from './useApi'
import { useWorkflowStore } from '@/stores/workflow.store'
import type { SSEEvent, TimelineNode, NodeStatus, ToolStepStatus } from '../../shared/types'

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
    tool_steps: [],
  }))
}

function appendCoderToolStep(
  nodes: TimelineNode[],
  step: { tool: string; status: ToolStepStatus; summary: string; input?: Record<string, unknown>; timestamp?: string },
): TimelineNode[] {
  return nodes.map((n) =>
    n.name === 'coder'
      ? { ...n, tool_steps: [...(n.tool_steps ?? []), step] }
      : n,
  )
}

function updateCoderToolResult(
  nodes: TimelineNode[],
  tool: string,
  status: ToolStepStatus,
  summary: string,
): TimelineNode[] {
  return nodes.map((n) => {
    if (n.name !== 'coder') return n
    const steps = [...(n.tool_steps ?? [])]
    for (let i = steps.length - 1; i >= 0; i--) {
      if (steps[i].tool === tool && steps[i].status === 'running') {
        steps[i] = { ...steps[i], status, summary }
        break
      }
    }
    return { ...n, tool_steps: steps }
  })
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
          const obsStatus = event.status
          let nodeStatus: NodeStatus = event.suspended
            ? event.failure_reason
              ? 'failed'
              : 'suspended'
            : 'success'
          if (obsStatus === 'error') nodeStatus = 'failed'
          else if (obsStatus === 'warning' && !event.suspended) nodeStatus = 'success'

          const detail =
            event.detail ??
            (typeof event.summary === 'object' && event.summary !== null
              ? (event.summary as Record<string, unknown>)
              : null)

          nodesRef.current = nodesRef.current.map((n) =>
            n.name === nodeName
              ? {
                  ...n,
                  status: nodeStatus,
                  completed_at: event.timestamp ?? null,
                  summary: detail,
                  observation_summary:
                    typeof event.summary === 'string' ? event.summary : n.observation_summary,
                  next_actions: event.next_actions ?? [],
                  suspended: event.suspended ?? false,
                  failure_reason: event.failure_reason ?? '',
                }
              : n,
          )
          updateWorkflow(threadId, { nodes: [...nodesRef.current] })
          break
        }
        case 'tool_call': {
          nodesRef.current = appendCoderToolStep(nodesRef.current, {
            tool: event.tool ?? 'unknown',
            status: 'running',
            summary: '',
            input: event.input,
            timestamp: event.timestamp,
          })
          updateWorkflow(threadId, { nodes: [...nodesRef.current] })
          break
        }
        case 'tool_result': {
          const st = (event.status ?? 'success') as ToolStepStatus
          const text = event.tool_summary ?? (typeof event.summary === 'string' ? event.summary : '')
          nodesRef.current = updateCoderToolResult(
            nodesRef.current,
            event.tool ?? 'unknown',
            st,
            text,
          )
          updateWorkflow(threadId, { nodes: [...nodesRef.current] })
          break
        }
        case 'interrupt': {
          updateWorkflow(threadId, {
            interrupt: true,
            hitl_next_actions: event.next_actions ?? ['approve', 'revise'],
          })
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
