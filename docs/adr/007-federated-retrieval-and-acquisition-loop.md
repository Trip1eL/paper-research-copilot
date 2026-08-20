# ADR 007: Federated Retrieval 与有界 Acquisition Loop

- Status: Accepted
- Date: 2026-08-20

## Context

Phase 4 已能安全摄取 arXiv PDF，但它与 Agent 检索链路相互独立。直接把动态论文并入 Curated
Collection 会破坏冻结 Baseline；让 Agent 反复联网则会造成不可控延迟、费用和副作用。内存 BM25
还可能在 Dense 已看到新 Point 时继续使用旧 Chunk snapshot。

## Decision

- Curated 和 Dynamic 保持独立 Qdrant Collection，各自执行现有 Dense + BM25 Hybrid RRF。
- 使用第二层确定性 RRF 融合两个 Corpus，按 Chunk ID 去重并重新编号 Citation。
- Dynamic Qdrant exact point count 作为 Retriever generation；变化后懒重建 BM25。
- 两个 Dense Retriever 共享最多 256 条 Query Embedding Cache，避免重复模型调用。
- Agent 先执行低成本的本地 Query Revision，仍 insufficient 才执行一次 Acquisition。
- Answer Model 返回 `INSUFFICIENT_EVIDENCE` 时，将该语义反馈同步回 Evidence Assessment，并按相同
  预算顺序路由到 Query Revision 或 Acquisition。
- Acquisition 后只重新检索和评估一次；成功、部分成功、失败或异常都消耗唯一 Round。
- arXiv 精确短语查询在调用前做有界压缩：优先保留独特方法名，否则最多保留 4 个内容词。
- 外部 Acquisition 默认关闭，CLI 或部署配置必须显式启用。
- Agent Result、SSE Trace 和前端展示 Query、候选、下载及索引计数。

## Consequences

冻结 Corpus 与动态资产的 provenance 和 Evaluation 边界保持清晰，新论文可以立即进入 Answer/Citation
链路。系统拥有严格停止条件，且 embedded Qdrant 只由一个共享 Dynamic Client 打开。

真实 `MemReranker` E2E 测试证明，结构性 Gate 会把不相关但数量充足的旧 Corpus Chunk 误判为
sufficient；Answer Model 的语义拒答现在可触发一次扩库，并在动态写入后完成 Answer/Citation。
Phase 6 仍必须用 In-corpus、Recoverable 和 Unrecoverable 三组 Open-world Cases 测量误触发和漏触发，
再决定是否增加检索置信度或独立 Semantic Gate；本 ADR 不预先用未经评估的阈值替代证据。
