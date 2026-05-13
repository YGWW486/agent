import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { SubmitForm } from './SubmitForm'

export function NewWorkflowPage() {
  useDocumentTitle('新建工作流')

  return (
    <div className="max-w-2xl mx-auto p-6">
      <h2 className="text-lg font-semibold mb-1">新建工作流</h2>
      <p className="text-sm text-text-muted mb-6">
        提交需求规格，启动 Planner → Coder → Reviewer → Merge 流水线。
      </p>
      <SubmitForm />
    </div>
  )
}
