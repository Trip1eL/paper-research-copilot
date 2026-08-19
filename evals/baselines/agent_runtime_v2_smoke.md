# Agent Runtime Evaluation：agent_runtime_v2_smoke

- Cases：1
- Collection：`agent_seed_v3_bge_m3_chunking_v1`
- Planner / Answer / Judge：`gpt-5.5` / `deepseek-v4-flash` / `gpt-5.5`
- Fixed 与 Oracle 使用冻结样本；LangGraph Agent 使用同一 Answer/Judge 口径。

## 总体对照

| Variant | Paper Recall@10 | Exact Page Recall@10 | Complete Papers@10 All/Cross | Answerability | Correctness | Faithfulness | Citation Completeness | Strict Run | Workflow P50/P95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed_hybrid_rrf | 100.00% | 100.00% | 100.00% / 0.00% | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% | 3811 / 3811 ms |
| langgraph_agent | 100.00% | 100.00% | 100.00% / 0.00% | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% | 13708 / 13708 ms |

## Agent 决策质量

| Variant | Router | Task Count | Task Coverage | Title Leakage | Strategy | Unnecessary Revision | Citation Validation | Planning P50/P95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| langgraph_agent | 100.00% | 100.00% | 100.00% | 0.00% | 100.00% | 0.00% | 100.00% | 9149 / 9149 ms |

## 逐题结果

| Variant | Case | Route | Tasks | Retry | Papers | Answer | Judge C/F/CC | Strict |
| --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |
| fixed_hybrid_rrf | AE-001 | fixed | - | - | 100% | answered | 4/4/4 | True |
| langgraph_agent | AE-001 | single_paper | 1 | 0 | 100% | answered | 4/4/4 | True |

## 成本与解释限制

| Variant | Model Calls | Known Planner Input/Output | Known Answer Input/Output | Judge Input/Output |
| --- | ---: | ---: | ---: | ---: |
| fixed_hybrid_rrf | 2 | 0 / 0 | 6443 / 392 | 2907 / 781 |
| langgraph_agent | 3 | 234 / 250 | 6297 / 258 | 2106 / 1031 |

- Cache 命中仍使用缓存中记录的原始生成延迟，避免把缓存查找耗时当作线上冷启动延迟。
- 历史 Planner 缓存若创建于 Token tracing 之前，其 Token 记为 unknown，不做估算。
- `Revision Recovery` 只有数据集中存在 `should_retry=true` 的样本时才有定义。
- 单次 v1 对照用于发现架构差异；稳定性结论仍应使用多次重复实验。
