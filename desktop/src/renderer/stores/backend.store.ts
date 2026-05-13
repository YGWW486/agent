import { create } from 'zustand'
import type { BackendState, BackendStatus } from '../../shared/types'

interface BackendStore extends BackendState {
  setState: (patch: Partial<BackendState>) => void
}

export const useBackendStore = create<BackendStore>((set) => ({
  status: 'stopped' as BackendStatus,
  pid: null,
  port: 8000,
  uptime: 0,
  error: '',

  setState: (patch) =>
    set((prev) => ({ ...prev, ...patch })),
}))

export function updateBackendFromIpc(state: BackendState): void {
  useBackendStore.getState().setState(state)
}
