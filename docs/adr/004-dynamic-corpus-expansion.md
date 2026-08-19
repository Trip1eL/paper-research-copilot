# ADR 004: Bounded Dynamic Corpus Expansion

- Status: Phase 4 foundation implemented; Agent integration pending Phase 5
- Date: 2026-08-19

## Context

Corpus v3 能提供可复现的 Agent 论文研究 Baseline，但不能覆盖用户提出的所有论文和新方向。直接
将运行时下载的论文写入 v3 会破坏 Dataset/Corpus 对应关系、历史结果和实验复现。

## Decision

- v2.0 只接入 arXiv Search API，其他学术来源使用同一 Provider Protocol 后续扩展。
- 只有 Deterministic Evidence Gate 判定不足且预算允许时，才触发一次 Acquisition Round。
- 每个任务最多执行 2 个 Search Query、选择 5 个候选、下载 2 篇论文。
- PDF 下载执行域名、HTTPS、文件头、Content-Type、大小、revision 和 SHA-256 校验。
- DOI/arXiv ID/revision/SHA-256 共同保证幂等与去重。
- 所有动态论文必须经过 Parser Quality Gate；失败资产进入 quarantine。
- 动态 Chunk 写入独立 Collection `paper_dynamic_bge_m3_chunking_v1`。
- Curated 与 Dynamic 分别检索，通过 Federated RRF 合并，不修改冻结的 v3 Collection。
- 成功动态写入后显式失效并重建 Dynamic BM25 snapshot。
- Paper Registry 保存来源、下载、Parse、Embedding 与 Collection provenance。

## Rejected alternatives

- **修改 Corpus v3**：破坏可复现 Baseline。
- **开放互联网爬取**：来源、授权、SSRF 和内容质量边界过大。
- **一次接入多个论文 API**：会过早引入身份对齐、版本冲突和多源去重。
- **只检索摘要而不摄取 PDF**：无法形成页码 Citation，也不能验证正文 Claim。
- **无限 Search/Reflection Loop**：成本和终止条件不可控。

## Consequences

系统从固定知识库问答升级为受控的 open-world RAG，但模型权重没有变化，因此该能力称为动态扩库而
不是自学习。Evaluation 必须分别报告 In-corpus、Recoverable 和 Unrecoverable Cases，并记录每次
扩库成本与副作用。

## Phase 4 implementation

- `PaperCandidate` 保存 versioned arXiv identity、DOI、作者、摘要、时间、分类和来源 URL。
- `paper_assets` 与 `acquisition_runs` 由 Alembic 0002 加入 `data/app.db`。
- Downloader 对每一次 redirect 重做 HTTPS、host 和 arXiv identity 校验，流式限制 50 MiB，并在
  `%PDF-`、Content-Type 和 SHA-256 验证后原子提交文件。
- Dynamic Ingestion 强制经过 Fast Parser Quality Gate，任意 quarantined 页面都会阻止 Embedding。
- 幂等按 arXiv identity/revision、DOI、SHA-256、稳定 Chunk ID 和 Qdrant metadata 五层执行。
- 本地 embedded Qdrant 使用独立 `data/qdrant_dynamic`，避免两个 Client 锁定同一路径；远程
  Qdrant 仍使用独立 Collection `paper_dynamic_bge_m3_chunking_v1`。
- Phase 4 通过 CLI 显式运行。Evidence Gate 自动触发、Federated RRF 和 Dynamic BM25 generation
  属于 Phase 5，不在本阶段伪装为已完成。
