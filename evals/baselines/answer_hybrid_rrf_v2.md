# Answer Baseline: answer_hybrid_rrf_v2

- Dataset：`evals/datasets/answer_generation_v2.jsonl`（32 cases）
- Retrieval：`hybrid_rrf` / Top-10
- Answer model：`deepseek-v4-flash`
- Prompt version：`answer_v2`
- Empty-answer retry attempts：`2`

## 总体指标

| Generation Success | Answerability | Key Point Recall | Citation Paper P/R | Strict Page P/R | Sentence Citation | P50/P95 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 96.88% | 78.12% | 71.24% | 74.19% / 75.81% | 60.54% / 74.19% | 60.16% | 4042 / 25168 ms |

## 逐题结果

| Case | Type | Status | Key Points | Paper Recall | Strict Page Recall | Sentence Citation | Total Latency |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| AE-001 | method | answered | 100.00% | 100.00% | 100.00% | 66.67% | 3811 ms |
| AE-002 | fact | answered | 100.00% | 100.00% | 100.00% | 75.00% | 8334 ms |
| AE-003 | fact | answered | 100.00% | 100.00% | 100.00% | 50.00% | 3485 ms |
| AE-004 | method | answered | 100.00% | 100.00% | 100.00% | 66.67% | 3825 ms |
| AE-005 | fact | answered | 100.00% | 100.00% | 100.00% | 100.00% | 2144 ms |
| AE-006 | method | answered | 100.00% | 100.00% | 100.00% | 100.00% | 3376 ms |
| AE-007 | method | answered | 75.00% | 100.00% | 100.00% | 66.67% | 2950 ms |
| AE-008 | method | answered | 100.00% | 100.00% | 100.00% | 75.00% | 3464 ms |
| AE-009 | method | answered | 100.00% | 100.00% | 100.00% | 66.67% | 3136 ms |
| AE-010 | method | answered | 75.00% | 100.00% | 100.00% | 66.67% | 2355 ms |
| AE-011 | method | answered | 75.00% | 100.00% | 100.00% | 100.00% | 4222 ms |
| AE-012 | method | answered | 100.00% | 100.00% | 100.00% | 100.00% | 4580 ms |
| AE-013 | method | answered | 100.00% | 100.00% | 100.00% | 66.67% | 3725 ms |
| AE-014 | method | answered | 100.00% | 100.00% | 100.00% | 63.64% | 3043 ms |
| AE-015 | fact | error | 0.00% | 0.00% | 0.00% | 0.00% | 38512 ms |
| AE-016 | cross_paper | answered | 50.00% | 50.00% | 50.00% | 54.55% | 25168 ms |
| AE-017 | cross_paper | insufficient_evidence | 0.00% | 0.00% | 0.00% | 0.00% | 37659 ms |
| AE-018 | cross_paper | insufficient_evidence | 0.00% | 0.00% | 0.00% | 0.00% | 12337 ms |
| AE-019 | unanswerable | insufficient_evidence | - | - | - | - | 3703 ms |
| AE-020 | fact | answered | 100.00% | 100.00% | 100.00% | 100.00% | 8982 ms |
| AE-021 | method | answered | 100.00% | 100.00% | 100.00% | 100.00% | 3043 ms |
| AE-022 | method | answered | 100.00% | 100.00% | 100.00% | 50.00% | 4740 ms |
| AE-023 | method | answered | 100.00% | 100.00% | 100.00% | 66.67% | 2677 ms |
| AE-024 | fact | answered | 100.00% | 100.00% | 100.00% | 100.00% | 7782 ms |
| AE-025 | fact | answered | 66.67% | 100.00% | 100.00% | 100.00% | 4042 ms |
| AE-026 | method | answered | 66.67% | 100.00% | 100.00% | 50.00% | 2512 ms |
| AE-027 | fact | insufficient_evidence | 0.00% | 0.00% | 0.00% | 0.00% | 5927 ms |
| AE-028 | method | answered | 100.00% | 100.00% | 100.00% | 100.00% | 3492 ms |
| AE-029 | cross_paper | answered | 100.00% | 100.00% | 50.00% | 80.00% | 9263 ms |
| AE-030 | cross_paper | insufficient_evidence | 0.00% | 0.00% | 0.00% | 0.00% | 12617 ms |
| AE-031 | cross_paper | insufficient_evidence | 0.00% | 0.00% | 0.00% | 0.00% | 13474 ms |
| AE-032 | cross_paper | insufficient_evidence | 0.00% | 0.00% | 0.00% | 0.00% | 7144 ms |

## 失败 Case

- Generation failure：AE-015
- Answerability error：AE-015, AE-017, AE-018, AE-027, AE-030, AE-031, AE-032
- Empty response cases：0.00%
- Truncation cases：6.25%
- Retry trigger / recovery：6.25% / 50.00%
- Finish reasons：{'stop': 31, 'length': 3}

## 口径限制

- Key Point Recall 是人工别名匹配，只衡量关键术语覆盖，不等于语义正确性。
- Strict Page 指标使用非穷举人工页码，因此是严格下界。
- Sentence Citation 只检查句子是否含 Citation marker，不判断 Claim-Evidence entailment。
- 下一阶段使用独立 LLM Judge 补充 correctness 与 faithfulness，不能替代这些确定性指标。
