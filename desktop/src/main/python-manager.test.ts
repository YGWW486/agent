import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

const mockSpawn = vi.fn()
vi.mock('child_process', () => ({ spawn: mockSpawn }))
vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('default')))

function mockProcess() {
  const listeners: Record<string, Array<(...args: unknown[]) => void>> = {}
  return {
    pid: 12345,
    stdout: { on: vi.fn() },
    stderr: { on: vi.fn() },
    kill: vi.fn(),
    on: vi.fn((event: string, cb: (...args: unknown[]) => void) => {
      ;(listeners[event] ??= []).push(cb)
    }),
    emit(event: string, ...args: unknown[]) {
      ;(listeners[event] ?? []).forEach((cb) => cb(...args))
    },
  }
}

describe('PythonManager', () => {
  let PythonManager: InstanceType<typeof import('./python-manager').PythonManager>
  let proc: ReturnType<typeof mockProcess>

  beforeEach(async () => {
    vi.clearAllMocks()
    proc = mockProcess()
    mockSpawn.mockReturnValue(proc)
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('default')))

    const mod = await import('./python-manager')
    PythonManager = new mod.PythonManager()
  })

  afterEach(async () => {
    await PythonManager.stop()
    vi.useRealTimers()
  })

  describe('start()', () => {
    it('spawns python with bridge/server.py', () => {
      PythonManager.start()

      expect(mockSpawn).toHaveBeenCalledTimes(1)
      const [cmd, args] = mockSpawn.mock.calls[0] as [string, string[]]
      expect(cmd).toMatch(/python/)
      expect(args[0]).toContain('bridge')
      expect(args[0]).toContain('server.py')
    })

    it('sets PYTHONPATH to project root so api/ imports work', () => {
      PythonManager.start()

      const [, , opts] = mockSpawn.mock.calls[0] as [string, string[], { env: Record<string, string>, cwd: string }]
      expect(opts.env.PYTHONPATH).toBeDefined()
      expect(opts.env.PYTHONPATH).toBe(opts.cwd)
      expect(opts.env.PYTHONPATH).toMatch(/qa$/)
    })

    it('sets status to "starting" immediately', () => {
      PythonManager.start()
      expect(PythonManager.state.status).toBe('starting')
    })

    it('transitions to "running" after health check passes', async () => {
      vi.useFakeTimers()
      vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce({ ok: true }))

      PythonManager.start()
      proc.emit('spawn')
      await vi.advanceTimersByTimeAsync(5000)

      expect(PythonManager.state.status).toBe('running')
      vi.useRealTimers()
    })

    it('transitions to "error" after max restart attempts', async () => {
      vi.useFakeTimers()
      PythonManager.start()

      // 4 crashes: initial + 3 restarts → 4th triggers error
      for (let i = 0; i < 4; i++) {
        // Set what next spawn() returns BEFORE emit triggers the restart
        const nextProc = mockProcess()
        mockSpawn.mockReturnValue(nextProc)
        proc.emit('exit', 1)
        await vi.advanceTimersByTimeAsync(1001)
        proc = nextProc
      }

      expect(PythonManager.state.status).toBe('error')
      expect(PythonManager.state.error).toContain('crashed')
      vi.useRealTimers()
    })

    it('restarts on unexpected exit', async () => {
      vi.useFakeTimers()
      PythonManager.start()

      const proc2 = mockProcess()
      mockSpawn.mockReturnValue(proc2)
      proc.emit('exit', 1)
      await vi.advanceTimersByTimeAsync(1001)

      expect(mockSpawn).toHaveBeenCalledTimes(2)
      expect(PythonManager.state.status).toBe('starting')
      vi.useRealTimers()
    })

    it('is a no-op when already starting', () => {
      PythonManager.start()
      PythonManager.start()
      expect(mockSpawn).toHaveBeenCalledTimes(1)
    })
  })

  describe('stop()', () => {
    it('calls kill with SIGTERM', async () => {
      PythonManager.start()
      await PythonManager.stop()
      expect(proc.kill).toHaveBeenCalledWith('SIGTERM')
    })

    it('sets status to "stopped" when process exits with code 0', async () => {
      PythonManager.start()
      await PythonManager.stop()
      proc.emit('exit', 0)
      expect(PythonManager.state.status).toBe('stopped')
    })

    it('is a no-op when already stopped', async () => {
      await PythonManager.stop()
      expect(mockSpawn).not.toHaveBeenCalled()
    })
  })

  describe('state', () => {
    it('exposes correct defaults', () => {
      expect(PythonManager.state).toEqual({
        status: 'stopped',
        pid: null,
        port: 8000,
        uptime: 0,
        error: '',
      })
    })

    it('emits "status-change" on start', () => {
      const listener = vi.fn()
      PythonManager.on('status-change', listener)
      PythonManager.start()

      expect(listener).toHaveBeenCalledWith(
        expect.objectContaining({ status: 'starting' }),
      )
    })
  })
})
