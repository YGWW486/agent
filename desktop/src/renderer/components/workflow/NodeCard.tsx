import { useState, useEffect } from 'react'
import { ChevronDown } from 'lucide-react'
import { cn } from '@/lib/cn'
import type { TimelineNode, NodeStatus } from '../../../shared/types'

const statusColors: Record<NodeStatus, string> = {
  pending: 'bg-status-stopped',
  running: 'bg-status-running animate-pulse-dot',
  success: 'bg-status-running',
  failed: 'bg-status-error',
  suspended: 'bg-status-suspended',
}

const statusLabels: Record<NodeStatus, string> = {
  pending: '等待中',
  running: '运行中',
  success: '已完成',
  failed: '失败',
  suspended: '挂起',
}

const nodeNameLabels: Record<string, string> = {
  planner: 'Planner · 任务拆解',
  coder: 'Coder · 代码生成',
  reviewer: 'Reviewer · 代码审查',
  merge: 'Merge · 合入审批',
}

export function nodeLabel(name: string): string {
  return nodeNameLabels[name] ?? name
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

interface NodeCardProps {
  node: TimelineNode
  children?: React.ReactNode
}

export function NodeCard({ node, children }: NodeCardProps) {
  const [expanded, setExpanded] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const hasChildren = Boolean(children)

  // 运行中的节点每秒更新耗时
  useEffect(() => {
    if (node.status !== 'running' || !node.started_at) {
      setElapsed(0)
      return
    }
    const started = new Date(node.started_at).getTime()
    const tick = () => setElapsed(Date.now() - started)
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [node.status, node.started_at])

  const duration =
    node.status === 'running' && node.started_at
      ? elapsed
      : node.started_at && node.completed_at
        ? new Date(node.completed_at).getTime() - new Date(node.started_at).getTime()
        : null

  return (
    <div
      className={cn(
        'rounded-lg border transition-colors',
        node.status === 'running'
          ? 'border-accent/30 bg-accent/5'
          : node.status === 'failed'
            ? 'border-status-error/20 bg-status-error/5'
            : node.status === 'suspended'
              ? 'border-status-suspended/20 bg-status-suspended/5'
              : 'border-white/8 bg-surface-elevated',
      )}
    >
      <button
        type="button"
        onClick={() => hasChildren && setExpanded(!expanded)}
        className={cn(
          'w-full flex items-center gap-3 px-4 py-3 text-left',
          hasChildren && 'cursor-pointer hover:bg-white/5 rounded-t-lg',
          !hasChildren && 'rounded-lg',
        )}
      >
        <span className={cn('w-2.5 h-2.5 rounded-full flex-shrink-0', statusColors[node.status])} />

        <span className="text-sm font-medium flex-1">{nodeLabel(node.name)}</span>

        {duration && (
          <span className="text-xs text-text-muted font-mono">{formatDuration(duration)}</span>
        )}

        <span
          className={cn(
            'text-xs px-2 py-0.5 rounded-full font-medium',
            node.status === 'success' && 'bg-status-running/15 text-status-running',
            node.status === 'running' && 'bg-accent/15 text-accent',
            node.status === 'failed' && 'bg-status-error/15 text-status-error',
            node.status === 'suspended' && 'bg-status-suspended/15 text-status-suspended',
            node.status === 'pending' && 'bg-white/5 text-text-muted',
          )}
        >
          {statusLabels[node.status]}
        </span>

        {hasChildren && (
          <ChevronDown
            className={cn(
              'w-4 h-4 text-text-muted transition-transform',
              expanded && 'rotate-180',
            )}
          />
        )}
      </button>

      {expanded && children && (
        <div className="px-4 pb-4 pt-1 border-t border-white/5">{children}</div>
      )}
    </div>
  )
}

export { statusColors, statusLabels }
export type { NodeStatus }
