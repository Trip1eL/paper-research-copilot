# Planner Model Ablation：planner_model_ablation_v1

- Dataset：`evals/datasets/agent_runtime_v1.jsonl`（8 Cases）
- Prompt：`research_planner_v1`
- Quality Gate：success=100%; router=100%; task_count=100%; task_coverage=100%; title_leakage=0%
- 延迟使用原始 generation latency；缓存查找耗时不参与模型对比。

## 总体结果

| Model | Success | Router | Task Count | Task Coverage | Title Leakage | Schema Retry | P50/P95 | Known Input/Output Tokens | Calls | Gate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| gpt-5.5 | 100.00% | 100.00% | 100.00% | 100.00% | 0.00% | 0.00% | 10719 / 14723 ms | 1475 / 1995 | 8 | True |
| deepseek-v4-flash | 100.00% | 87.50% | 87.50% | 93.75% | 0.00% | 12.50% | 5084 / 23923 ms | 2529 / 3015 | 9 | False |

## 逐题结果

| Model | Case | Success | Route | Tasks | Facets | Leakage | Attempts | Latency |
| --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: |
| gpt-5.5 | AE-001 | True | single_paper | 1 | 100% | False | 1 | 9149 ms |
| gpt-5.5 | AE-007 | True | single_paper | 1 | 100% | False | 1 | 10675 ms |
| gpt-5.5 | AE-014 | True | single_paper | 1 | 100% | False | 1 | 9114 ms |
| gpt-5.5 | AE-016 | True | cross_paper | 2 | 100% | False | 1 | 10719 ms |
| gpt-5.5 | AE-017 | True | cross_paper | 2 | 100% | False | 1 | 9570 ms |
| gpt-5.5 | AE-018 | True | cross_paper | 2 | 100% | False | 1 | 11705 ms |
| gpt-5.5 | AE-019 | True | cross_paper | 2 | 100% | False | 1 | 14723 ms |
| gpt-5.5 | AE-020 | True | cross_paper | 2 | 100% | False | 1 | 12394 ms |
| deepseek-v4-flash | AE-001 | True | single_paper | 1 | 100% | False | 1 | 3756 ms |
| deepseek-v4-flash | AE-007 | True | single_paper | 1 | 100% | False | 1 | 3978 ms |
| deepseek-v4-flash | AE-014 | True | single_paper | 1 | 100% | False | 1 | 5084 ms |
| deepseek-v4-flash | AE-016 | True | cross_paper | 2 | 100% | False | 1 | 5715 ms |
| deepseek-v4-flash | AE-017 | True | cross_paper | 2 | 100% | False | 1 | 3440 ms |
| deepseek-v4-flash | AE-018 | True | cross_paper | 2 | 100% | False | 1 | 3329 ms |
| deepseek-v4-flash | AE-019 | True | single_paper | 1 | 50% | False | 2 | 23923 ms |
| deepseek-v4-flash | AE-020 | True | cross_paper | 2 | 100% | False | 1 | 6246 ms |

## 实验说明

- 两组使用相同的 system/user Prompt、max_tokens、Pydantic Schema、重试策略和 Corpus alias 泄漏审计。
- 缓存命中时从原始记录读取 generation latency，不使用缓存查找耗时。
- Provider 负载随时间变化，因此延迟用于方向性对比，不代表服务 SLA。
- 部分 GPT 历史缓存创建于 Token/attempts tracing 之前，因此 GPT Token 合计只代表 已知记录，旧记录的 attempts 兼容值为 1。
- AE-019 对标签定义敏感：严格门槛遵循当前 Runtime 策略，即语料级缺失验证使用 多个 Retrieval Task。

## 决策

- 推荐模型：`gpt-5.5`
- 原因：gpt-5.5 通过全部质量门槛，并且在通过门槛的候选模型中 Planner P50 最低（10719 ms）。
- 该决策只覆盖 Planner；Retrieval、Answer 和 Judge 模型没有随本实验改变。
- 8 条 Case 可用于 MVP 选型，但仍需在更大的路由集上复验泛化能力。
