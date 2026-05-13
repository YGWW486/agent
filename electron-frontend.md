# Electron Desktop Frontend — Implementation Plan

> **目标**: 为 Agentic Engineering Console (FastAPI 后端) 构建 Electron + React 桌面前端
> **后端 API**: v3.0.0, 9 个 REST 端点 + SSE 流
> **生成方式**: 双代理并行分析 (code-explorer API 契约 + architect 前端设计)

---

## 技术栈

| 层 | 选型 | 理由 |
|----|------|------|
| 桌面壳 | Electron 33 | 需求指定; 跨进程管理 Python 后端 |
| 构建 | Vite + electron-vite | 快速 HMR, 类型化 preload |
| UI 框架 | React 18 + TypeScript | 生态最大, 组件库/Diff 工具丰富 |
| 状态管理 | Zustand | 轻量, 分 domain slice, TS 友好 |
| 样式 | Tailwind CSS + Radix UI (shadcn/ui) | 无头可访问组件, 符合 ECC web 规则 |
| Diff 查看 | Monaco Editor (diff mode) | 语法高亮 + inline diff 金标准 |
| SSE | 自定义 fetch ReadableStream | EventSource 不支持 POST/Custom Headers |
| DAG 可视化 | @xyflow/react | 流程图/节点图, 可交互 |
| IPC | contextBridge + typed preload | 沙箱安全, 仅暴露白名单 API |
| 设置持久化 | electron-store | JSON 文件, 主进程读写可加密 |

---

## 文件结构

```
desktop/
├── electron.vite.config.ts
├── package.json
├── tsconfig.json
├── tailwind.config.ts
├── src/
│   ├── main/                          # Electron 主进程
│   │   ├── index.ts                   # BrowserWindow 创建, 生命周期
│   │   ├── python-manager.ts          # spawn/monitor/kill Python 后端
│   │   ├── ipc-handlers.ts            # ipcMain: 后端控制/文件对话框/设置读写
│   │   └── settings-store.ts          # electron-store 封装 (keys, models, ports)
│   ├── preload/
│   │   └── index.ts                   # contextBridge → window.electronAPI
│   └── renderer/
│       ├── App.tsx                    # 路由 + 布局
│       ├── main.tsx                   # React 入口
│       ├── components/
│       │   ├── layout/
│       │   │   ├── AppShell.tsx       # 主布局容器
│       │   │   ├── Sidebar.tsx        # 项目切换 + 后端状态
│       │   │   └── TopBar.tsx         # 面包屑 + 快捷操作
│       │   ├── workflow/
│       │   │   ├── SubmitForm.tsx     # 提交 spec 表单
│       │   │   ├── Timeline.tsx       # 节点时间线 (Planner/Coder/Reviewer/Merge)
│       │   │   ├── NodeCard.tsx       # 单节点状态卡片 (展开可看详情)
│       │   │   ├── TaskDAGView.tsx    # Task DAG 可视化 (@xyflow/react)
│       │   │   ├── ApprovalPanel.tsx  # 人工审批面板 (通过/拒绝 + 备注)
│       │   │   └── SelfCheckTable.tsx # Coder 自检结果表格
│       │   ├── code/
│       │   │   ├── DiffViewer.tsx     # Monaco diff editor (只读)
│       │   │   ├── CodePreview.tsx    # 代码片段预览
│       │   │   └── TestCaseViewer.tsx # Reviewer 附带测试展示
│       │   ├── index/
│       │   │   ├── IndexManager.tsx   # graph.json 加载/重建
│       │   │   └── IndexStats.tsx     # 节点/边/文件统计
│       │   ├── settings/
│       │   │   ├── SettingsPage.tsx   # 设置主页
│       │   │   ├── APISettings.tsx    # API Keys + 模型路由
│       │   │   ├── ProjectSettings.tsx # 多项目管理
│       │   │   └── AdvancedSettings.tsx # Token 预算/超时等
│       │   └── ui/                    # shadcn/ui 组件 (Button/Badge/Spinner/...)
│       ├── stores/                    # Zustand stores
│       │   ├── workflow.store.ts      # Map<threadId, WorkflowState>
│       │   ├── settings.store.ts      # API keys, models, port, projects
│       │   ├── backend.store.ts       # stopped/starting/running/error
│       │   └── index.store.ts         # graph stats
│       ├── hooks/
│       │   ├── useSSE.ts              # fetch-stream SSE (指数退避重连)
│       │   ├── useBackend.ts          # 后端生命周期 IPC 封装
│       │   └── useWorkflow.ts         # workflow CRUD + SSE 绑定
│       ├── lib/
│       │   ├── api.ts                 # fetch 封装 (9 个端点)
│       │   ├── ipc.ts                 # 类型化 window.electronAPI
│       │   └── types.ts              # 前后端共享类型定义
│       └── styles/
│           ├── tokens.css             # 设计 Token
│           └── globals.css            # Tailwind + 全局样式
```

