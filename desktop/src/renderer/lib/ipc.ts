import type { ElectronAPI } from '../../preload/index'

export const api = (): ElectronAPI => window.electronAPI
