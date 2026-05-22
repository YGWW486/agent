import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

import { parseSSEStream, calcBackoff } from './useSSE'

const MAX_BACKOFF_MS = 30_000

function sseFrame(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`
}

function mockStream(...chunks: string[]) {
  const encoder = new TextEncoder()
  let i = 0
  return new ReadableStream({
    pull(controller) {
      if (i < chunks.length) {
        controller.enqueue(encoder.encode(chunks[i]))
        i++
      } else {
        controller.close()
      }
    },
  })
}

describe('parseSSEStream', () => {
  it('parses a single SSE frame', async () => {
    const stream = mockStream(sseFrame('node_start', { node: 'planner' }))

    const events: unknown[] = []
    await parseSSEStream(stream, (evt) => events.push(evt))

    expect(events).toHaveLength(1)
    expect(events[0]).toMatchObject({ event: 'node_start', node: 'planner' })
  })

  it('parses multiple frames in one chunk', async () => {
    const chunk =
      sseFrame('node_start', { node: 'planner' }) +
      sseFrame('node_complete', { node: 'planner', summary: { task_count: 5 } })

    const stream = mockStream(chunk)
    const events: unknown[] = []
    await parseSSEStream(stream, (evt) => events.push(evt))

    expect(events).toHaveLength(2)
    expect(events[0]).toMatchObject({ event: 'node_start' })
    expect(events[1]).toMatchObject({ event: 'node_complete' })
  })

  it('handles frames split across chunks', async () => {
    const fullFrame = sseFrame('node_complete', { node: 'coder', summary: { code_len: 200 } })
    const splitPoint = Math.floor(fullFrame.length / 2)

    const stream = mockStream(fullFrame.slice(0, splitPoint), fullFrame.slice(splitPoint))
    const events: unknown[] = []
    await parseSSEStream(stream, (evt) => events.push(evt))

    expect(events).toHaveLength(1)
    expect(events[0]).toMatchObject({ event: 'node_complete' })
  })

  it('emits heartbeat events', async () => {
    const stream = mockStream('event: heartbeat\ndata: {}\n\n')
    const events: unknown[] = []
    await parseSSEStream(stream, (evt) => events.push(evt))

    expect(events).toHaveLength(1)
    expect(events[0]).toMatchObject({ event: 'heartbeat' })
  })

  it('emits workflow_complete with thread_id', async () => {
    const stream = mockStream(sseFrame('workflow_complete', { thread_id: 'abc' }))
    const events: unknown[] = []
    await parseSSEStream(stream, (evt) => events.push(evt))

    expect(events[0]).toMatchObject({ event: 'workflow_complete', thread_id: 'abc' })
  })

  it('emits interrupt event', async () => {
    const stream = mockStream(
      sseFrame('interrupt', { message: '等待审批', timestamp: '2026-01-01T00:00:00Z' }),
    )
    const events: unknown[] = []
    await parseSSEStream(stream, (evt) => events.push(evt))

    expect(events[0]).toMatchObject({
      event: 'interrupt',
      message: '等待审批',
    })
  })

  it('parses P5 observation fields on node_complete', async () => {
    const stream = mockStream(
      sseFrame('node_complete', {
        node: 'planner',
        status: 'success',
        summary: '已拆解 3 个任务',
        next_actions: [],
        detail: { task_count: 3 },
      }),
    )
    const events: unknown[] = []
    await parseSSEStream(stream, (evt) => events.push(evt))

    expect(events[0]).toMatchObject({
      event: 'node_complete',
      status: 'success',
      summary: '已拆解 3 个任务',
      next_actions: [],
      detail: { task_count: 3 },
    })
  })

  it('handles empty data gracefully', async () => {
    const stream = mockStream('event: heartbeat\ndata: \n\n')
    const events: unknown[] = []
    await parseSSEStream(stream, (evt) => events.push(evt))

    expect(events).toHaveLength(1)
    expect(events[0]).toMatchObject({ event: 'heartbeat' })
  })

  it('ignores comment lines starting with colon', async () => {
    const stream = mockStream(': this is a comment\nevent: heartbeat\ndata: {}\n\n')
    const events: unknown[] = []
    await parseSSEStream(stream, (evt) => events.push(evt))

    expect(events).toHaveLength(1)
    expect(events[0]).toMatchObject({ event: 'heartbeat' })
  })

  it('throws on stream error', async () => {
    const stream = new ReadableStream({
      start(controller) {
        controller.error(new Error('stream broke'))
      },
    })

    await expect(parseSSEStream(stream, () => {})).rejects.toThrow('stream broke')
  })
})

describe('backoff', () => {
  it('calculates exponential backoff with jitter', () => {

    // Attempt 0: ~1000ms
    const d0 = calcBackoff(0)
    expect(d0).toBeGreaterThanOrEqual(800)
    expect(d0).toBeLessThanOrEqual(1200)

    // Attempt 3: ~8000ms
    const d3 = calcBackoff(3)
    expect(d3).toBeGreaterThanOrEqual(6400)
    expect(d3).toBeLessThanOrEqual(9600)

    // Attempt 10: clamped at 30000ms
    const d10 = calcBackoff(10)
    expect(d10).toBeGreaterThanOrEqual(24000)
    expect(d10).toBeLessThanOrEqual(MAX_BACKOFF_MS)
  })
})
