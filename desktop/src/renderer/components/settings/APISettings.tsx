import { useSettingsStore } from '@/stores/settings.store'

export function APISettings() {
  const { settings, saveToIpc } = useSettingsStore()

  return (
    <div className="space-y-5">
      {/* Provider selector */}
      <div>
        <label htmlFor="llm-provider" className="block text-sm font-medium mb-1.5">
          LLM 提供商
        </label>
        <select
          id="llm-provider"
          value={settings.llm_provider}
          onChange={(e) => saveToIpc('llm_provider', e.target.value)}
          className="w-full rounded-md border border-white/10 bg-surface-overlay px-3 py-2 text-sm text-text-primary"
        >
          <option value="anthropic">Anthropic (Claude)</option>
          <option value="deepseek">DeepSeek</option>
        </select>
        <p className="text-[11px] text-text-muted mt-1">
          切换后需重启后端生效
        </p>
      </div>

      {/* Anthropic */}
      {settings.llm_provider === 'anthropic' && (
        <div>
          <label htmlFor="anthropic-key" className="block text-sm font-medium mb-1.5">
            Anthropic API 密钥
          </label>
          <input
            id="anthropic-key"
            type="password"
            value={settings.anthropic_api_key}
            onChange={(e) => saveToIpc('anthropic_api_key', e.target.value)}
            placeholder="sk-ant-…"
            className="w-full rounded-md border border-white/10 bg-surface-overlay px-3 py-2 text-sm text-text-primary placeholder:text-text-muted font-mono"
          />
        </div>
      )}

      {/* DeepSeek */}
      {settings.llm_provider === 'deepseek' && (
        <div className="space-y-4">
          <div>
            <label htmlFor="deepseek-key" className="block text-sm font-medium mb-1.5">
              DeepSeek API 密钥
            </label>
            <input
              id="deepseek-key"
              type="password"
              value={settings.deepseek_api_key}
              onChange={(e) => saveToIpc('deepseek_api_key', e.target.value)}
              placeholder="sk-…"
              className="w-full rounded-md border border-white/10 bg-surface-overlay px-3 py-2 text-sm text-text-primary placeholder:text-text-muted font-mono"
            />
          </div>
          <div className="p-3 rounded-md bg-accent/5 border border-accent/10 text-[11px] text-text-secondary space-y-1">
            <p className="font-medium text-accent">DeepSeek V4 注意事项</p>
            <p>· 模型 ID：<code className="text-text-primary">deepseek-v4-pro</code>（推理）/ <code className="text-text-primary">deepseek-v4-flash</code>（轻量）</p>
            <p>· 旧 ID <code className="text-text-primary">deepseek-chat</code> 将于 <strong>2026-07-24</strong> 下线</p>
            <p>· API 端点：<code className="text-text-primary">https://api.deepseek.com/v1</code></p>
            <p>· 推荐 temperature：<strong>1.0</strong>（非 0.4-0.7）</p>
            <p>· 账户需至少 <strong>$2</strong> 余额</p>
          </div>
        </div>
      )}

      {/* LangSmith (both providers) */}
      <div>
        <label htmlFor="langsmith-key" className="block text-sm font-medium mb-1.5">
          LangSmith API 密钥 <span className="text-text-muted font-normal">（可选）</span>
        </label>
        <input
          id="langsmith-key"
          type="password"
          value={settings.langsmith_api_key}
          onChange={(e) => saveToIpc('langsmith_api_key', e.target.value)}
          placeholder="ls__…"
          className="w-full rounded-md border border-white/10 bg-surface-overlay px-3 py-2 text-sm text-text-primary placeholder:text-text-muted font-mono"
        />
      </div>

      <div className="p-3 rounded-md bg-surface-overlay border border-white/8">
        <p className="text-xs text-text-muted">
          密钥通过 <code className="text-text-secondary">electron-store</code> 本地加密存储，不会发送到任何外部服务器。
        </p>
      </div>
    </div>
  )
}
