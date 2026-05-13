import { FolderOpen, Plus, X, PenLine, Eye } from 'lucide-react'
import { cn } from '@/lib/cn'

export interface WorkspaceDir {
  path: string
  writable: boolean
}

interface WorkspaceSelectorProps {
  dirs: WorkspaceDir[]
  onChange: (dirs: WorkspaceDir[]) => void
}

export function WorkspaceSelector({ dirs, onChange }: WorkspaceSelectorProps) {
  const handleSelect = async (writable: boolean) => {
    const dir = await window.electronAPI?.dialog.selectDirectory()
    if (!dir) return
    if (dirs.some((d) => d.path === dir)) return // 不重复添加
    onChange([...dirs, { path: dir, writable }])
  }

  const handleRemove = (path: string) => {
    onChange(dirs.filter((d) => d.path !== path))
  }

  const handleToggle = (path: string) => {
    onChange(dirs.map((d) => (d.path === path ? { ...d, writable: !d.writable } : d)))
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="block text-sm font-medium">
          工作区 <span className="text-text-muted font-normal">（可选，限定 Agent 操作范围）</span>
        </label>
      </div>

      {dirs.length > 0 && (
        <div className="space-y-1">
          {dirs.map((dir) => (
            <div
              key={dir.path}
              className={cn(
                'flex items-center gap-2 px-3 py-2 rounded-md border text-xs group transition-colors',
                dir.writable
                  ? 'border-accent/20 bg-accent/5'
                  : 'border-white/8 bg-surface-overlay',
              )}
            >
              <FolderOpen className={cn('w-3.5 h-3.5 flex-shrink-0', dir.writable ? 'text-accent' : 'text-text-muted')} />

              <span className="flex-1 font-mono text-text-secondary truncate">{dir.path}</span>

              <button
                type="button"
                onClick={() => handleToggle(dir.path)}
                className={cn(
                  'flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium transition-colors flex-shrink-0',
                  dir.writable
                    ? 'bg-accent/15 text-accent hover:bg-accent/25'
                    : 'bg-white/5 text-text-muted hover:bg-white/10 hover:text-text-secondary',
                )}
                title={dir.writable ? '可写，点击切换只读' : '只读，点击切换可写'}
              >
                {dir.writable ? (
                  <PenLine className="w-3 h-3" />
                ) : (
                  <Eye className="w-3 h-3" />
                )}
                {dir.writable ? '可写' : '只读'}
              </button>

              <button
                type="button"
                onClick={() => handleRemove(dir.path)}
                className="p-0.5 rounded text-text-muted hover:text-status-error hover:bg-status-error/10 transition-colors flex-shrink-0"
                title="移除"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => handleSelect(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border border-accent/30 bg-accent/10 text-accent hover:bg-accent/20 transition-colors"
        >
          <Plus className="w-3.5 h-3.5" />
          添加可写目录
        </button>
        <button
          type="button"
          onClick={() => handleSelect(false)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border border-white/10 bg-surface-overlay text-text-secondary hover:bg-surface-highlight transition-colors"
        >
          <Eye className="w-3.5 h-3.5" />
          添加只读目录
        </button>
      </div>
    </div>
  )
}

/** 将工作区目录序列化为 Agent 可读的上下文文本 */
export function serializeWorkspace(dirs: WorkspaceDir[]): string {
  if (dirs.length === 0) return ''

  const writable = dirs.filter((d) => d.writable)
  const readOnly = dirs.filter((d) => !d.writable)

  const lines: string[] = ['## 工作区配置']
  if (writable.length > 0) {
    lines.push('### 可写目录（你可以在这些目录中创建和修改文件）')
    writable.forEach((d) => lines.push(`- ${d.path}`))
  }
  if (readOnly.length > 0) {
    lines.push('### 只读目录（你只能读取这些目录作为参考，不可修改）')
    readOnly.forEach((d) => lines.push(`- ${d.path}`))
  }
  lines.push('')
  return lines.join('\n')
}
