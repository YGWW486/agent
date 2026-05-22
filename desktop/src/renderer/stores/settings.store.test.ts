import { describe, it, expect, beforeEach } from 'vitest'
import { useSettingsStore } from './settings.store'

describe('settingsStore', () => {
  beforeEach(() => {
    useSettingsStore.setState({
      settings: {
        anthropic_api_key: '',
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
      },
      loaded: false,
    })
  })

  it('starts with loaded=false', () => {
    expect(useSettingsStore.getState().loaded).toBe(false)
  })

  it('setSettings merges partial updates immutably', () => {
    const prev = useSettingsStore.getState().settings
    useSettingsStore.getState().setSettings({ port: 9000 })

    expect(useSettingsStore.getState().settings.port).toBe(9000)
    expect(useSettingsStore.getState().settings).not.toBe(prev)
    expect(prev.port).toBe(8000) // original unchanged
  })

  it('setSettings preserves unmodified fields', () => {
    useSettingsStore.getState().setSettings({ port: 9999 })

    expect(useSettingsStore.getState().settings.port).toBe(9999)
    expect(useSettingsStore.getState().settings.host).toBe('127.0.0.1')
    expect(useSettingsStore.getState().settings.max_revisions).toBe(0)
  })
})
