import { spawn } from 'node:child_process'
import type { ChildProcess } from 'node:child_process'
import { join, resolve } from 'node:path'
import { existsSync } from 'node:fs'
import { EventEmitter } from 'node:events'
import type { BackendState, Settings } from '../shared/types'
import { getSettingsStore } from './settings-store'

const ROOT = resolve(import.meta.dirname, '..', '..', '..')
const MAX_RESTART = 3
const HEALTH_POLL_MS = 5000
const HEALTH_MAX_ATTEMPTS = 12 // 60 seconds total
const KILL_TIMEOUT_MS = 5000

let _electronApp: { isPackaged: boolean } | null = null
try {
  _electronApp = require('electron').app
} catch {
  // Running in test environment — electron module not available
}

function isPackaged(): boolean {
  return _electronApp?.isPackaged ?? false
}

function findPython(): string {
  const isWin = process.platform === 'win32'
  const venvPython = isWin
    ? join(ROOT, '.venv', 'Scripts', 'python.exe')
    : join(ROOT, '.venv', 'bin', 'python3')
  if (existsSync(venvPython)) return venvPython
  return isWin ? 'python' : 'python3'
}

function getBackendCommand(): { cmd: string; args: string[]; cwd: string } {
  if (isPackaged()) {
    // Production: use bundled PyInstaller .exe
    const exePath = join(process.resourcesPath!, 'backend', 'agentic-server.exe')
    return { cmd: exePath, args: [], cwd: process.resourcesPath! }
  }
  // Development: use Python source with .venv
  const python = findPython()
  const serverPath = join(ROOT, 'bridge', 'server.py')
  return { cmd: python, args: [serverPath], cwd: ROOT }
}

export class PythonManager extends EventEmitter {
  private process: ChildProcess | null = null
  private restartCount = 0
  private startedAt = 0
  private pollTimer: ReturnType<typeof setInterval> | null = null
  private killTimer: ReturnType<typeof setTimeout> | null = null

  private _state: BackendState = {
    status: 'stopped',
    pid: null,
    port: 8000,
    uptime: 0,
    error: '',
  }

  get state(): Readonly<BackendState> {
    return { ...this._state }
  }

  private setState(patch: Partial<BackendState>) {
    this._state = { ...this._state, ...patch }
    this.emit('status-change', this.state)
  }

  start(port = 8000): void {
    if (this._state.status === 'running' || this._state.status === 'starting') return
    this.setState({ status: 'starting', port, error: '' })
    this.restartCount = 0
    this.spawnProcess(port)
  }

