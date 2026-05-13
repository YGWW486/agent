import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { WorkspaceDir } from '@/components/workflow/WorkspaceSelector'

interface DraftState {
  spec: string
  context: string
  workspace: WorkspaceDir[]
  setSpec: (spec: string) => void
  setContext: (context: string) => void
  setWorkspace: (dirs: WorkspaceDir[]) => void
  clear: () => void
}

export const useDraftStore = create<DraftState>()(
  persist(
    (set) => ({
      spec: '',
      context: '',
      workspace: [],
      setSpec: (spec) => set({ spec }),
      setContext: (context) => set({ context }),
      setWorkspace: (workspace) => set({ workspace }),
      clear: () => set({ spec: '', context: '', workspace: [] }),
    }),
    {
      name: 'aec-draft',
      // 只持久化数据字段，不存函数
      partialize: (state) => ({ spec: state.spec, context: state.context, workspace: state.workspace }),
    },
  ),
)
