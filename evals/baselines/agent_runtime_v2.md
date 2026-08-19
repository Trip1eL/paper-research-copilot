# Agent Runtime Evaluation：agent_runtime_v2

- Cases：12
- Collection：`agent_seed_v3_bge_m3_chunking_v1`
- Planner / Answer / Judge：`gpt-5.5` / `deepseek-v4-flash` / `gpt-5.5`
- 固定对照使用已保存样本；LangGraph Agent 使用同一 Answer/Judge 口径。

## 总体对照

| Variant | Paper Recall@10 | Exact Page Recall@10 | Complete Papers@10 All/Cross | Answerability | Correctness | Faithfulness | Citation Completeness | Strict Run | Workflow P50/P95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed_hybrid_rrf | 86.36% | 77.27% | 72.73% / 40.00% | 75.00% | 68.75% | 66.67% | 68.75% | 66.67% | 7144 / 25168 ms |
| langgraph_agent | 95.45% | 90.91% | 90.91% / 80.00% | 100.00% | 93.75% | 89.58% | 95.83% | 91.67% | 18663 / 32893 ms |

## Agent 决策质量

| Variant | Router | Task Count | Task Coverage | Title Leakage | Strategy | Unnecessary Revision | Citation Validation | Planning P50/P95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| langgraph_agent | 91.67% | 91.67% | 95.83% | 0.00% | 91.67% | 0.00% | 100.00% | 10675 / 12569 ms |

## 逐题结果

| Variant | Case | Route | Tasks | Retry | Papers | Answer | Judge C/F/CC | Strict |
| --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |
| fixed_hybrid_rrf | AE-001 | fixed | - | - | 100% | answered | 4/4/4 | True |
| fixed_hybrid_rrf | AE-007 | fixed | - | - | 100% | answered | 4/4/4 | True |
| fixed_hybrid_rrf | AE-016 | fixed | - | - | 50% | answered | 2/2/2 | False |
| fixed_hybrid_rrf | AE-017 | fixed | - | - | 100% | insufficient_evidence | 0/0/0 | False |
| fixed_hybrid_rrf | AE-019 | fixed | - | - | N/A | insufficient_evidence | 4/4/4 | True |
| fixed_hybrid_rrf | AE-020 | fixed | - | - | 100% | answered | 4/4/4 | True |
| fixed_hybrid_rrf | AE-021 | fixed | - | - | 100% | answered | 4/3/3 | True |
| fixed_hybrid_rrf | AE-023 | fixed | - | - | 100% | answered | 4/4/4 | True |
| fixed_hybrid_rrf | AE-025 | fixed | - | - | 100% | answered | 3/4/4 | True |
| fixed_hybrid_rrf | AE-029 | fixed | - | - | 100% | answered | 4/3/4 | True |
| fixed_hybrid_rrf | AE-031 | fixed | - | - | 50% | insufficient_evidence | 0/0/0 | False |
| fixed_hybrid_rrf | AE-032 | fixed | - | - | 50% | insufficient_evidence | 0/0/0 | False |
| langgraph_agent | AE-001 | single_paper | 1 | 0 | 100% | answered | 4/4/4 | True |
| langgraph_agent | AE-007 | single_paper | 1 | 0 | 100% | answered | 4/4/4 | True |
| langgraph_agent | AE-016 | cross_paper | 2 | 0 | 100% | answered | 4/3/3 | True |
| langgraph_agent | AE-017 | cross_paper | 2 | 0 | 100% | answered | 4/4/4 | True |
| langgraph_agent | AE-019 | cross_paper | 2 | 0 | N/A | insufficient_evidence | 4/4/4 | True |
| langgraph_agent | AE-020 | cross_paper | 2 | 0 | 100% | answered | 4/4/4 | True |
| langgraph_agent | AE-021 | single_paper | 1 | 0 | 100% | answered | 4/3/3 | True |
| langgraph_agent | AE-023 | single_paper | 1 | 0 | 100% | answered | 4/4/4 | True |
| langgraph_agent | AE-025 | cross_paper | 2 | 0 | 100% | answered | 3/4/4 | True |
| langgraph_agent | AE-029 | cross_paper | 2 | 0 | 100% | answered | 4/3/4 | True |
| langgraph_agent | AE-031 | cross_paper | 2 | 0 | 100% | answered | 4/3/4 | True |
| langgraph_agent | AE-032 | cross_paper | 2 | 0 | 50% | answered | 2/3/4 | False |

## 成本与解释限制

| Variant | Model Calls | Known Planner Input/Output | Known Answer Input/Output | Judge Input/Output |
| --- | ---: | ---: | ---: | ---: |
| fixed_hybrid_rrf | 21 | 0 / 0 | 84872 / 11924 | 26215 / 8762 |
| langgraph_agent | 35 | 2473 / 3146 | 75131 / 9783 | 41327 / 12145 |

- Cache 命中仍使用缓存中记录的原始生成延迟，避免把缓存查找耗时当作线上冷启动延迟。
- 历史 Planner 缓存若创建于 Token tracing 之前，其 Token 记为 unknown，不做估算。
- `Revision Recovery` 只有数据集中存在 `should_retry=true` 的样本时才有定义。
- 单次架构对照用于发现差异；稳定性结论仍应使用多次重复实验。
