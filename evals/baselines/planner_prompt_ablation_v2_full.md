# Planner Model Ablation v2：planner_prompt_ablation_v2_full

- Dataset：`evals/datasets/planner_routing_v2.jsonl`（40 Cases）
- Label-sensitive：3 Cases
- Prompt：`research_planner_corpus_verification_v2`
- Quality Gate：success=100%; core_router=100%; core_task_count=100%; task_coverage=100%; acceptable_router=100%; acceptable_task_count=100%; title_leakage=0%

## 总体指标

| Model | Success | Strict Route/Task | Acceptable Route/Task | Coverage | Core Route/Task/Coverage | Boundary Strict/Acceptable/Coverage | Leakage | Retry | P50/P95 | Gate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| deepseek-v4-flash | 100.00% | 97.50% / 92.50% | 100.00% / 100.00% | 100.00% | 100.00% / 94.59% / 100.00% | 66.67% / 100.00% / 100.00% | 0.00% | 7.50% | 5040 / 25812 ms | False |

## 分类指标

### deepseek-v4-flash

| Category | Cases | Strict Route | Acceptable Route | Strict Task | Acceptable Task | Coverage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| single_lookup | 16 | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| cross_comparison | 13 | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| multi_method_synthesis | 2 | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| corpus_verification | 5 | 100.00% | 100.00% | 60.00% | 100.00% | 100.00% |
| routing_boundary | 4 | 75.00% | 100.00% | 75.00% | 100.00% | 100.00% |

## 调用成本与延迟

| Model | Calls | Input Tokens | Output Tokens | P50 | P95 | Retry |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| deepseek-v4-flash | 44 | 23257 | 22114 | 5040 ms | 25812 ms | 7.50% |

## 失败审计

| Model | Failed | Strict Route Errors | Unacceptable Routes | Core Task Errors | Low Coverage | Leakage |
| --- | --- | --- | --- | --- | --- | --- |
| deepseek-v4-flash | 无 | PR-039 | 无 | PR-034, PR-036 | 无 | 无 |

## 逐题结果

| Model | Case | Category | Route S/A | Tasks S/A | Facets | Attempts | Latency |
| --- | --- | --- | --- | --- | ---: | ---: | ---: |
| deepseek-v4-flash | PR-001 | single_lookup | True/True | True/True | 100% | 1 | 4353 ms |
| deepseek-v4-flash | PR-002 | single_lookup | True/True | True/True | 100% | 1 | 4336 ms |
| deepseek-v4-flash | PR-003 | single_lookup | True/True | True/True | 100% | 1 | 5040 ms |
| deepseek-v4-flash | PR-004 | single_lookup | True/True | True/True | 100% | 1 | 10047 ms |
| deepseek-v4-flash | PR-005 | single_lookup | True/True | True/True | 100% | 1 | 3908 ms |
| deepseek-v4-flash | PR-006 | single_lookup | True/True | True/True | 100% | 1 | 4263 ms |
| deepseek-v4-flash | PR-007 | single_lookup | True/True | True/True | 100% | 1 | 6471 ms |
| deepseek-v4-flash | PR-008 | single_lookup | True/True | True/True | 100% | 1 | 4841 ms |
| deepseek-v4-flash | PR-009 | single_lookup | True/True | True/True | 100% | 1 | 5839 ms |
| deepseek-v4-flash | PR-010 | single_lookup | True/True | True/True | 100% | 1 | 6557 ms |
| deepseek-v4-flash | PR-011 | single_lookup | True/True | True/True | 100% | 1 | 5937 ms |
| deepseek-v4-flash | PR-012 | single_lookup | True/True | True/True | 100% | 1 | 3311 ms |
| deepseek-v4-flash | PR-013 | single_lookup | True/True | True/True | 100% | 1 | 4209 ms |
| deepseek-v4-flash | PR-014 | single_lookup | True/True | True/True | 100% | 1 | 7873 ms |
| deepseek-v4-flash | PR-015 | single_lookup | True/True | True/True | 100% | 1 | 4863 ms |
| deepseek-v4-flash | PR-016 | single_lookup | True/True | True/True | 100% | 1 | 6997 ms |
| deepseek-v4-flash | PR-017 | cross_comparison | True/True | True/True | 100% | 1 | 5327 ms |
| deepseek-v4-flash | PR-018 | cross_comparison | True/True | True/True | 100% | 1 | 3282 ms |
| deepseek-v4-flash | PR-019 | cross_comparison | True/True | True/True | 100% | 1 | 4537 ms |
| deepseek-v4-flash | PR-020 | cross_comparison | True/True | True/True | 100% | 1 | 7590 ms |
| deepseek-v4-flash | PR-021 | cross_comparison | True/True | True/True | 100% | 1 | 3592 ms |
| deepseek-v4-flash | PR-022 | cross_comparison | True/True | True/True | 100% | 1 | 4453 ms |
| deepseek-v4-flash | PR-023 | cross_comparison | True/True | True/True | 100% | 1 | 2912 ms |
| deepseek-v4-flash | PR-024 | cross_comparison | True/True | True/True | 100% | 1 | 3238 ms |
| deepseek-v4-flash | PR-025 | cross_comparison | True/True | True/True | 100% | 1 | 6348 ms |
| deepseek-v4-flash | PR-026 | cross_comparison | True/True | True/True | 100% | 1 | 5994 ms |
| deepseek-v4-flash | PR-027 | cross_comparison | True/True | True/True | 100% | 1 | 2762 ms |
| deepseek-v4-flash | PR-028 | cross_comparison | True/True | True/True | 100% | 1 | 4535 ms |
| deepseek-v4-flash | PR-029 | cross_comparison | True/True | True/True | 100% | 1 | 4251 ms |
| deepseek-v4-flash | PR-030 | multi_method_synthesis | True/True | True/True | 100% | 3 | 44670 ms |
| deepseek-v4-flash | PR-031 | multi_method_synthesis | True/True | True/True | 100% | 1 | 5022 ms |
| deepseek-v4-flash | PR-032 | corpus_verification | True/True | True/True | 100% | 1 | 3283 ms |
| deepseek-v4-flash | PR-033 | corpus_verification | True/True | True/True | 100% | 2 | 26245 ms |
| deepseek-v4-flash | PR-034 | corpus_verification | True/True | False/True | 100% | 1 | 7652 ms |
| deepseek-v4-flash | PR-035 | corpus_verification | True/True | True/True | 100% | 1 | 4441 ms |
| deepseek-v4-flash | PR-036 | corpus_verification | True/True | False/True | 100% | 1 | 5488 ms |
| deepseek-v4-flash | PR-037 | routing_boundary | True/True | True/True | 100% | 1 | 9041 ms |
| deepseek-v4-flash | PR-038 | routing_boundary | True/True | True/True | 100% | 1 | 9718 ms |
| deepseek-v4-flash | PR-039 | routing_boundary | False/True | False/True | 100% | 2 | 25812 ms |
| deepseek-v4-flash | PR-040 | routing_boundary | True/True | True/True | 100% | 1 | 8340 ms |

## 决策

- 推荐模型：`无`
- 原因：没有候选模型通过全部 v2 质量门槛，保留当前生产 Planner。
- DeepSeek 使用 corpus-verification Prompt v2；与 v1 保持相同 Schema、max_tokens、重试和泄漏审计。
- 全集 Gate 用于检查定向 Prompt 是否对其他问题类别产生回退。
