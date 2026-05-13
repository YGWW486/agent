import { useEffect, useRef, useCallback, useState } from 'react'
import type { SSEEvent, SSEEventType } from '../../shared/types'

const MAX_BACKOFF_MS = 30_000
const BASE_BACKOFF_MS = 1_000
const JITTER = 0.2
const MAX_BUFFER_BYTES = 1_048_576 // 1 MB

export function calcBackoff(attempt: number): number {
  const base = Math.min(BASE_BACKOFF_MS * 2 ** attempt, MAX_BACKOFF_MS)
  const jitter = base * JITTER * (Math.random() * 2 - 1)
  return Math.min(Math.round(base + jitter), MAX_BACKOFF_MS)
}

export async function parseSSEStream(
  stream: ReadableStream<Uint8Array>,
  onEvent: (event: SSEEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const reader = stream.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      if (signal?.aborted) break

      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      if (buffer.length > MAX_BUFFER_BYTES) {
        throw new Error('SSE buffer exceeded 1 MB — possible malformed stream')
      }

      const parts = buffer.split('\n\n')
      buffer = parts.pop() ?? ''

      for (const part of parts) {
        const parsed = parseSSEFrame(part)
        if (parsed) onEvent(parsed)
      }
    }
  } finally {
    reader.releaseLock()
  }
}

function parseSSEFrame(raw: string): SSEEvent | null {
  let eventType = 'message'
  const dataLines: string[] = []

  for (const line of raw.split('\n')) {
    if (line.startsWith(':') || line === '') continue
    if (line.startsWith('event:')) {
      eventType = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trim())
    }
  }

  if (eventType === 'message' && dataLines.length === 0) return null

  const dataStr = dataLines.join('\n')

  let data: Record<string, unknown> = {}
  if (dataStr) {
    try {
      data = JSON.parse(dataStr)
    } catch {
      data = { raw: dataStr }
    }
  }

  return {
    event: eventType as SSEEventType,
    ...data,
  }
}

interface UseSSEOptions {
  threadId: string | null
  streamUrl: string
  onEvent: (event: SSEEvent) => void
  onStatusRefresh?: () => Promise<void>
}

export function useSSE({ threadId, streamUrl, onEvent, onStatusRefresh }: UseSSEOptions) {
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState('')
  const attemptRef = useRef(0)
  const abortRef = useRef<AbortController | null>(null)
  const runningRef = useRef(false)

  const connect = useCallback(async () => {
    if (!threadId) return
    runningRef.current = true
    setError('')

    while (runningRef.current) {
      const controller = new AbortController()
      abortRef.current = controller

      try {
        if (attemptRef.current > 0 && onStatusRefresh) {
          await onStatusRefresh()
        }

        const res = await fetch(streamUrl, { signal: controller.signal })

        // 404: 工作流已不存在（后端重启后内存丢失），放弃重连
        if (res.status === 404) {
          setError('工作流已过期（后端重启后不再可用）')
          break
        }

        if (!res.ok || !res.body) {
          throw new Error(`SSE 连接失败 (${res.status})`)
        }

        setConnected(true)
        attemptRef.current = 0

        await parseSSEStream(res.body, (event) => {
          onEvent(event)
        }, controller.signal)

        break
      } catch (err) {
        if (!runningRef.current) break
        if ((err as Error).name === 'AbortError') break

        setConnected(false)
        const delay = calcBackoff(attemptRef.current)
        attemptRef.current++

        await new Promise((resolve) => setTimeout(resolve, delay))
      }
    }

    setConnected(false)
  }, [threadId, streamUrl, onEvent, onStatusRefresh])

  useEffect(() => {
    connect()
    return () => {
      runningRef.current = false
      abortRef.current?.abort()
    }
  }, [connect])

  return { connected, error }
}
