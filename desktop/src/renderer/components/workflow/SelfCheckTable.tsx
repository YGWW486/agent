import { cn } from '@/lib/cn'

interface SelfCheckItem {
  condition_id: string
  status: 'satisfied' | 'not_satisfied' | 'uncertain'
  evidence: string
}

interface SelfCheckTableProps {
  items: SelfCheckItem[]
}

const statusStyles: Record<SelfCheckItem['status'], string> = {
  satisfied: 'bg-status-running/15 text-status-running',
  not_satisfied: 'bg-status-error/15 text-status-error',
  uncertain: 'bg-status-suspended/15 text-status-suspended',
}

export function SelfCheckTable({ items }: SelfCheckTableProps) {
  if (items.length === 0) {
    return <p className="text-xs text-text-muted py-4 text-center">No self-check data available.</p>
  }

  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="border-b border-white/8">
          <th className="text-left py-2 font-medium text-text-muted">Condition</th>
          <th className="text-left py-2 font-medium text-text-muted">Status</th>
          <th className="text-left py-2 font-medium text-text-muted">Evidence</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.condition_id} className="border-b border-white/5 last:border-0">
            <td className="py-2 font-mono text-[11px]">{item.condition_id}</td>
            <td className="py-2">
              <span className={cn('px-1.5 py-0.5 rounded-full text-[11px]', statusStyles[item.status])}>
                {item.status.replace('_', ' ')}
              </span>
            </td>
            <td className="py-2 text-text-muted max-w-xs truncate">{item.evidence || '—'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
