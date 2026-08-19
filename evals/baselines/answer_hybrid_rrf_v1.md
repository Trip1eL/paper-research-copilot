# Answer Baseline: answer_hybrid_rrf_v1

- Dataset：`evals/datasets/answer_generation_v1.jsonl`（20 cases）
- Retrieval：`hybrid_rrf` / Top-10
- Answer model：`deepseek-v4-flash`
- Prompt version：`answer_v1`
- Empty-answer retry attempts：`2`

## 总体指标

| Generation Success | Answerability | Key Point Recall | Citation Paper P/R | Strict Page P/R | Sentence Citation | P50/P95 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 90.00% | 85.00% | 80.56% | 83.33% / 83.33% | 66.67% / 83.33% | 61.64% | 4319 / 23938 ms |

## 逐题结果

| Case | Type | Status | Key Points | Paper Recall | Strict Page Recall | Sentence Citation | Total Latency |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| AE-001 | method | answered | 100.00% | 100.00% | 100.00% | 50.00% | 2662 ms |
| AE-002 | fact | answered | 100.00% | 100.00% | 100.00% | 100.00% | 4412 ms |
| AE-003 | fact | answered | 100.00% | 100.00% | 100.00% | 100.00% | 5970 ms |
| AE-004 | method | answered | 100.00% | 100.00% | 100.00% | 66.67% | 3544 ms |
| AE-005 | fact | answered | 100.00% | 100.00% | 100.00% | 42.86% | 3168 ms |
| AE-006 | method | answered | 100.00% | 100.00% | 100.00% | 100.00% | 2867 ms |
| AE-007 | method | answered | 100.00% | 100.00% | 100.00% | 66.67% | 4406 ms |
| AE-008 | method | answered | 100.00% | 100.00% | 100.00% | 50.00% | 4080 ms |
| AE-009 | method | answered | 100.00% | 100.00% | 100.00% | 66.67% | 5234 ms |
| AE-010 | method | answered | 75.00% | 100.00% | 100.00% | 50.00% | 4040 ms |
| AE-011 | method | answered | 75.00% | 100.00% | 100.00% | 75.00% | 5514 ms |
| AE-012 | method | answered | 100.00% | 100.00% | 100.00% | 66.67% | 4319 ms |
| AE-013 | method | answered | 100.00% | 100.00% | 100.00% | 75.00% | 2833 ms |
| AE-014 | method | answered | 100.00% | 100.00% | 100.00% | 100.00% | 2404 ms |
| AE-015 | fact | answered | 100.00% | 100.00% | 100.00% | 100.00% | 7571 ms |
| AE-016 | cross_paper | error | 0.00% | 0.00% | 0.00% | 0.00% | 24624 ms |
| AE-017 | cross_paper | error | 0.00% | 0.00% | 0.00% | 0.00% | 23938 ms |
| AE-018 | cross_paper | insufficient_evidence | 0.00% | 0.00% | 0.00% | 0.00% | 8767 ms |
| AE-019 | unanswerable | insufficient_evidence | - | - | - | - | 2761 ms |
| AE-020 | unanswerable | insufficient_evidence | - | - | - | - | 3743 ms |

## 失败 Case

- Generation failure：AE-016, AE-017
- Answerability error：AE-016, AE-017, AE-018

## 口径限制

- Key Point Recall 是人工别名匹配，只衡量关键术语覆盖，不等于语义正确性。
- Strict Page 指标使用非穷举人工页码，因此是严格下界。
- Sentence Citation 只检查句子是否含 Citation marker，不判断 Claim-Evidence entailment。
- 下一阶段使用独立 LLM Judge 补充 correctness 与 faithfulness，不能替代这些确定性指标。
