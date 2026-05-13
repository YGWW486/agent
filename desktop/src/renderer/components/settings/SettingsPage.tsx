import { useEffect, useState } from 'react'
import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { useSettingsStore } from '@/stores/settings.store'
import { APISettings } from './APISettings'
import { AdvancedSettings } from './AdvancedSettings'

type Tab = 'api' | 'advanced'

export function SettingsPage() {
  useDocumentTitle('设置')
  const { loaded, loadFromIpc } = useSettingsStore()
  const [tab, setTab] = useState<Tab>('api')

  useEffect(() => {
    loadFromIpc()
  }, [loadFromIpc])

  if (!loaded) {
    return <div className="p-6 text-sm text-text-muted">加载设置中…</div>
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: 'api', label: 'API 密钥' },
    { key: 'advanced', label: '高级设置' },
  ]

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6">
      <div>
        <h2 className="text-lg font-semibold mb-1">设置</h2>
        <p className="text-sm text-text-muted">配置 API 密钥、模型参数与后端选项。</p>
      </div>

      <div className="flex gap-1 border-b border-white/8">
        {tabs.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={`px-4 py-2 text-sm border-b-2 transition-colors ${
              tab === key
                ? 'border-accent text-accent'
                : 'border-transparent text-text-muted hover:text-text-secondary'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'api' && <APISettings />}
      {tab === 'advanced' && <AdvancedSettings />}
    </div>
  )
}
