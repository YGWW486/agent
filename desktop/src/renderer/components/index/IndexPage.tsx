import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { IndexManager } from './IndexManager'
import { IndexStats } from './IndexStats'
import { useIndexStore } from '@/stores/index.store'

export function IndexPage() {
  useDocumentTitle('知识索引')
  const error = useIndexStore((s) => s.error)

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6">
      <div>
        <h2 className="text-lg font-semibold mb-1">知识索引</h2>
        <p className="text-sm text-text-muted">
          加载 graph.json 文件，为 Agent 上下文感知查询提供项目结构索引。
        </p>
      </div>

      {error && (
        <div role="alert" className="p-3 rounded-md bg-status-error/15 text-status-error text-sm border border-status-error/25">
          {error}
        </div>
      )}

      <IndexManager />
      <IndexStats />
    </div>
  )
}
