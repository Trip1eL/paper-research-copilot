# Evaluation Assets

- `datasets/` contains versioned, human-reviewable JSONL evaluation cases.
- `baselines/` will contain reproducible retrieval and agent configurations.
- `results/` contains generated experiment artifacts and is ignored by Git.

当前 `datasets/retrieval_diagnostic_v1.jsonl` 包含 25 条 Retrieval 诊断问题，记录问题类型、
相关论文、相关页码和证据提示。它用于下一阶段建立 Recall@K Baseline，目前不包含模型输出、
检索结果或评分，因此不是完整的 Golden Dataset。

校验数据结构及论文 ID：

```powershell
conda run -n paper-research-copilot python scripts/validate_retrieval_diagnostics.py
```

运行 Dense Retrieval Baseline：

```powershell
conda run -n paper-research-copilot paper-rag evaluate-retriever `
  --version 1 --top-k 10 --baseline-id dense_v1
```

- `baselines/dense_v1.json`：机器可读的配置、总体指标和分组指标。
- `baselines/dense_v1.md`：可读报告、逐题 Top-1 和失败 Case。
- `results/dense_v1.jsonl`：逐题 Top-10 原始结果，被 Git 忽略。

`retrieval_diagnostic_v1` 中的问题都包含论文名，因此当前 Paper Recall 主要反映已知论文条件
下的定位能力。后续需要单独建立不含论文名的 Discovery 子集。

## retrieval_discovery_v2

`retrieval_discovery_v2.jsonl` 面向 `agent-seed-v2`，共 50 条不含目标论文名的问题：

- DS-001 至 DS-025：保留 v1 的问题和相关页，作为 Corpus 扩大前后的 paired anchors。
- DS-026 至 DS-040：15 条新增单论文 Hard Negative，覆盖新增 10 篇论文和细粒度方法事实。
- DS-041 至 DS-050：10 条新增跨论文对比题。
- 共 15 条 cross-paper、30 条 Hard Negative，并覆盖 v2 全部 20 篇论文。

校验命令：

```powershell
conda run -n paper-research-copilot python scripts/validate_retrieval_diagnostics.py `
  --dataset evals/datasets/retrieval_discovery_v2.jsonl `
  --corpus corpus/v2/corpus.json `
  --manifest corpus/v2/manifest.jsonl
```

校验包括 Schema、唯一 Case ID、论文 ID、页码范围和目标论文 Title Leakage。页码由
`scripts/search_corpus_pages.py` 基于当前 `PdfParser` 输出进行人工核对。

## retrieval_discovery_v3

`retrieval_discovery_v3.jsonl` 面向 40 篇 `agent-seed-v3`，共 100 条：

- DS-001 至 DS-050 原样保留 Discovery v2，作为扩容前后的 paired anchors。
- DS-051 至 DS-080 为新增单论文 challenge。
- DS-081 至 DS-100 为新增跨论文 challenge。
- 合计 35 条 cross-paper、80 条 Hard Negative，并覆盖 v3 全部 40 篇论文。

```powershell
conda run -n paper-research-copilot python scripts/validate_retrieval_diagnostics.py `
  --dataset evals/datasets/retrieval_discovery_v3.jsonl `
  --corpus corpus/v3/corpus.json `
  --manifest corpus/v3/manifest.jsonl
