import { useEffect, useCallback } from 'react'
import { useBackendStore, updateBackendFromIpc } from '@/stores/backend.store'
import type { BackendState } from '../../shared/types'

const api = () => window.electronAPI

const autoStarted = { current: false }

export function useBackend() {
  const status = useBackendStore((s) => s.status)

  useEffect(() => {
    if (!window.electronAPI) return
    const cleanup = window.electronAPI.on(
      'backend:status-changed',
      (state) => {
        updateBackendFromIpc(state as BackendState)
      },
    )

    // Auto-start backend on first mount
    if (!autoStarted.current) {
      autoStarted.current = true
      api().backend.status().then((state) => {
        const s = state as BackendState
        updateBackendFromIpc(s)
        if (s.status === 'stopped') {
          api().backend.start().then((s2) => updateBackendFromIpc(s2 as BackendState))
        }
      })
    }

    return cleanup
  }, [])

  const start = useCallback(async () => {
    const state = await api().backend.start()
    updateBackendFromIpc(state as BackendState)
  }, [])

  const stop = useCallback(async () => {
    const state = await api().backend.stop()
    updateBackendFromIpc(state as BackendState)
  }, [])

  const refresh = useCallback(async () => {
    const state = await api().backend.status()
    updateBackendFromIpc(state as BackendState)
  }, [])

  return { status, start, stop, refresh } as const
}
