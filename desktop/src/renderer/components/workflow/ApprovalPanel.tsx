import { useState } from 'react'
import { Check, X, AlertTriangle } from 'lucide-react'
import { useApi } from '@/hooks/useApi'
import { useWorkflowStore } from '@/stores/workflow.store'
import type { TimelineNode } from '../../../shared/types'

interface ApprovalPanelProps {
  threadId: string
  nodes: TimelineNode[]
}

export function ApprovalPanel({ threadId, nodes }: ApprovalPanelProps) {
  const api = useApi()
  const updateWorkflow = useWorkflowStore((s) => s.updateWorkflow)
  const [submitting, setSubmitting] = useState(false)
  const [rejectReason, setRejectReason] = useState('')
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)

  const reviewer = nodes.find((n) => n.name === 'reviewer')
  const coder = nodes.find((n) => n.name === 'coder')
  const reviewerSummary = (reviewer?.summary ?? {}) as Record<string, unknown>
  const coderSummary = (coder?.summary ?? {}) as Record<string, unknown>

  const handleAction = async (approved: boolean) => {
    if (!approved && !rejectReason.trim()) return

    setSubmitting(true)
    setError('')

    try {
      const result = await api.approveWorkflow(threadId, approved, approved ? '' : rejectReason.trim())

      if (approved) {
        updateWorkflow(threadId, {
          interrupt: false,
          result: (result as { code?: string }).code ?? '',
        })
      } else {
        updateWorkflow(threadId, { interrupt: false })
      }

      setDone(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : '审批失败')
    } finally {
      setSubmitting(false)
    }
  }

  if (done) {
    return (
      <div className="p-4 rounded-lg border border-status-running/25 bg-status-running/5">
        <p className="text-sm text-status-running">已提交审批决定，工作流将继续执行。</p>
      </div>
    )
  }

  return (
    <div className="space-y-4 p-4 rounded-lg border border-status-suspended/25 bg-status-suspended/5">
      <div className="flex items-center gap-2">
        <AlertTriangle className="w-5 h-5 text-status-suspended" />
        <span className="text-sm font-semibold text-status-suspended">工作流已暂停 — 等待人工审批</span>
      </div>

      <div className="grid grid-cols-2 gap-3 text-xs">
        {coder && coderSummary.task_index !== undefined && (
          <div className="p-2 rounded bg-surface-overlay">
            <span className="text-text-muted">Coder 任务</span>
            <div className="font-mono mt-0.5">
              #{(coderSummary.task_index as number) + 1} | {coderSummary.code_len ?? 0} 字符
            </div>
          </div>
        )}
        {reviewer && (
          <div className="p-2 rounded bg-surface-overlay">
            <span className="text-text-muted">Reviewer 结论</span>
            <div className="font-semibold mt-0.5" style={{ color: reviewerSummary.verdict === 'PASS' ? 'oklch(68% 0.18 140)' : 'oklch(65% 0.2 20)' }}>
              {reviewerSummary.verdict === 'PASS' ? '通过' : reviewerSummary.verdict === 'REJECT' ? '拒绝' : '未知'}
            </div>
          </div>
        )}
      </div>

      {error && (
        <div role="alert" className="p-2 rounded bg-status-error/15 text-status-error text-xs">
          {error}
        </div>
      )}

      <div>
        <label htmlFor="reject-reason" className="block text-xs font-medium text-text-muted mb-1">
          拒绝理由 <span className="text-status-error">*</span>
        </label>
        <textarea
          id="reject-reason"
          rows={3}
          maxLength={2000}
          value={rejectReason}
          onChange={(e) => setRejectReason(e.target.value)}
          placeholder="拒绝时必填 — 说明代码需要修改的具体原因…"
          className="w-full rounded-md border border-white/10 bg-surface-overlay px-3 py-2 text-xs text-text-primary placeholder:text-text-muted resize-y"
        />
      </div>

      <div className="flex gap-3">
        <button
          type="button"
          disabled={submitting}
          onClick={() => handleAction(true)}
          className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-md text-sm font-medium bg-status-running/20 text-status-running hover:bg-status-running/30 disabled:opacity-40 transition-colors"
        >
          <Check className="w-4 h-4" />
          通过 · 合入
        </button>
        <button
          type="button"
          disabled={submitting || !rejectReason.trim()}
          onClick={() => handleAction(false)}
          className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-md text-sm font-medium bg-status-error/20 text-status-error hover:bg-status-error/30 disabled:opacity-40 transition-colors"
        >
          <X className="w-4 h-4" />
          拒绝 · 打回修改
        </button>
      </div>
    </div>
  )
}
