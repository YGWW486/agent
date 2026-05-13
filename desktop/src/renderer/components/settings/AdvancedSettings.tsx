import { useSettingsStore } from '@/stores/settings.store'

export function AdvancedSettings() {
  const { settings, saveToIpc } = useSettingsStore()

  const handleNumber = (key: string) => (e: React.ChangeEvent<HTMLInputElement>) => {
    const n = Number(e.target.value)
    if (!isNaN(n) && n > 0) saveToIpc(key, n)
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        {[
          { key: 'port', label: '后端端口', value: settings.port },
          { key: 'max_revisions', label: '最大修订轮次', value: settings.max_revisions },
          { key: 'workflow_timeout', label: '工作流超时 (秒)', value: settings.workflow_timeout },
          { key: 'task_token_limit', label: '单任务 Token 上限', value: settings.task_token_limit },
        ].map(({ key, label, value }) => (
          <div key={key}>
            <label htmlFor={`adv-${key}`} className="block text-xs text-text-muted mb-1">
              {label}
            </label>
            <input
              id={`adv-${key}`}
              type="number"
              value={value}
              onChange={handleNumber(key)}
              className="w-full rounded-md border border-white/10 bg-surface-overlay px-3 py-2 text-sm text-text-primary font-mono"
            />
          </div>
        ))}
      </div>

      <div>
        <label htmlFor="adv-budget" className="block text-xs text-text-muted mb-1">
          每日 Token 预算
        </label>
        <input
          id="adv-budget"
          type="number"
          value={settings.daily_token_budget}
          onChange={handleNumber('daily_token_budget')}
          className="w-full rounded-md border border-white/10 bg-surface-overlay px-3 py-2 text-sm text-text-primary font-mono"
        />
      </div>
    </div>
  )
}
