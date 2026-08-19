# Answer Stability: answer_generation_observability_v2

- Cases：AE-016, AE-017, AE-018
- Repetitions：3
- Evidence：`frozen_top_k_from_answer_baseline`
- Answer / Judge：`deepseek-v4-flash` / `gpt-5.5`

## 总体结果

| Variant | Gen Success | Answerability | Correctness | Faithfulness | Citation Completeness | Strict Runs | Stable Cases | Status / Citation Stable | Mean within-case Stddev C/F/CC | Gen P50/P95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| answer_hybrid_rrf_v1 | 88.89% | 22.22% | 16.67% | 11.11% | 11.11% | 0.00% | 0.00% | 66.67% / 66.67% | 0.118 / 0.079 / 0.079 | 14613 / 50847 ms |
| answer_hybrid_rrf_rerank_v1 | 100.00% | 100.00% | 97.22% | 83.33% | 94.44% | 100.00% | 100.00% | 100.00% / 33.33% | 0.039 / 0.079 / 0.039 | 16941 / 46571 ms |

## 生成终止状态

| Variant | Empty Cases | Truncated Cases | Retry Trigger | Retry Recovery | Finish Reasons |
| --- | ---: | ---: | ---: | ---: | --- |
| answer_hybrid_rrf_v1 | 0.00% | 22.22% | 22.22% | 50.00% | `{'length': 3, 'stop': 8}` |
| answer_hybrid_rrf_rerank_v1 | 0.00% | 11.11% | 11.11% | 100.00% | `{'stop': 9, 'length': 1}` |

## 逐 Case 结果

### answer_hybrid_rrf_v1

| Case | Status Stable | Unique Answers/Citations | Correctness Mean/Min | Faithfulness Mean/Min | Completeness Mean/Min | Strict Pass |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| AE-016 | False | 3/2 | 50.00%/0.00% | 33.33%/0.00% | 33.33%/0.00% | 0.00% |
| AE-017 | True | 1/1 | 0.00%/0.00% | 0.00%/0.00% | 0.00%/0.00% | 0.00% |
| AE-018 | True | 1/1 | 0.00%/0.00% | 0.00%/0.00% | 0.00%/0.00% | 0.00% |

### answer_hybrid_rrf_rerank_v1

| Case | Status Stable | Unique Answers/Citations | Correctness Mean/Min | Faithfulness Mean/Min | Completeness Mean/Min | Strict Pass |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| AE-016 | True | 3/2 | 91.67%/75.00% | 75.00%/75.00% | 83.33%/75.00% | 100.00% |
| AE-017 | True | 3/3 | 100.00%/100.00% | 91.67%/75.00% | 100.00%/100.00% | 100.00% |
| AE-018 | True | 3/1 | 100.00%/100.00% | 83.33%/75.00% | 100.00%/100.00% | 100.00% |

## 口径

- Strict Run 要求生成成功、Answerability 正确，且 Judge 三维均不低于 3/4。
- Stable Case 要求同一 Case 的所有重复运行都通过 Strict Run。
- Citation Stable 要求每次运行引用的论文/页码集合完全一致。
- 本实验冻结每个 Answer Baseline 的 Top-K Evidence，只测量生成与引用选择波动。
