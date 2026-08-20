# ADR 009: Question Screening 与 Candidate Relevance Gate

- Status: Accepted
- Date: 2026-08-20

## Context

Open-world Evaluation v1 暴露了三类高代价错误：含糊问题会进入 Retrieval 或 Acquisition；短缩写
`SAGE` 会召回同名但不同领域的论文；不存在的 `GPT-7` 会被弱化为普通 `GPT`，最终下载并索引无关
PDF。仅凭 Answer Model 最终拒答无法阻止下载、Parse、Embedding 和 Qdrant 写入等副作用。

## Decision

- 生产 Runtime 在 Planning 后、Retrieval 前执行确定性 `QuestionAmbiguityGate`。第一版只覆盖高置信度
  模式：未解析前文指代、无评价标准的“最佳”问题、无目标与约束的论文方法选型。
- 命中 Gate 时生成结构化 `QuestionScreening` 与 `screen_question` Trace，直接返回确定性的
  `INSUFFICIENT_EVIDENCE`；不调用 Retriever、Acquisition 或 Answer LLM。
- arXiv Query 保留 CamelCase、全大写缩写和带版本号模型名。短缩写使用“实体 + 研究上下文”的
  结构化表达式，例如 `all:"SAGE" AND all:"Deep Research Agents"`。
- Candidate 在下载前验证 Title/Abstract：显式实体必须完整匹配；长查询还必须至少匹配两个上下文词。
  `GPT` 不等价于 `GPT-7`，`Causal-AgentIR` 也不等价于独立实体 `AgentIR`。
- 包含显式方法或模型名的 Query 最多下载排名第 1 的 Candidate；通用主题 Query 继续遵守原
  `max_downloads` 预算。
- 0 个 Candidate 通过时 Acquisition 明确记为 `failed`，`selected/downloaded/indexed` 均为 0，且
  不进入 Parse、Embedding 或 Qdrant。

## Consequences

冻结的 16 条 Open-world Dataset 在无 Query Revision 消融下由 `11/16 (68.75%)` 提升为
`16/16 (100%)`。Recoverable Success、Unrecoverable No-index、Ambiguous Abstention、Dynamic
Evidence、Target Citation 和 Parser Provenance 均达到 `100%`；下载/索引从 `12/11` 降至 `5/5`，
Point Delta 从 `270` 降至 `116`。

Trigger Precision 为 `62.5%` 而非 `100%`，因为当前策略允许 Unrecoverable 问题执行一次无副作用的
arXiv Metadata Search；该指标把 Recoverable 作为唯一正类，因此这三次受控搜索仍计入 False Positive。
当前 Gate 是高精度规则而非通用语义分类器，也尚未实现多轮 Clarification 协议。
