import { cn } from '@/lib/cn'
import { NodeCard } from './NodeCard'
import type { TimelineNode } from '../../../shared/types'

interface TimelineProps {
  nodes: TimelineNode[]
  renderDetail?: (node: TimelineNode) => React.ReactNode
}

const stageColor: Record<string, string> = {
  planner: 'bg-stage-planner',
  coder: 'bg-stage-coder',
  reviewer: 'bg-stage-reviewer',
  merge: 'bg-stage-merge',
}

const stageBorder: Record<string, string> = {
  planner: 'border-stage-planner/30',
  coder: 'border-stage-coder/30',
  reviewer: 'border-stage-reviewer/30',
  merge: 'border-stage-merge/30',
}

export function Timeline({ nodes, renderDetail }: TimelineProps) {
  if (nodes.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 py-12 text-center">
        <div className="w-8 h-8 rounded-full bg-surface-overlay flex items-center justify-center">
          <span className="text-text-muted text-sm">—</span>
        </div>
        <p className="text-[13px] text-text-muted">等待工作流启动…</p>
        <p className="text-[11px] text-text-muted">流水线节点将在此处逐一显示。</p>
      </div>
    )
  }

  return (
    <div className="relative">
      <div className="absolute left-[24px] top-4 bottom-4 w-px bg-white/6" aria-hidden="true" />

      <div className="space-y-1.5">
        {nodes.map((node, i) => (
          <div key={node.name} className="relative pl-12 animate-fade-in" style={{ animationDelay: `${i * 80}ms`, animationFillMode: 'backwards' }}>
            <div
              className={cn(
                'absolute left-[20px] top-[20px] w-[9px] h-[9px] rounded-full border-2 z-10 bg-surface-elevated',
                node.status === 'running'
                  ? cn(stageColor[node.name], 'border-transparent animate-pulse-dot')
                  : node.status === 'success'
                    ? cn(stageColor[node.name], 'border-transparent')
                    : node.status === 'failed'
                      ? 'bg-status-error border-status-error/30'
                      : 'bg-status-pending border-white/10',
              )}
              aria-hidden="true"
            />

            <div className={cn('rounded-lg border-l-2', stageBorder[node.name])}>
              <NodeCard node={node}>
                {renderDetail?.(node)}
              </NodeCard>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
