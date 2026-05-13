import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { useWorkflowStore } from '@/stores/workflow.store'
import { useApi } from '@/hooks/useApi'
import { cn } from '@/lib/cn'
import { GitBranch, ArrowRight, Plus, Loader2, Trash2 } from 'lucide-react'

interface WorkflowSummary {
  thread_id: string
  spec: string
  status: string
  suspended: boolean
  error: string
}

function statusBadge(status: string, suspended: boolean) {
  if (suspended) return { label: '挂起', color: 'text-status-suspended bg-status-suspended/10' }
  if (status === 'approved' || status === 'completed') return { label: '已完成', color: 'text-status-running bg-status-running/10' }
  if (status === 'failed' || status === 'timeout') return { label: '失败', color: 'text-status-error bg-status-error/10' }
  if (status === 'running' || status === 'coding' || status === 'reviewing') return { label: '运行中', color: 'text-accent bg-accent/10' }
  return { label: status || '未知', color: 'text-text-muted bg-white/5' }
}

export function WorkflowsPage() {
  useDocumentTitle('工作流')
  const api = useApi()
  const localWorkflows = useWorkflowStore((s) => s.workflows)
  const addWorkflow = useWorkflowStore((s) => s.addWorkflow)
  const [history, setHistory] = useState<WorkflowSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState<string | null>(null)

  const handleDelete = async (threadId: string) => {
    if (deleting) return
    setDeleting(threadId)
    try {
      await api.deleteWorkflow(threadId)
      setHistory((prev) => prev.filter((w) => w.thread_id !== threadId))
      // 也从本地 store 移除
      useWorkflowStore.getState().removeWorkflow(threadId)
    } catch {
      // 静默失败
    } finally {
      setDeleting(null)
    }
  }

  // 启动时从后端加载历史工作流，并同步到本地 store
  useEffect(() => {
    api.listWorkflows().then((list) => {
      setHistory(list)
      for (const wf of list) {
        if (!localWorkflows.has(wf.thread_id)) {
          addWorkflow(wf.thread_id, wf.spec)
        }
      }
      setLoading(false)
    }).catch(() => setLoading(false))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // 合并历史 + 本地
  const allIds = new Set<string>()
  const merged: WorkflowSummary[] = []
  for (const wf of history) {
    if (!allIds.has(wf.thread_id)) {
      allIds.add(wf.thread_id)
      merged.push(wf)
    }
  }
  for (const [tid, state] of localWorkflows) {
    if (!allIds.has(tid)) {
      allIds.add(tid)
      merged.push({ thread_id: tid, spec: state.spec, status: '', suspended: state.interrupt, error: state.error })
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48">
        <Loader2 className="w-5 h-5 text-text-muted animate-spin" />
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold mb-1">工作流</h2>
          <p className="text-sm text-text-muted">查看所有已提交的工作流及其执行状态，重启后历史记录仍然保留。</p>
        </div>
        <Link
          to="/workflow/new"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-accent hover:bg-accent-hover text-white transition-colors"
        >
          <Plus className="w-3.5 h-3.5" strokeWidth={2.5} />
          新建
        </Link>
      </div>

      {merged.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-16 text-center">
          <div className="w-12 h-12 rounded-full bg-surface-overlay flex items-center justify-center">
            <GitBranch className="w-5 h-5 text-text-muted" />
          </div>
          <p className="text-sm text-text-muted">暂无工作流</p>
          <Link
            to="/workflow/new"
            className="flex items-center gap-1.5 text-xs text-accent hover:text-accent-hover transition-colors"
          >
            创建第一个工作流 <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
      ) : (
        <div className="space-y-1.5">
          {merged.map((wf) => {
            const badge = statusBadge(wf.status, wf.suspended)
            return (
              <div
                key={wf.thread_id}
                className="flex items-center gap-3 p-3 rounded-lg border border-white/6 bg-surface-elevated hover:border-white/12 hover:bg-surface-overlay transition-all group"
              >
                <Link to={`/workflow/${wf.thread_id}`} className="flex items-center gap-4 flex-1 min-w-0">
                  <code className="text-xs text-accent font-mono w-16 flex-shrink-0 truncate">
                    {wf.thread_id}
                  </code>
                  <span className="flex-1 text-[13px] text-text-primary truncate">
                    {wf.spec.slice(0, 80)}{wf.spec.length > 80 ? '…' : ''}
                  </span>
                  <span className={cn('text-[11px] px-2 py-0.5 rounded-full font-medium flex-shrink-0', badge.color)}>
                    {badge.label}
                  </span>
                  <ArrowRight className="w-3.5 h-3.5 text-text-muted opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
                </Link>
                <button
                  type="button"
                  onClick={() => handleDelete(wf.thread_id)}
                  disabled={deleting === wf.thread_id}
                  className="p-1 rounded text-text-muted hover:text-status-error hover:bg-status-error/10 opacity-0 group-hover:opacity-100 transition-all flex-shrink-0"
                  title="删除"
                >
                  {deleting === wf.thread_id ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Trash2 className="w-3.5 h-3.5" />
                  )}
                </button>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
