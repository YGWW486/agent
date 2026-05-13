import { create } from 'zustand'
import type { IndexStats } from '../../shared/types'

interface IndexStore {
  stats: IndexStats | null
  loading: boolean
  error: string
  setStats: (stats: IndexStats) => void
  setLoading: (loading: boolean) => void
  setError: (error: string) => void
}

export const useIndexStore = create<IndexStore>((set) => ({
  stats: null,
  loading: false,
  error: '',

  setStats: (stats) => set({ stats, error: '' }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error, loading: false }),
}))
