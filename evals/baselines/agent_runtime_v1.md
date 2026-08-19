# Agent Runtime Evaluation：agent_runtime_v1

- Cases：8
- Collection：`agent_seed_v2_bge_m3_chunking_v1`
- Planner / Answer / Judge：`gpt-5.5` / `deepseek-v4-flash` / `gpt-5.5`
- Fixed 与 Oracle 使用冻结样本；LangGraph Agent 使用同一 Answer/Judge 口径。

## 总体对照

| Variant | Paper Recall@10 | Exact Page Recall@10 | Complete Papers@10 All/Cross | Answerability | Correctness | Faithfulness | Citation Completeness | Strict Run | Workflow P50/P95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed_hybrid_rrf | 75.00% | 75.00% | 50.00% / 0.00% | 75.00% | 71.88% | 68.75% | 71.88% | 75.00% | 3374 / 24522 ms |
| fixed_hybrid_rerank | 91.67% | 91.67% | 83.33% / 66.67% | 87.50% | 87.50% | 78.12% | 81.25% | 87.50% | 3057 / 22892 ms |
| oracle_route | 100.00% | 100.00% | 100.00% / 100.00% | 100.00% | 96.88% | 96.88% | 100.00% | 100.00% | 3374 / 17079 ms |
| langgraph_agent | 100.00% | 91.67% | 100.00% / 100.00% | 100.00% | 100.00% | 96.88% | 96.88% | 100.00% | 18075 / 58527 ms |

## Agent 决策质量

| Variant | Router | Task Count | Task Coverage | Title Leakage | Strategy | Unnecessary Revision | Citation Validation | Planning P50/P95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| langgraph_agent | 100.00% | 100.00% | 100.00% | 0.00% | 100.00% | 0.00% | 100.00% | 10719 / 14723 ms |

## 逐题结果

| Variant | Case | Route | Tasks | Retry | Papers | Answer | Judge C/F/CC | Strict |
| --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |
| fixed_hybrid_rrf | AE-001 | fixed | - | - | 100% | answered | 3/3/4 | True |
| fixed_hybrid_rrf | AE-007 | fixed | - | - | 100% | answered | 4/4/4 | True |
| fixed_hybrid_rrf | AE-014 | fixed | - | - | 100% | answered | 4/4/4 | True |
| fixed_hybrid_rrf | AE-016 | fixed | - | - | 50% | answered | 4/3/3 | True |
| fixed_hybrid_rrf | AE-017 | fixed | - | - | 50% | error | 0/0/0 | False |
| fixed_hybrid_rrf | AE-018 | fixed | - | - | 50% | insufficient_evidence | 0/0/0 | False |
| fixed_hybrid_rrf | AE-019 | fixed | - | - | N/A | insufficient_evidence | 4/4/4 | True |
| fixed_hybrid_rrf | AE-020 | fixed | - | - | N/A | insufficient_evidence | 4/4/4 | True |
| fixed_hybrid_rerank | AE-001 | fixed | - | - | 100% | answered | 4/3/4 | True |
| fixed_hybrid_rerank | AE-007 | fixed | - | - | 100% | answered | 4/4/4 | True |
| fixed_hybrid_rerank | AE-014 | fixed | - | - | 100% | answered | 4/4/4 | True |
| fixed_hybrid_rerank | AE-016 | fixed | - | - | 50% | answered | 4/3/3 | True |
| fixed_hybrid_rerank | AE-017 | fixed | - | - | 100% | error | 0/0/0 | False |
| fixed_hybrid_rerank | AE-018 | fixed | - | - | 100% | answered | 4/3/3 | True |
| fixed_hybrid_rerank | AE-019 | fixed | - | - | N/A | insufficient_evidence | 4/4/4 | True |
| fixed_hybrid_rerank | AE-020 | fixed | - | - | N/A | insufficient_evidence | 4/4/4 | True |
| oracle_route | AE-001 | fixed | - | - | 100% | answered | 3/3/4 | True |
| oracle_route | AE-007 | fixed | - | - | 100% | answered | 4/4/4 | True |
| oracle_route | AE-014 | fixed | - | - | 100% | answered | 4/4/4 | True |
| oracle_route | AE-016 | fixed | - | - | 100% | answered | 4/4/4 | True |
| oracle_route | AE-017 | fixed | - | - | 100% | answered | 4/4/4 | True |
| oracle_route | AE-018 | fixed | - | - | 100% | answered | 4/4/4 | True |
| oracle_route | AE-019 | fixed | - | - | N/A | insufficient_evidence | 4/4/4 | True |
| oracle_route | AE-020 | fixed | - | - | N/A | insufficient_evidence | 4/4/4 | True |
| langgraph_agent | AE-001 | single_paper | 1 | 0 | 100% | answered | 4/4/4 | True |
| langgraph_agent | AE-007 | single_paper | 1 | 0 | 100% | answered | 4/4/4 | True |
| langgraph_agent | AE-014 | single_paper | 1 | 0 | 100% | answered | 4/4/4 | True |
| langgraph_agent | AE-016 | cross_paper | 2 | 0 | 100% | answered | 4/3/3 | True |
| langgraph_agent | AE-017 | cross_paper | 2 | 0 | 100% | answered | 4/4/4 | True |
| langgraph_agent | AE-018 | cross_paper | 2 | 0 | 100% | answered | 4/4/4 | True |
| langgraph_agent | AE-019 | cross_paper | 2 | 0 | N/A | insufficient_evidence | 4/4/4 | True |
| langgraph_agent | AE-020 | cross_paper | 2 | 0 | N/A | insufficient_evidence | 4/4/4 | True |

## 成本与解释限制

| Variant | Model Calls | Known Planner Input/Output | Known Answer Input/Output | Judge Input/Output |
| --- | ---: | ---: | ---: | ---: |
| fixed_hybrid_rrf | 12 | 0 / 0 | 0 / 0 | 12092 / 3523 |
| fixed_hybrid_rerank | 13 | 0 / 0 | 0 / 0 | 20183 / 5635 |
| oracle_route | 14 | 0 / 0 | 19257 / 4518 | 24065 / 6205 |
| langgraph_agent | 23 | 1475 / 1995 | 57550 / 7846 | 22852 / 6568 |

- Cache 命中仍使用缓存中记录的原始生成延迟，避免把缓存查找耗时当作线上冷启动延迟。
- 历史 Planner 缓存若创建于 Token tracing 之前，其 Token 记为 unknown，不做估算。
- `Revision Recovery` 只有数据集中存在 `should_retry=true` 的样本时才有定义。
- 单次 v1 对照用于发现架构差异；稳定性结论仍应使用多次重复实验。
