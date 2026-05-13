import { useLocation, Link } from 'react-router-dom'
import { Plus, Minus, Square, X, Zap } from 'lucide-react'
import { useEffect, useState } from 'react'
import { cn } from '@/lib/cn'

const ROUTE_TITLES: Record<string, string> = {
  '/': '仪表盘',
  '/workflows': '工作流',
  '/workflow/new': '新建工作流',
  '/index': '知识索引',
  '/settings': '设置',
}

export function TopBar() {
  const location = useLocation()
  const pathname = location.pathname
  const title = ROUTE_TITLES[pathname] ?? pathname.split('/').filter(Boolean).join(' / ')
  const [isMaximized, setIsMaximized] = useState(false)

  useEffect(() => {
    const api = window.electronAPI
    if (!api?.window) return
    api.window.isMaximized().then(setIsMaximized)
    return api.on('window:maximize-changed', (state) => setIsMaximized(state as boolean))
  }, [])

  const handleMinimize = () => window.electronAPI?.window.minimize()
  const handleMaximize = () => window.electronAPI?.window.maximize()
  const handleClose = () => window.electronAPI?.window.close()

  return (
    <header
      className="h-9 flex items-center justify-between bg-surface-elevated border-b border-white/6 flex-shrink-0 select-none"
      style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}
    >
      <div className="flex items-center gap-2.5 pl-3">
        <Zap className="w-4 h-4 text-accent" strokeWidth={2.5} />
        <span className="text-[12px] text-text-muted font-medium tracking-wide">控制台</span>
        <span className="text-[12px] text-text-muted/30">/</span>
        <span className="text-[12px] text-text-primary">{title}</span>
      </div>

      <div className="flex-1 h-full" />

      <div className="flex items-center gap-1 pr-1" style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}>
        <Link
          to="/workflow/new"
          className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium rounded-md bg-accent hover:bg-accent-hover text-white transition-colors active:scale-[0.98]"
        >
          <Plus className="w-3 h-3" strokeWidth={2.5} />
          新建
        </Link>

        <span className="w-px h-4 bg-white/8 mx-0.5" />

        <WindowButton onClick={handleMinimize} label="最小化">
          <Minus className="w-3 h-3" strokeWidth={1.5} />
        </WindowButton>
        <WindowButton onClick={handleMaximize} label={isMaximized ? '还原' : '最大化'}>
          <Square className={cn('w-3 h-3', isMaximized && 'scale-x-[-1]')} strokeWidth={1.5} />
        </WindowButton>
        <WindowButton onClick={handleClose} label="关闭" isClose>
          <X className="w-3.5 h-3.5" strokeWidth={1.5} />
        </WindowButton>
      </div>
    </header>
  )
}

function WindowButton({
  onClick,
  label,
  isClose,
  children,
}: {
  onClick: () => void
  label: string
  isClose?: boolean
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className={cn(
        'w-8 h-7 flex items-center justify-center rounded transition-colors',
        isClose
          ? 'text-text-muted hover:bg-[#c42b1c] hover:text-white'
          : 'text-text-muted hover:bg-white/10 hover:text-text-primary',
      )}
    >
      {children}
    </button>
  )
}
