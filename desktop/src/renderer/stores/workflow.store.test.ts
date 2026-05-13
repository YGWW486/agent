import { describe, it, expect, beforeEach } from 'vitest'
import { useWorkflowStore } from './workflow.store'

describe('workflowStore', () => {
  beforeEach(() => {
    // Reset store between tests
    useWorkflowStore.setState({ workflows: new Map() })
  })

  it('starts with empty map', () => {
    expect(useWorkflowStore.getState().workflows.size).toBe(0)
  })

  it('addWorkflow inserts with spec and default state', () => {
    useWorkflowStore.getState().addWorkflow('t1', 'build login')

    const wf = useWorkflowStore.getState().getWorkflow('t1')
    expect(wf).toBeDefined()
    expect(wf!.threadId).toBe('t1')
    expect(wf!.spec).toBe('build login')
    expect(wf!.nodes).toEqual([])
    expect(wf!.interrupt).toBe(false)
    expect(wf!.error).toBe('')
    expect(wf!.result).toBe('')
  })

  it('addWorkflow does not mutate previous Map', () => {
    const prevMap = useWorkflowStore.getState().workflows
    useWorkflowStore.getState().addWorkflow('t1', 'spec')

    expect(useWorkflowStore.getState().workflows).not.toBe(prevMap)
    expect(prevMap.size).toBe(0)
  })

  it('updateWorkflow patches existing workflow', () => {
    useWorkflowStore.getState().addWorkflow('t1', 'spec')
    useWorkflowStore.getState().updateWorkflow('t1', { error: 'boom' })

    const wf = useWorkflowStore.getState().getWorkflow('t1')
    expect(wf!.error).toBe('boom')
    expect(wf!.spec).toBe('spec') // unchanged
  })

  it('updateWorkflow returns prev state for unknown threadId', () => {
    const prev = useWorkflowStore.getState()
    useWorkflowStore.getState().updateWorkflow('unknown', { error: 'x' })

    expect(useWorkflowStore.getState()).toBe(prev)
  })

  it('getWorkflow returns undefined for unknown threadId', () => {
    expect(useWorkflowStore.getState().getWorkflow('nope')).toBeUndefined()
  })

  it('handles multiple workflows independently', () => {
    useWorkflowStore.getState().addWorkflow('t1', 'spec1')
    useWorkflowStore.getState().addWorkflow('t2', 'spec2')
    useWorkflowStore.getState().updateWorkflow('t1', { error: 'e1' })

    expect(useWorkflowStore.getState().workflows.size).toBe(2)
    expect(useWorkflowStore.getState().getWorkflow('t1')!.error).toBe('e1')
    expect(useWorkflowStore.getState().getWorkflow('t2')!.error).toBe('')
  })
})
