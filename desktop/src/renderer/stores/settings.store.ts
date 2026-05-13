import { create } from 'zustand'
import type { Settings, ModelRouting } from '../../shared/types'

const defaults: Settings = {
  llm_provider: 'anthropic',
  anthropic_api_key: '',
  deepseek_api_key: '',
  langsmith_api_key: '',
  host: '127.0.0.1',
  port: 8000,
  model_routing: {
    simple: 'claude-haiku-4-5-20251001',
    standard: 'claude-sonnet-4-6',
    complex: 'claude-opus-4-7',
  },
  max_revisions: 3,
  workflow_timeout: 300,
  daily_token_budget: 1_000_000,
  task_token_limit: 100_000,
}

interface SettingsStore {
  settings: Settings
  loaded: boolean
  setSettings: (patch: Partial<Settings>) => void
  loadFromIpc: () => Promise<void>
  saveToIpc: (key: string, value: unknown) => Promise<void>
}

export const useSettingsStore = create<SettingsStore>((set, get) => ({
  settings: { ...defaults },
  loaded: false,

  setSettings: (patch) =>
    set((prev) => ({ settings: { ...prev.settings, ...patch } })),

  loadFromIpc: async () => {
    if (!window.electronAPI) return
    try {
      const all = await window.electronAPI.settings.getAll()
      set({ settings: { ...defaults, ...(all as Settings) }, loaded: true })
    } catch {
      set({ settings: { ...defaults }, loaded: true })
    }
  },

  saveToIpc: async (key, value) => {
    if (!window.electronAPI) return
    await window.electronAPI.settings.set(key, value)
    get().setSettings({ [key]: value } as Partial<Settings>)
  },
}))
