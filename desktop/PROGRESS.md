# Electron Desktop — Engineering Progress Log

> 滚动更新，记录每个 Phase 的实际交付物、技术决策和偏差。
> 最后更新: 2026-05-12

---

## Phase 1: 项目脚手架 ✅ 2026-05-12

### 工作摘要

从零创建 `desktop/` 项目，基于 electron-vite + React 18 + TypeScript + Tailwind 3。
构建三进程全绿，类型检查零错误。

### 创建的文件 (22 个)

```
desktop/
├── package.json                          # 全部 34 个依赖声明
├── electron.vite.config.ts               # main/preload/renderer 三进程构建
├── tsconfig.json                         # 引用 tsconfig.node.json + tsconfig.web.json
├── tsconfig.node.json                    # main/preload 编译选项 (ES2022, bundler)
├── tsconfig.web.json                     # renderer 编译选项 (ES2022 + DOM + react-jsx)
├── tailwind.config.ts                    # 暗色主题 + 自定义颜色 token
├── postcss.config.mjs                    # Tailwind + Autoprefixer
├── electron-builder.yml                  # Windows NSIS / Linux AppImage / macOS DMG
├── .gitignore                            # node_modules/ out/ dist/
├── index.html → src/renderer/index.html  # CSP 已配置, Google Fonts 预连接
├── src/
│   ├── main/
│   │   └── index.ts                      # BrowserWindow (sandbox+contextIsolation)
│   ├── preload/
│   │   └── index.ts                      # contextBridge 白名单: backend/dialog/settings/on
│   ├── shared/
│   │   └── types.ts                      # 18 个 TS 类型, 1:1 映射 agent/models.py
│   └── renderer/
│       ├── index.html
│       ├── main.tsx                      # React 18 createRoot 入口
│       ├── App.tsx                       # BrowserRouter + Routes (/ + /settings)
│       ├── env.d.ts                      # window.electronAPI 全局类型声明
│       ├── components/
│       │   └── layout/
│       │       ├── AppShell.tsx          # flex 双栏布局 (Sidebar + main)
│       │       ├── Sidebar.tsx           # 导航 + 后端状态指示灯占位
│       │       └── TopBar.tsx            # 面包屑占位 + New Workflow 按钮
│       ├── lib/
│       │   ├── cn.ts                     # clsx + tailwind-merge 工具函数
│       │   └── ipc.ts                    # 类型安全 window.electronAPI 访问
│       └── styles/
│           └── globals.css               # Tailwind + CSS 自定义属性 + 滚动条样式
```

### 技术决策

