# LLM Judge Baseline: answer_hybrid_rrf_gpt55_judge_v1

- Answer Baseline：`answer_hybrid_rrf_v1`
- Judge：`gpt-5.5` / `answer_judge_v1`
- Cases：20（LLM=15, deterministic=5, cache=1）

## 总体指标

| Correctness | Faithfulness | Citation Completeness | Overall | Human Review | Judge P50/P95 | Input/Output Tokens |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 85.00% | 83.75% | 85.00% | 84.58% | 0.00% | 20553 / 24617 ms | 38327 / 12145 |

## 逐题结果

| Case | Source | Correctness | Faithfulness | Citation Completeness | Review | Latency |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| AE-001 | cache | 4/4 | 4/4 | 4/4 | False | 24617 ms |
| AE-002 | llm | 4/4 | 4/4 | 4/4 | False | 18376 ms |
| AE-003 | llm | 4/4 | 4/4 | 4/4 | False | 18506 ms |
| AE-004 | llm | 4/4 | 4/4 | 4/4 | False | 21661 ms |
| AE-005 | llm | 4/4 | 4/4 | 4/4 | False | 20989 ms |
| AE-006 | llm | 4/4 | 4/4 | 4/4 | False | 18796 ms |
| AE-007 | llm | 4/4 | 3/4 | 4/4 | False | 26643 ms |
| AE-008 | llm | 4/4 | 4/4 | 4/4 | False | 20553 ms |
| AE-009 | llm | 4/4 | 4/4 | 4/4 | False | 19094 ms |
| AE-010 | llm | 4/4 | 4/4 | 4/4 | False | 20174 ms |
| AE-011 | llm | 4/4 | 4/4 | 4/4 | False | 24602 ms |
| AE-012 | llm | 4/4 | 4/4 | 4/4 | False | 24263 ms |
| AE-013 | llm | 4/4 | 4/4 | 4/4 | False | 22733 ms |
| AE-014 | llm | 4/4 | 4/4 | 4/4 | False | 13745 ms |
| AE-015 | llm | 4/4 | 4/4 | 4/4 | False | 13327 ms |
| AE-016 | deterministic | 0/4 | 0/4 | 0/4 | False | 0 ms |
| AE-017 | deterministic | 0/4 | 0/4 | 0/4 | False | 0 ms |
| AE-018 | deterministic | 0/4 | 0/4 | 0/4 | False | 0 ms |
| AE-019 | deterministic | 4/4 | 4/4 | 4/4 | False | 0 ms |
| AE-020 | deterministic | 4/4 | 4/4 | 4/4 | False | 0 ms |

## 审计信息

- Judge failures：AE-016, AE-017, AE-018
- Human review：无
- 0 分包含 Generation Failure、错误拒答和 Judge Failure，避免只统计成功样本。
- LLM Judge 与确定性指标并列使用，不覆盖 Answer、Evidence、Citation 或延迟。
