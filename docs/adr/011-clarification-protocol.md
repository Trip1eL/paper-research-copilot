# ADR-011：Clarification Protocol 与父子研究任务

- 状态：Accepted
- 日期：2026-08-20

## 背景

Question Gate 已能识别无上下文指代、无评价标准的最高级问题和缺少目标约束的选型问题，但旧行为
只是确定性返回 `INSUFFICIENT_EVIDENCE`。这能防止错误检索和动态扩库，却没有让用户补充信息后
继续研究，也无法持久化一次追问交互的来源关系。

## 决策

Ambiguous 父任务正常结束为 `succeeded`，`AgentResult.clarification` 返回结构化追问：Rule、Prompt
和 Required Information。用户通过 `POST /api/v1/research/{task_id}/clarify` 提交补充后，系统创建
一个新的 Child Research Task，并把“原问题 + 用户补充”组成可独立执行的问题重新进入完整 Runtime。

父子关系使用独立的 `research_task_clarifications` 表持久化，记录 Parent Task、Child Task、补充文本、
规范化响应 Hash 和时间。`parent_task_id + response_hash` 唯一，因此重复提交相同补充会返回同一个
Child Task，不重复执行 Agent。

## 原因

- Ambiguous Graph 已自然结束，没有可恢复的中断点；复用 LangGraph Resume 会混淆进程恢复和用户交互。
- 新 Child Task 保留独立 Event、Checkpoint、Result 和错误边界，同时 Parent 的拒绝原因不会被覆盖。
- 单独关系表比在任务表加入一组交互字段更适合审计，也为后续多轮 Clarification 保留扩展空间。
- Answer Status 仍保持 `answered / insufficient_evidence`，冻结的 Open-world v1 金标无需修改。

## 不变量

- 只有 `succeeded` 且确实包含 `clarification` 的任务可以接受补充。
- 追问前不执行 Retrieval、Acquisition 或 Answer LLM，不产生 Dynamic Corpus 写入。
- Child 问题同时保留原问题和补充内容；补充仍然含糊时可以再次产生 Clarification。
- Memory Repository 与 SQLite Repository 必须实现相同的幂等和父子关系语义。

## 验证

`clarification_v1.jsonl` 冻结三类协议 Case。确定性 Evaluation 分别测量 Ambiguity Detection、Prompt
Presence、Pre-clarification Side-effect Free、Child Runtime Re-entry、Child Answer Behavior 和
Provenance。其中 Answer Behavior 只核对 `answered / insufficient_evidence` 状态，不测语义正确性。
真实模型结果必须通过独立 Live Evaluation 和人工审计，不能用协议测试替代答案质量结论。
