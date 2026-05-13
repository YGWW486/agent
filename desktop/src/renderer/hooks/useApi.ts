import { useMemo } from 'react'
import { useBackendStore } from '@/stores/backend.store'
import { createApi } from '@/lib/api'

export function useApi() {
  const port = useBackendStore((s) => s.port)
  return useMemo(() => createApi(`http://127.0.0.1:${port}`), [port])
}
