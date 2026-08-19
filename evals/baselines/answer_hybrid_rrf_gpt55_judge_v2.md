# LLM Judge Baseline: answer_hybrid_rrf_gpt55_judge_v2

- Answer Baseline：`answer_hybrid_rrf_v2`
- Judge：`gpt-5.5` / `answer_judge_v1`
- Cases：32（LLM=24, deterministic=8, cache=0）

## 总体指标

| Correctness | Faithfulness | Citation Completeness | Overall | Human Review | Judge P50/P95 | Input/Output Tokens |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 74.22% | 73.44% | 75.00% | 74.22% | 0.00% | 22002 / 33130 ms | 71792 / 22912 |

## 逐题结果

| Case | Source | Correctness | Faithfulness | Citation Completeness | Review | Latency |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| AE-001 | llm | 4/4 | 4/4 | 4/4 | False | 20318 ms |
| AE-002 | llm | 4/4 | 4/4 | 4/4 | False | 23549 ms |
| AE-003 | llm | 4/4 | 3/4 | 3/4 | False | 25394 ms |
| AE-004 | llm | 4/4 | 3/4 | 4/4 | False | 29597 ms |
| AE-005 | llm | 4/4 | 4/4 | 4/4 | False | 11697 ms |
| AE-006 | llm | 4/4 | 4/4 | 4/4 | False | 20285 ms |
| AE-007 | llm | 4/4 | 4/4 | 4/4 | False | 25467 ms |
| AE-008 | llm | 4/4 | 4/4 | 4/4 | False | 23243 ms |
| AE-009 | llm | 4/4 | 4/4 | 4/4 | False | 18832 ms |
| AE-010 | llm | 4/4 | 4/4 | 4/4 | False | 17144 ms |
| AE-011 | llm | 4/4 | 4/4 | 4/4 | False | 25816 ms |
| AE-012 | llm | 3/4 | 4/4 | 4/4 | False | 22002 ms |
| AE-013 | llm | 4/4 | 4/4 | 4/4 | False | 17266 ms |
| AE-014 | llm | 4/4 | 4/4 | 4/4 | False | 23847 ms |
| AE-015 | deterministic | 0/4 | 0/4 | 0/4 | False | 0 ms |
| AE-016 | llm | 2/4 | 2/4 | 2/4 | False | 39658 ms |
| AE-017 | deterministic | 0/4 | 0/4 | 0/4 | False | 0 ms |
| AE-018 | deterministic | 0/4 | 0/4 | 0/4 | False | 0 ms |
| AE-019 | deterministic | 4/4 | 4/4 | 4/4 | False | 0 ms |
| AE-020 | llm | 4/4 | 4/4 | 4/4 | False | 25670 ms |
| AE-021 | llm | 4/4 | 3/4 | 3/4 | False | 21104 ms |
| AE-022 | llm | 4/4 | 4/4 | 4/4 | False | 21219 ms |
| AE-023 | llm | 4/4 | 4/4 | 4/4 | False | 20824 ms |
| AE-024 | llm | 4/4 | 4/4 | 4/4 | False | 19914 ms |
| AE-025 | llm | 3/4 | 4/4 | 4/4 | False | 15183 ms |
| AE-026 | llm | 3/4 | 4/4 | 4/4 | False | 19335 ms |
| AE-027 | deterministic | 0/4 | 0/4 | 0/4 | False | 0 ms |
| AE-028 | llm | 4/4 | 4/4 | 4/4 | False | 25244 ms |
| AE-029 | llm | 4/4 | 3/4 | 4/4 | False | 33130 ms |
| AE-030 | deterministic | 0/4 | 0/4 | 0/4 | False | 0 ms |
| AE-031 | deterministic | 0/4 | 0/4 | 0/4 | False | 0 ms |
| AE-032 | deterministic | 0/4 | 0/4 | 0/4 | False | 0 ms |

## 审计信息

- Judge failures：AE-015, AE-017, AE-018, AE-027, AE-030, AE-031, AE-032
- Human review：无
- 0 分包含 Generation Failure、错误拒答和 Judge Failure，避免只统计成功样本。
- LLM Judge 与确定性指标并列使用，不覆盖 Answer、Evidence、Citation 或延迟。
