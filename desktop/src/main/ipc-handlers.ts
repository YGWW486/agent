import { ipcMain, dialog, BrowserWindow, app } from 'electron'
import { PythonManager } from './python-manager'
import { getSettingsStore } from './settings-store'
import type { Settings } from '../shared/types'

export const pythonManager = new PythonManager()

const ALLOWED_SETTINGS_KEYS: ReadonlyArray<keyof Settings> = [
  'llm_provider',
  'anthropic_api_key',
  'deepseek_api_key',
  'langsmith_api_key',
  'host',
  'port',
  'model_routing',
  'max_revisions',
  'workflow_timeout',
  'daily_token_budget',
  'task_token_limit',
]

function redactKeys(all: Settings): Record<string, unknown> {
  return {
    ...all,
    anthropic_api_key: all.anthropic_api_key ? '••••••••' : '',
    deepseek_api_key: all.deepseek_api_key ? '••••••••' : '',
    langsmith_api_key: all.langsmith_api_key ? '••••••••' : '',
  }
}

export function registerIpcHandlers(): void {
  // ── Window controls ──────────────────────────────
  ipcMain.handle('window:minimize', () => {
    BrowserWindow.getFocusedWindow()?.minimize()
  })
  ipcMain.handle('window:maximize', () => {
    const win = BrowserWindow.getFocusedWindow()
    if (win) {
      win.isMaximized() ? win.unmaximize() : win.maximize()
    }
  })
  ipcMain.handle('window:close', () => {
    BrowserWindow.getFocusedWindow()?.close()
  })
  ipcMain.handle('window:isMaximized', () => {
    return BrowserWindow.getFocusedWindow()?.isMaximized() ?? false
  })

  // Track maximize state changes for all windows
  app.on('browser-window-created', (_event, win) => {
    win.on('maximize', () => win.webContents.send('window:maximize-changed', true))
    win.on('unmaximize', () => win.webContents.send('window:maximize-changed', false))
  })

  // ── Backend lifecycle ────────────────────────────
  ipcMain.handle('backend:start', async () => {
    try {
      const settings = getSettingsStore()
      pythonManager.start(settings.get('port'))
      return pythonManager.state
    } catch (err) {
      console.error('[IPC] backend:start failed:', err)
      return { ...pythonManager.state, error: 'Failed to start backend' }
    }
  })

  ipcMain.handle('backend:stop', async () => {
    try {
      await pythonManager.stop()
      return pythonManager.state
    } catch (err) {
      console.error('[IPC] backend:stop failed:', err)
      return { ...pythonManager.state, error: 'Failed to stop backend' }
    }
  })

  ipcMain.handle('backend:status', async () => {
    return pythonManager.state
  })

  pythonManager.on('status-change', (state) => {
    for (const win of BrowserWindow.getAllWindows()) {
      win.webContents.send('backend:status-changed', state)
    }
  })

  ipcMain.handle('dialog:selectDirectory', async () => {
    try {
      const win = BrowserWindow.getFocusedWindow()
      if (!win) return null

      const result = await dialog.showOpenDialog(win, {
        properties: ['openDirectory'],
      })

      if (result.canceled || result.filePaths.length === 0) return null
      return result.filePaths[0]
    } catch (err) {
      console.error('[IPC] dialog:selectDirectory failed:', err)
      return null
    }
  })

  ipcMain.handle('settings:get', (_event, key: string) => {
    const store = getSettingsStore()
    // Redact API keys even on single-key get
    if (key === 'anthropic_api_key' || key === 'deepseek_api_key' || key === 'langsmith_api_key') {
      const val = store.get(key as keyof Settings)
      return val ? '••••••••' : ''
    }
    return store.get(key as keyof Settings)
  })

  ipcMain.handle('settings:set', (_event, key: string, value: unknown) => {
    if (!ALLOWED_SETTINGS_KEYS.includes(key as keyof Settings)) {
      throw new Error(`Invalid settings key: ${key}`)
    }
    if (key === 'port' && typeof value !== 'number') {
      throw new Error('port must be a number')
    }
    if (key === 'model_routing' && (typeof value !== 'object' || value === null)) {
      throw new Error('model_routing must be an object')
    }
    const store = getSettingsStore()
    store.set(key as keyof Settings, value as never)
  })

  ipcMain.handle('settings:getAll', () => {
    const store = getSettingsStore()
    return redactKeys(store.getAll())
  })
}