  private spawnProcess(port: number): void {
    const { cmd, args, cwd } = getBackendCommand()

    // 从 electron-store 读取用户设置，注入为 Python 环境变量
    let storeSettings: Settings | Record<string, unknown> = {}
    try {
      storeSettings = getSettingsStore().getAll()
    } catch {
      // settings store 不可用时回退（如测试环境）
    }

    const settingEnv: Record<string, string> = {}
    if (storeSettings.llm_provider) settingEnv['LLM_PROVIDER'] = String(storeSettings.llm_provider)
    if (storeSettings.anthropic_api_key) settingEnv['ANTHROPIC_API_KEY'] = String(storeSettings.anthropic_api_key)
    if (storeSettings.deepseek_api_key) settingEnv['DEEPSEEK_API_KEY'] = String(storeSettings.deepseek_api_key)
    if (storeSettings.langsmith_api_key) settingEnv['LANGSMITH_API_KEY'] = String(storeSettings.langsmith_api_key)
    if (storeSettings.host) settingEnv['HOST'] = String(storeSettings.host)
    if (storeSettings.max_revisions !== undefined) settingEnv['MAX_REVISIONS'] = String(storeSettings.max_revisions)
    if (storeSettings.workflow_timeout !== undefined) settingEnv['WORKFLOW_TIMEOUT'] = String(storeSettings.workflow_timeout)
    if (storeSettings.daily_token_budget !== undefined) settingEnv['DAILY_TOKEN_BUDGET'] = String(storeSettings.daily_token_budget)
    if (storeSettings.task_token_limit !== undefined) settingEnv['TASK_TOKEN_LIMIT'] = String(storeSettings.task_token_limit)

    this.process = spawn(cmd, args, {
      cwd,
      env: Object.fromEntries(Object.entries({
        PORT: String(port),
        PYTHONPATH: cwd,
        PATH: process.env.PATH || '',
        SYSTEMROOT: process.env.SYSTEMROOT || '',
        HOME: process.env.HOME || '',
        USERPROFILE: process.env.USERPROFILE || '',
        VIRTUAL_ENV: process.env.VIRTUAL_ENV || '',
        PYTHONUNBUFFERED: '1',
        ...settingEnv,
        // .env 中的值作为回退
        ANTHROPIC_API_KEY: settingEnv['ANTHROPIC_API_KEY'] || process.env.ANTHROPIC_API_KEY || '',
        DEEPSEEK_API_KEY: settingEnv['DEEPSEEK_API_KEY'] || process.env.DEEPSEEK_API_KEY || '',
        LANGSMITH_API_KEY: settingEnv['LANGSMITH_API_KEY'] || process.env.LANGSMITH_API_KEY || '',
        LANGSMITH_PROJECT: process.env.LANGSMITH_PROJECT || '',
        LANGSMITH_ENDPOINT: process.env.LANGSMITH_ENDPOINT || '',
        LANGSMITH_TRACING: process.env.LANGSMITH_TRACING || '',
      }).filter(([, v]) => v !== '')) as Record<string, string>,
      stdio: ['pipe', 'pipe', 'pipe'],
    })

    this.process.stdout?.on('data', (chunk: Buffer) => {
      // stdout forwarded for debugging — no PII expected in Python server logs
      process.stdout.write(`[python] ${chunk.toString()}`)
    })
    this.process.stderr?.on('data', (chunk: Buffer) => {
      process.stderr.write(`[python:err] ${chunk.toString()}`)
    })

    this.process.on('spawn', () => {
      this.setState({ pid: this.process!.pid ?? null })
      this.startedAt = Date.now()
      this.startHealthPoll(port)
    })

    this.process.on('exit', (code) => {
      this.clearTimers()
      if (this._state.status === 'stopped') return

      if (code === 0) {
        this.setState({ status: 'stopped', pid: null, uptime: 0 })
        return
      }

      this.restartCount++
      if (this.restartCount <= MAX_RESTART) {
        this.setState({
          status: 'starting',
          pid: null,
          error: `Process exited (code ${code}), restarting ${this.restartCount}/${MAX_RESTART}`,
        })
        setTimeout(() => this.spawnProcess(port), 1000)
      } else {
        this.setState({
          status: 'error',
          pid: null,
          error: `Process crashed ${MAX_RESTART} times, giving up`,
        })
      }
    })
  }

  private startHealthPoll(port: number): void {
    let attempts = 0
    this.pollTimer = setInterval(async () => {
      attempts++
      try {
        const res = await fetch(`http://127.0.0.1:${port}/api/health`)
        if (res.ok) {
          this.clearPollTimer()
          this.setState({
            status: 'running',
            uptime: Date.now() - this.startedAt,
          })
          return
        }
      } catch {
        // backend not ready yet
      }

      if (attempts >= HEALTH_MAX_ATTEMPTS) {
        this.clearPollTimer()
        this.process?.kill('SIGTERM')
        this.setState({
          status: 'error',
          error: `Health check failed after ${HEALTH_MAX_ATTEMPTS} attempts (${HEALTH_MAX_ATTEMPTS * HEALTH_POLL_MS / 1000}s)`,
        })
      }
    }, HEALTH_POLL_MS)
  }

  async stop(): Promise<void> {
    if (this._state.status === 'stopped') return

    this.clearTimers()

    if (this.process && this.process.pid) {
      // 先标记为主动停止，防止 exit 事件误判为崩溃重启
      this.setState({ status: 'stopped' })

      // Try graceful HTTP shutdown first, then SIGTERM
      try {
        const port = this._state.port
        await fetch(`http://127.0.0.1:${port}/api/shutdown`, { method: 'POST' })
      } catch {
        // shutdown endpoint may not exist; fall through to SIGTERM
      }

      // SIGTERM: graceful on Unix, immediate on Windows (documented limitation)
      this.process.kill('SIGTERM')

      this.killTimer = setTimeout(() => {
        if (this.process && this.process.exitCode === null) {
          this.process.kill('SIGKILL')
        }
      }, KILL_TIMEOUT_MS)
    } else {
      this.setState({ status: 'stopped', pid: null, uptime: 0 })
    }
  }

  private clearTimers(): void {
    this.clearPollTimer()
    if (this.killTimer) {
      clearTimeout(this.killTimer)
      this.killTimer = null
    }
  }

  private clearPollTimer(): void {
    if (this.pollTimer) {
      clearInterval(this.pollTimer)
      this.pollTimer = null
    }
  }
}