---

## 实现步骤 (12 Phase)

### Phase 1: 项目脚手架 (预计 2h)

**交付物**: 空白 Electron 窗口, React 渲染, Vite 热更新

- 用 `npm create @quick-start/electron` 初始化
- 安装依赖: React, TypeScript, Tailwind, Zustand, shadcn/ui
- 验证 `pnpm dev` 可启动空白窗口
- 创建 `src/lib/types.ts`: 从后端 `agent/models.py` 移植所有接口定义

### Phase 2: Python 后端生命周期 (预计 3h)

**文件**: `src/main/python-manager.ts`, `src/main/ipc-handlers.ts`, `src/preload/index.ts`

- `python-manager.ts`:
  - `start()`: `child_process.spawn('python', ['bridge/server.py'])`, 检测 `.venv`
  - 每 5s 轮询 `GET /api/health` 直到 200
  - `stop()`: SIGTERM → 等 5s → SIGKILL
  - `on('exit')`: 自动重启 (最多 3 次)
  - 通过 IPC 暴露 `pid`, `uptime`, `status`
- `ipc-handlers.ts`: 注册 `backend:start`, `backend:stop`, `backend:status`, `dialog:selectDirectory`, `settings:get`, `settings:set`
- `preload/index.ts`: `contextBridge.exposeInMainWorld('electronAPI', {...})`
- `backend.store.ts`: Zustand store 绑定 IPC 事件

### Phase 3: 布局框架 (预计 2h)

**文件**: `AppShell.tsx`, `Sidebar.tsx`, `TopBar.tsx`

- AppShell: 左侧 Sidebar + 右侧内容区
- Sidebar: 后端状态指示灯 (绿/黄/红) + 项目选择器 + 导航
- TopBar: 面包屑 + "新建工作流"按钮
- 路由: `react-router` — `/workflow/new`, `/workflow/:threadId`, `/index`, `/settings`

### Phase 4: 工作流提交 (预计 2h)

**文件**: `SubmitForm.tsx`, `src/lib/api.ts`

- `api.ts`: fetch 封装基类 `http://127.0.0.1:${port}/api`
  - `startWorkflow(spec, context)` → `POST /api/workflow`
  - `getWorkflowStatus(threadId)` → `GET /api/workflow/{id}`
  - `approveWorkflow(threadId, approved, comment)` → `POST /api/workflow/{id}/approve`
  - `resumeWorkflow(threadId, targetNode)` → `POST /api/workflow/{id}/resume`
  - `getSkills()` → `GET /api/skills`
  - `healthCheck()` → `GET /api/health`
  - `rebuildIndex(path)` → `POST /api/index/rebuild`
  - `getContext(files, depth)` → `GET /api/context`
- SubmitForm: 多行文本框 + 可选 context + "提交"按钮
- 提交后跳转 `/workflow/:threadId`

### Phase 5: SSE 实时流 (预计 3h)

**文件**: `src/hooks/useSSE.ts`, `src/hooks/useWorkflow.ts`

- `useSSE(threadId)`: 
  - 打开 `GET /api/workflow/{threadId}/stream` with `fetch()`
  - `response.body.getReader()` 逐块读取
  - 解析 SSE 帧: `event: type\ndata: json`
  - 事件: `node_start`, `node_complete`, `interrupt`, `workflow_complete`, `workflow_error`, `stream_end`, `heartbeat`
  - 断连自动重连 (指数退避: 1s, 2s, 4s, max 30s, 加 jitter)
  - 重连后先 `GET status` 补全状态, 再开新 stream