```

v3 独立 Collection 为 `agent_seed_v3_bge_m3_chunking_v1`，包含 2,152 个 1024 维
`BAAI/bge-m3` 向量。Dense、BM25、Hybrid RRF 的 100 Case 结果分别位于
`baselines/dense_discovery_v3.*`、`baselines/bm25_discovery_v3.*` 和
`baselines/hybrid_rrf_discovery_v3.*`。统一分组及扩库漂移报告：

```powershell
conda run -n paper-research-copilot python scripts/build_retrieval_v3_comparison.py
```

总体 Paper Recall@10 为 `92.00% / 67.92% / 92.17%`，Exact Page Recall@10 为
`83.92% / 65.67% / 86.92%`。Hybrid 在新增单论文题上表现稳定，但新增跨论文题的 Complete
Papers@10 只有 `50%`，不能替代 Agent Runtime 的 Coverage-aware Retrieval。

## answer_generation_v1

`answer_generation_v1.jsonl` 用于端到端 Answer + Citation Evaluation：

- 18 条可回答问题，包括 15 条单论文和 3 条跨论文问题。
- 2 条 Corpus 外问题，用于验证结构化拒答。
- 可回答 Case 包含 reference answer、目标论文/页码和 Key Point aliases。
- Key Point aliases 只用于确定性词面覆盖，不能替代语义 Judge。

`answer_generation_v2.jsonl` 为 Corpus v3 的版本化扩展，共 32 条：31 条可回答、1 条拒答、
7 条 cross-paper。前 19 条保持 v1 契约；`AE-020` 因 tau-bench 已进入 v3 而改为可回答，
`AE-019` 仍然拒答，因为语料没有 GPT-5.5 在 SWE-bench Verified 上的结果。AE-021 至
AE-032 覆盖新增的 Reflection/Safety、Web/Computer Agent、Software Engineering 和
Agentic RAG 论文。历史 `answer_generation_v1` 不修改，旧基线仍可复现。

运行低延迟与 Reranker 对照：

```powershell
paper-rag evaluate-answer --strategy hybrid_rrf `
  --baseline-id answer_hybrid_rrf_v1

paper-rag evaluate-answer --strategy hybrid_rrf_rerank `
  --baseline-id answer_hybrid_rrf_rerank_v1
```

报告位于 `baselines/answer_evaluation_v1_comparison.md`。Raw Answer、Evidence、Citation、错误
和分阶段延迟保存于 ignored 的 `results/answer_*.jsonl`。

## gpt-5.5 Answer Judge v1

Judge 复用保存的 Answer Result，不重新生成答案：

```powershell
paper-rag evaluate-judge `
  --baseline-id answer_hybrid_rrf_gpt55_judge_v1

paper-rag evaluate-judge `
  --answer-baseline .\evals\baselines\answer_hybrid_rrf_rerank_v1.json `
  --answer-results .\evals\results\answer_hybrid_rrf_rerank_v1.jsonl `
  --baseline-id answer_hybrid_rrf_rerank_gpt55_judge_v1
```

`--case-id AE-001` 可用于单题 Smoke；重复参数可选择多题。缓存位于 `judges/`，只有输入哈希、
Judge model 与 prompt version 全部一致时才命中。Baseline JSON/Markdown 位于 `baselines/`，
逐题 Judge Result 位于 ignored 的 `results/`。完整结果见
`baselines/answer_judge_v1_comparison.md`。

## Answer Stability v1

固定两个 Answer Baseline 已保存的 Top-10 Evidence，对代表性 Case 重复生成 3 次：

```powershell
conda run --no-capture-output -n paper-research-copilot `
  python -u scripts/run_answer_stability.py --repetitions 3
```

默认 Case 为 `AE-001/007/014/016/017/018/019/020`；可重复传入 `--case-id` 覆盖。Answer
缓存位于 ignored 的 `stability/`，Judge 使用独立 repetition cache，支持中断续跑。正式结果
位于 `baselines/answer_stability_v1.json|md`，证据审计位于
`baselines/answer_low_score_audit_v1.md`。

## Generation Observability v2

三条跨论文题的定向实验记录 `finish_reason`、截断、重试和恢复率：

```powershell
conda run --no-capture-output -n paper-research-copilot `
  python -u scripts/run_answer_stability.py `
  --case-id AE-016 --case-id AE-017 --case-id AE-018 `
  --baseline-id answer_generation_observability_v2 `
  --judge-cache-tag generation_v2b
```

报告位于 `baselines/answer_generation_observability_v2.json|md`。当前 Provider 可能返回
`finish_reason=length + empty content`，评测按截断记录，并统计 retry trigger/recovery。

## Coverage-aware Retrieval v1

运行四组跨论文 Coverage 消融：

```powershell
conda run --no-capture-output -n paper-research-copilot `
  python -u scripts/run_coverage_ablation.py
