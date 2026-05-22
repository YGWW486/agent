# Agentic Engineering Console — 使用说明书

> 版本: 0.1.0 | 最后更新: 2026-05-13

---

## 目录

1. [项目概述](#1-项目概述)
2. [环境准备](#2-环境准备)
3. [网页端使用](#3-网页端使用)
4. [桌面端使用](#4-桌面端使用)
5. [桌面端打包](#5-桌面端打包)
6. [操作流程](#6-操作流程)
7. [配置参考](#7-配置参考)
8. [API 参考](#8-api-参考)
9. [故障排查](#9-故障排查)
10. [构建产物与打包经验](#10-构建产物与打包经验)

---

## 1. 项目概述

Agentic Engineering Console 是一个**本地优先**的多 Agent 编码控制台。后端使用 FastAPI + LangGraph 编排 AI Agent 流水线，前端提供 Electron 桌面应用（也可独立使用 Web 界面）。

### 核心流程

```
用户提交 Spec → Planner(拆解任务DAG) → Coder(编写代码+自检)
    → Reviewer(审查+附带测试) → 人工审批(Merge) → 查看 Diff/代码
```

### 技术架构

```
┌─────────────────────────────────────────────┐
│  Electron Desktop (React + TypeScript)       │
│  ┌──────────────────────────────────────┐   │
│  │  Renderer (UI)                        │   │
│  │  Zustand stores / SSE hooks / Monaco │   │
│  └──────────┬───────────────────────────┘   │
│             │ IPC (contextBridge)            │
│  ┌──────────┴───────────────────────────┐   │
│  │  Main Process                         │   │
│  │  PythonManager / SettingsStore        │   │
│  └──────────┬───────────────────────────┘   │
│             │ child_process.spawn             │
├─────────────┴───────────────────────────────┤
│  Python Backend (FastAPI + LangGraph)        │
│  ┌──────────────────────────────────────┐   │
│  │  API Routes (/api/*)                  │   │
│  │  Agent Orchestrator (Planner/Coder/   │   │
│  │    Reviewer/Merge)                    │   │
│  │  GraphIndex (graphify 知识图谱查询)   │   │
│  │  AnthropicLLM (SDK 封装)              │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

---

## 2. 环境准备

### 2.1 系统要求

| 项 | 最低配置 |
|----|----------|
| 操作系统 | Windows 10+ (首发); macOS/Linux 后续 |
| Python | 3.12+ |
| Node.js | 18+ |
| 包管理器 | pip + pnpm (推荐) |
| 磁盘空间 | ~2 GB (含 .venv + node_modules) |

### 2.2 克隆与安装

```bash
# 1. 进入项目目录
cd D:\ZHIYI\AUTO\qa

# 2. 创建 Python 虚拟环境
python -m venv .venv

# 3. 激活虚拟环境 (Windows PowerShell)
.venv\Scripts\Activate.ps1

# 4. 安装 Python 依赖
pip install -r requirements.txt

# 5. 安装前端依赖
cd desktop
pnpm install
cd ..
```

> **常见问题：Electron 二进制未下载**
>
> `pnpm install` 完成后，Electron 的二进制文件（~188 MB）可能因网络或权限问题未能自动下载。表现为 `pnpm dev` 报错 `Error: Electron uninstall`。
>
> **验证是否已下载**：
> ```powershell
> # 存在 dist/ 目录和 path.txt 即为正常
> ls desktop\node_modules\electron\dist\electron.exe
> ls desktop\node_modules\electron\path.txt
> ```
>
> **如果缺失，手动下载**：
> ```powershell
> cd desktop
> # 国内网络先设镜像
> $env:ELECTRON_MIRROR = "https://npmmirror.com/mirrors/electron/"
> # 执行安装脚本，下载 Electron 二进制到 node_modules/electron/dist/
> node node_modules/electron/install.js
> ```
>
> 详见 [第 9 节故障排查](#91-常见问题) 和 [第 10.3 节坑 1](#坑-1pnpm-把-electron-二进制隔离到-ignored)。

### 2.3 配置环境变量

复制并编辑 `.env` 文件：

```bash
# 必填
ANTHROPIC_API_KEY=sk-ant-xxxxx        # 你的 Anthropic API Key

# 可选
LANGSMITH_API_KEY=ls_xxxxx            # LangSmith 可观测性 (推荐)
LANGSMITH_TRACING=true
```

其他配置项见 [第 7 节](#7-配置参考)。

---

## 3. 网页端使用

网页端指**不启动 Electron 桌面壳**，直接通过浏览器访问 Python 后端。适合开发调试、API 测试、或服务器部署场景。

### 3.1 启动后端服务

```bash
# 确保在项目根目录，且 .venv 已激活
python bridge/server.py
```

输出：
```
INFO - Agent Server starting on 127.0.0.1:8000
INFO - Default model: claude-sonnet-4-6
```

### 3.2 访问接口

| 地址 | 说明 |
|------|------|
| `http://127.0.0.1:8000/` | 服务状态 + 运行时间 |
| `http://127.0.0.1:8000/docs` | Swagger UI — 交互式 API 文档 |
| `http://127.0.0.1:8000/api/health` | 健康检查（含 token 用量） |
| `http://127.0.0.1:8000/api/skills` | Agent 能力清单 |

### 3.3 通过 Swagger UI 提交工作流

1. 打开 `http://127.0.0.1:8000/docs`
2. 找到 `POST /api/workflow`，点击 "Try it out"
3. 填写请求体：

```json
{
  "spec": "创建一个 Python FastAPI 用户登录接口，支持 JWT 认证",
  "context": "项目使用 FastAPI + Pydantic，数据库为 PostgreSQL"
}
```

4. 点击 Execute，获取 `thread_id`
5. 用 `GET /api/workflow/{thread_id}` 查询状态
6. 用 `GET /api/workflow/{thread_id}/stream` 打开 SSE 流查看实时进度
7. 当状态显示 `suspended` 时，用 `POST /api/workflow/{thread_id}/approve` 进行审批

### 3.4 使用 curl 测试

```bash
# 提交工作流
curl -X POST http://127.0.0.1:8000/api/workflow \
  -H "Content-Type: application/json" \
  -d '{"spec": "创建一个 FastAPI 健康检查端点", "context": ""}'

# 查询状态
curl http://127.0.0.1:8000/api/workflow/{thread_id}

# 审批通过
curl -X POST http://127.0.0.1:8000/api/workflow/{thread_id}/approve \
  -H "Content-Type: application/json" \
  -d '{"approved": true, "comment": ""}'

# 审批拒绝
curl -X POST http://127.0.0.1:8000/api/workflow/{thread_id}/approve \
  -H "Content-Type: application/json" \
  -d '{"approved": false, "comment": "缺少输入验证"}'

# 建立知识索引（先运行 /graphify 生成 graph.json）
curl -X POST http://127.0.0.1:8000/api/index/rebuild \
  -H "Content-Type: application/json" \
  -d '{"graph_path": "D:/ZHIYI/AUTO/qa/graphify-out/graph.json"}'

# 查询上下文
curl "http://127.0.0.1:8000/api/context?files=agent/orchestrator.py,bridge/server.py&depth=2"
```

---

## 4. 桌面端使用

### 4.1 开发模式启动

```bash
cd desktop

# 同时启动：Electron 窗口 + Python 后端 + Vite HMR
pnpm dev
```

启动后：
1. Electron 窗口打开，显示主界面
2. Sidebar 右下角状态指示灯：红(stopped) → 黄(starting) → 绿(running)
3. 绿色亮起后即可正常使用所有功能

### 4.2 界面导览

```
┌──────────────────────────────────────────────────┐
│  TopBar: 面包屑导航 + [New Workflow]              │
├────────┬─────────────────────────────────────────┤
│Sidebar │  主内容区                                │
│        │                                          │
│ 导航:  │  / → HomePage (仪表盘)                   │
│ 🏠 Home │  /workflows → 工作流列表               │
│ ⚡ New  │  /workflow/new → 提交 Spec              │
│ 📊 Index│  /workflow/:id → 时间线+审批+Diff      │
│ ⚙️ Sett.│ /index → 知识索引管理                   │
│        │  /settings → 设置页                      │
│ ────── │                                          │
│ 后端   │                                          │
│ 🟢 运行 │                                          │
│ pid:42 │                                          │
└────────┴──────────────────────────────────────────┘
```

### 4.3 各页面说明

**HomePage** — 仪表盘，4 张功能卡片快速跳转。

**New Workflow** — 提交新需求：
- Spec 文本框：输入需求描述（最多 50000 字符）
- Context 文本框：可选的额外上下文
- 提交后自动跳转到工作流详情页

**Workflow Detail** — 实时查看执行进度：
- Timeline 垂直线：4 个节点（Planner → Coder → Reviewer → Merge）
- 节点状态色：灰(等待) → 蓝(运行中) → 绿(成功) → 红(失败) → 橙(挂起)
- Coder 节点展开 → DiffViewer + SelfCheckTable
- Reviewer 节点展开 → TestCaseViewer（附带测试用例）
- 收到 `interrupt` 事件 → ApprovalPanel 自动显示

**Index Manager** — 知识图谱管理：
- 点击选择 graph.json 文件路径
- 点击 "Rebuild Index" 触发后端加载
- 统计面板显示 node_count / edge_count / files_indexed

**Settings** — 两个 Tab：
- API Keys: Anthropic API Key + LangSmith API Key（密码框，存储于 electron-store）
- Advanced: 端口 / 超时时间 / Token 预算 / 最大修订次数

### 4.4 类型检查与测试

**后端（Python / Agent harness）** — 仓库根目录，无需 API Key：

```bash
pip install -r requirements.txt
python -m pytest tests/ -q
```

详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

**桌面端（Electron）**：

```bash
cd desktop

# TypeScript 类型检查
pnpm typecheck

# 运行前端单元测试
pnpm test

# 覆盖率报告
pnpm test:coverage
```

---

## 5. 桌面端打包

### 5.1 打包流程概览

```
Stage 1: PyInstaller          Stage 2: electron-builder       Stage 3: 验证
  bridge/server.py              out/ (electron-vite build)      解压到裸机测试
       │                              │
  agentic-server.exe  ──→  extraResources/backend/
  (26 MB, 单文件)            + .env.example
                                    │
                               desktop/dist/
                               ├── setup.exe      (108 MB)
                               └── portable.exe   (108 MB)
```

### 5.2 Stage 1 — Python 后端打包

使用项目根目录的 `pyinstaller-server.spec`：

```powershell
# 在项目根目录，确保 .venv 已激活
pip install pyinstaller

# 使用预置 spec 文件打包
pyinstaller pyinstaller-server.spec
```

产出：`dist/agentic-server.exe`（26 MB，单文件）

**注意：** 这个 exe 是命令行服务程序。双击会弹出终端窗口 — 这是正常的，用户不会直接碰它。Electron 客户端通过 `PythonManager` 在后台静默拉起。

### 5.3 Stage 2 — Electron 打包

`desktop/electron-builder.yml` 已配置好：

```yaml
extraResources:
  - from: ../dist/agentic-server.exe   # PyInstaller 产出
    to: backend                         # → resources/backend/
  - from: ../.env.example
    to: .env.example
```

`python-manager.ts` 已自动区分 dev/prod：

```typescript
// 开发环境：spawn('python', ['bridge/server.py'])
// 生产环境：spawn('resources/backend/agentic-server.exe')
function getBackendCommand() {
  if (isPackaged()) {
    return { cmd: join(process.resourcesPath, 'backend', 'agentic-server.exe'), args: [], cwd: process.resourcesPath }
  }
  return { cmd: findPython(), args: [join(ROOT, 'bridge', 'server.py')], cwd: ROOT }
}
```

打包命令：

```powershell
cd desktop

# 国内环境设置镜像（仅首次需要下载 Electron 80MB 二进制）
$env:ELECTRON_MIRROR = "https://npmmirror.com/mirrors/electron/"

# 执行打包
pnpm package
# 等同于: electron-vite build && electron-builder
```

### 5.4 构建产物

详见 [第 10 节](#10-构建产物与打包经验)。

### 5.5 打包前检查清单

```
□ tsc --noEmit 零错误
□ pnpm test 42/42 pass
□ PyInstaller 生成 agentic-server.exe 成功
□ agentic-server.exe 可独立运行（终端窗口正常启动 FastAPI）
□ electron-builder.yml extraResources 指向 .exe（非 .py 源码）
□ python-manager.ts 区分 dev/prod 启动路径（isPackaged() 判断）
□ .env.example 已创建且密钥为空
□ 本地服务仅监听 127.0.0.1（settings.py HOST 默认值）
□ settings:getAll 脱敏 API Key（redactKeys() → ••••••••）
```

---

## 6. 操作流程

### 6.1 完整工作流（端到端）

```
① [可选] 建立知识索引
   打开 Index 页面 → 选择 graph.json → Rebuild Index
         ↓
② 提交 Spec
   打开 New Workflow → 输入需求 → 提交
         ↓
③ 观察执行
   页面自动跳转到时间线视图
   Planner → 拆解任务 (显示 task_count)
   Coder → 生成代码 (显示 code_len)
   Reviewer → 审查代码 (显示 PASS/REJECT)
         ↓
④ 人工审批
   SSE 收到 interrupt → ApprovalPanel 自动弹出
   查看：Coder 自检 + Reviewer 结论 + 附带测试
   决策：通过 → 点击 Approve / 拒绝 → 填写理由 → Reject
         ↓
⑤ 查看产出
   Coder 节点展开 → DiffViewer (Monaco diff 只读)
   Reviewer 节点展开 → TestCaseViewer (可复制测试代码)
```

### 6.2 失败处理流程

| 场景 | 界面表现 | 操作 |
|------|----------|------|
| Planner 失败 | Timeline 节点标红，显示错误 | 修改 Spec 后重新提交 |
| Coder 失败 | 自动重试 1 次，仍失败→橙色挂起 | 点击 Resume 手动恢复 |
| Reviewer REJECT | Coder 自动收到反馈并修正 | 等待下一轮 Coder→Reviewer |
| 连续 2 个 Coder 任务失败 | 挂起，提示 Planner 不合理 | 修改 Spec 或手动调整 |
| API 不可用 | Sidebar 状态灯变红，错误提示 | 检查 API Key 和网络 |

### 6.3 多项目管理

每个项目独立维护：
- 独立的 `.env` 配置（通过桌面端 Settings 切换）
- 独立的 `graph.json` 知识索引
- 工作流 memory 隔离（通过 LangGraph checkpoint thread_id）

---

## 7. 配置参考

### 7.1 .env 完整配置项

```bash
# ── 必填 ──
ANTHROPIC_API_KEY=sk-ant-xxxxx           # Anthropic API 密钥

# ── 模型配置 ──
ANTHROPIC_DEFAULT_MODEL=claude-sonnet-4-6  # 默认模型
ANTHROPIC_MAX_TOKENS=4096                  # 单次最大输出 token
ANTHROPIC_THINKING_BUDGET=16000            # 扩展思考预算

# ── 模型分级（Haiku/轻量 | Sonnet/标准 | Opus/复杂）──
# MODEL_ROUTING 格式为 JSON: {"simple":"...","standard":"...","complex":"..."}

# ── LangSmith 可观测性（推荐开启）──
LANGSMITH_API_KEY=ls_xxxxx
LANGSMITH_PROJECT=agentic-qa
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_TRACING=true

# ── 服务配置 ──
HOST=127.0.0.1           # 仅本机回环（安全红线，不可改为 0.0.0.0）
PORT=8000
WORKERS=1

# ── 工作流配置 ──
MAX_REVISIONS=0           # Reviewer 拒绝后最大修订轮次（0=不限，>0 超限挂起）
WORKFLOW_TIMEOUT=300      # 单个工作流超时（秒）

# ── 重试配置 ──
PLANNER_RETRY_MAX=1       # Planner 最多重试次数
CODER_RETRY_MAX=1         # Coder 自动重试次数
REVIEWER_RETRY_MAX=0      # Reviewer 不自动重试（拒绝走 coder 回路）

# ── 熔断器 ──
CIRCUIT_BREAKER_THRESHOLD=5    # 连续失败 N 次后熔断
CIRCUIT_BREAKER_RECOVERY=60.0  # 熔断后恢复等待时间（秒）

# ── 成本控制 ──
DAILY_TOKEN_BUDGET=1000000  # 每日 token 预算
TASK_TOKEN_LIMIT=100000     # 单任务 token 上限

# ── GraphIndex ──
GRAPH_INDEX_DB=data/graph_index.db  # SQLite 持久化路径

# ── 上下文预算（Planner/Coder prompt 组装）──
PLANNER_CONTEXT_MAX_FILES=30   # Planner 最多展示的文件摘要条数（0=不限不适用，按条数 cap）
CODER_CONTEXT_DEPTH=2          # Coder 按 file_scope BFS 扩展深度（最大 3）
CODER_CONTEXT_MAX_FILES=15     # file_scope 为空时的降级概览条数
CONTEXT_MAX_CHARS=24000        # 单段项目上下文字符硬上限

# ── Coder 只读工具（Phase 4）──
CODER_TOOLS_ENABLED=false      # 开启 Coder read_file/list_dir/search_repo 子循环
CODER_TOOL_MAX_ROUNDS=5        # 每轮 Coder 最多 tool 调用轮次
WORKSPACE_ROOT=                 # 工作区根（空=进程 CWD）；API 可用 workspace_path 覆盖
READ_FILE_MAX_BYTES=65536      # read_file 单文件上限
SEARCH_RG_MAX_RESULTS=50       # ripgrep 结果条数上限
SEARCH_RG_TIMEOUT_SEC=5        # ripgrep 超时（秒）
```

**Coder 只读工具（`CODER_TOOLS_ENABLED=true`）**：

- 工具：`read_file`、`list_dir`、`search_repo`（图谱 + ripgrep 混合）。
- 写盘仍仅由 **Merge** 节点执行；Coder 只输出 `CoderOutput`。
- 敏感文件（`.env`、`.env.*`、`credentials.json`、`*.pem`、`*.key`）默认不可读。
- 启动工作流时可传 `workspace_path` 指定项目根目录（见 API `POST /api/workflow`）。

### 7.1.1 SSE 观测契约（Phase 5）

工作流 SSE 事件（`node_complete`、`tool_result`、`interrupt`、`workflow_error`）统一携带：

| 字段 | 说明 |
|------|------|
| `status` | `success` / `warning` / `error` |
| `summary` | 人可读一行结论 |
| `next_actions` | 建议操作，如 `approve`、`revise`、`resume` |
| `artifacts` | `thread_id`、文件路径等 |
| `detail` | 节点深度数据（`_diff`、`_tasks` 等，供 Timeline 展开） |

HITL 中断时 `interrupt` 事件 `next_actions` 为 `["approve","revise"]`。

### 7.1.2 工作流队列

`POST /api/workflow` 将任务放入 `RequestQueue`，后台 worker 消费执行。队列满时返回 **HTTP 503**（`QUEUE_MAXSIZE`，默认 50）。

### 7.1.3 内置 Skills

`GET /api/skills` 的 `registered_skills` 列出已注册技能，当前内置：

- **rebuild_index**：加载 `graph.json` 到 GraphIndex（与 `POST /api/index/rebuild` 等价，经线程池执行）

**行为说明**：

- **Planner**：索引已加载时展示全局 stats + 前 N 个文件摘要；超出部分提示在 Task `file_scope` 中指定路径。
- **Coder**：按当前 Task 的 `file_scope` 做 BFS 子图注入（节点/边/摘要）；`file_scope` 为空时仅展示降级概览（非全仓无 cap）。
- **未加载索引**：Planner/Coder 均回退为用户提交的工作区 `context` 文本。

### 7.2 模型路由

系统按任务复杂度自动选择模型：

| 角色 | 用途 | 推荐模型 |
|------|------|----------|
| `simple` | 简单摘要、统计 | `claude-haiku-4-5-20251001` |
| `standard` | Planner/Coder 节点 | `claude-sonnet-4-6` |
| `complex` | Reviewer 审查 | `claude-opus-4-7` |

---

## 8. API 参考

### 8.1 端点总览

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/` | 服务状态 + 运行时间 |
| `GET` | `/api/health` | 健康检查（含 token 用量） |
| `GET` | `/api/skills` | Agent 能力清单 + 已注册技能 |
| `POST` | `/api/workflow` | 提交 spec，启动后台工作流 |
| `GET` | `/api/workflow/{id}` | 查询工作流当前状态 |
| `GET` | `/api/workflow/{id}/stream` | SSE 流，推送节点实时状态 |
| `POST` | `/api/workflow/{id}/approve` | 人工审批（通过/拒绝） |
| `POST` | `/api/workflow/{id}/resume` | 恢复挂起的工作流 |
| `POST` | `/api/index/rebuild` | 加载 graph.json 到内存索引 |
| `GET` | `/api/context` | 按文件 BFS 查询项目上下文 |

### 8.2 SSE 事件类型

| 事件 | 触发时机 | 数据结构 |
|------|----------|----------|
| `node_start` | 节点开始执行 | `{event, node, timestamp}` |
| `node_complete` | 节点执行完成 | `{event, node, timestamp, summary}` |
| `interrupt` | 工作流挂起等审批 | `{event, message, timestamp}` |
| `workflow_complete` | 全部任务完成 | `{event, thread_id}` |
| `workflow_error` | 工作流异常 | `{event, thread_id, error}` |
| `stream_end` | SSE 流结束 | `{event}` |
| `heartbeat` | 30s 无事件保活 | `{event: "heartbeat"}` |

### 8.3 请求/响应示例

**POST /api/workflow**
```json
// Request
{"spec": "创建用户注册 API", "context": "FastAPI + SQLAlchemy"}

// Response
{"thread_id": "a1b2c3d4", "status": "started", "stream_url": "/api/workflow/a1b2c3d4/stream"}
```

**POST /api/workflow/{id}/approve**
```json
// Request (通过)
{"approved": true, "comment": ""}

// Request (拒绝)
{"approved": false, "comment": "缺少邮箱格式验证"}
```

**GET /api/context?files=agent/orchestrator.py&depth=2**
```json
// Response
{
  "status": "ok",
  "nodes": [{"id": "...", "label": "planner_node"}],
  "edges": [{"source": "...", "target": "...", "relation": "calls"}],
  "file_summaries": {"agent/orchestrator.py": "LangGraph orchestrator: build_workflow, planner_node, coder_node"}
}
```

---

## 9. 故障排查

### 9.1 常见问题

| 问题 | 可能原因 | 解决方法 |
|------|----------|----------|
| `python: command not found` | 未激活 .venv | `venv\Scripts\Activate.ps1` |
| `ANTHROPIC_API_KEY not set` | .env 未配置 | 编辑 `.env` 填入 API Key |
| Electron 窗口空白 | Vite 未完成构建 | 等待终端显示 `ready in xxx ms` |
| Sidebar 一直黄灯 | Python 后端未启动成功 | 检查终端 `[python]` 日志 |
| SSE 连接断开 | 后端崩溃或超时 | 自动重连（指数退避），无需手动操作 |
| `HOST=0.0.0.0` 被覆盖 | python-manager 强制 127.0.0.1 | 安全红线，不可更改 |
| `pnpm: command not found` | 未安装 pnpm | `npm install -g pnpm` |
| `Error: Electron uninstall` (pnpm dev 启动报错) | Electron 二进制文件未下载到 `node_modules/electron/dist/`，缺少 `path.txt` | 手动运行 `node node_modules/electron/install.js`，国内可先设 `$env:ELECTRON_MIRROR="https://npmmirror.com/mirrors/electron/"` |
| electron-builder 下载慢 | 国内网络 | 设置 `ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/` |

### 9.2 日志查看

| 层级 | 位置 | 命令 |
|------|------|------|
| Python 后端 | 终端标准输出 | `python bridge/server.py` |
| Electron 主进程 | 终端 `[python]`/`[python:err]` 前缀 | `pnpm dev` |
| 渲染进程 | 桌面窗口 DevTools (F12) | `Ctrl+Shift+I` |
| LangSmith | `https://smith.langchain.com` | 需配置 LANGSMITH_API_KEY |

### 9.3 重置状态

```bash
# 清理 Python 缓存
find . -type d -name "__pycache__" -exec rm -rf {} +

# 清理数据库
rm -f data/graph_index.db

# 清理 Electron 构建缓存
cd desktop && rm -rf out/ dist/

# 清理并重装依赖
rm -rf node_modules/ .venv/
python -m venv .venv && pip install -r requirements.txt
cd desktop && pnpm install
```

---

## 附录：快捷键与技巧

| 操作 | 快捷键/方法 |
|------|-------------|
| 打开 DevTools | `F12` (桌面端) |
| 强制刷新 UI | `Ctrl+R` (桌面端) |
| 重启后端 | Sidebar → 后端状态 → Stop → Start |
| 复制测试代码 | TestCaseViewer → 📋 Copy 按钮 |
| Monaco Diff 导航 | `Ctrl+F` 搜索, 滚轮缩放 |
| Swagger 调试 | `http://127.0.0.1:8000/docs` |

---

## 10. 构建产物与打包经验

### 10.1 全部构建产物地图

```
D:\ZHIYI\AUTO\qa\
│
├── dist/                                    ← PyInstaller 产出
│   └── agentic-server.exe          26 MB     Python 后端（命令行服务，单文件）
│
├── desktop/
│   ├── out/                                  ← electron-vite 开发构建
│   │   ├── main/index.js            13 KB    Electron 主进程
│   │   ├── preload/index.js         1.4 KB   contextBridge 预加载
│   │   └── renderer/                         React + Vite HMR 输出
│   │
│   └── dist/                                 ← electron-builder 打包产物
│       ├── agentic-engineering-console-0.1.0-setup.exe    108 MB    NSIS 安装包
│       ├── agentic-engineering-console-0.1.0-portable.exe 108 MB    绿色免安装（自解压）
│       ├── agentic-engineering-console-0.1.0-setup.exe.blockmap  115 KB   增量更新校验
│       ├── builder-debug.yml                          6.5 KB    打包调试信息
│       ├── builder-effective-config.yaml              933 B     合并后的有效配置
│       └── win-unpacked/                                       调试用原始输出目录
│
│   └── node_modules/                        ← pnpm 依赖（不纳入打包）
│       └── .ignored/electron/dist/electron.exe  188 MB   开发用 Electron 二进制
│
└── %LOCALAPPDATA%\electron\Cache\           ← electron-builder 全局缓存
    └── electron-v33.4.11-win32-x64.zip  110 MB    Electron 发行版（仅下载一次）
```

### 10.2 两种构建的区别

| | 开发构建 (pnpm dev) | 生产打包 (pnpm package) |
|---|---|---|
| Electron 二进制来源 | `node_modules/.ignored/electron/dist/electron.exe` | `%LOCALAPPDATA%\electron\Cache\` 缓存 |
| 后端启动方式 | `spawn('python', ['bridge/server.py'])` | `spawn('backend/agentic-server.exe')` |
| 文件结构 | 源文件 + Vite HMR | 编译后的 JS bundle + asar 存档 |
| Python 依赖 | 需要本地 .venv | 打包在 agentic-server.exe 内 |
| 体积 | ~300 MB（含 node_modules） | ~108 MB（单个 exe） |

### 10.3 打包踩坑记录

**坑 1：pnpm 导致 Electron 二进制缺失 → `Error: Electron uninstall`**

- **现象**：`pnpm dev` 报错 `Error: Electron uninstall`，`node_modules/electron/` 下缺少 `dist/` 目录和 `path.txt`
- **原因 A**：Electron 的 postinstall 下载脚本未执行（网络超时 / pnpm 权限限制 / postinstall 被 electron-builder 钩子覆盖）
- **原因 B**：pnpm 安全策略把已下载的 `electron/dist/electron.exe`（188 MB）隔离到 `node_modules/.ignored/electron/dist/`
- **诊断**：先确认二进制是否被隔离到 `.ignored`：
  ```powershell
  ls desktop\node_modules\.ignored\electron\dist\electron.exe   # 如果存在 → 原因 B
  ```
- **修复 A（二进制未下载）**——手动运行 Electron 安装脚本：
  ```powershell
  cd desktop
  # 国内网络先设镜像
  $env:ELECTRON_MIRROR = "https://npmmirror.com/mirrors/electron/"
  # 下载 ~188MB 的 Electron 二进制到 node_modules/electron/dist/
  node node_modules/electron/install.js
  ```
- **修复 B（二进制被 .ignored 隔离）**——环境变量临时绕过或创建 Junction：
  ```powershell
  # 临时绕过（设置环境变量后立即生效）
  $env:ELECTRON_EXEC_PATH = "node_modules\.ignored\electron\dist\electron.exe"

  # 永久修复（复制 path.txt + 创建目录 Junction）
  Copy-Item "node_modules\.ignored\electron\path.txt" "node_modules\electron\path.txt"
  mklink /J "node_modules\electron\dist" "node_modules\.ignored\electron\dist"
  ```

**坑 2：electron-builder 从 GitHub 下载超时**

- **现象**：`dial tcp 20.205.243.166:443: connectex: ...`
- **原因**：国内直连 GitHub Releases 不稳定
- **解决**：设置淘宝镜像，仅首次下载 80MB：
  ```powershell
  $env:ELECTRON_MIRROR = "https://npmmirror.com/mirrors/electron/"
  ```
- **缓存位置**：`%LOCALAPPDATA%\electron\Cache\` — 第二次打包秒过

**坑 3：虚拟环境路径迁移后 pip 崩溃**

- **现象**：`Fatal error in launcher: Unable to create process`
- **原因**：项目从 `D:\githubdownloads\qa\` 移动到 `D:\ZHIYI\AUTO\qa\`，.venv 内的 pip 硬编码了旧路径
- **解决**：删除 `.venv` 重建：
  ```powershell
  Remove-Item -Recurse -Force .venv
  python -m venv .venv
  .venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  ```

**坑 4：PyInstaller spec 中 `from` 必须精确匹配文件**

- **现象**：electron-builder 打包后 `resources/backend/` 为空
- **原因**：`extraResources.from` 写的是 `../dist/agentic-server`（目录），但 PyInstaller 产出的是 `agentic-server.exe`（单文件）
- **修复**：加 `.exe` 后缀：
  ```yaml
  extraResources:
    - from: ../dist/agentic-server.exe   # 精确匹配文件名
      to: backend
  ```

**坑 5：打包后只显示背景色，没有 UI 界面**

- **现象**：双击 `portable.exe`，窗口打开但只有暗色背景，没有任何 UI 元素。DevTools Console 无任何报错。
- **原因**：`BrowserRouter` 使用 HTML5 History API，依赖服务端路由。Electron 打包后用 `file://` 协议加载 HTML（URL 形如 `file:///C:/.../app.asar/out/renderer/index.html`），`window.location.pathname` 是磁盘路径，匹配不到 `/` 路由，React Router 渲染空白。
- **修复**：换成 `HashRouter`，路由走 hash 片段（`#/`），与加载协议无关：
  ```tsx
  // src/renderer/App.tsx
  import { HashRouter, Routes, Route } from 'react-router-dom'  // 改这里
  
  export function App() {
    return (
      <HashRouter>   {/* 改这里 */}
        <Routes>
          ...
        </Routes>
      </HashRouter>
    )
  }
  ```
- **教训**：Electron 桌面应用的 React Router 一律用 `HashRouter`，开发和打包都兼容。

**坑 6：CSP 拦截 Google Fonts 导致字体不加载**

- **现象**：DevTools Console 显示 `Refused to load the stylesheet 'https://fonts.googleapis.com/...' because it violates CSP "style-src 'self' 'unsafe-inline'"`
- **原因**：CSP 的 `style-src` 只允许 `'self'` 和 `'unsafe-inline'`，Google Fonts 的外部 CSS 被拦截
- **修复**：在 CSP 中加 `https://fonts.googleapis.com`：
  ```html
  <meta http-equiv="Content-Security-Policy"
    content="... style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
             style-src-elem 'self' 'unsafe-inline' https://fonts.googleapis.com;
             font-src 'self' https://fonts.gstatic.com; ..."
  />
  ```
- **教训**：CSP 需要显式列出所有外部资源域名；`style-src` 和 `style-src-elem` 两者都要配（Chromium 优先读后者）。

### 10.4 增量 vs 全量构建

```
pnpm dev ──→ 修改源码 ──→ 页面自动热更新（HMR，毫秒级）
                │
                ├── .ts/.tsx 变化 → esbuild 只重编译该文件
                ├── .css 变化   → Tailwind JIT 只生成用到的 class
                └── 新文件      → Vite 增量添加到 bundle

pnpm package ──→ electron-vite build ──→ electron-builder ──→ .exe
                      增量的               每次全量重打包
                  (Vite 只编译变化的)     (但 Electron 二进制读缓存)
```

| 操作 | 增量/全量 | 首次耗时 | 后续耗时 |
|------|-----------|----------|----------|
| `pnpm dev` | 增量 | 5-10s | 即时 (HMR) |
| `pnpm test` | 增量 | 1.5s | 即时 (Vite 缓存) |
| `electron-vite build` | 按需增量 | 8s | 2-3s |
| `electron-builder` | 全量 | 3-5min | 30-60s |
| `pyinstaller` | 全量 | 2-3min | 2-3min（可单独跳过） |

**提示**：日常开发不需要频繁打包。`pnpm dev` 热更新即可。仅有以下情况需要完整打包：
- 发给其他人测试
- 发布新版本
- 验证后端 PyInstaller 打包是否完整（新依赖加入后）
