import { NavLink } from 'react-router-dom'
import { Home, Settings, GitBranch, Network, Zap, ChevronRight, Square, RefreshCw, Play } from 'lucide-react'
import { useBackend } from '@/hooks/useBackend'
import { cn } from '@/lib/cn'

const navItems = [
  { to: '/', icon: Home, label: '首页', end: true },
  { to: '/workflows', icon: GitBranch, label: '工作流', end: false },
  { to: '/index', icon: Network, label: '索引', end: false },
  { to: '/settings', icon: Settings, label: '设置', end: false },
]

const statusConfig: Record<string, { color: string; bg: string; label: string }> = {
  running: { color: 'bg-status-running', bg: 'bg-status-running/10', label: '运行中' },
  starting: { color: 'bg-status-suspended', bg: 'bg-status-suspended/10', label: '启动中…' },
  error: { color: 'bg-status-error', bg: 'bg-status-error/10', label: '异常' },
  stopped: { color: 'bg-status-stopped', bg: 'bg-status-stopped/10', label: '已停止' },
}

export function Sidebar() {
  const { status, start, stop } = useBackend()
  const info = statusConfig[status] ?? statusConfig.stopped

  return (
    <aside
      className="w-56 flex-shrink-0 border-r border-white/6 bg-surface-elevated flex flex-col select-none"
      aria-label="主导航"
    >
      <div className="h-12 flex items-center gap-2 px-4 border-b border-white/6">
        <div className="w-6 h-6 rounded-md bg-accent flex items-center justify-center">
          <Zap className="w-3.5 h-3.5 text-white" strokeWidth={2.5} />
        </div>
        <span className="font-semibold text-sm tracking-tight">控制台</span>
        <span className="text-[10px] text-text-muted ml-auto font-mono">v0.1</span>
      </div>

      <nav className="flex-1 p-2 space-y-0.5" aria-label="页面导航">
        {navItems.map(({ to, icon: Icon, label, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-2.5 px-2.5 py-1.5 rounded-md text-[13px] font-medium transition-colors',
                isActive
                  ? 'bg-white/8 text-text-primary'
                  : 'text-text-secondary hover:text-text-primary hover:bg-white/5',
              )
            }
          >
            {({ isActive }) => (
              <>
                <Icon className={cn('w-4 h-4', isActive ? 'text-accent' : 'text-text-muted')} aria-hidden="true" />
                {label}
                {isActive && <ChevronRight className="w-3.5 h-3.5 text-accent ml-auto" />}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="p-3 border-t border-white/6 space-y-2">
        <div
          className="flex items-center gap-2.5 px-2.5 py-2 rounded-md bg-surface-overlay"
          role="status"
          aria-label={`后端状态：${info.label}`}
        >
          <span className="relative flex h-2 w-2">
            <span className={cn('absolute inset-0 rounded-full', info.color)} />
            <span className={cn('absolute inset-0 rounded-full animate-ping', info.color, status === 'running' ? 'opacity-40' : 'opacity-0')} />
          </span>
          <span className="text-[12px] text-text-secondary">后端</span>
          <span className="text-[12px] text-text-muted ml-auto">{info.label}</span>
        </div>

        <div className="flex gap-1 px-2.5">
          {status === 'stopped' || status === 'error' ? (
            <button
              type="button"
              onClick={start}
              className="flex-1 flex items-center justify-center gap-1 py-1.5 rounded text-[11px] font-medium bg-status-running/20 text-status-running hover:bg-status-running/30 transition-colors"
            >
              <Play className="w-3 h-3" />
              启动
            </button>
          ) : status === 'running' ? (
            <>
              <button
                type="button"
                onClick={stop}
                className="flex-1 flex items-center justify-center gap-1 py-1.5 rounded text-[11px] font-medium bg-status-error/15 text-status-error hover:bg-status-error/25 transition-colors"
              >
                <Square className="w-3 h-3" />
                停止
              </button>
              <button
                type="button"
                onClick={async () => { await stop(); await new Promise(r => setTimeout(r, 1500)); await start() }}
                className="flex items-center justify-center w-7 h-7 rounded text-[11px] text-text-muted hover:bg-white/10 hover:text-text-secondary transition-colors"
                title="重启后端"
              >
                <RefreshCw className="w-3 h-3" />
              </button>
            </>
          ) : null}
        </div>

        <div className="flex items-center gap-1.5 text-[11px] text-text-muted px-2.5">
          <kbd className="px-1.5 py-0.5 rounded bg-surface-overlay text-[10px] border border-white/8">⌘</kbd>
          <kbd className="px-1.5 py-0.5 rounded bg-surface-overlay text-[10px] border border-white/8">K</kbd>
          <span>命令面板</span>
        </div>
      </div>
    </aside>
  )
}
