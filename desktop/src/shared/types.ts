/** Shared types between main, preload, and renderer processes. */

export type BackendStatus = 'stopped' | 'starting' | 'running' | 'error'

export interface BackendState {
  status: BackendStatus
  pid: number | null
  port: number
  uptime: number
  error: string
}

export interface HealthResponse {
  status: string
  model: string
  token_usage: Record<string, number>
}

export interface StartWorkflowResponse {
  thread_id: string
  status: string
  stream_url: string
}

export interface WorkflowState {
  thread_id: string
  status: string
  plan_summary: PlanSummary | null
  code: string
  review_summary: ReviewSummary | null
  revision_count: number
  current_task_index: number
  suspended: boolean
  failure_reason: string
  error: string
}

export interface PlanSummary {
  task_count: number
  current_task: string | null
}

export interface ReviewSummary {
  verdict: 'PASS' | 'REJECT'
  reason: string
}

export interface Settings {
  llm_provider: string
  anthropic_api_key: string
  deepseek_api_key: string
  langsmith_api_key: string
  host: string
  port: number
  model_routing: ModelRouting
  max_revisions: number
  workflow_timeout: number
  daily_token_budget: number
  task_token_limit: number
}

export interface ModelRouting {
  simple: string
  standard: string
  complex: string
}

export interface IndexStats {
  node_count: number
  edge_count: number
  files_indexed: number
  loaded_at: string
}

export interface RegisteredSkill {
  name: string
  category: string
  description: string
  parameters: Record<string, unknown>
  execution_count?: number
}

export interface SkillsResponse {
  workflow: string
  hitl: string
  models: ModelRouting
  max_revisions: number
  features: string[]
  registered_skills?: RegisteredSkill[]
}

export type SSEEventType =
  | 'node_start'
  | 'node_complete'
  | 'tool_call'
  | 'tool_result'
  | 'interrupt'
  | 'workflow_complete'
  | 'workflow_error'
  | 'stream_end'
  | 'heartbeat'

export type ToolStepStatus = 'running' | 'success' | 'warning' | 'error'
export type ObsStatus = 'success' | 'warning' | 'error'

export interface ToolStep {
  tool: string
  status: ToolStepStatus
  summary: string
  input?: Record<string, unknown>
  timestamp?: string
}

export interface SSEEvent {
  event: SSEEventType
  node?: string
  timestamp?: string
  /** P5: 人可读结论（字符串）；历史数据可能无此字段 */
  summary?: string
  detail?: Record<string, unknown>
  next_actions?: string[]
  artifacts?: Record<string, unknown>
  status?: ObsStatus | ToolStepStatus
  suspended?: boolean
  failure_reason?: string
  message?: string
  thread_id?: string
  error?: string
  tool?: string
  input?: Record<string, unknown>
  tool_summary?: string
}

export type NodeStatus = 'pending' | 'running' | 'success' | 'failed' | 'suspended'

export interface TimelineNode {
  name: string
  label: string
  status: NodeStatus
  /** 节点 detail（_diff、_tasks 等） */
  summary: Record<string, unknown> | null
  observation_summary?: string
  next_actions?: string[]
  started_at: string | null
  completed_at: string | null
  suspended: boolean
  failure_reason: string
  tool_steps?: ToolStep[]
}

export interface WrittenFile {
  path: string
  backup: string | null
  size: number
}

export interface TestResults {
  ran: boolean
  passed: number
  failed: number
  total: number
  output: string
  message?: string
  return_code?: number
}

export interface WorkflowUIState {
  threadId: string
  nodes: TimelineNode[]
  spec: string
  interrupt: boolean
  hitl_next_actions?: string[]
  error: string
  result: string
  writtenFiles: WrittenFile[]
  testResults: TestResults | null
}
