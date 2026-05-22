import type { ToolStep } from '../../../shared/types'
import { cn } from '@/lib/cn'

const STATUS_COLOR: Record<string, string> = {
  running: 'text-accent',
  success: 'text-success',
  warning: 'text-warning',
  error: 'text-danger',
}

interface ToolStepsListProps {
  steps: ToolStep[]
}

export function ToolStepsList({ steps }: ToolStepsListProps) {
  if (!steps.length) return null

  return (
    <div className="space-y-1">
      <p className="text-xs text-text-muted font-medium">工具调用</p>
      <ul className="space-y-1">
        {steps.map((step, i) => (
          <li
            key={`${step.tool}-${i}`}
            className="text-xs p-2 rounded bg-surface-overlay border border-border-subtle"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono font-medium">{step.tool}</span>
              <span className={cn('capitalize', STATUS_COLOR[step.status] ?? 'text-text-muted')}>
                {step.status}
              </span>
            </div>
            {step.summary ? (
              <p className="mt-1 text-text-secondary">{step.summary}</p>
            ) : null}
            {step.input?.path ? (
              <p className="mt-0.5 font-mono text-text-muted truncate">
                {String(step.input.path)}
              </p>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  )
}
