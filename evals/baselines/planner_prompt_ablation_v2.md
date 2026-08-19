# Planner Prompt Ablation：planner_prompt_ablation_v2

## 全集对照

| Variant | Core Route/Task/Coverage | Overall Coverage | Retry | P50/P95 | Gate |
| --- | ---: | ---: | ---: | ---: | --- |
| Production GPT Prompt v1 | 97.30% / 97.30% / 100.00% | 100.00% | 0.00% | 10675 / 13595 ms | False |
| DeepSeek Prompt v1 | 100.00% / 100.00% / 100.00% | 98.75% | 5.00% | 4961 / 10754 ms | False |
| DeepSeek Prompt v2 | 100.00% / 94.59% / 100.00% | 100.00% | 7.50% | 5040 / 25812 ms | False |

## 定向稳定性

| Repetition | Route/Task | Coverage | Retry | P50/P95 | Gate |
| --- | ---: | ---: | ---: | ---: | --- |
| deepseek_prompt_v2_r1 | 100.00% / 100.00% | 100.00% | 20.00% | 7652 / 26245 ms | False |
| deepseek_prompt_v2_r2 | 100.00% / 100.00% | 100.00% | 0.00% | 5165 / 8285 ms | False |
| deepseek_prompt_v2_r3 | 100.00% / 100.00% | 100.00% | 10.00% | 5550 / 20136 ms | True |

## 决策

- Production switch review：`False`
- Prompt v2 未同时通过全集 Gate 和全部定向重复，生产 Planner 保持不变。
- full_quality_gate：`False`
- all_stability_repetitions_pass：`False`
- retry_not_worse_than_deepseek_v1：`False`
- p95_faster_than_production_gpt：`False`
- 详细全集和稳定性逐题结果见同名前缀的 `_full` 与 `_stability` 报告。