- `useWorkflow(threadId)`: 组合 `useSSE` + workflow store

### Phase 6: 时间线组件 (预计 4h)

**文件**: `Timeline.tsx`, `NodeCard.tsx`, `TaskDAGView.tsx`

- `Timeline`: 垂直时间线, 4 个固定节点槽位 (Planner → Coder → Reviewer → Merge)
  - Planner: 显示 `task_count`, 展开看 TaskDAG
  - Coder: 显示 `task_index` / `code_len`, 展开看 diff + 自检
  - Reviewer: 显示 `verdict` (PASS/REJECT), `test_count`
  - Merge: 最终合并状态
- 节点状态色: `pending`(灰)→`running`(蓝/动画)→`success`(绿)→`failed`(红)→`suspended`(橙)
- `TaskDAGView`: 用 @xyflow/react 渲染 Task DAG, 标注已完成节点
- `SelfCheckTable`: 表格展示 Coder 自检 (condition_id → status → evidence)

### Phase 7: 审批面板 (预计 2h)

**文件**: `ApprovalPanel.tsx`

- SSE 收到 `interrupt` 事件时渲染
- 显示 coder 自检摘要 + reviewer 结论 + 附带测试用例
- 两个按钮: "通过 (Merge)" / "拒绝 (打回 Coder)"
- 拒绝时必须填写备注 (textarea)
- 调用 `POST /api/workflow/{threadId}/approve`
- 挂起恢复: `POST /api/workflow/{threadId}/resume`

### Phase 8: 代码与 Diff 查看 (预计 3h)

**文件**: `DiffViewer.tsx`, `CodePreview.tsx`, `TestCaseViewer.tsx`

- `DiffViewer`: Monaco Editor `createDiffEditor`, 左旧右新, 只读模式
  - 数据源: `CoderOutput.diff` 字段 (JSON 解析后的字符串)
- `CodePreview`: Monaco 只读模式, 语法高亮
- `TestCaseViewer`: 展示 Reviewer 的 `test_cases` 列表, 可复制代码

### Phase 9: 知识索引管理 (预计 2h)

**文件**: `IndexManager.tsx`, `IndexStats.tsx`, `index.store.ts`

- `IndexManager`: 文件选择器 (IPC dialog) + "重建索引"按钮
  - 调用 `POST /api/index/rebuild`
- `IndexStats`: 展示 node_count / edge_count / files_indexed / loaded_at
- `index.store.ts`: 与 API 同步

### Phase 10: 设置页 (预计 3h)

**文件**: `SettingsPage.tsx`, `APISettings.tsx`, `ProjectSettings.tsx`, `AdvancedSettings.tsx`, `settings.store.ts`

- API 密钥: password field (Anthropic, LangSmith)
- 模型路由: dropdown (Haiku/Sonnet/Opus) × 3 角色
- 超时/重试/Token 预算: number inputs
- 项目管理: 添加/删除项目目录
- 通过 IPC `settings:set` 写入 `settings.json`
- 后端端口: number input (需重启生效)

### Phase 11: 打包与绿色 Zip (预计 3h)

- `electron-builder` 配置: Windows NSIS 或 portable zip
- Python 后端: 用 PyInstaller 打包为独立 exe, 放入 Electron 资源目录
- 验证: 解压到新 Windows 机器, 双击运行, 无需安装 Python
- 启动时自动检测 .env 文件, 缺失则弹出首次设置向导

### Phase 12: 测试 (预计 3h)

- `useSSE.test.ts`: mock fetch, 模拟 SSE 事件帧
- `workflow.store.test.ts`: 状态转换逻辑
- `Timeline.test.tsx`: 各节点状态渲染
- `ApprovalPanel.test.tsx`: approve/reject 流程
- E2E (Playwright): mock 后端, 完整 spec→approval 流程

---

## 数据流总览

