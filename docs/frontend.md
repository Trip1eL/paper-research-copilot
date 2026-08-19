# React 研究工作台

## 定位

前端是 FastAPI Task Layer 的薄客户端，用于展示一次论文研究任务的输入、实时 Agent Trace、最终
报告、Evidence 和 Research Plan。它不包含模型路由、检索策略或 Citation 判断，所有研究语义
来自后端公开契约。

当前技术栈为 React 19、TypeScript、Vite 和 Lucide Icons。没有引入全局状态库、组件框架或
Markdown 渲染器，以保持第一个可展示版本的依赖和行为边界清晰。

## 启动

### 生产演示模式

在项目根目录执行：

```powershell
.\scripts\start_demo.ps1
```

脚本在需要时安装锁定的前端依赖，执行 TypeScript 检查和 Vite Production Build，然后启动
FastAPI。浏览器只需访问 `http://127.0.0.1:8000`。FastAPI 会托管 `frontend/dist`，并为前端
页面路由返回 `index.html`；不存在的 `/api`、`/health`、`/docs` 等后端路径仍返回后端 404，
不会被网页回退掩盖。

### 开发模式

先启动后端：

```powershell
conda activate paper-research-copilot
paper-research-api
```

再启动前端：

```powershell
cd frontend
npm install
npm run dev
```

浏览器访问 `http://127.0.0.1:5173`。Vite 将 `/health` 和 `/api` 代理到
`http://127.0.0.1:8000`，开发环境不需要放宽后端 CORS。生产构建：

```powershell
npm test
npm run build
```

构建产物位于 ignored 的 `frontend/dist/`。当前单机演示由 FastAPI 同源托管；更大规模部署时，
可改为反向代理静态文件并继续将 `/api` 和 `/health` 转发至 FastAPI。

## 工作区布局

桌面使用三栏操作界面：

```text
Research Query      Agent Trace          Research Output
问题输入             SSE 节点时间线        Report / Evidence / Plan
Task 状态            outcome + latency    Answer + Citations
关键指标             details              Chunk + Retrieval Score
```

小于 1080px 时，左侧任务栏固定为第一列，Timeline 与 Result 在第二列上下排列；小于 720px 时
改为单列文档流，避免横向滚动。固定按钮、Tab、Metric Grid 和 Timeline Icon 均有稳定尺寸，长问题、
论文标题和 Chunk 文本使用换行或截断，不改变布局轨道。

## 状态与事件

提交过程：

1. POST 创建任务，立即显示 `queued` 和 Task ID。
2. EventSource 订阅命名 SSE 事件，按 sequence 去重并排序。
3. `task_succeeded/task_failed` 到达后主动关闭 EventSource，避免浏览器对正常 EOF 自动重连。
4. 终态再 GET Task Snapshot，取得完整 AgentResult。
5. SSE 异常时关闭连接并每 2 秒轮询 Task，终态后停止。

当前页面刷新不会恢复旧 Task，因为后端 Task Store 本身也是进程内内存实现。后续增加持久化时，
可以在 URL 中保存 Task ID，再用 `?after=N` 恢复事件，而不需要修改现有 Result 组件。

## 结果视图

- Report：展示 Evidence Gate 状态、结构化回答和 Citation Sources。
- Evidence：展示最终 Top-K Chunk、论文标题、页码、Section、分数和文本预览。
- Plan：展示 single/cross-paper Route、Revision、Rationale、Queries、Goals 和 Assessment。

Citation Source 是命令按钮：点击后切换到 Evidence Tab，并滚动、高亮对应 Citation ID。不能使用
普通锚点，因为未选中的 Tab 不会渲染 Evidence DOM；这是浏览器交互验收中发现并修复的问题。

## 当前边界

- 不保存历史任务或用户偏好。
- 不支持任务取消和重试按钮。
- Answer 按纯文本安全渲染，不执行模型输出中的 HTML。
- Evidence 只显示六行预览，完整 Chunk 仍存在 DOM 文本中；后续可增加展开控制。
- 当前没有身份认证，前后端只用于本机开发展示。
