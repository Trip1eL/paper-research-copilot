# Planner Model Ablation v2：planner_model_ablation_v2

- Dataset：`evals/datasets/planner_routing_v2.jsonl`（40 Cases）
- Label-sensitive：3 Cases
- Prompt：`research_planner_v1`
- Quality Gate：success=100%; core_router=100%; core_task_count=100%; task_coverage=100%; acceptable_router=100%; acceptable_task_count=100%; title_leakage=0%

## 总体指标

| Model | Success | Strict Route/Task | Acceptable Route/Task | Coverage | Core Route/Task/Coverage | Boundary Strict/Acceptable/Coverage | Leakage | Retry | P50/P95 | Gate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| gpt-5.5 | 100.00% | 95.00% / 95.00% | 97.50% / 97.50% | 100.00% | 97.30% / 97.30% / 100.00% | 66.67% / 100.00% / 100.00% | 0.00% | 0.00% | 10675 / 13595 ms | False |
| deepseek-v4-flash | 100.00% | 95.00% / 95.00% | 100.00% / 100.00% | 98.75% | 100.00% / 100.00% / 100.00% | 33.33% / 100.00% / 83.33% | 0.00% | 5.00% | 4961 / 10754 ms | False |

## 分类指标

### gpt-5.5

| Category | Cases | Strict Route | Acceptable Route | Strict Task | Acceptable Task | Coverage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| single_lookup | 16 | 93.75% | 93.75% | 93.75% | 93.75% | 100.00% |
| cross_comparison | 13 | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| multi_method_synthesis | 2 | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| corpus_verification | 5 | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| routing_boundary | 4 | 75.00% | 100.00% | 75.00% | 100.00% | 100.00% |

### deepseek-v4-flash

| Category | Cases | Strict Route | Acceptable Route | Strict Task | Acceptable Task | Coverage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| single_lookup | 16 | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| cross_comparison | 13 | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| multi_method_synthesis | 2 | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| corpus_verification | 5 | 60.00% | 100.00% | 60.00% | 100.00% | 90.00% |
| routing_boundary | 4 | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |

## 调用成本与延迟

| Model | Calls | Input Tokens | Output Tokens | P50 | P95 | Retry |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| gpt-5.5 | 40 | 9361 | 10876 | 10675 ms | 13595 ms | 0.00% |
| deepseek-v4-flash | 42 | 12657 | 17471 | 4961 ms | 10754 ms | 5.00% |

## 失败审计

| Model | Failed | Strict Route Errors | Unacceptable Routes | Core Task Errors | Low Coverage | Leakage |
| --- | --- | --- | --- | --- | --- | --- |
| gpt-5.5 | 无 | PR-016, PR-039 | PR-016 | PR-016 | 无 | 无 |
| deepseek-v4-flash | 无 | PR-032, PR-035 | 无 | 无 | PR-032 | 无 |

## 逐题结果

