# Planner Model Ablation v2：planner_prompt_ablation_v2_stability

- Dataset：`evals/datasets/planner_routing_v2.jsonl`（10 Cases）
- Label-sensitive：3 Cases
- Prompt：`research_planner_corpus_verification_v2`
- Quality Gate：success=100%; core_router=100%; core_task_count=100%; task_coverage=100%; acceptable_router=100%; acceptable_task_count=100%; title_leakage=0%

## 总体指标

| Model | Success | Strict Route/Task | Acceptable Route/Task | Coverage | Core Route/Task/Coverage | Boundary Strict/Acceptable/Coverage | Leakage | Retry | P50/P95 | Gate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| deepseek-v4-flash | 100.00% | 90.00% / 70.00% | 100.00% / 100.00% | 100.00% | 100.00% / 71.43% / 100.00% | 66.67% / 100.00% / 100.00% | 0.00% | 20.00% | 7652 / 26245 ms | False |
| deepseek-v4-flash | 100.00% | 100.00% / 90.00% | 100.00% / 100.00% | 100.00% | 100.00% / 85.71% / 100.00% | 100.00% / 100.00% / 100.00% | 0.00% | 0.00% | 5165 / 8285 ms | False |
| deepseek-v4-flash | 100.00% | 90.00% / 90.00% | 100.00% / 100.00% | 100.00% | 100.00% / 100.00% / 100.00% | 66.67% / 100.00% / 100.00% | 0.00% | 10.00% | 5550 / 20136 ms | True |

## 分类指标

### deepseek-v4-flash

| Category | Cases | Strict Route | Acceptable Route | Strict Task | Acceptable Task | Coverage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| single_lookup | 1 | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| corpus_verification | 5 | 100.00% | 100.00% | 60.00% | 100.00% | 100.00% |
| routing_boundary | 4 | 75.00% | 100.00% | 75.00% | 100.00% | 100.00% |

### deepseek-v4-flash

| Category | Cases | Strict Route | Acceptable Route | Strict Task | Acceptable Task | Coverage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| single_lookup | 1 | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| corpus_verification | 5 | 100.00% | 100.00% | 80.00% | 100.00% | 100.00% |
| routing_boundary | 4 | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |

### deepseek-v4-flash

| Category | Cases | Strict Route | Acceptable Route | Strict Task | Acceptable Task | Coverage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| single_lookup | 1 | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| corpus_verification | 5 | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| routing_boundary | 4 | 75.00% | 100.00% | 75.00% | 100.00% | 100.00% |

## 调用成本与延迟

| Model | Calls | Input Tokens | Output Tokens | P50 | P95 | Retry |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| deepseek-v4-flash | 12 | 5775 | 7330 | 7652 ms | 26245 ms | 20.00% |
| deepseek-v4-flash | 10 | 5775 | 5694 | 5165 ms | 8285 ms | 0.00% |
| deepseek-v4-flash | 11 | 5775 | 5567 | 5550 ms | 20136 ms | 10.00% |

## 失败审计

| Model | Failed | Strict Route Errors | Unacceptable Routes | Core Task Errors | Low Coverage | Leakage |
| --- | --- | --- | --- | --- | --- | --- |
| deepseek-v4-flash | 无 | PR-039 | 无 | PR-034, PR-036 | 无 | 无 |
| deepseek-v4-flash | 无 | 无 | 无 | PR-036 | 无 | 无 |
| deepseek-v4-flash | 无 | PR-039 | 无 | 无 | 无 | 无 |

## 逐题结果