```

脚本先生成并缓存 2 条子查询，再用 Corpus v2 标题与 slug 做泄漏审计；通过后比较 Hybrid、
Global Reranker、Coverage Merge、Coverage + per-subquery Reranker。三条 Case 每组生成 3 次，
并运行同一 `gpt-5.5` Judge。产物：

- `query_decompositions/answer_cross_paper_v1_deepseek-v4-flash.jsonl`：精确分解与耗时。
- `baselines/coverage_aware_ablation_v1.json|md`：Retrieval + Answer/Judge 汇总。
- `diagnostics/coverage_aware_retrieval_v1.json`：逐题目标论文、Evidence、配额与分阶段延迟。
- `results/coverage_aware_ablation_v1.jsonl`：36 个逐次 Answer/Judge 样本。
- `stability/` 与 `judges/coverage_v1_*`：可续跑缓存。

当前三题中，Coverage 两组的 Complete Papers@10 均为 100%；不加 Reranker 的方案质量不低
且约快 1.5 秒，因此被选为后续 cross-paper Retrieval 候选。

## Agent Runtime Evaluation v1

运行 Agent-vs-Fixed-RAG 对照：

```powershell
conda run --no-capture-output -n paper-research-copilot `
  python -u scripts/run_agent_evaluation.py
```

数据集为 `datasets/agent_runtime_v1.jsonl`。Fixed Hybrid、Fixed + Reranker 和 Oracle 复用冻结
Stability/Coverage 样本；LangGraph Agent 逐 Case 缓存到 ignored 的 `data/agent/`，Judge 缓存到
`judges/`，中断后可继续。正式结果位于 `baselines/agent_runtime_v1.json|md`，逐题 Plan、
Evidence、Answer、Judge、路由指标和分阶段成本位于 `diagnostics/agent_runtime_v1.json`。

默认 `--repetition 1` 用于单次架构对照。历史冻结 Answer Token 不完整时报告为 unknown/0 known
tokens，不进行反推；模型调用数仍按原始执行所需调用统计。

`agent_runtime_v2.jsonl` 为 Corpus v3 准备了 12 条 Agent Golden Cases，其中 7 条
cross-paper、11 条可回答、1 条拒答，并与 `answer_generation_v2.jsonl` 的 question、
answerable 和 relevant pages 严格一致。v2 模式显式读取已保存 Answer/Judge v2 作为 Fixed
Hybrid 对照，不能复用 v1 Stability/Coverage 样本：

```powershell
conda run --no-capture-output -n paper-research-copilot python -u `
  scripts/run_agent_evaluation.py `
  --dataset evals/datasets/agent_runtime_v2.jsonl `
  --answer-dataset evals/datasets/answer_generation_v2.jsonl `
  --all-cases --version 3 `
  --collection agent_seed_v3_bge_m3_chunking_v1 `
  --baseline-id agent_runtime_v2 `
  --agent-cache data/agent/runtime_evaluation_v2.jsonl `
  --saved-answer-results evals/results/answer_hybrid_rrf_v2.jsonl `
  --saved-judge-results evals/results/answer_hybrid_rrf_gpt55_judge_v2.jsonl `
  --judge-cache-tag agent_runtime_v2
```

Agent 相比 Fixed Hybrid 将跨论文 Complete Papers@10 从 `40%` 提升到 `80%`，Strict Run
从 `66.67%` 提升到 `91.67%`，代价是 Workflow P50 从 `7.1 s` 增至 `18.7 s`。脚本会逐题
缓存成功结果；Runtime 异常也会记录为 error 并计 0 分，不再让单条失败中断整批实验。

## Planner Model Ablation v1

只运行 Planner 模型消融，不重复 Retrieval、Answer 或 Judge：

```powershell
conda run --no-capture-output -n paper-research-copilot `
  python -u scripts/run_planner_ablation.py
```

脚本使用 `agent_runtime_v1.jsonl` 的 Router、Task Count 和 Facet 金标，比较 `gpt-5.5` 与
`deepseek-v4-flash` 的结构成功率、质量、泄漏、attempts、Token 和原始 generation latency。
Plan 缓存位于 ignored 的 `data/agent/`。正式报告位于
`baselines/planner_model_ablation_v1.json|md`，逐题 Plan 位于
`diagnostics/planner_model_ablation_v1.json`。

## Planner/Router Dataset v2

40 条扩展路由数据位于 `datasets/planner_routing_v2.jsonl`。校验命令：

```powershell
conda run -n paper-research-copilot `
  python scripts/validate_planner_routing_dataset.py
```

校验包括 Case/Question 唯一性、Pydantic 路由契约、Facet、源 Case 存在性及源问题逐字一致性。
数据包含 Strict 与 Acceptable 两套路由/任务标签。运行真实 v2 消融：

```powershell
conda run --no-capture-output -n paper-research-copilot `
  python -u scripts/run_planner_ablation_v2.py