```
[Settings]──IPC──→ main/settings-store.ts (electron-store JSON)
[SubmitForm]──POST /api/workflow──→ {thread_id}
    │
    └─→ useSSE(threadId)─→ GET /api/workflow/{id}/stream
            ├─ node_start/nod_complete ──→ workflow.store ──→ Timeline
            ├─ interrupt ──→ ApprovalPanel 显示
            │     └─→ POST /api/workflow/{id}/approve ──→ 继续/打回
            ├─ workflow_complete ──→ DiffViewer 显示产出
            └─ workflow_error ──→ 错误提示

[IndexManager]──POST /api/index/rebuild──→ index.store
[PythonManager]──child_process──→ backend.store (status/pid/uptime)
```

---

## 边缘情况处理

| 场景 | 策略 |
|------|------|
| 后端崩溃 | python-manager 检测 exit → backend.store="error" → 自动重启(最多3次) → SSE 重连 |
| SSE 断连 | 指数退避重连(1s,2s,4s,...max30s) + jitter; 重连后先 poll status 补全 |
| 工作流挂起 | NodeCard 显示 "Suspended" 标签 + failure_reason + Resume 按钮 |
| 长时间运行 | SSE heartbeat 保持连接; powerSaveBlocker 防休眠; Timeline 显示耗时 |
| 多工作流并发 | workflow.store 为 Map<threadId,WorkflowState>; Sidebar 列出活跃线程 |
| .env 缺失 | 首次启动弹出 SetupWizard, 引导填写 API key |
| Python 未安装 | 启动时检测 Python 路径, 提示安装或指向 .venv |
| HOST=0.0.0.0 | 启动时自动改写为 127.0.0.1 (安全红线) |

---

## 关键依赖

```json
{
  "dependencies": {
    "react": "^18.3",
    "react-dom": "^18.3",
    "react-router-dom": "^6",
    "zustand": "^5",
    "@monaco-editor/react": "^4",
    "@xyflow/react": "^12",
    "@radix-ui/react-dialog": "^1",
    "@radix-ui/react-select": "^2",
    "@radix-ui/react-tabs": "^1",
    "tailwindcss": "^4",
    "lucide-react": "^0",
    "electron-store": "^10",
    "clsx": "^2"
  },
  "devDependencies": {
    "electron": "^33",
    "electron-vite": "^2",
    "electron-builder": "^25",
    "typescript": "^5",
    "vitest": "^2",
    "@testing-library/react": "^16",
    "playwright": "^1"
  }
}
```

---

## 变更文件清单

| 操作 | 文件 | Phase |
|------|------|-------|
| 创建 | `desktop/` 整个目录 | 1 |
| 创建 | `desktop/src/main/python-manager.ts` | 2 |
| 创建 | `desktop/src/main/ipc-handlers.ts` | 2 |
| 创建 | `desktop/src/preload/index.ts` | 2 |
| 创建 | `desktop/src/renderer/App.tsx` | 3 |
| 创建 | `desktop/src/renderer/components/layout/*` | 3 |
| 创建 | `desktop/src/renderer/components/workflow/*` | 4,6,7 |
| 创建 | `desktop/src/renderer/components/code/*` | 8 |
| 创建 | `desktop/src/renderer/components/index/*` | 9 |
| 创建 | `desktop/src/renderer/components/settings/*` | 10 |
| 创建 | `desktop/src/renderer/stores/*` | 2-10 |
| 创建 | `desktop/src/renderer/hooks/useSSE.ts` | 5 |
| 创建 | `desktop/src/renderer/lib/api.ts` | 4 |
| 创建 | `desktop/src/renderer/lib/types.ts` | 1 |
| 创建 | `desktop/src/renderer/lib/ipc.ts` | 2 |
| 修改 | `config/settings.py` HOST 默认值 | 安全 |
| 创建 | `desktop/tests/*` | 12 |
| 创建 | `desktop/electron-builder.yml` | 11 |

---

> **注意**: 多模型后端 (Codex/Gemini) 未安装，本次计划由 code-explorer + architect 双代理并行分析合成。
> 计划保存时间: 2026-05-11
