# FastAPI 与任务事件接口

## 目标

API 将已有 LangGraph Agent Runtime 暴露为异步研究任务。HTTP 层不实现 Planning、Retrieval、
Evidence Gate 或 Answer 逻辑，只负责请求校验、任务状态、错误边界和事件传输。

当前版本面向单机作品演示：使用 SQLite 任务仓库和单 Worker，避免本地 Qdrant、SQLite 与 Planner
Cache 被多进程并发写入。服务重启后 Task、Event、Result 可查询，遗留 running Task 会转为
interrupted；仍不能使用多个 Uvicorn Worker。

## 启动

完整作品演示推荐在项目根目录执行：

```powershell
.\scripts\start_demo.ps1
```

该命令先生成 `frontend/dist`，再启动 FastAPI；工作台和 API 统一位于
`http://127.0.0.1:8000`。仅开发或调试 API 时，可使用下面的独立入口。

安装或更新 editable package 后启动：

```powershell
python -m pip install -e ".[dev]"
paper-research-api
```

也可以直接运行：

```powershell
python -m uvicorn paper_research_copilot.api.app:app --host 127.0.0.1 --port 8000
```

OpenAPI 位于 `http://127.0.0.1:8000/docs`。服务仅绑定本机地址，当前没有认证，不应直接暴露到
公网。

## 接口

### `GET /health`

第一次调用会惰性构建 Agent Runtime，并实际检查模型配置、Corpus v3、Qdrant Collection 是否
存在且非空，同时报告 `task_store`、`checkpoint_ready` 和 checkpoint 错误。生产配置只有 Runtime
与 Checkpoint 均就绪才返回 `status=ok`。

### `POST /api/v1/research`

请求：

```json
{
  "question": "ReAct 如何结合推理轨迹和外部行动？"
}
```

返回 HTTP 202，包括 `task_id`、初始 `queued` 状态、任务 URL 和 SSE URL。问题会去除多余空白，
长度限制为 5–2000 字符；未知字段被拒绝，客户端不能覆盖模型或检索配置。

### `GET /api/v1/research/{task_id}`

返回 `queued/running/interrupted/succeeded/failed` 状态。成功后 `result` 是完整 `AgentResult`，包含 Plan、
Evidence、Evidence Assessment、Answer、Citations、Retry Count 和节点 Trace；失败时返回错误类型
与信息，不返回半成品结果。

### `GET /api/v1/research/{task_id}/events`

返回 `text/event-stream`。事件按 API `sequence` 严格递增：

```text
task_queued
task_started
agent_node: plan_research
agent_node: retrieve_evidence
agent_node: assess_evidence
agent_node: revise_queries（只在 Evidence 不足时出现）
agent_node: write_report
agent_node: validate_citations
task_interrupted / task_succeeded / task_failed
```

`agent_node` 内嵌 Runtime 原生 `AgentEvent`，包含 node、outcome、latency 和安全的 details。连接空闲
15 秒时发送 SSE heartbeat；终态事件发送后连接正常结束。`?after=N` 可跳过已经消费的事件，便于
前端断线或服务重启后继续读取。

### `POST /api/v1/research/{task_id}/resume`

只接受 `interrupted` Task，返回 HTTP 202。服务先确认 `thread_id=task_id` 的 LangGraph checkpoint
存在，再原子写入 `task_resumed` 并进入队列；状态不匹配或无 checkpoint 返回 HTTP 409。恢复只保证
最近已提交 node 边界，不能恢复某个节点内部的 Python 指令。

PowerShell 可用以下命令观察原始事件：

```powershell
curl.exe -N http://127.0.0.1:8000/api/v1/research/<task_id>/events
```

## 生命周期与并发

```text
POST
  -> queued event
  -> ThreadPoolExecutor(max_workers=1)
  -> running event
  -> Agent Runtime node callbacks
  -> succeeded(result) / failed(error)
```

`ResearchTaskService` 使用 Repository 作为唯一数据源，`Condition` 只负责当前进程内唤醒 SSE；
Task 状态和对应 Event 在同一 SQLite 事务中提交，sequence 由数据库分配。业务库 `data/app.db`
与 LangGraph 内部库 `data/checkpoints.db` 分离。应用关闭时等待当前任务结束并幂等关闭 Runtime 与
数据库。未来若扩展为多实例，应保持现有 HTTP/Repository 契约，将 SQLite 与本地 Executor 替换为
PostgreSQL 和独立 Worker。
