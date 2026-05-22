import { create } from 'zustand'
import type { WorkflowUIState } from '../../shared/types'

interface WorkflowStore {
  workflows: Map<string, WorkflowUIState>
  addWorkflow: (threadId: string, spec: string) => void
  updateWorkflow: (threadId: string, patch: Partial<WorkflowUIState>) => void
  removeWorkflow: (threadId: string) => void
  getWorkflow: (threadId: string) => WorkflowUIState | undefined
}

export const useWorkflowStore = create<WorkflowStore>((set, get) => ({
  workflows: new Map(),

  addWorkflow: (threadId, spec) =>
    set((prev) => {
      const next = new Map(prev.workflows)
      next.set(threadId, {
        threadId,
        spec,
        nodes: [],
        interrupt: false,
        error: '',
        result: '',
        writtenFiles: [],
        testResults: null,
      })
      return { workflows: next }
    }),

  updateWorkflow: (threadId, patch) =>
    set((prev) => {
      const existing = prev.workflows.get(threadId)
      if (!existing) return prev
      const next = new Map(prev.workflows)
      next.set(threadId, { ...existing, ...patch })
      return { workflows: next }
    }),

  removeWorkflow: (threadId) =>
    set((prev) => {
      const next = new Map(prev.workflows)
      next.delete(threadId)
      return { workflows: next }
    }),

  getWorkflow: (threadId) => get().workflows.get(threadId),
}))
