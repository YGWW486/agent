import { useState } from 'react'
import { FolderOpen, RefreshCw } from 'lucide-react'
import { useApi } from '@/hooks/useApi'
import { useIndexStore } from '@/stores/index.store'

export function IndexManager() {
  const api = useApi()
  const { stats, loading, setStats, setLoading, setError } = useIndexStore()
  const [graphPath, setGraphPath] = useState(stats?.loaded_at ?? '')

  const handleSelectDir = async () => {
    const dir = await window.electronAPI?.dialog.selectDirectory()
    if (dir) {
      setGraphPath(`${dir}/graph.json`)
    }
  }

  const handleRebuild = async () => {
    if (!graphPath.trim()) return
    setLoading(true)
    try {
      const result = await api.rebuildIndex(graphPath.trim())
      setStats(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : '索引重建失败')
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <button
          type="button"
          onClick={handleSelectDir}
          className="flex items-center gap-1.5 px-3 py-2 rounded-md text-xs font-medium border border-white/10 bg-surface-elevated hover:bg-surface-overlay transition-colors"
        >
          <FolderOpen className="w-3.5 h-3.5" />
          选择 graph.json
        </button>
        <button
          type="button"
          onClick={handleRebuild}
          disabled={loading || !graphPath.trim()}
          className="flex items-center gap-1.5 px-3 py-2 rounded-md text-xs font-medium bg-accent text-white hover:bg-accent/90 disabled:opacity-40 transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          {loading ? '索引中…' : '重建索引'}
        </button>
      </div>
      {graphPath && (
        <p className="text-xs text-text-muted font-mono truncate">{graphPath}</p>
      )}
    </div>
  )
}
