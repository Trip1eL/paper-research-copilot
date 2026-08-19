# Answer Baseline: answer_hybrid_rrf_rerank_v1

- Dataset：`evals/datasets/answer_generation_v1.jsonl`（20 cases）
- Retrieval：`hybrid_rrf_rerank` / Top-10
- Answer model：`deepseek-v4-flash`
- Prompt version：`answer_v1`
- Empty-answer retry attempts：`2`

## 总体指标

| Generation Success | Answerability | Key Point Recall | Citation Paper P/R | Strict Page P/R | Sentence Citation | P50/P95 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 95.00% | 95.00% | 93.06% | 94.44% / 94.44% | 70.83% / 94.44% | 74.35% | 5679 / 23501 ms |

## 逐题结果

| Case | Type | Status | Key Points | Paper Recall | Strict Page Recall | Sentence Citation | Total Latency |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| AE-001 | method | answered | 100.00% | 100.00% | 100.00% | 50.00% | 4795 ms |
| AE-002 | fact | answered | 100.00% | 100.00% | 100.00% | 75.00% | 5702 ms |
| AE-003 | fact | answered | 100.00% | 100.00% | 100.00% | 100.00% | 4456 ms |
| AE-004 | method | answered | 100.00% | 100.00% | 100.00% | 50.00% | 4899 ms |
| AE-005 | fact | answered | 100.00% | 100.00% | 100.00% | 100.00% | 5156 ms |
| AE-006 | method | answered | 100.00% | 100.00% | 100.00% | 100.00% | 5312 ms |
| AE-007 | method | answered | 100.00% | 100.00% | 100.00% | 100.00% | 6745 ms |
| AE-008 | method | answered | 100.00% | 100.00% | 100.00% | 100.00% | 5001 ms |
| AE-009 | method | answered | 100.00% | 100.00% | 100.00% | 50.00% | 4142 ms |
| AE-010 | method | answered | 100.00% | 100.00% | 100.00% | 100.00% | 6579 ms |
| AE-011 | method | answered | 100.00% | 100.00% | 100.00% | 80.00% | 6000 ms |
| AE-012 | method | answered | 75.00% | 100.00% | 100.00% | 66.67% | 8995 ms |
| AE-013 | method | answered | 100.00% | 100.00% | 100.00% | 100.00% | 5541 ms |
| AE-014 | method | answered | 100.00% | 100.00% | 100.00% | 50.00% | 5679 ms |
| AE-015 | fact | answered | 100.00% | 100.00% | 100.00% | 100.00% | 4797 ms |
| AE-016 | cross_paper | error | 0.00% | 0.00% | 0.00% | 0.00% | 26359 ms |
| AE-017 | cross_paper | answered | 100.00% | 100.00% | 100.00% | 50.00% | 23501 ms |
| AE-018 | cross_paper | answered | 100.00% | 100.00% | 100.00% | 66.67% | 11910 ms |
| AE-019 | unanswerable | insufficient_evidence | - | - | - | - | 4300 ms |
| AE-020 | unanswerable | insufficient_evidence | - | - | - | - | 5992 ms |

## 失败 Case

- Generation failure：AE-016
- Answerability error：AE-016

## 口径限制

- Key Point Recall 是人工别名匹配，只衡量关键术语覆盖，不等于语义正确性。
- Strict Page 指标使用非穷举人工页码，因此是严格下界。
- Sentence Citation 只检查句子是否含 Citation marker，不判断 Claim-Evidence entailment。
- 下一阶段使用独立 LLM Judge 补充 correctness 与 faithfulness，不能替代这些确定性指标。
