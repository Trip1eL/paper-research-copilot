# ADR 005: Durable Single-node Runtime Storage

- Status: Implemented in v2.0 Phase 3
- Date: 2026-08-19

## Context

v1 的 `ResearchTaskService` 使用进程内字典和 `ThreadPoolExecutor(max_workers=1)`。服务重启后任务、
SSE 事件和结果全部丢失，LangGraph 也没有 Checkpointer。动态下载和向量写入属于外部副作用，如果
没有持久化状态和幂等键，恢复运行可能产生重复论文、重复 Embedding 或错误任务状态。

## Decision

- v2.0 保持单机、单 Worker 运行模型，不引入 Redis/Celery。
- 使用 SQLAlchemy 2 + Alembic 管理 `data/app.db`。Phase 3 先保存 Task、Event、Result；Paper
  Registry 和 Acquisition Run 随 Phase 4 的稳定领域模型增加后续 Migration。
- 使用 `langgraph-checkpoint-sqlite` 管理独立的 `data/checkpoints.db`。
- API/Agent 通过 Repository Protocol 访问业务数据，不依赖 ORM Model。
- Graph `thread_id` 固定为 API `task_id`，只保证已提交 node 边界的恢复。
- 启动时把遗留 `running` 任务转为 `interrupted`；用户通过显式 Resume API 继续。
- Event sequence 在数据库事务中分配，并以 `(task_id, sequence)` 唯一约束保持 SSE 可续读。
- 所有外部副作用使用稳定 idempotency key，并在提交后记录结果。
- 业务数据库与 Checkpoint 数据库分离，避免迁移和锁生命周期耦合。

## Rejected alternatives

- **PostgreSQL + Redis + Celery**：适合多实例生产系统，但超出当前单机作品的并发和部署目标。
- **只保存最终 Report**：无法恢复任务，也不能审计 Acquisition 与节点事件。
- **直接读取 LangGraph checkpoint 作为 API 数据库**：耦合内部 Schema，API 查询和迁移不可控。
- **进程启动后自动重跑所有 running Task**：外部副作用尚未全部幂等前存在重复执行风险。
- **单个 SQLite 文件保存全部内容**：业务迁移与 LangGraph 内部表相互影响，并增加写锁竞争。

## Consequences

v2.0 能证明重启恢复和副作用幂等，但不宣称支持水平扩容或多 Uvicorn Worker。Repository 边界允许
未来把 Application Store 切换到 PostgreSQL，而不修改 API/Agent 契约。

## Verification

- SQLite Repository 重开后 Task、Event、Result 与 `after=N` cursor 保持有效。
- Alembic `upgrade head` 可重复执行，事件使用 `(task_id, sequence)` 唯一约束。
- 真实 LangGraph 在 Retrieval 节点故障后关闭并重开 `checkpoints.db`，Resume 不重复 Planner 节点。
- API 显式执行 `interrupted -> queued -> running -> succeeded`，重复或无 checkpoint Resume 返回冲突。
