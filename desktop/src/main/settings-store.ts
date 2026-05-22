import { app } from 'electron'
import * as fs from 'fs'
import * as path from 'path'
import type { Settings } from '../shared/types'

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
  max_revisions: 0,
  workflow_timeout: 300,
  daily_token_budget: 1_000_000,
  task_token_limit: 100_000,
}

class SettingsStore {
  private data: Settings
  private filePath: string

  constructor() {
    this.filePath = path.join(app.getPath('userData'), 'settings.json')
    this.data = { ...defaults }
    this._load()
  }

  get<K extends keyof Settings>(key: K): Settings[K] {
    return this.data[key]
  }

  set<K extends keyof Settings>(key: K, value: Settings[K]): void {
    this.data[key] = value
    this._save()
  }

  getAll(): Settings {
    return { ...this.data }
  }

  setAll(partial: Partial<Settings>): void {
    Object.assign(this.data, partial)
    this._save()
  }

  private _load(): void {
    try {
      if (fs.existsSync(this.filePath)) {
        const raw = fs.readFileSync(this.filePath, 'utf-8')
        const parsed = JSON.parse(raw)
        this.data = { ...defaults, ...parsed }
      }
    } catch {
      this.data = { ...defaults }
    }
  }

  private _save(): void {
    try {
      const dir = path.dirname(this.filePath)
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true })
      }
      fs.writeFileSync(this.filePath, JSON.stringify(this.data, null, 2), 'utf-8')
    } catch {
      // best-effort persist
    }
  }
}

let _store: SettingsStore | null = null

export function getSettingsStore(): SettingsStore {
  if (!_store) {
    _store = new SettingsStore()
  }
  return _store
}