1. **postcss.config.mjs 而非 .js** — 避免 `type: module` 警告和 preload 输出变为 .mjs
2. **index.html 放在 src/renderer/** — electron-vite 默认约定，构建输出路径正确
3. **暗色主题默认** — 工具型桌面软件更适合暗色，减少视觉疲劳
4. **Tailwind 3 而非 4** — shadcn/ui 和 @radix-ui 生态当前兼容 Tailwind 3
5. **`type: module` 未设置** — electron-vite 内部处理 ESM/CJS，显式设置会改变 preload 输出后缀
6. **ELECTRON_MIRROR=npmmirror.com** — 国内网络环境 Electron 二进制下载必需

### 类型映射 (Python Pydantic → TypeScript)

| Python (`agent/models.py`) | TypeScript (`src/shared/types.ts`) |
|---------------------------|-----------------------------------|
| `WorkflowRequest` | `{ spec: string; context: string }` (inline) |
| `ApproveRequest` | `{ approved: boolean; comment: string }` (inline) |
| `Task`, `TaskDAG` | `PlanSummary { task_count; current_task }` (精简) |
| `SelfCheckItem`, `SelfCheckReport` | (Phase 6 用到时细化) |
| `CoderOutput` | (Phase 8 DiffViewer 时细化) |
| `ReviewResult`, `TestCase` | `ReviewSummary { verdict; reason }` (精简) |
| `Settings` (Pydantic) | `Settings` (TS interface, 14 字段) |
| SSE 事件 | `SSEEvent`, `SSEEventType`, `TimelineNode`, `NodeStatus` |
| Backend 状态 | `BackendStatus`, `BackendState`, `HealthResponse` |

### 构建验证

```
electron-vite build  →  main (4.21 kB) + preload (1.05 kB) + renderer (274 kB JS + 14 kB CSS)
tsc --noEmit         →  零错误
```

### 待后续 Phase 处理

- `vitest.config.ts` — Phase 2 需要时创建
- Monaco Editor worker 配置 — Phase 8
- @xyflow/react 样式 — Phase 6
- electron-store 主进程封装 — Phase 10
- Python 后端 spawn 逻辑 — Phase 2

---

---

## Phase 2: Python Backend Lifecycle ✅ 2026-05-12

### 工作摘要

实现 Electron 主进程中 Python FastAPI 后端的完整生命周期管理：spawn/health-poll/auto-restart/SIGTERM 清理。通过 IPC + contextBridge 将后端状态暴露给渲染进程，使用 Zustand store 管理 UI 状态。

### 创建的文件 (5 个)

- `src/main/python-manager.ts` (171 行) — PythonManager 类：spawn/monitor/kill，自动重启（最多 3 次），健康检查轮询（5s 间隔，最多 60s），跨平台 .venv 检测
- `src/main/python-manager.test.ts` (152 行) — 11 个单元测试：启动/停止/重启/错误耗尽/幂等/事件发射
- `src/main/ipc-handlers.ts` (93 行) — ipcMain handlers：backend / dialog / settings，带输入验证和 API key 脱敏
- `src/main/settings-store.ts` (27 行) — electron-store 封装，类型化 Settings 默认值
- `src/renderer/stores/backend.store.ts` (20 行) — Zustand store：backend 状态 + setState
- `src/renderer/hooks/useBackend.ts` (28 行) — React hook：IPC start/stop/refresh + SSE 状态同步

### 修改的文件 (1 个)

- `src/main/index.ts` — 注册 registerIpcHandlers() + before-quit 进程清理

### 技术决策

1. **PythonManager 使用 EventEmitter 而非直接暴露 listener** — 与 Node.js child_process 模式一致，便于多个消费者监听状态变化
2. **健康检查超时保护（12 次 = 60s）** — 避免端口冲突导致无限轮询，超时后自动 SIGTERM + 报错
3. **env 变量白名单而非透传整个 process.env** — 安全红线，仅传递 Python 后端实际需要的变量
4. **stop() 先尝试 HTTP shutdown 再 SIGTERM** — 优雅关闭优先，回退到进程终止
5. **settings:getAll 脱敏 API keys** — 向渲染进程返回 `••••••••`，防止 XSS/供应链攻击泄露密钥
6. **settings:set 运行时白名单校验** — TypeScript 类型擦除后仍有保护，拒绝未知 key
7. **跨平台 findPython()** — Windows 检测 `.venv/Scripts/python.exe`，macOS/Linux 检测 `.venv/bin/python3`
8. **node: 协议前缀** — 依赖注入攻击防御，require('child_process') 不会被恶意 npm 包劫持

### 审查结果

- **code-reviewer**: 3 CRITICAL + 4 HIGH → 全部已修复
- **security-reviewer**: 0 CRITICAL + 3 HIGH → 全部已修复
- 关键修复：orphan 进程清理 / API key 脱敏 / 输入验证 / 健康检查超时

### 测试结果

```
11 passed, 0 failed
```
- start(): 5 tests (spawn args, status transitions, health pass/fail, max restart, idempotency)
- stop(): 3 tests (SIGTERM, exit code 0, no-op)
- state(): 2 tests (defaults, status-change event)

---

---

## Phase 3: Layout Framework ✅ 2026-05-12

### 工作摘要

将 Phase 1 的布局占位壳连上真实后端状态（useBackend/useBackendStore/Zustand），补全 6 条路由 + 页面占位组件，通过 WCAG 2.2 AA a11y 审计并修复全部 7 个违规项。

### 创建的文件 (6 个)

- `src/renderer/components/index/HomePage.tsx` (37 行) — Dashboard 仪表盘，4 张功能卡片跳转
- `src/renderer/components/workflow/WorkflowsPage.tsx` (8 行) — Phase 4 占位
- `src/renderer/components/workflow/NewWorkflowPage.tsx` (8 行) — Phase 4 占位
- `src/renderer/components/workflow/WorkflowDetailPage.tsx` (14 行) — Phase 5-6 占位
- `src/renderer/components/index/IndexPage.tsx` (8 行) — Phase 9 占位
- `src/renderer/components/settings/SettingsPage.tsx` (8 行) — Phase 10 占位
- `src/renderer/hooks/useDocumentTitle.ts` (13 行) — 路由切换更新 document.title

### 修改的文件 (8 个)

- `src/renderer/App.tsx` — 6 条路由 (/ /workflows /workflow/new /workflow/:threadId /index /settings)
- `src/renderer/components/layout/Sidebar.tsx` — useBackend() 实时状态灯 + 4 导航项 + ARIA labels
- `src/renderer/components/layout/TopBar.tsx` — 动态面包屑 + `aria-current="page"`
- `src/renderer/components/layout/AppShell.tsx` — skip-to-content 链接 + `id="main-content"`
- `src/renderer/hooks/useBackend.ts` — electronAPI guard + selectors（防崩溃 + 减渲染）
- `src/renderer/styles/globals.css` — focus-visible ring + skip-link + overflow-x 修正
- `src/renderer/index.html` — lang="zh-CN" → lang="en"
- `tailwind.config.ts` — status color 对比度提升（pending 50→65, 新增 stopped 62）

### 技术决策

1. **Zustand selector** — useBackend 只用 `useBackendStore((s) => s.status)`，避免 pid/uptime 变化触发 Sidebar 重渲染
2. **electronAPI guard** — `if (!window.electronAPI) return` 防止浏览器/测试环境崩溃
3. **focus-visible 全局样式** — 而非每个组件单独加 ring，减少重复
4. **useDocumentTitle 而非 react-helmet** — 零依赖，cleanup 恢复旧标题

### a11y 审查结果

- **a11y-architect**: 1 CRITICAL + 3 HIGH + 3 MEDIUM → 全部已修复
- 修复项：focus-visible ring / skip-link / 页面标题 / aria-current / lang 修正 / 颜色对比度 / overflow-x

---

---

## Phase 4: Workflow Submit + API ✅ 2026-05-12

### 工作摘要

实现完整 API 层（8 个后端端点 + AbortController 30s 超时 + 错误净化），SubmitForm 组件（spec + context → POST → 跳转 detail 页），Zustand workflow store（Map 不可变更新模式）。

### 创建的文件 (4 个)

- `src/renderer/lib/api.ts` (96 行) — createApi() 工厂：8 endpoint + request() 统一错误/超时/AbortController
- `src/renderer/lib/api.test.ts` (157 行) — 11 个单元测试覆盖全部 9 个方法
- `src/renderer/stores/workflow.store.ts` (36 行) — Map<threadId, WorkflowUIState> + immutable set pattern
- `src/renderer/hooks/useApi.ts` (9 行) — useMemo createApi 从 backend port

### 修改的文件 (3 个)

- `src/renderer/components/workflow/SubmitForm.tsx` (71 行) — spec + context textarea + submit + loading/error/validation
- `src/renderer/components/workflow/NewWorkflowPage.tsx` — 使用 SubmitForm
- `src/renderer/components/workflow/WorkflowDetailPage.tsx` — 从 workflow store 读取并显示 spec

### 技术决策

1. **createApi(baseUrl) 工厂函数而非单例** — 可通过 port 动态重建（useApi hook 用 useMemo + port 依赖）
2. **request() 错误三分类** — AbortError → "timed out", network error → "unreachable", HTTP error → "failed (status)"
3. **错误详情 console.error 记录，UI 显示净化消息** — 防止内部路径/堆栈泄露到界面
4. **输入 maxLength=50000** — 客户端长度限制防 DoS
5. **AbortController 30s 超时** — 防 UI 永久挂起

### 审查结果

- **code-reviewer**: 1 HIGH (网络错误包装) + 2 MEDIUM → 全修
- **security-reviewer**: 1 HIGH (错误泄露) + 1 MEDIUM (输入长度) → 全修

### 测试结果

```
22 passed, 0 failed (api: 11 + python-manager: 11)
```

---

---

## Phase 5: SSE Real-time Stream ✅ 2026-05-12

### 工作摘要

实现核心 SSE 实时流：ReadableStream 读取 + TextDecoder 缓冲拆分帧 + SSE 协议解析 + 指数退避重连。useWorkflow 将 SSE 事件转换为 TimelineNode 状态机（pending→running→success/failed/suspended）。

### 创建的文件 (3 个)

- `src/renderer/hooks/useSSE.ts` (149 行) — parseSSEStream() + calcBackoff() + useSSE() hook
- `src/renderer/hooks/useSSE.test.ts` (128 行) — 10 tests: SSE 帧解析 + backoff
- `src/renderer/hooks/useWorkflow.ts` (110 行) — SSE 事件 → workflow.store TimelineNode 状态机

### 修改的文件 (1 个)

- `src/renderer/components/workflow/WorkflowDetailPage.tsx` — 集成 useWorkflow + timeline 可视化

### 技术决策

1. **SSE 解析从 hook 中解耦** — `parseSSEStream()` 纯函数，独立可测（无需 @testing-library/react），hook 仅做 React 生命周期包装
2. **ReadableStream + TextDecoder** — 而非 EventSource，因为 EventSource 不支持 POST/Custom Headers
3. **SSE 帧缓冲区拆分** — `\n\n` 分隔完整帧，尾帧残留在 buffer 等下一个 chunk
4. **重连前先 poll status** — `attemptRef > 0` 时调 `getWorkflowStatus()` 补全断连期间遗漏的状态
5. **multi-line data: 支持** — SSE spec 要求多行 `data:` 拼接 `\n`，当前实现符合标准
6. **1 MB 缓冲区上限** — 防止畸形流导致无界内存增长（DoS 防御）
7. **AbortSignal 穿透到 parseSSEStream** — 组件卸载时不仅 abort fetch，也停止 reader 循环
8. **node_complete 三态推导** — success（正常）/ failed（suspended + failure_reason）/ suspended（需审批）

### 审查结果

- **code-reviewer**: 2 HIGH + 3 MEDIUM + 1 LOW → 全修
- HIGH-1: jitter 超 cap → `Math.min(round(base+jitter), MAX_BACKOFF_MS)`
- HIGH-2: failed status 不可达 → failure_reason 推导 failed
- MED-1: 无飞行中 abort → AbortSignal 穿透
- MED-2: 无缓冲区上限 → 1MB cap
- MED-3: 多行 data: 覆盖 → 拼接支持

### 测试结果

```
32 passed, 0 failed (api: 11 + python-manager: 11 + useSSE: 10)
```

---

---

## Phase 6: Timeline Components ✅ 2026-05-12

### 工作摘要

将 WorkflowDetailPage 中的简易时间线替换为 4 个专业组件：Timeline（垂直线布局 + 连接线）、NodeCard（状态色 + 展开/收起 + 耗时）、TaskDAGView（@xyflow/react 任务 DAG 可视化）、SelfCheckTable（Coder 自检结果表）。

### 创建的文件 (4 个)

- `src/renderer/components/workflow/Timeline.tsx` (35 行) — 垂直线 + 连接节点 + renderDetail prop
- `src/renderer/components/workflow/NodeCard.tsx` (90 行) — 状态圆点 + 标签 + 耗时 + 展开/收起
- `src/renderer/components/workflow/TaskDAGView.tsx` (76 行) — @xyflow/react ReactFlow + 任务节点/边 + 完成态着色
- `src/renderer/components/workflow/SelfCheckTable.tsx` (48 行) — condition → status → evidence 三列表格

### 修改的文件 (1 个)

- `src/renderer/components/workflow/WorkflowDetailPage.tsx` — 使用 Timeline + renderDetail 替代内联时间线

### 技术决策

1. **renderDetail 函数注入** — Timeline 通过 `renderDetail(node)` prop 让父组件定义每个节点的展开内容，Timeline 本身只负责布局
2. **if/else 代替 switch-case** — esbuild 对 switch-case 内 `{ }` 块语法兼容性差，改用 if/else 链
3. **@xyflow/react 集成** — 节点颜色根据完成状态变化：绿（已完成）→ 绿环高亮（进行中）→ 灰（未开始）
4. **NodeCard expand/collapse** — chevron 动画 180° 旋转，hasChildren 为 false 时不显示箭头
5. **SelfCheckTable 空状态** — 无数据时显示 "No self-check data available."

### 构建结果

```
TSC: zero errors | Build: clean (no warnings)
CSS: 39.5 KB (+22 KB from xyflow styles)
JS:  736.6 KB (+364 KB from xyflow bundle)
Tests: 32 passed (unchanged — no new logic tests)
```

---

---

## Phase 7: Approval Panel ✅ 2026-05-12

### 工作摘要

实现人工审批面板：当 SSE 收到 `interrupt` 事件时，替换简单 alert 为完整审批 UI。显示 coder/reviewer 摘要，Approve 按钮直接提交，Reject 按钮要求填写拒绝理由（必填 textarea）。调用 `POST /api/workflow/{id}/approve`，提交后更新 workflow store 清除 interrupt 标志。

### 创建的文件 (1 个)

- `src/renderer/components/workflow/ApprovalPanel.tsx` (113 行) — 审批面板：coder/reviewer 摘要网格 + 拒绝理由 textarea（必填校验）+ Approve/Reject 双按钮 + loading/error/done 三态

### 修改的文件 (1 个)

- `src/renderer/components/workflow/WorkflowDetailPage.tsx` — 用 `<ApprovalPanel>` 替换 `<div role="alert">` interrupt 提示

### 技术决策

1. **Reject 按钮 disabled={!rejectReason.trim()}** — 拒绝必须填写理由，客户端强制
2. **done 状态** — 提交成功后显示 "Decision submitted." 绿条，不显示按钮
3. **`interrupt: false` 写入 store** — 审批后立即清除，UI 自动收起面板
4. **ApprovalPanel 直接调用 useApi + useWorkflowStore** — 自包含组件，prop 只传 threadId + nodes

---

---

## Phase 8: Code + Diff Viewer ✅ 2026-05-12

### 工作摘要

集成 Monaco Editor：DiffViewer（左右分栏 diff 只读）、CodePreview（单文件语法高亮）、TestCaseViewer（可展开测试用例 + 一键复制代码）。全部接入 WorkflowDetailPage 的 Coder/Reviewer 节点展开面板。

### 创建的文件 (3 个)

- `src/renderer/components/code/DiffViewer.tsx` (33 行) — Monaco DiffEditor, side-by-side, read-only
- `src/renderer/components/code/CodePreview.tsx` (30 行) — Monaco Editor, read-only, 语法高亮
- `src/renderer/components/code/TestCaseViewer.tsx` (84 行) — 折叠测试列表 + Copy 按钮 (2s "Copied" feedback)

### 修改的文件 (1 个)

- `src/renderer/components/workflow/WorkflowDetailPage.tsx` — Coder 展开: DiffViewer/CodePreview + SelfCheckTable; Reviewer 展开: TestCaseViewer

### 技术决策

1. **Monaco 通过 @monaco-editor/react 引入** — 自动处理 worker/CDN 加载，diff 和 editor 两个组件共用
2. **vs-dark 主题** — 与应用暗色主题一致
3. **DiffViewer 先判断 diff 再判断 code** — 优先展示 unified diff，无 diff 时回退到纯代码预览
4. **TestCaseViewer navigator.clipboard.writeText** — 现代 API，失败静默处理
5. **复制反馈 2s 自动消失** — Check 图标 + "Copied" 文字

### 构建结果

```
TSC: zero errors | Build: clean | Tests: 32/32 pass
JS:  772.9 KB (+30 KB Monaco React wrapper)
CSS: 40.1 KB
```

---

---

## Phase 9: Index Management ✅ 2026-05-12

### 工作摘要

知识图谱索引管理：文件选择器（IPC dialog）+ 重建索引按钮（调用 POST /api/index/rebuild）+ 统计面板（node/edge/file count）。

### 创建的文件 (3 个)

- `src/renderer/stores/index.store.ts` (20 行) — Zustand store (stats/loading/error)
- `src/renderer/components/index/IndexManager.tsx` (51 行) — graph.json 路径选择 + Rebuild 按钮 + loading spin
- `src/renderer/components/index/IndexStats.tsx` (25 行) — 4 格统计卡片 (nodes/edges/files/loaded_at)

### 修改的文件 (1 个)

- `src/renderer/components/index/IndexPage.tsx` — 使用 IndexManager + IndexStats 替代占位

---

## Phase 10: Settings Pages ✅ 2026-05-12

### 工作摘要

设置页：Tab 切换（API Keys / Advanced），API 密钥 password 字段 + electron-store IPC 持久化，高级参数（port/timeout/budget/token_limit）number input。

### 创建的文件 (3 个)

- `src/renderer/stores/settings.store.ts` (38 行) — Zustand + IPC sync (loadFromIpc/saveToIpc)
- `src/renderer/components/settings/APISettings.tsx` (35 行) — Anthropic/LangSmith key password fields
- `src/renderer/components/settings/AdvancedSettings.tsx` (43 行) — port/max_revisions/timeout/budget/token_limit

### 修改的文件 (1 个)

- `src/renderer/components/settings/SettingsPage.tsx` — Tab 切换 + loadFromIpc on mount

---

## Phase 11: Packaging ✅ 2026-05-12

### 变更

- `electron-builder.yml` — 添加 portable zip target + `extraResources` (bridge/agent/api/config/requirements.txt)

### 打包目标

| Platform | Format |
|----------|--------|
| Windows | NSIS installer + portable zip |
| Linux | AppImage |
| macOS | DMG |

---

## Phase 12: Tests ✅ 2026-05-12

### 新增测试

- `src/renderer/stores/workflow.store.test.ts` (54 行) — 7 tests: Map immutability, add/update/get, multi-workflow
- `src/renderer/stores/settings.store.test.ts` (40 行) — 3 tests: defaults, partial merge immutability, field preservation

### 测试覆盖

```
42 passed, 0 failed (5 test files)
  api.test.ts:              11 tests
  python-manager.test.ts:   11 tests
  useSSE.test.ts:           10 tests
  workflow.store.test.ts:    7 tests
  settings.store.test.ts:    3 tests
```

---

## 项目最终统计

| 指标 | 数值 |
|------|------|
| 总文件数 | 60+ |
| 源文件 (.ts/.tsx) | 43 |
| 测试文件 | 5 |
| 测试用例 | 42 (100% pass) |
| 主进程 bundle | 12.6 KB |
| Preload bundle | 1.1 KB |
| 渲染进程 JS | 784 KB |
| 渲染进程 CSS | 40.5 KB |
| TypeScript 错误 | 0 |
| Build 警告 | 0 |
| 依赖包数 | 721 |

---

## Template for Next Phases

```markdown
## Phase N: <名称> ✅ <日期>

### 工作摘要
<2-3句话>

### 创建的文件
- file1.ts — 说明
- file2.tsx — 说明

### 修改的文件
- existing.ts — 变更说明

### 技术决策
1. 决策 — 原因

### 测试结果
- 单元测试: N pass, 0 fail
- 覆盖率: XX%
```
