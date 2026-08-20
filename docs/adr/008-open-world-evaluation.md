# ADR 008: 隔离式 Open-world Evaluation

- Status: Accepted
- Date: 2026-08-20

## Context

Phase 5 已证明单个 Corpus 外问题可以触发搜索、下载、Parse、Embedding、Federated Retrieval 和
Citation，但单例演示无法说明触发是否准确。若多个 Case 共享 Dynamic Corpus，前一条下载结果会改变
后一条初始条件；若只看最终拒答，又会掩盖下载并索引无关论文的副作用。

## Decision

- Dataset 分为 In-corpus、Recoverable、Unrecoverable 和 Ambiguous 四类，分别定义 Acquisition 为
  forbidden、required 或 optional，并冻结 Answer Status 与目标论文身份。
- 每个 Case 使用独立且初始为空的 Dynamic Qdrant Collection、SQLite 和 PDF 目录；Curated Corpus v3
  保持冻结并共享。
- Run Cache 绑定 Dataset SHA、Case、Corpus、模型、Embedding 和 Retry 配置。只有指纹完全一致时才
  复用；发现没有 Cache 的脏动态状态时拒绝运行。
- Recoverable Strict Pass 要求：一次有界扩库、目标 Dynamic Evidence、目标 Citation、Parser
  provenance、正确 Answer Status 和 Citation Validation 全部通过。
- Unrecoverable Strict Pass 不只要求拒答，还要求 Point Delta 为 0，防止无关论文污染动态知识库。
- Ambiguous Case 当前要求不扩库并拒答，用于量化尚未实现的 Clarification/Input Gate。
- 同时保存生产策略 Smoke 与 `max_retries=0` Acquisition 消融，避免把 Revision Planner 失败错误归因
  给 Academic Search 或 Dynamic Ingestion。

## Consequences

Baseline 可以复现每类行为和副作用，失败能够定位到 Planner、Search、Ingestion、Retrieval 或 Answer。
代价是 Recoverable Case 必须重复真实下载和 Embedding，P95 显著高于普通问答；因此成功结果使用严格
指纹缓存，不为追求稳定分数反复调用模型。

首轮 16-Case 消融显示 In-corpus 5/5 通过、Recoverable 4/5 通过、Unrecoverable 2/3 Strict Pass、
Ambiguous 0/3 Strict Pass。下一步优先实现 Acquisition 前的 Ambiguity Gate 和 Candidate Relevance
Validation，再评估是否需要修改 arXiv Search Query 结构；不在本阶段直接调相似度阈值。
