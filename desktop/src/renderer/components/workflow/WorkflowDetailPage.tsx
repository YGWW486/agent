import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { useWorkflowStore } from '@/stores/workflow.store'
import { useWorkflow } from '@/hooks/useWorkflow'
import { useApi } from '@/hooks/useApi'
import { Timeline } from './Timeline'
import { TaskDAGView } from './TaskDAGView'
import { SelfCheckTable } from './SelfCheckTable'
import { ApprovalPanel } from './ApprovalPanel'
import { DiffViewer } from '@/components/code/DiffViewer'
import { CodePreview } from '@/components/code/CodePreview'
import { TestCaseViewer } from '@/components/code/TestCaseViewer'
import { cn } from '@/lib/cn'
import { RotateCcw } from 'lucide-react'
import type { TimelineNode, WrittenFile } from '../../../shared/types'

function nodeSummary(node: TimelineNode): string | null {
  if (!node.summary) return null
  const s = node.summary as Record<string, unknown>
  switch (node.name) {
    case 'planner':
      return `任务数: ${s.task_count ?? '—'}`
    case 'coder':
      return `第 ${String((s.task_index as number) + 1)} 个任务 | ${s.code_len ?? 0} 字符`
    case 'reviewer':
      return `结论: ${s.verdict ?? '—'} | 测试: ${s.test_count ?? 0}`
    case 'merge':
      return `状态: ${s.status ?? '—'}`
    default:
      return null
  }
}

