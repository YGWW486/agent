import { Link } from 'react-router-dom'
import { Plus, ArrowRight, GitBranch, Circle } from 'lucide-react'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { useBackend } from '@/hooks/useBackend'
import { useBackendStore } from '@/stores/backend.store'
import { useWorkflowStore } from '@/stores/workflow.store'
import { cn } from '@/lib/cn'

const statusConfig: Record<string, { color: string; label: string }> = {
  running: { color: 'bg-status-running', label: '运行中' },
  starting: { color: 'bg-status-suspended', label: '启动中…' },
  error: { color: 'bg-status-error', label: '异常' },
  stopped: { color: 'bg-status-stopped', label: '已停止' },
}

export function HomePage() {
  useDocumentTitle('首页')
  const { status } = useBackend()
  const backendStatus = useBackendStore((s) => s.status)
  const backendPort = useBackendStore((s) => s.port)
  const backendUptime = useBackendStore((s) => s.uptime)
  const workflows = useWorkflowStore((s) => s.workflows)
  const recentWorkflows = Array.from(workflows.values()).reverse().slice(0, 3)
  const info = statusConfig[status] ?? statusConfig.stopped

  const uptimeText = backendUptime > 0
    ? `${Math.floor(backendUptime / 1000)}s`
    : '—'

  return (
    <div className="flex flex-col items-center justify-center h-full gap-8 px-6 animate-fade-in">
      <div className="text-center space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">
          Agentic Engineering 控制台
        </h1>
        <p className="text-[13px] text-text-muted max-w-sm mx-auto leading-relaxed">
          多 Agent 编码流水线 — Planner → Coder → Reviewer → Merge，人工审批节点
        </p>
      </div>

      {/* Backend status card */}
      <div className="w-full max-w-md rounded-xl border border-white/8 bg-surface-elevated p-4">
        <div className="flex items-center gap-3 mb-3">
          <span className="relative flex h-2.5 w-2.5">
            <span className={cn('absolute inset-0 rounded-full', info.color)} />
            <span className={cn('absolute inset-0 rounded-full animate-ping', info.color, status === 'running' ? 'opacity-50' : 'opacity-0')} />
          </span>
          <span className="text-[13px] font-medium">后端服务</span>
          <span className={cn('text-[12px] ml-auto', info.color.replace('bg-', 'text-'))}>{info.label}</span>
        </div>
        <div className="grid grid-cols-2 gap-3 text-xs text-text-muted">
          <div>
            <span className="block text-[11px]">端口</span>
            <span className="font-mono text-text-secondary">{backendPort}</span>
          </div>
          <div>
            <span className="block text-[11px]">运行时间</span>
            <span className="font-mono text-text-secondary">{uptimeText}</span>
          </div>
        </div>
      </div>

      {/* Primary CTA */}
      <Link
        to="/workflow/new"
        className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-accent hover:bg-accent-hover text-white text-[13px] font-medium transition-colors active:scale-[0.98]"
      >
        <Plus className="w-4 h-4" />
        新建工作流
        <ArrowRight className="w-3.5 h-3.5 opacity-50 -ml-0.5" />
      </Link>

      {/* Recent workflows */}
      {recentWorkflows.length > 0 && (
        <div className="w-full max-w-md space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-text-muted">最近工作流</span>
            <Link to="/workflows" className="text-[11px] text-accent hover:text-accent-hover transition-colors">
              查看全部 →
            </Link>
          </div>
          {recentWorkflows.map((wf) => (
            <Link
              key={wf.threadId}
              to={`/workflow/${wf.threadId}`}
              className="flex items-center gap-3 p-2.5 rounded-lg border border-white/6 bg-surface-elevated hover:border-white/10 transition-colors group"
            >
              <Circle className="w-1.5 h-1.5 text-text-muted fill-current flex-shrink-0" />
              <code className="text-[11px] text-accent font-mono flex-shrink-0">{wf.threadId}</code>
              <span className="text-[12px] text-text-secondary truncate flex-1">
                {wf.spec.slice(0, 50)}{wf.spec.length > 50 ? '…' : ''}
              </span>
              <GitBranch className="w-3 h-3 text-text-muted opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
