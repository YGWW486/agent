# 开发日志

> 记录每次修改计划、完成情况、遇到的问题及解决方案。

---

## 2026-05-14 · 工具调用层迁移 + 架构分析

### 计划
- 自研 LLM Provider 层（`AnthropicLLM` / `DeepSeekLLM`）迁移到 LangChain 原生抽象
- 工具调用统一使用 `with_structured_output()`，消除 Anthropic ↔ OpenAI 格式手动翻译
- 重试逻辑从自研 `retry_async` 迁移到 LangChain 内置 `with_retry()`

### 完成

**工具调用层迁移**
- `agent/llm.py` 重写：460 行 → 145 行
  - 删除 `AnthropicLLM`、`DeepSeekLLM` 两个类（手动构造 tool schema、Anthropic/OpenAI 格式互译）
  - 新增 `create_llm()` 工厂函数，mode 三态：`chat` / `thinking` / `structured`
  - 新增 `TokenTracker` LangChain callback，替代旧两个类各自的 `_track_usage`
  - DeepSeek `thinking_mode` 透传：`ChatOpenAI(model_kwargs={"thinking_mode": "non-thinking"})`
- `agent/retry.py` 精简：删除 `RetryConfig`、`retry_async`、`with_retry`，保留 `CircuitBreaker`、`FallbackHandler`
- `agent/orchestrator.py` 三个节点统一：
  - 改前：`llm.chat_with_structured_output(system=..., messages=..., output_model=TaskDAG, tool_name="output_plan", ...)`
  - 改后：`create_llm(mode="structured").with_retry(stop_after_attempt=N).with_structured_output(TaskDAG).ainvoke(messages)`
- `agent/__init__.py` + `api/routes.py` 适配新导出（`get_llm_info` 替代 `get_llm().model` / `get_llm().token_usage()`）
- `requirements.txt` 新增 4 个依赖：`langchain-core>=0.3.0`、`langchain-anthropic>=0.3.0`、`langchain-openai>=0.3.0`、`tenacity>=8.0.0`

**架构分析**
- 定位：LangGraph 编排 + LangChain 工具抽象，在"自研太累"和"框架太重"之间取平衡点
- 对比 MCP：PRD 已明确不做 MCP Server，三个工具（output_plan/output_code/output_review）是硬编码流水线节点，MCP 徒增复杂度
- 对比 CrewAI/AutoGen：不换全套框架，LangGraph StateGraph + checkpoint + HITL 编排能力更强更透明
- 选用 `with_structured_output()` 而非 `bind_tools() + ToolNode`：因为三个"工具"本质是不同 LLM 节点的输出 schema，不是需要执行的函数
- 唯一保留的自研组件：`CircuitBreaker`（工作流级熔断），LangChain 无等价物

### 验证
- 全部 13 个已有测试通过（`pytest tests/ -v`）
- Anthropic + DeepSeek 双路径导入正常
- LangGraph 流水线编译通过（`CompiledStateGraph`）

### 不变的部分
- LangGraph StateGraph 结构（planner → coder → reviewer → merge）
- Bridge 层 / API 路由 / Electron 前端：零改动
- Pydantic 模型（TaskDAG、CoderOutput、ReviewResult）：零改动

---

## 2026-05-13 · 打包流程贯通 + UI 中文化 + 设计升级 + UX 第一批

### 计划
- 贯通桌面端完整打包流程
- 全界面中文化
- 基于 OpenDesign/Cursor 设计系统升级视觉
- UX 优化第一批（后端自启动、工作流列表、首页实时数据、中文化收尾）

### 完成

**打包**
- 修复 pnpm `.ignored` 导致 Electron 二进制不可用 → 手动创建 Junction
- 修复 electron-builder 国内下载超时 → 设置 `ELECTRON_MIRROR` 淘宝镜像
- 创建 `pyinstaller-server.spec`，PyInstaller 打包 Python 后端为单文件 exe (26 MB)
- `electron-builder.yml` extraResources 指向 `.exe` 而非 `.py` 源码
- `python-manager.ts` 实现 `getBackendCommand()` 区分 dev/prod 启动路径
- 创建 `.env.example`（密钥置空）
- 修复 `PYTHONPATH` 缺失导致 `ModuleNotFoundError: No module named 'api'`
- 修复空字符串 env var 覆盖 `.env` 导致 Pydantic `bool_parsing` 报错
- 修复 `BrowserRouter` → `HashRouter`（`file://` 协议下路由失效）
- 修复 CSP 拦截 Google Fonts
- 产出：`desktop/dist/agentic-engineering-console-0.1.0-portable.exe` (108 MB)

**UI 中文化**
- TopBar: 控制台 / 仪表盘 / 工作流 / 新建工作流 / 知识索引 / 设置
- Sidebar: 首页 / 工作流 / 索引 / 设置 / 后端状态 / 命令面板
- NodeCard: Planner·任务拆解 / Coder·代码生成 / Reviewer·代码审查 / Merge·合入审批
- 状态标签: 等待中 / 运行中 / 已完成 / 失败 / 挂起
- ApprovalPanel: 通过·合入 / 拒绝·打回修改
- SubmitForm: 需求规格 / 上下文（可选）/ 启动工作流
- Settings: API 密钥 / 高级设置 / 后端端口 等
- Index: 节点数 / 边数 / 已索引文件 / 加载时间 / 重建索引

