import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApi } from '@/hooks/useApi'
import { useWorkflowStore } from '@/stores/workflow.store'
import { useDraftStore } from '@/stores/draft.store'
import { WorkspaceSelector, serializeWorkspace } from './WorkspaceSelector'

export function SubmitForm() {
  const { spec, context, workspace, setSpec, setContext, setWorkspace, clear } = useDraftStore()
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const api = useApi()
  const navigate = useNavigate()
  const addWorkflow = useWorkflowStore((s) => s.addWorkflow)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!spec.trim()) return

    setSubmitting(true)
    setError('')

    try {
      const workspaceText = serializeWorkspace(workspace)
      const fullContext = [workspaceText, context.trim()].filter(Boolean).join('\n\n')
      const result = await api.startWorkflow(spec.trim(), fullContext)
      addWorkflow(result.thread_id, spec.trim())
      clear() // 提交后清空草稿
      navigate(`/workflow/${result.thread_id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : '启动工作流失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div role="alert" className="p-3 rounded-md bg-status-error/15 text-status-error text-sm border border-status-error/25">
          {error}
        </div>
      )}

      <WorkspaceSelector dirs={workspace} onChange={setWorkspace} />

      <div>
        <label htmlFor="spec" className="block text-sm font-medium mb-1.5">
          需求规格
        </label>
        <textarea
          id="spec"
          required
          rows={8}
          maxLength={50000}
          value={spec}
          onChange={(e) => setSpec(e.target.value)}
          placeholder="描述你希望 Agent 构建的内容…"
          className="w-full rounded-md border border-white/10 bg-surface-overlay px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent/50 resize-y"
        />
      </div>

      <div>
        <label htmlFor="context" className="block text-sm font-medium mb-1.5">
          上下文 <span className="text-text-muted font-normal">（可选）</span>
        </label>
        <textarea
          id="context"
          rows={4}
          maxLength={50000}
          value={context}
          onChange={(e) => setContext(e.target.value)}
          placeholder="额外的上下文信息，如文件路径、约束条件、需求说明…"
          className="w-full rounded-md border border-white/10 bg-surface-overlay px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent/50 resize-y"
        />
      </div>

      <button
        type="submit"
        disabled={submitting || !spec.trim()}
        className="w-full py-2.5 rounded-md text-sm font-medium bg-accent text-white hover:bg-accent/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        {submitting ? '启动中…' : '启动工作流'}
      </button>
    </form>
  )
}
