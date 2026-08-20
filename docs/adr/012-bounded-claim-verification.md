# ADR-012：Bounded Claim-level Verification

- 状态：Accepted
- 日期：2026-08-20

## 背景

Citation Validation 只能证明 Citation ID 指向最终 Evidence，离线 LLM Judge 则依赖 Reference Answer，
两者都不能在生产 Runtime 中阻止“引用存在但具体 Claim 不被引用内容支持”的回答。直接加入开放式
Reflection Loop 会显著增加延迟、成本和不可预测性，也会与当前最多一次 Revision/Acquisition 的有界
Agent 原则冲突。

## 决策

在 `write_report` 与最终 `validate_citations` 之间增加一个可配置的 `verify_claims` 节点。Verifier 使用
`gpt-5.5`，只读取候选回答及其实际引用的 Evidence，将最多 8 个关键 Claim 判为 `supported`、
`partially_supported` 或 `unsupported`。

- 全部支持时直接放行原回答。
- 存在部分支持或不支持 Claim 时，同一次结构化输出必须给出一次修订后的完整回答。
- 修订只能使用原回答已有 Citation ID；无可保留内容时返回 `INSUFFICIENT_EVIDENCE`。
- 修订后仍执行确定性 Citation Validation，不进入第二次 Verification 或循环 Reflection。
- Provider 或 Schema 最终失败时保留原回答，但把 Verification 标为 `error` 和
  `needs_human_review=true`，不得静默标成通过。
- 旧任务的 `AgentResult.verification` 可以为空，保持持久化 JSON 向后兼容。

## 原因

该设计把 Reflection 限制为一次 Claim-Evidence 检查和一次必要修订，能够展示真实的质量控制闭环，
同时保持停止条件清晰。生产 Verifier 不读取 Evaluation Reference Answer，避免数据泄漏；离线 Judge
仍负责带金标的 Correctness/Faithfulness 评估，两者职责分离。

## 验证与边界

`claim_verification_v1` 使用两条历史真实回答和两条人工注入错误。真实 `gpt-5.5` Smoke 达到
`4/4 Strict Pass`：两个正样本直接通过，两个对抗样本均修订，注入内容移除率为 `100%`。四次调用
总延迟约 `76s`，单次约 `14.1–27.7s`，因此可通过 `AGENT_CLAIM_VERIFICATION_ENABLED=false`
关闭低延迟模式。

四条 Case 不能外推为开放域统计正确率；Verifier 与 Planner 使用同一高能力模型仍存在相关偏差。
当前不增加多 Judge、自一致性或递归 Reflection，必要时由 `needs_human_review` 暴露不确定性。
