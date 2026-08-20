# ADR 010: Revision Planner Schema Recovery

- Status: Accepted
- Date: 2026-08-20

## Context

Phase 6 的生产配置 Smoke 在 `max_retries=1` 时只有 `25%` Strict Pass。失败都发生在
`revise_queries`：模型连续三次输出不符合 `_PlanPayload` 的 JSON，而旧重试逻辑每次发送完全相同的
Prompt，既没有告诉模型错误字段，也没有在模型不可用时提供降级路径。无 Revision 消融能够验证
Acquisition，却不能代表生产 Runtime 稳定。

## Decision

- Revision Prompt 中的 Previous Plan 只序列化 `_PlanPayload`，不再传入 Runtime 字段 `question` 和
  `revision`；输出要求明确禁止额外字段。
- JSON、Pydantic Schema、Task Shape、Question Type、Unchanged Query 和 Alias Leakage 等错误会保存
  原始响应与具体错误路径。下一次调用使用 Schema-aware Repair Prompt，而不是重复相同 Prompt。
- 模型尝试耗尽后，仅 Revision 使用 Deterministic Fallback：保持 Question Type、Task 数量、连续 ID
  和 Goal，通过通用检索术语扩展 Query，保证 Revision 合法且发生变化。Initial Planning 继续严格
  失败，不用 Fallback 掩盖入口问题。
- Validation 类 Fallback 写入 Planner Cache；最终错误为瞬时 `provider_error` 时只完成当次降级，不
  缓存 Fallback，服务恢复后允许重新尝试模型。
- Planner Cache Hash 对 Revision Recovery 版本敏感，避免复用旧策略生成的 Revision。
- `PlanningResult`、Planner Generation Trace、LangGraph Event 和 Open-world Diagnostics 记录 Attempt、
  Repair、Fallback、失败原因以及 Revision 前后 Query。

## Consequences

第一轮 Schema-aware Repair 实验中，8/8 Revision 首次响应都多出 `question` 字段，第二次 Repair 均
成功：Strict Pass `16/16`，LLM Attempts `16`，Repair Attempts `8`，Fallback `0`。这证明 Repair
安全网有效，也定位出 Previous Plan 示例与目标 Payload 不一致的共同根因。

修正 Prompt Payload 后，同一冻结 Dataset 的 8/8 Revision 全部首次通过：Strict Pass 保持
`16/16`，LLM Attempts 从 `16` 降到 `8`，Repair Attempts 从 `8` 降到 `0`，Fallback 仍为 `0`。
相较 Repair 实验，观测到 P95 从约 `73.9s` 降至 `62.2s`，已知总 Token 减少 `8,053`。Fallback
目前由自动化故障注入验证，未在正式 Dataset 中触发。