```

正式报告位于 `baselines/planner_model_ablation_v2.json|md`，逐题 Plan 位于
`diagnostics/planner_model_ablation_v2.json`。Runner 使用独立模型缓存并逐题持久化，可中断恢复。
当前 GPT 和 DeepSeek 均未通过全量 Gate：GPT 在 `PR-016` 过度拆分，DeepSeek 在 `PR-032`
遗漏一个验证 Facet。生产 Planner 继续使用 `gpt-5.5`。

## Planner Prompt Ablation v2

运行 corpus verification 定向 Prompt 与稳定性实验：

```powershell
conda run --no-capture-output -n paper-research-copilot `
  python -u scripts/run_planner_prompt_ablation.py
```

脚本执行 DeepSeek Prompt v2 的 40 条全集评估，并对 10 条高风险样本做 3 次独立缓存重复。
生产切换同时检查质量、稳定性、Retry 和相对 GPT 的 P95。产物：

- `baselines/planner_prompt_ablation_v2.json|md`：v1/v2 对照与最终生产评审。
- `baselines/planner_prompt_ablation_v2_full.json|md`：40 条全集指标。
- `baselines/planner_prompt_ablation_v2_stability.json|md`：三次定向重复。
- `diagnostics/planner_prompt_ablation_v2_full.json`：全集逐题 Plan。
- `diagnostics/planner_prompt_ablation_v2_stability.json`：30 条重复样本 Plan。

当前 Production switch review 为 False：Prompt v2 补齐 Coverage，但 Core Task Count、Retry 和
P95 回退，三次定向重复只有一次通过全部 Gate。

## Planner Retry Diagnostics v1

使用全新缓存定向复跑历史长尾 Case，并记录 attempt 级根因：

```powershell
conda run --no-capture-output -n paper-research-copilot `
  python -u scripts/run_planner_retry_diagnostics.py
```

正式产物：

- `baselines/planner_retry_diagnostics_v1.json|md`：Outcome、Retry、Recovery 和延迟汇总。
- `diagnostics/planner_retry_diagnostics_v1.json`：脱敏逐 attempt 记录，只含响应 SHA256。
- `data/agent/planner_retry_diagnostics_v1_raw.jsonl`：包含原始响应的本地 ignored Trace。

9 个 Plan 最终全部成功，Retry Rate 为 33.33%。4 个失败 attempts 全部为截断，Output Token
均达到上限 1800；没有观察到 JSON、Schema、Task Shape、Leakage 或 Provider Error。

## Planner Truncation Recovery Ablation v1

运行三组截断恢复策略的交错对照：

```powershell
conda run --no-capture-output -n paper-research-copilot `
  python -u scripts/run_planner_truncation_ablation.py
```

三组分别为 `same_1800`、仅在截断后追加紧凑 JSON 指令的 `compact_1800`，以及
`same_2400`。默认使用 `PR-030/033/039`，每题每组独立重复 3 次。正式产物：

- `baselines/planner_truncation_recovery_v1.json|md`：质量、Retry、Recovery、延迟和 Token 汇总。
- `diagnostics/planner_truncation_recovery_v1.json`：脱敏 attempt trace、结构化 Plan 与逐次评分。
- `data/agent/planner_truncation_recovery_v1_raw.jsonl`：包含原始响应的本地 ignored Trace。

结果中只有 `same_2400` 达到 9/9 Success 并通过质量 Gate；`same_1800` 与 `compact_1800` 各有
一次终态截断失败。不过 `same_2400` 仍有 44.44% Retry Rate 和 68.8 秒 P95，因此它只是当前
DeepSeek Prompt v2 的可靠性候选，不会自动修改生产 Planner 或全局 Token 配置。

`compact_2400` 的停止实验使用显式策略参数，避免重跑其他组：

```powershell
conda run --no-capture-output -n paper-research-copilot `
  python -u scripts/run_planner_truncation_ablation.py `
  --baseline-id planner_compact_2400_ablation_v1 `
  --strategy same_2400 --strategy compact_2400
```

结果位于 `baselines/planner_compact_2400_ablation_v1.json|md` 和
`diagnostics/planner_compact_2400_ablation_v1.json`。Compact 组发生终态截断失败，P95 73.1 秒，
没有通过质量 Gate；项目停止继续做同类 Prompt/Token 微调。
