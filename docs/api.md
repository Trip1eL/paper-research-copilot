# FastAPI 与任务事件接口

## 目标

API 将已有 LangGraph Agent Runtime 暴露为异步研究任务。HTTP 层不实现 Planning、Retrieval、
Evidence Gate 或 Answer 逻辑，只负责请求校验、任务状态、错误边界和事件传输。

当前版本面向单机作品演示：使用进程内任务仓库和单 Worker，避免本地 Qdrant 与 Planner Cache
被并发写入。服务重启后任务不会恢复，也不能使用多个 Uvicorn Worker；这些是明确的 MVP 边界。

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
存在且非空。成功返回 `status=ok`；失败返回 `status=degraded` 和脱敏错误，同时服务进程仍保持
可用，便于修正配置后再次探测。

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

返回 `queued/running/succeeded/failed` 状态。成功后 `result` 是完整 `AgentResult`，包含 Plan、
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
task_succeeded / task_failed
```

`agent_node` 内嵌 Runtime 原生 `AgentEvent`，包含 node、outcome、latency 和安全的 details。连接空闲
15 秒时发送 SSE heartbeat；终态事件发送后连接正常结束。`?after=N` 可跳过已经消费的事件，便于
前端断线后在任务仍保留于当前进程时继续读取。

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

`ResearchTaskService` 通过 `Condition` 保护任务记录和事件列表；Agent Runtime 惰性构建并复用，
应用关闭时等待当前任务结束，再幂等关闭 Qdrant Runtime。下一阶段若需要多用户并发，应保持现有
HTTP/Pydantic 契约，将任务仓库和 Executor 替换为 Redis + 独立 Worker，而不是在 Route 内增加
后台逻辑。
