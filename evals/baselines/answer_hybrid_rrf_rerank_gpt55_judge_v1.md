# LLM Judge Baseline: answer_hybrid_rrf_rerank_gpt55_judge_v1

- Answer Baseline：`answer_hybrid_rrf_rerank_v1`
- Judge：`gpt-5.5` / `answer_judge_v1`
- Cases：20（LLM=17, deterministic=3, cache=0）

## 总体指标

| Correctness | Faithfulness | Citation Completeness | Overall | Human Review | Judge P50/P95 | Input/Output Tokens |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 95.00% | 93.75% | 95.00% | 94.58% | 0.00% | 21002 / 27195 ms | 51071 / 14337 |

## 逐题结果

| Case | Source | Correctness | Faithfulness | Citation Completeness | Review | Latency |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| AE-001 | llm | 4/4 | 3/4 | 4/4 | False | 27625 ms |
| AE-002 | llm | 4/4 | 4/4 | 4/4 | False | 23102 ms |
| AE-003 | llm | 4/4 | 4/4 | 4/4 | False | 14372 ms |
| AE-004 | llm | 4/4 | 4/4 | 4/4 | False | 20108 ms |
| AE-005 | llm | 4/4 | 4/4 | 4/4 | False | 19505 ms |
| AE-006 | llm | 4/4 | 4/4 | 4/4 | False | 23811 ms |
| AE-007 | llm | 4/4 | 4/4 | 4/4 | False | 21002 ms |
| AE-008 | llm | 4/4 | 4/4 | 4/4 | False | 18196 ms |
| AE-009 | llm | 4/4 | 4/4 | 4/4 | False | 11712 ms |
| AE-010 | llm | 4/4 | 4/4 | 4/4 | False | 20674 ms |
| AE-011 | llm | 4/4 | 4/4 | 4/4 | False | 23505 ms |
| AE-012 | llm | 4/4 | 4/4 | 4/4 | False | 22232 ms |
| AE-013 | llm | 4/4 | 4/4 | 4/4 | False | 23297 ms |
| AE-014 | llm | 4/4 | 4/4 | 4/4 | False | 16376 ms |
| AE-015 | llm | 4/4 | 4/4 | 4/4 | False | 12124 ms |
| AE-016 | deterministic | 0/4 | 0/4 | 0/4 | False | 0 ms |
| AE-017 | llm | 4/4 | 4/4 | 4/4 | False | 26010 ms |
| AE-018 | llm | 4/4 | 4/4 | 4/4 | False | 27195 ms |
| AE-019 | deterministic | 4/4 | 4/4 | 4/4 | False | 0 ms |
| AE-020 | deterministic | 4/4 | 4/4 | 4/4 | False | 0 ms |

## 审计信息

- Judge failures：AE-016
- Human review：无
- 0 分包含 Generation Failure、错误拒答和 Judge Failure，避免只统计成功样本。
- LLM Judge 与确定性指标并列使用，不覆盖 Answer、Evidence、Citation 或延迟。