**设计升级**
- Tailwind 色彩体系：冷蓝灰 → 暖炭色 `oklch(18% 0.005 85)`
- Accent：蓝 `oklch(68% 0.18 250)` → 暖橙 `oklch(65% 0.19 40)`
- Pipeline 4 色板：Planner 桃红 / Coder 青绿 / Reviewer 蓝 / Merge 紫
- 自定义标题栏：`frame: false` + 窗口控制按钮（最小化/最大化/关闭）
- 标题栏可拖拽（`-webkit-app-region: drag`）
- HomePage 布局：后端状态大卡 + 最近工作流 + CTA
- Sidebar 加启动/停止/重启按钮

**Bug 修复**
- `useBackendStore` selector 返回新对象导致 React 无限循环 → 拆为独立 primitive selector
- `python-manager.ts` spawn 缺少 `PYTHONPATH` → 添加且过滤空字符串 env var
- 新增 `PYTHONPATH` 测试用例 (43 tests)

### 问题记录

| # | 问题 | 根因 | 修复 |
|---|------|------|------|
| 1 | `pnpm dev` 报 Electron uninstall | pnpm 把 electron 二进制隔离到 `.ignored` | Junction 链接 + `ELECTRON_EXEC_PATH` |
| 2 | electron-builder 下载超时 | 国内直连 GitHub | `ELECTRON_MIRROR` 设淘宝镜像 |
| 3 | pip 路径迁移崩溃 | .venv 硬编码旧路径 | 删 .venv 重建 |
| 4 | `resources/backend/` 为空 | extraResources.from 文件名不精确 | 加 `.exe` 后缀 |
| 5 | portable.exe 只显示背景色 | BrowserRouter 在 file:// 下失效 | 换 HashRouter |
| 6 | Google Fonts 不加载 | CSP 未放行 fonts.googleapis.com | style-src 加域名 |
| 7 | ModuleNotFoundError: No module named 'api' | Python sys.path 不含项目根目录 | spawn env 加 PYTHONPATH |
| 8 | Pydantic ValidationError LANGSMITH_TRACING | 空字符串 env var 覆盖 .env | filter 空值不传给子进程 |
| 9 | React 无限循环 HomePage | Zustand selector 每次返回新对象 | 拆为独立 primitive selectors |
| 10 | React Router v7 警告 | 未设 future flags | HashRouter 加 future prop |

---

## 2026-05-12 · Electron 12 阶段全部完成

### 完成
- Phase 1: 项目脚手架 (electron-vite + React 18 + TypeScript + Tailwind 3)
- Phase 2: Python 后端生命周期管理 (PythonManager: spawn/health-poll/auto-restart)
- Phase 3: 布局框架 (AppShell + Sidebar + TopBar + 6 路由)
- Phase 4: 工作流提交 + API 层 (SubmitForm + createApi + workflow store)
- Phase 5: SSE 实时流 (useSSE: ReadableStream + 指数退避重连)
- Phase 6: 时间线组件 (Timeline + NodeCard + TaskDAGView + SelfCheckTable)
- Phase 7: 审批面板 (ApprovalPanel: approve/reject + 拒绝理由)
- Phase 8: 代码查看 (DiffViewer + CodePreview + TestCaseViewer，Monaco Editor)
- Phase 9: 知识索引管理 (IndexManager + IndexStats + index store)
- Phase 10: 设置页 (APISettings + AdvancedSettings + settings store)
- Phase 11: 打包 (electron-builder: NSIS + portable)
- Phase 12: 测试 (42 tests, 5 test files, 100% pass)

### 技术栈
- 前端: Electron 33 + React 18 + TypeScript + Tailwind 3 + Zustand + Monaco Editor + @xyflow/react
- 后端: FastAPI + LangGraph + Anthropic SDK + SSE (sse-starlette)
- 构建: electron-vite + pnpm
- 测试: Vitest (42 用例)
- 安全: contextBridge + sandbox + 127.0.0.1 绑定 + API Key 脱敏

---

## 2026-05-05 · graphify 集成决策

### 决策
- graphify 实现路径：集成既有 CLI + 轻量封装
- 索引触发：手动触发 `POST /api/index/rebuild`
- 查询接口：`GET /api/context?files=x&depth=2`
- 存储：内存字典 + SQLite 持久化缓存

---

## 待实施

### UX 优化第二批
- [ ] Toast 通知系统
- [ ] Timeline 自动滚动
- [ ] 设置保存反馈
- [ ] 审批面板自动聚焦
- [ ] ⌘K 命令面板

### UX 优化第三批
- [ ] 多项目管理
- [ ] Monaco Editor 懒加载
- [ ] 键盘快捷键面板
- [ ] 工作流详情分栏布局
- [ ] 工作流报告导出

### 新功能
- [ ] 多目录选择（可写/只读）+ Agent 权限扩展请求
- [ ] Agent 文件操作摘要（审批时展示）
- [ ] 工作流报告导出
