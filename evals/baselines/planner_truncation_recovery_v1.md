# Planner Truncation Recovery Ablation：planner_truncation_recovery_v1

- Model：`deepseek-v4-flash`
- Prompt：`research_planner_corpus_verification_v2`
- Cases：PR-030, PR-033, PR-039
- Repetitions：3（共 27 Plans）
- Raw trace：`data/agent/planner_truncation_recovery_v1_raw.jsonl`（ignored，不进入 Git）

## 汇总

| Strategy | Quality | Success | Route S/A | Tasks S/A | Facets | Leakage | Retry / Recovery | Truncated | P50 / P95 | Calls | Output Tokens |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| same_1800 | False | 88.89% | 55.56% / 88.89% | 55.56% / 88.89% | 88.89% | 0.00% | 55.56% / 80.00% | 7 | 25052 / 60863 ms | 15 | 19743 |
| compact_1800 | False | 88.89% | 55.56% / 77.78% | 55.56% / 77.78% | 88.89% | 0.00% | 11.11% / 0.00% | 3 | 11685 / 64210 ms | 11 | 14609 |
| same_2400 | True | 100.00% | 66.67% / 100.00% | 66.67% / 100.00% | 100.00% | 0.00% | 44.44% / 100.00% | 5 | 12092 / 68764 ms | 14 | 22373 |

## 推荐

- Strategy：`same_2400`
- Reason：same_2400 通过质量门槛，并按 Retry Rate、P95、Output Tokens、实现复杂度的顺序取得最优排序。
- 本实验未自动修改生产默认配置。

## 逐次结果

| Rep | Case | Strategy | Success | Route | Tasks | Facets | Outcomes | Latency | Tokens |
| ---: | --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: |
| 1 | PR-030 | same_1800 | False | None | 0 | 0% | truncated -> truncated -> truncated | 60863 ms | 7176 |
| 1 | PR-030 | compact_1800 | True | cross_paper | 3 | 100% | accepted | 11342 ms | 1763 |
| 1 | PR-030 | same_2400 | True | cross_paper | 3 | 100% | truncated -> accepted | 48012 ms | 5712 |
| 1 | PR-033 | same_1800 | True | cross_paper | 2 | 100% | truncated -> accepted | 25052 ms | 3479 |
| 1 | PR-033 | compact_1800 | True | cross_paper | 2 | 100% | accepted | 5726 ms | 1162 |
| 1 | PR-033 | same_2400 | True | cross_paper | 2 | 100% | accepted | 11499 ms | 1592 |
| 1 | PR-039 | same_1800 | True | cross_paper | 2 | 100% | truncated -> accepted | 31263 ms | 3890 |
| 1 | PR-039 | compact_1800 | False | None | 0 | 0% | truncated -> truncated -> truncated | 64210 ms | 7259 |
| 1 | PR-039 | same_2400 | True | cross_paper | 2 | 100% | accepted | 9212 ms | 1415 |
| 2 | PR-030 | same_1800 | True | cross_paper | 3 | 100% | accepted | 10384 ms | 1756 |
| 2 | PR-030 | compact_1800 | True | cross_paper | 3 | 100% | accepted | 7172 ms | 1443 |
| 2 | PR-030 | same_2400 | True | cross_paper | 3 | 100% | truncated -> truncated -> accepted | 68764 ms | 8028 |
| 2 | PR-033 | same_1800 | True | cross_paper | 2 | 100% | accepted | 6770 ms | 1217 |
| 2 | PR-033 | compact_1800 | True | cross_paper | 2 | 100% | accepted | 16888 ms | 2287 |
| 2 | PR-033 | same_2400 | True | cross_paper | 2 | 100% | accepted | 4844 ms | 1002 |
| 2 | PR-039 | same_1800 | True | cross_paper | 2 | 100% | accepted | 13530 ms | 1736 |
| 2 | PR-039 | compact_1800 | True | cross_paper | 2 | 100% | accepted | 20929 ms | 2201 |
| 2 | PR-039 | same_2400 | True | cross_paper | 2 | 100% | truncated -> accepted | 37464 ms | 4351 |
| 3 | PR-030 | same_1800 | True | cross_paper | 3 | 100% | truncated -> accepted | 27397 ms | 3856 |
| 3 | PR-030 | compact_1800 | True | single_paper | 1 | 100% | accepted | 10814 ms | 1589 |
| 3 | PR-030 | same_2400 | True | cross_paper | 3 | 100% | truncated -> accepted | 44707 ms | 5418 |
| 3 | PR-033 | same_1800 | True | cross_paper | 2 | 100% | accepted | 12204 ms | 1789 |
| 3 | PR-033 | compact_1800 | True | cross_paper | 2 | 100% | accepted | 13032 ms | 1860 |
| 3 | PR-033 | same_2400 | True | cross_paper | 2 | 100% | accepted | 12092 ms | 1636 |
| 3 | PR-039 | same_1800 | True | cross_paper | 2 | 100% | truncated -> accepted | 25962 ms | 3549 |
| 3 | PR-039 | compact_1800 | True | cross_paper | 2 | 100% | accepted | 11685 ms | 1549 |
| 3 | PR-039 | same_2400 | True | cross_paper | 2 | 100% | accepted | 9033 ms | 1370 |

正式 Diagnostics 不包含 `raw_response`，只保留 SHA256、长度、错误、成本和结构化 Plan；原始响应只保存在 ignored 路径。
