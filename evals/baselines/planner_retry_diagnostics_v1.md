# Planner Retry Diagnostics：planner_retry_diagnostics_v1

- Model：`deepseek-v4-flash`
- Prompt：`research_planner_corpus_verification_v2`
- Cases：PR-030, PR-033, PR-039
- Repetitions：3
- Raw trace：`data/agent/planner_retry_diagnostics_v1_raw.jsonl`（ignored，不进入 Git）

## 汇总

- Success：100.00%
- Retry Rate：33.33%
- Retry Recovery：100.00%
- Outcomes：`{'accepted': 9, 'truncated': 4}`
- Finish reasons：`{'stop': 9, 'length': 4}`
- Max tokens：1800
- Output-limit hits：4
- Empty truncated responses：3
- P50/P95：13092 / 49837 ms
- Diagnosis：观察到的 Planner 重试触发类型：truncated=4。其中 4/4 个截断 attempt 的 output_tokens 达到配置上限 1800，3 个返回空 content。

## 逐次结果

| Rep | Case | Success | Attempts | Outcomes | Latency |
| ---: | --- | --- | ---: | --- | ---: |
| 1 | PR-030 | True | 1 | accepted | 11152 ms |
| 1 | PR-033 | True | 2 | truncated -> accepted | 24321 ms |
| 1 | PR-039 | True | 1 | accepted | 5229 ms |
| 2 | PR-030 | True | 1 | accepted | 13092 ms |
| 2 | PR-033 | True | 1 | accepted | 7736 ms |
| 2 | PR-039 | True | 1 | accepted | 9823 ms |
| 3 | PR-030 | True | 3 | truncated -> truncated -> accepted | 49837 ms |
| 3 | PR-033 | True | 2 | truncated -> accepted | 25807 ms |
| 3 | PR-039 | True | 1 | accepted | 13832 ms |

正式 Diagnostics 不包含 `raw_response`，仅包含响应 SHA256、长度、错误和成本；原始响应只保存在 ignored 路径。
