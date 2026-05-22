import { useState } from 'react'
import { Check, X, AlertTriangle, FlaskConical, ClipboardList, ChevronDown } from 'lucide-react'
import { useApi } from '@/hooks/useApi'
import { useWorkflowStore } from '@/stores/workflow.store'
import { cn } from '@/lib/cn'
import type { TimelineNode, TestResults } from '../../../shared/types'

interface SelfCheckItem {
  condition_id: string
  status: 'satisfied' | 'not_satisfied' | 'uncertain'
  evidence: string
}

interface TestCase {
  name: string
  code: string
}

interface ApprovalPanelProps {
  threadId: string
  nodes: TimelineNode[]
}

const SC_STATUS: Record<SelfCheckItem['status'], string> = {
  satisfied: 'bg-status-running/15 text-status-running',
  not_satisfied: 'bg-status-error/15 text-status-error',
  uncertain: 'bg-status-suspended/15 text-status-suspended',
}

function CompactSelfCheck({ items }: { items: SelfCheckItem[] }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-1.5 text-xs text-text-muted mb-2">
        <ClipboardList className="w-3.5 h-3.5" />
        <span>Coder 自检 ({items.length} 项)</span>
      </div>
      <table className="w-full text-[11px]">
        <thead>
          <tr className="border-b border-white/5">
            <th className="text-left py-1.5 font-medium text-text-muted">条件</th>
            <th className="text-left py-1.5 font-medium text-text-muted">状态</th>
            <th className="text-left py-1.5 font-medium text-text-muted">证据</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.condition_id} className="border-b border-white/5 last:border-0">
              <td className="py-1.5 font-mono">{item.condition_id}</td>
              <td className="py-1.5">
                <span className={cn('px-1.5 py-0.5 rounded-full text-[10px]', SC_STATUS[item.status])}>
                  {item.status === 'satisfied' ? '✓' : item.status === 'not_satisfied' ? '✗' : '?'}
                </span>
              </td>
              <td className="py-1.5 text-text-muted max-w-[140px] truncate">{item.evidence || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function CompactTestCases({ tests }: { tests: TestCase[] }) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null)

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-1.5 text-xs text-text-muted mb-2">
        <FlaskConical className="w-3.5 h-3.5" />
        <span>Reviewer 附带测试 ({tests.length} 个)</span>
      </div>
      {tests.slice(0, 2).map((test, i) => (
        <div key={`${test.name}-${i}`} className="rounded border border-white/8 overflow-hidden">
          <button
            type="button"
            onClick={() => setExpandedIdx(expandedIdx === i ? null : i)}
            className="w-full flex items-center gap-2 px-2.5 py-1.5 text-left text-[11px] hover:bg-white/5 transition-colors"
          >
            <ChevronDown className={cn('w-3 h-3 text-text-muted transition-transform', expandedIdx === i && 'rotate-180')} />
            <span className="font-medium flex-1 truncate">{test.name}</span>
          </button>
          {expandedIdx === i && (
            <div className="border-t border-white/8">
              <pre className="p-2.5 text-[11px] font-mono overflow-x-auto whitespace-pre bg-surface-overlay max-h-36 overflow-y-auto">
                {test.code}
              </pre>
            </div>
          )}
        </div>
      ))}
      {tests.length > 2 && (
        <p className="text-[10px] text-text-muted px-1">+ {tests.length - 2} 更多测试用例（在 Reviewer 节点展开查看）</p>
      )}
    </div>
  )
}

function TestResultsBadge({ results }: { results: TestResults }) {
  const allPassed = results.passed === results.total && results.total > 0

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-1.5 text-xs text-text-muted mb-2">
        <FlaskConical className="w-3.5 h-3.5" />
        <span>测试执行结果</span>
      </div>
      <div className={cn(
        'flex items-center gap-2 p-2 rounded text-xs',
        allPassed ? 'bg-status-running/10 text-status-running' : 'bg-status-error/10 text-status-error',
      )}>
        <span className="font-mono font-semibold">
          {results.passed}/{results.total} passed
        </span>
        {results.failed > 0 && (
          <span className="font-mono">· {results.failed} failed</span>
        )}
      </div>
      {results.output && !allPassed && (
        <pre className="text-[10px] font-mono overflow-x-auto whitespace-pre-wrap bg-surface-overlay p-2 rounded max-h-24 overflow-y-auto text-text-muted">
          {results.output.slice(0, 600)}
        </pre>
      )}
    </div>
  )
}

export function ApprovalPanel({ threadId, nodes }: ApprovalPanelProps) {
  const api = useApi()
  const updateWorkflow = useWorkflowStore((s) => s.updateWorkflow)
  const hitlActions = useWorkflowStore(
    (s) => s.getWorkflow(threadId)?.hitl_next_actions ?? ['approve', 'revise'],
  )
  const workflow = useWorkflowStore((s) => s.getWorkflow(threadId))
  const [submitting, setSubmitting] = useState(false)
  const [rejectReason, setRejectReason] = useState('')
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)

  const reviewer = nodes.find((n) => n.name === 'reviewer')
  const coder = nodes.find((n) => n.name === 'coder')
  const reviewerSummary = (reviewer?.summary ?? {}) as Record<string, unknown>
  const coderSummary = (coder?.summary ?? {}) as Record<string, unknown>

  const selfCheckItems = (coderSummary._self_check as SelfCheckItem[] | undefined) ?? []
  const testCases = (reviewerSummary._test_cases as TestCase[] | undefined) ?? []
  const testResults =
    (reviewerSummary._test_results as TestResults | undefined) ??
    workflow?.testResults ??
    null

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
      <div className="flex items-center gap-2 flex-wrap">
        <AlertTriangle className="w-5 h-5 text-status-suspended" />
        <span className="text-sm font-semibold text-status-suspended">工作流已暂停 — 等待人工审批</span>
        {hitlActions.length > 0 && (
          <span className="flex gap-1.5 ml-auto">
            {hitlActions.map((action) => (
              <span
                key={action}
                className="text-xs px-2 py-0.5 rounded-full bg-white/10 text-text-muted font-mono"
              >
                {action}
              </span>
            ))}
          </span>
        )}
      </div>

      {/* Reviewer 结论 */}
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
              {reviewerSummary.verdict === 'PASS' ? '✓ 通过' : reviewerSummary.verdict === 'REJECT' ? '✗ 拒绝' : '未知'}
            </div>
          </div>
        )}
      </div>

      {/* Reviewer 理由 */}
      {reviewerSummary.reason && (
        <p className="text-xs text-text-muted leading-relaxed">{(reviewerSummary.reason as string).slice(0, 300)}</p>
      )}

      {/* 验证证据区域 */}
      <div className="space-y-3 p-3 rounded bg-surface-overlay/50 border border-white/5">
        <p className="text-xs font-medium text-text-secondary">验证证据</p>

        {/* Coder 自检 */}
        {selfCheckItems.length > 0 && <CompactSelfCheck items={selfCheckItems} />}

        {/* Reviewer 附带测试 */}
        {testCases.length > 0 && <CompactTestCases tests={testCases} />}

        {/* 测试执行结果 */}
        {testResults && testResults.ran && <TestResultsBadge results={testResults} />}
        {testResults && !testResults.ran && testResults.message && (
          <p className="text-[11px] text-text-muted">{testResults.message}</p>
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
