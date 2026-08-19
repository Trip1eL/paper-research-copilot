# Agent Seed Corpus v1 Chunk 检查报告

- Corpus：`agent-seed-v1` / v1
- Chunking：`chunking_v1`
- 参数：`3200 chars / 400 overlap`
- 生成日期：`2026-08-15`
- 论文 / 页面 / Chunk：10 / 347 / 571

## 全局分布

| Metric | Value |
| --- | ---: |
| Total chars | 1283698 |
| Mean chars | 2248.16 |
| Min chars | 113 |
| P50 chars | 2465 |
| P95 chars | 3177 |
| Max chars | 3199 |
| Short chunks (< 500) | 13 |
| Oversized chunks | 0 |
| Duplicate Chunk IDs | 0 |
| Missing required metadata | 0 |
| Section coverage | 99.65% |

## 逐论文分布

| Paper | Pages | Chunks | Mean chars | Min | Max | Section coverage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| react | 33 | 55 | 2158.67 | 484 | 3191 | 100.00% |
| toolformer | 17 | 34 | 2312.15 | 615 | 3199 | 100.00% |
| reflexion | 19 | 30 | 2128.5 | 113 | 3183 | 100.00% |
| lats | 23 | 42 | 2461.79 | 723 | 3190 | 100.00% |
| memgpt | 13 | 26 | 2398.0 | 519 | 3192 | 100.00% |
| generative-agents | 22 | 57 | 2529.79 | 535 | 3191 | 98.25% |
| voyager | 42 | 59 | 2286.2 | 521 | 3195 | 100.00% |
| camel | 77 | 108 | 2049.09 | 213 | 3188 | 100.00% |
| autogen | 43 | 76 | 2237.51 | 245 | 3199 | 98.68% |
| agentbench | 58 | 84 | 2218.13 | 433 | 3194 | 100.00% |

## 说明

- Chunk 不跨页，页码可以直接用于 Citation。
- Section title 由确定性规则识别，覆盖率不等于准确率，需要抽样检查。
- 本报告只描述 Chunk 分布，不包含 Retrieval 指标或策略优劣结论。