| Model | Case | Category | Route S/A | Tasks S/A | Facets | Attempts | Latency |
| --- | --- | --- | --- | --- | ---: | ---: | ---: |
| gpt-5.5 | PR-001 | single_lookup | True/True | True/True | 100% | 1 | 9149 ms |
| gpt-5.5 | PR-002 | single_lookup | True/True | True/True | 100% | 1 | 14333 ms |
| gpt-5.5 | PR-003 | single_lookup | True/True | True/True | 100% | 1 | 11236 ms |
| gpt-5.5 | PR-004 | single_lookup | True/True | True/True | 100% | 1 | 8459 ms |
| gpt-5.5 | PR-005 | single_lookup | True/True | True/True | 100% | 1 | 10675 ms |
| gpt-5.5 | PR-006 | single_lookup | True/True | True/True | 100% | 1 | 7548 ms |
| gpt-5.5 | PR-007 | single_lookup | True/True | True/True | 100% | 1 | 10196 ms |
| gpt-5.5 | PR-008 | single_lookup | True/True | True/True | 100% | 1 | 9164 ms |
| gpt-5.5 | PR-009 | single_lookup | True/True | True/True | 100% | 1 | 9067 ms |
| gpt-5.5 | PR-010 | single_lookup | True/True | True/True | 100% | 1 | 8787 ms |
| gpt-5.5 | PR-011 | single_lookup | True/True | True/True | 100% | 1 | 9554 ms |
| gpt-5.5 | PR-012 | single_lookup | True/True | True/True | 100% | 1 | 9114 ms |
| gpt-5.5 | PR-013 | single_lookup | True/True | True/True | 100% | 1 | 8559 ms |
| gpt-5.5 | PR-014 | single_lookup | True/True | True/True | 100% | 1 | 9568 ms |
| gpt-5.5 | PR-015 | single_lookup | True/True | True/True | 100% | 1 | 9149 ms |
| gpt-5.5 | PR-016 | single_lookup | False/False | False/False | 100% | 1 | 13225 ms |
| gpt-5.5 | PR-017 | cross_comparison | True/True | True/True | 100% | 1 | 10719 ms |
| gpt-5.5 | PR-018 | cross_comparison | True/True | True/True | 100% | 1 | 12455 ms |
| gpt-5.5 | PR-019 | cross_comparison | True/True | True/True | 100% | 1 | 9422 ms |
| gpt-5.5 | PR-020 | cross_comparison | True/True | True/True | 100% | 1 | 9415 ms |
| gpt-5.5 | PR-021 | cross_comparison | True/True | True/True | 100% | 1 | 10325 ms |
| gpt-5.5 | PR-022 | cross_comparison | True/True | True/True | 100% | 1 | 9570 ms |
| gpt-5.5 | PR-023 | cross_comparison | True/True | True/True | 100% | 1 | 13595 ms |
| gpt-5.5 | PR-024 | cross_comparison | True/True | True/True | 100% | 1 | 10071 ms |
| gpt-5.5 | PR-025 | cross_comparison | True/True | True/True | 100% | 1 | 11007 ms |
| gpt-5.5 | PR-026 | cross_comparison | True/True | True/True | 100% | 1 | 10737 ms |
| gpt-5.5 | PR-027 | cross_comparison | True/True | True/True | 100% | 1 | 11152 ms |
| gpt-5.5 | PR-028 | cross_comparison | True/True | True/True | 100% | 1 | 11705 ms |
| gpt-5.5 | PR-029 | cross_comparison | True/True | True/True | 100% | 1 | 10631 ms |
| gpt-5.5 | PR-030 | multi_method_synthesis | True/True | True/True | 100% | 1 | 11532 ms |
| gpt-5.5 | PR-031 | multi_method_synthesis | True/True | True/True | 100% | 1 | 11243 ms |
| gpt-5.5 | PR-032 | corpus_verification | True/True | True/True | 100% | 1 | 14723 ms |
| gpt-5.5 | PR-033 | corpus_verification | True/True | True/True | 100% | 1 | 12394 ms |
| gpt-5.5 | PR-034 | corpus_verification | True/True | True/True | 100% | 1 | 12746 ms |
| gpt-5.5 | PR-035 | corpus_verification | True/True | True/True | 100% | 1 | 11627 ms |
| gpt-5.5 | PR-036 | corpus_verification | True/True | True/True | 100% | 1 | 11463 ms |
| gpt-5.5 | PR-037 | routing_boundary | True/True | True/True | 100% | 1 | 8591 ms |
| gpt-5.5 | PR-038 | routing_boundary | True/True | True/True | 100% | 1 | 12219 ms |
| gpt-5.5 | PR-039 | routing_boundary | False/True | False/True | 100% | 1 | 11813 ms |
| gpt-5.5 | PR-040 | routing_boundary | True/True | True/True | 100% | 1 | 9812 ms |
| deepseek-v4-flash | PR-001 | single_lookup | True/True | True/True | 100% | 1 | 3756 ms |
| deepseek-v4-flash | PR-002 | single_lookup | True/True | True/True | 100% | 1 | 10754 ms |
| deepseek-v4-flash | PR-003 | single_lookup | True/True | True/True | 100% | 1 | 4010 ms |
| deepseek-v4-flash | PR-004 | single_lookup | True/True | True/True | 100% | 1 | 4122 ms |
| deepseek-v4-flash | PR-005 | single_lookup | True/True | True/True | 100% | 1 | 3978 ms |
| deepseek-v4-flash | PR-006 | single_lookup | True/True | True/True | 100% | 1 | 4692 ms |
| deepseek-v4-flash | PR-007 | single_lookup | True/True | True/True | 100% | 1 | 4329 ms |
| deepseek-v4-flash | PR-008 | single_lookup | True/True | True/True | 100% | 1 | 5991 ms |
| deepseek-v4-flash | PR-009 | single_lookup | True/True | True/True | 100% | 1 | 4094 ms |
| deepseek-v4-flash | PR-010 | single_lookup | True/True | True/True | 100% | 1 | 7154 ms |
| deepseek-v4-flash | PR-011 | single_lookup | True/True | True/True | 100% | 1 | 6296 ms |
| deepseek-v4-flash | PR-012 | single_lookup | True/True | True/True | 100% | 1 | 5084 ms |
| deepseek-v4-flash | PR-013 | single_lookup | True/True | True/True | 100% | 1 | 3650 ms |
| deepseek-v4-flash | PR-014 | single_lookup | True/True | True/True | 100% | 1 | 4961 ms |
| deepseek-v4-flash | PR-015 | single_lookup | True/True | True/True | 100% | 1 | 2850 ms |
| deepseek-v4-flash | PR-016 | single_lookup | True/True | True/True | 100% | 1 | 8988 ms |
| deepseek-v4-flash | PR-017 | cross_comparison | True/True | True/True | 100% | 1 | 5715 ms |
| deepseek-v4-flash | PR-018 | cross_comparison | True/True | True/True | 100% | 1 | 3283 ms |
| deepseek-v4-flash | PR-019 | cross_comparison | True/True | True/True | 100% | 1 | 4160 ms |
| deepseek-v4-flash | PR-020 | cross_comparison | True/True | True/True | 100% | 1 | 2716 ms |
| deepseek-v4-flash | PR-021 | cross_comparison | True/True | True/True | 100% | 1 | 4252 ms |
| deepseek-v4-flash | PR-022 | cross_comparison | True/True | True/True | 100% | 1 | 3440 ms |
| deepseek-v4-flash | PR-023 | cross_comparison | True/True | True/True | 100% | 1 | 6254 ms |
| deepseek-v4-flash | PR-024 | cross_comparison | True/True | True/True | 100% | 1 | 2942 ms |
| deepseek-v4-flash | PR-025 | cross_comparison | True/True | True/True | 100% | 1 | 3648 ms |
| deepseek-v4-flash | PR-026 | cross_comparison | True/True | True/True | 100% | 1 | 4526 ms |
| deepseek-v4-flash | PR-027 | cross_comparison | True/True | True/True | 100% | 1 | 5277 ms |
| deepseek-v4-flash | PR-028 | cross_comparison | True/True | True/True | 100% | 1 | 3329 ms |
| deepseek-v4-flash | PR-029 | cross_comparison | True/True | True/True | 100% | 1 | 2879 ms |
| deepseek-v4-flash | PR-030 | multi_method_synthesis | True/True | True/True | 100% | 2 | 24107 ms |
| deepseek-v4-flash | PR-031 | multi_method_synthesis | True/True | True/True | 100% | 1 | 4524 ms |
| deepseek-v4-flash | PR-032 | corpus_verification | False/True | False/True | 50% | 2 | 23923 ms |
| deepseek-v4-flash | PR-033 | corpus_verification | True/True | True/True | 100% | 1 | 6246 ms |
| deepseek-v4-flash | PR-034 | corpus_verification | True/True | True/True | 100% | 1 | 6268 ms |
| deepseek-v4-flash | PR-035 | corpus_verification | False/True | False/True | 100% | 1 | 7247 ms |
| deepseek-v4-flash | PR-036 | corpus_verification | True/True | True/True | 100% | 1 | 6691 ms |
| deepseek-v4-flash | PR-037 | routing_boundary | True/True | True/True | 100% | 1 | 5471 ms |
| deepseek-v4-flash | PR-038 | routing_boundary | True/True | True/True | 100% | 1 | 6613 ms |
| deepseek-v4-flash | PR-039 | routing_boundary | True/True | True/True | 100% | 1 | 8480 ms |
| deepseek-v4-flash | PR-040 | routing_boundary | True/True | True/True | 100% | 1 | 5175 ms |

## 决策

- 推荐模型：`无`
- 原因：没有候选模型通过全部 v2 质量门槛，保留当前生产 Planner。
- 两组使用相同的 system/user Prompt、max_tokens、Pydantic Schema、重试策略和 Corpus alias 泄漏审计。
- Strict 指标遵循唯一金标；Acceptable 指标允许人工标注的合理替代；Core 指标排除 label-sensitive Cases。
- Route 和 Task Count 可采用 Acceptable 标注，但所有 Case 的证据 Facet Coverage 仍须为 100%。
- 缓存命中时读取原始 generation latency；Provider 负载随时间变化，延迟仅用于方向性对比。
