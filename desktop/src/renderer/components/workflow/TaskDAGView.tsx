import { useMemo } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

interface TaskInfo {
  task_id: string
  description: string
  estimated_minutes: number
  dependencies: string[]
}

interface TaskDAGViewProps {
  tasks: TaskInfo[]
  currentTaskIndex: number
}

export function TaskDAGView({ tasks, currentTaskIndex }: TaskDAGViewProps) {
  const { nodes, edges } = useMemo(() => {
    const flowNodes: Node[] = tasks.map((t, i) => ({
      id: t.task_id,
      data: {
        label: (
          <div className="text-xs leading-tight">
            <div className="font-mono font-semibold text-[10px] opacity-60 mb-0.5">{t.task_id}</div>
            <div className="line-clamp-2">{t.description}</div>
            <div className="text-[10px] opacity-50 mt-1">{t.estimated_minutes}m</div>
          </div>
        ),
      },
      position: { x: 0, y: 0 },
      style: {
        background: i <= currentTaskIndex ? 'oklch(68% 0.18 140 / 0.15)' : 'oklch(22% 0.01 260)',
        border:
          i === currentTaskIndex
            ? '1px solid oklch(68% 0.18 140 / 0.6)'
            : i < currentTaskIndex
              ? '1px solid oklch(68% 0.18 140 / 0.25)'
              : '1px solid oklch(100% 0 0 / 0.08)',
        borderRadius: '8px',
        padding: '10px 14px',
        width: 180,
      },
    }))

    const flowEdges: Edge[] = tasks.flatMap((t) =>
      t.dependencies.map((dep) => ({
        id: `${dep}→${t.task_id}`,
        source: dep,
        target: t.task_id,
        style: { stroke: 'oklch(100% 0 0 / 0.15)' },
      })),
    )

    return { nodes: flowNodes, edges: flowEdges }
  }, [tasks, currentTaskIndex])

  if (tasks.length === 0) {
    return <p className="text-xs text-text-muted py-4 text-center">No task DAG data available.</p>
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3 text-xs text-text-muted">
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-status-running/50" /> Done
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-status-running ring-1 ring-status-running/60" /> In progress
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-white/10" /> Pending
        </span>
      </div>
      <div className="h-64 rounded-md border border-white/8 overflow-hidden">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          fitViewOptions={{ padding: 0.3 }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="oklch(100% 0 0 / 0.04)" gap={20} />
          <Controls className="[&>button]:!bg-surface-overlay [&>button]:!border-white/10 [&>button]:!text-text-secondary" />
          <MiniMap
            className="!bg-surface-overlay !border-white/10"
            maskColor="oklch(14% 0.01 260 / 0.8)"
            nodeColor="oklch(22% 0.01 260)"
          />
        </ReactFlow>
      </div>
    </div>
  )
}
