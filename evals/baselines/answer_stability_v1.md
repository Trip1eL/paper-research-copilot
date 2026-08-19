# Answer Stability: answer_stability_v1

- Cases：AE-001, AE-007, AE-014, AE-016, AE-017, AE-018, AE-019, AE-020
- Repetitions：3
- Evidence：`frozen_top_k_from_answer_baseline`
- Answer / Judge：`deepseek-v4-flash` / `gpt-5.5`

## 总体结果

| Variant | Gen Success | Answerability | Correctness | Faithfulness | Citation Completeness | Strict Runs | Stable Cases | Status / Citation Stable | Mean within-case Stddev C/F/CC | Gen P50/P95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| answer_hybrid_rrf_v1 | 87.50% | 70.83% | 68.75% | 66.67% | 67.71% | 66.67% | 62.50% | 75.00% / 62.50% | 0.068 / 0.054 / 0.039 | 3415 / 24522 ms |
| answer_hybrid_rrf_rerank_v1 | 87.50% | 87.50% | 86.46% | 83.33% | 85.42% | 87.50% | 75.00% | 75.00% / 37.50% | 0.133 / 0.133 / 0.118 | 3776 / 22892 ms |

## 逐 Case 结果

### answer_hybrid_rrf_v1

| Case | Status Stable | Unique Answers/Citations | Correctness Mean/Min | Faithfulness Mean/Min | Completeness Mean/Min | Strict Pass |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| AE-001 | True | 3/2 | 91.67%/75.00% | 91.67%/75.00% | 100.00%/100.00% | 100.00% |
| AE-007 | True | 3/1 | 100.00%/100.00% | 100.00%/100.00% | 100.00%/100.00% | 100.00% |
| AE-014 | True | 3/2 | 100.00%/100.00% | 100.00%/100.00% | 100.00%/100.00% | 100.00% |
| AE-016 | False | 3/3 | 58.33%/0.00% | 41.67%/0.00% | 41.67%/0.00% | 33.33% |
| AE-017 | False | 2/1 | 0.00%/0.00% | 0.00%/0.00% | 0.00%/0.00% | 0.00% |
| AE-018 | True | 1/1 | 0.00%/0.00% | 0.00%/0.00% | 0.00%/0.00% | 0.00% |
| AE-019 | True | 1/1 | 100.00%/100.00% | 100.00%/100.00% | 100.00%/100.00% | 100.00% |
| AE-020 | True | 1/1 | 100.00%/100.00% | 100.00%/100.00% | 100.00%/100.00% | 100.00% |

### answer_hybrid_rrf_rerank_v1

| Case | Status Stable | Unique Answers/Citations | Correctness Mean/Min | Faithfulness Mean/Min | Completeness Mean/Min | Strict Pass |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| AE-001 | True | 3/3 | 91.67%/75.00% | 83.33%/75.00% | 100.00%/100.00% | 100.00% |
| AE-007 | True | 3/1 | 100.00%/100.00% | 100.00%/100.00% | 100.00%/100.00% | 100.00% |
| AE-014 | True | 3/2 | 100.00%/100.00% | 100.00%/100.00% | 100.00%/100.00% | 100.00% |
| AE-016 | False | 2/2 | 33.33%/0.00% | 25.00%/0.00% | 25.00%/0.00% | 33.33% |
| AE-017 | False | 3/3 | 66.67%/0.00% | 66.67%/0.00% | 66.67%/0.00% | 66.67% |
| AE-018 | True | 3/2 | 100.00%/100.00% | 91.67%/75.00% | 91.67%/75.00% | 100.00% |
| AE-019 | True | 1/1 | 100.00%/100.00% | 100.00%/100.00% | 100.00%/100.00% | 100.00% |
| AE-020 | True | 1/1 | 100.00%/100.00% | 100.00%/100.00% | 100.00%/100.00% | 100.00% |

## 口径

- Strict Run 要求生成成功、Answerability 正确，且 Judge 三维均不低于 3/4。
- Stable Case 要求同一 Case 的所有重复运行都通过 Strict Run。
- Citation Stable 要求每次运行引用的论文/页码集合完全一致。
- 本实验冻结每个 Answer Baseline 的 Top-K Evidence，只测量生成与引用选择波动。