function renderNodeDetail(node: TimelineNode): React.ReactNode {
  const s = (node.summary ?? {}) as Record<string, unknown>

  if (node.name === 'planner') {
    return (
      <div className="space-y-3 pt-2">
        <p className="text-xs text-text-muted">
          共 {s.task_count ?? 0} 个任务。下方为任务 DAG 可视化。
        </p>
        <TaskDAGView
          tasks={(s._tasks as TaskDAGView['props']['tasks']) ?? []}
          currentTaskIndex={0}
        />
      </div>
    )
  }

  if (node.name === 'coder') {
    const diff = s._diff as string | undefined
    const code = s._code as string | undefined
    const selfCheckItems = (s._self_check as SelfCheckTable['props']['items']) ?? []
    return (
      <div className="space-y-3 pt-2">
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="p-2 rounded bg-surface-overlay">
            <span className="text-text-muted">任务序号</span>
            <div className="font-mono mt-0.5">第 {String(s.task_index ?? '—')} 个</div>
          </div>
          <div className="p-2 rounded bg-surface-overlay">
            <span className="text-text-muted">代码长度</span>
            <div className="font-mono mt-0.5">{s.code_len ?? 0} 字符</div>
          </div>
        </div>
        {diff && (
          <DiffViewer original="" modified={diff} language="python" />
        )}
        {code && !diff && (
          <CodePreview code={code} language="python" />
        )}
        {selfCheckItems.length > 0 && (
          <>
            <p className="text-xs text-text-muted font-medium">自检结果</p>
            <SelfCheckTable items={selfCheckItems} />
          </>
        )}
      </div>
    )
  }

  if (node.name === 'reviewer') {
    const verdict = s.verdict as string | undefined
    const testCases = (s._test_cases as TestCaseViewer['props']['tests']) ?? []
    return (
      <div className="space-y-3 pt-2">
        <div className="flex items-center gap-3">
          <span className="text-xs text-text-muted">审查结论：</span>
          <span
            className={cn(
              'text-xs px-2 py-0.5 rounded-full font-semibold',
              verdict === 'PASS'
                ? 'bg-status-running/15 text-status-running'
                : 'bg-status-error/15 text-status-error',
            )}
          >
            {verdict === 'PASS' ? '通过' : verdict === 'REJECT' ? '拒绝' : '—'}
          </span>
        </div>
        <div className="text-xs text-text-muted">
          生成测试数：<span className="font-mono text-text-secondary">{s.test_count ?? 0}</span>
        </div>
        {testCases.length > 0 && <TestCaseViewer tests={testCases} />}
      </div>
    )
  }

  if (node.name === 'merge') {
    const writtenFiles = (s._written_files as WrittenFile[]) ?? []
    return (
      <div className="space-y-3 pt-2">
        <div className="text-xs text-text-muted">
          状态：<span className="text-text-secondary">{s.status === 'approved' ? '已合入' : s.status ?? '等待中'}</span>
        </div>
        {writtenFiles.length > 0 && (
          <>
            <p className="text-xs font-medium text-text-muted">已写入文件（{writtenFiles.length}）</p>
            <div className="space-y-1">
              {writtenFiles.map((f) => (
                <div key={f.path} className="flex items-center gap-2 p-2 rounded bg-surface-overlay text-xs">
                  <code className="font-mono text-text-secondary flex-1 truncate">{f.path}</code>
                  <span className="text-text-muted flex-shrink-0">{(f.size / 1024).toFixed(1)} KB</span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    )
  }

  return null
}

export function WorkflowDetailPage() {
  const { threadId } = useParams<{ threadId: string }>()
  useDocumentTitle(`工作流 ${threadId}`)
  const workflow = useWorkflowStore((s) => s.getWorkflow(threadId ?? ''))
  const mergeNode = workflow?.nodes.find((n) => n.name === 'merge')
  const isComplete = mergeNode?.status === 'success'
  // 已完成/失败/挂起的工作流不重连 SSE
  const shouldStream = !isComplete && !workflow?.error && !workflow?.interrupt
  const { connected } = useWorkflow(shouldStream ? (threadId ?? null) : null)
  const api = useApi()
  const [restoring, setRestoring] = useState(false)
  const [restoreMsg, setRestoreMsg] = useState('')

  const handleRestore = async () => {
    if (!threadId) return
    setRestoring(true)
    try {
      const result = await api.restoreWorkflow(threadId)
      setRestoreMsg(`已恢复 ${(result as { restored?: string[] }).restored?.length ?? 0} 个文件`)
    } catch (err) {
      setRestoreMsg(err instanceof Error ? err.message : '恢复失败')
    } finally {
      setRestoring(false)
    }
  }

  if (!workflow) {
    return (
      <div className="p-6">
        <p className="text-sm text-text-muted">未找到该工作流。</p>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">
          工作流{' '}
          <code className="text-sm text-accent font-mono">{threadId}</code>
        </h2>
        <div className="flex items-center gap-2 text-xs">
          <span
            className={cn(
              'w-2 h-2 rounded-full',
              connected ? 'bg-status-running' : 'bg-status-stopped',
            )}
          />
          <span className="text-text-muted">{connected ? '实时' : '已断开'}</span>
        </div>
      </div>

      {workflow.error && (
        <div
          role="alert"
          className="p-3 rounded-md bg-status-error/15 text-status-error text-sm border border-status-error/25"
        >
          {workflow.error}
        </div>
      )}

      {workflow.interrupt && (
        <ApprovalPanel threadId={threadId!} nodes={workflow.nodes} />
      )}

      {isComplete && (
        <div className="flex items-center justify-between p-3 rounded-lg border border-status-running/20 bg-status-running/5">
          <div className="text-xs">
            <span className="text-status-running font-medium">工作流已完成</span>
            <span className="text-text-muted ml-2">— 文件已写入磁盘</span>
          </div>
          <button
            type="button"
            onClick={handleRestore}
            disabled={restoring}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[11px] font-medium border border-status-error/25 bg-status-error/10 text-status-error hover:bg-status-error/20 disabled:opacity-40 transition-colors"
          >
            <RotateCcw className="w-3 h-3" />
            {restoring ? '恢复中…' : '撤销写入'}
          </button>
        </div>
      )}
      {restoreMsg && (
        <div className="p-2 rounded bg-surface-overlay text-xs text-text-secondary">{restoreMsg}</div>
      )}

      <div>
        <h3 className="text-sm font-medium text-text-muted mb-1">需求规格</h3>
        <pre className="whitespace-pre-wrap text-sm bg-surface-overlay rounded-md p-3 border border-white/8 max-h-32 overflow-y-auto">
          {workflow.spec}
        </pre>
      </div>

      <div>
        <h3 className="text-sm font-medium text-text-muted mb-3">执行时间线</h3>
        <Timeline nodes={workflow.nodes} renderDetail={renderNodeDetail} />
      </div>
    </div>
  )
}