| Model | Case | Category | Route S/A | Tasks S/A | Facets | Attempts | Latency |
| --- | --- | --- | --- | --- | ---: | ---: | ---: |
| deepseek-v4-flash | PR-016 | single_lookup | True/True | True/True | 100% | 1 | 6997 ms |
| deepseek-v4-flash | PR-032 | corpus_verification | True/True | True/True | 100% | 1 | 3283 ms |
| deepseek-v4-flash | PR-033 | corpus_verification | True/True | True/True | 100% | 2 | 26245 ms |
| deepseek-v4-flash | PR-034 | corpus_verification | True/True | False/True | 100% | 1 | 7652 ms |
| deepseek-v4-flash | PR-035 | corpus_verification | True/True | True/True | 100% | 1 | 4441 ms |
| deepseek-v4-flash | PR-036 | corpus_verification | True/True | False/True | 100% | 1 | 5488 ms |
| deepseek-v4-flash | PR-037 | routing_boundary | True/True | True/True | 100% | 1 | 9041 ms |
| deepseek-v4-flash | PR-038 | routing_boundary | True/True | True/True | 100% | 1 | 9718 ms |
| deepseek-v4-flash | PR-039 | routing_boundary | False/True | False/True | 100% | 2 | 25812 ms |
| deepseek-v4-flash | PR-040 | routing_boundary | True/True | True/True | 100% | 1 | 8340 ms |
| deepseek-v4-flash | PR-016 | single_lookup | True/True | True/True | 100% | 1 | 5616 ms |
| deepseek-v4-flash | PR-032 | corpus_verification | True/True | True/True | 100% | 1 | 4257 ms |
| deepseek-v4-flash | PR-033 | corpus_verification | True/True | True/True | 100% | 1 | 7538 ms |
| deepseek-v4-flash | PR-034 | corpus_verification | True/True | True/True | 100% | 1 | 5165 ms |
| deepseek-v4-flash | PR-035 | corpus_verification | True/True | True/True | 100% | 1 | 5998 ms |
| deepseek-v4-flash | PR-036 | corpus_verification | True/True | False/True | 100% | 1 | 8285 ms |
| deepseek-v4-flash | PR-037 | routing_boundary | True/True | True/True | 100% | 1 | 5541 ms |
| deepseek-v4-flash | PR-038 | routing_boundary | True/True | True/True | 100% | 1 | 4484 ms |
| deepseek-v4-flash | PR-039 | routing_boundary | True/True | True/True | 100% | 1 | 2954 ms |
| deepseek-v4-flash | PR-040 | routing_boundary | True/True | True/True | 100% | 1 | 2926 ms |
| deepseek-v4-flash | PR-016 | single_lookup | True/True | True/True | 100% | 1 | 5092 ms |
| deepseek-v4-flash | PR-032 | corpus_verification | True/True | True/True | 100% | 1 | 3977 ms |
| deepseek-v4-flash | PR-033 | corpus_verification | True/True | True/True | 100% | 1 | 7687 ms |
| deepseek-v4-flash | PR-034 | corpus_verification | True/True | True/True | 100% | 1 | 4568 ms |
| deepseek-v4-flash | PR-035 | corpus_verification | True/True | True/True | 100% | 2 | 20136 ms |
| deepseek-v4-flash | PR-036 | corpus_verification | True/True | True/True | 100% | 1 | 5550 ms |
| deepseek-v4-flash | PR-037 | routing_boundary | True/True | True/True | 100% | 1 | 6389 ms |
| deepseek-v4-flash | PR-038 | routing_boundary | True/True | True/True | 100% | 1 | 3374 ms |
| deepseek-v4-flash | PR-039 | routing_boundary | False/True | False/True | 100% | 1 | 8748 ms |
| deepseek-v4-flash | PR-040 | routing_boundary | True/True | True/True | 100% | 1 | 7093 ms |

## 决策

- 推荐模型：`deepseek-v4-flash`
- 原因：deepseek-v4-flash 通过全部 v2 质量门槛，并且在通过门槛的候选模型中 P50 最低（5550 ms）。
- 每次重复使用独立缓存；r1 复用同一次真实生成的全集结果。
- 定向集包含全部 corpus verification、全部 routing boundary 和过度拆分样本 PR-016。
