# Planner Truncation Recovery Ablation：planner_compact_2400_ablation_v1

- Model：`deepseek-v4-flash`
- Prompt：`research_planner_corpus_verification_v2`
- Cases：PR-030, PR-033, PR-039
- Repetitions：3（共 18 Plans）
- Raw trace：`data/agent/planner_compact_2400_ablation_v1_raw.jsonl`（ignored，不进入 Git）

## 汇总

| Strategy | Quality | Success | Route S/A | Tasks S/A | Facets | Leakage | Retry / Recovery | Truncated | P50 / P95 | Calls | Output Tokens |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| same_2400 | False | 100.00% | 66.67% / 88.89% | 55.56% / 77.78% | 100.00% | 0.00% | 0.00% / N/A | 0 | 10156 / 20151 ms | 9 | 9229 |
| compact_2400 | False | 88.89% | 66.67% / 77.78% | 66.67% / 77.78% | 88.89% | 0.00% | 33.33% / 66.67% | 6 | 16261 / 73118 ms | 14 | 25735 |

## 推荐

- Strategy：`none`
- Reason：没有策略通过全部质量门槛；保留当前生产配置，不继续进行同类 Prompt 微调。
- 本实验未自动修改生产默认配置。

## 逐次结果

| Rep | Case | Strategy | Success | Route | Tasks | Facets | Outcomes | Latency | Tokens |
| ---: | --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: |
| 1 | PR-030 | same_2400 | True | cross_paper | 3 | 100% | accepted | 5428 ms | 1145 |
| 1 | PR-030 | compact_2400 | True | single_paper | 1 | 100% | accepted | 9280 ms | 1514 |
| 1 | PR-033 | same_2400 | True | cross_paper | 2 | 100% | accepted | 12228 ms | 1822 |
| 1 | PR-033 | compact_2400 | False | None | 0 | 0% | truncated -> truncated -> truncated | 73118 ms | 9083 |
| 1 | PR-039 | same_2400 | True | cross_paper | 2 | 100% | accepted | 4593 ms | 963 |
| 1 | PR-039 | compact_2400 | True | cross_paper | 2 | 100% | truncated -> accepted | 41891 ms | 5408 |
| 2 | PR-030 | same_2400 | True | cross_paper | 3 | 100% | accepted | 10936 ms | 1827 |
| 2 | PR-030 | compact_2400 | True | cross_paper | 3 | 100% | accepted | 2610 ms | 893 |
| 2 | PR-033 | same_2400 | True | cross_paper | 2 | 100% | accepted | 7816 ms | 1386 |
| 2 | PR-033 | compact_2400 | True | cross_paper | 2 | 100% | truncated -> truncated -> accepted | 70082 ms | 8829 |
| 2 | PR-039 | same_2400 | True | single_paper | 1 | 100% | accepted | 20151 ms | 2562 |
| 2 | PR-039 | compact_2400 | True | single_paper | 1 | 100% | accepted | 18442 ms | 2521 |
| 3 | PR-030 | same_2400 | True | single_paper | 1 | 100% | accepted | 13404 ms | 1869 |
| 3 | PR-030 | compact_2400 | True | cross_paper | 3 | 100% | accepted | 15771 ms | 2262 |
| 3 | PR-033 | same_2400 | True | cross_paper | 3 | 100% | accepted | 7204 ms | 1318 |
| 3 | PR-033 | compact_2400 | True | cross_paper | 2 | 100% | accepted | 9877 ms | 1547 |
| 3 | PR-039 | same_2400 | True | cross_paper | 2 | 100% | accepted | 10156 ms | 1551 |
| 3 | PR-039 | compact_2400 | True | single_paper | 1 | 100% | accepted | 16261 ms | 2149 |

正式 Diagnostics 不包含 `raw_response`，只保留 SHA256、长度、错误、成本和结构化 Plan；原始响应只保存在 ignored 路径。
