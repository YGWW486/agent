import { useIndexStore } from '@/stores/index.store'

export function IndexStats() {
  const stats = useIndexStore((s) => s.stats)

  if (!stats) {
    return <p className="text-xs text-text-muted py-4">尚未加载索引，点击"重建索引"开始。</p>
  }

  return (
    <div className="grid grid-cols-2 gap-2">
      {[
        { label: '节点数', value: stats.node_count },
        { label: '边数', value: stats.edge_count },
        { label: '已索引文件', value: stats.files_indexed },
        { label: '加载时间', value: stats.loaded_at ? new Date(stats.loaded_at).toLocaleString() : '—' },
      ].map(({ label, value }) => (
        <div key={label} className="p-3 rounded-lg bg-surface-elevated border border-white/8">
          <div className="text-xs text-text-muted mb-0.5">{label}</div>
          <div className="text-lg font-semibold font-mono">
            {typeof value === 'number' ? value.toLocaleString() : value}
          </div>
        </div>
      ))}
    </div>
  )
}
