# Retriever Baseline: dense_discovery_v2

- 评估日期：`2026-08-17`
- Dataset：`evals/datasets/retrieval_discovery_v2.jsonl`（50 cases）
- Corpus：`agent-seed-v2` / v2
- Collection：`agent_seed_v2_bge_m3_chunking_v1`
- Embedding：`BAAI/bge-m3`
- Chunking：`chunking_v1`
- Strategy：`dense`
- Strategy parameters：`{}`
- First query / subsequent mean：423.64 / 287.15 ms
- P50 / P95 / Max latency：267.24 / 306.95 / 1272.06 ms

## 总体指标

| K | Paper Hit | Paper Recall | Complete Papers | Exact Page Hit | Exact Page Recall | Complete Pages | Same-page Redundancy |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 88.00% | 74.17% | 62.00% | 60.00% | 53.00% | 46.00% | 0.00% |
| 3 | 94.00% | 86.33% | 78.00% | 84.00% | 74.83% | 66.00% | 8.00% |
| 5 | 98.00% | 90.33% | 82.00% | 92.00% | 84.33% | 76.00% | 10.00% |
| 10 | 98.00% | 95.50% | 92.00% | 94.00% | 87.83% | 80.00% | 12.80% |

- Paper MRR@10：0.9200
- Exact Page MRR@10：0.7190

## 初步观察

- Top-10 Paper Recall 为 95.50%；完整覆盖率为 92.00%。
- Top-10 Exact Page Recall 为 87.83%；该指标受非穷举页码标注影响，是严格下界。
- Top-10 Same-page Redundancy 为 12.80%。
- 从 Top-5 增加到 Top-10，Paper Recall 变化 +5.17%，Exact Page Recall 变化 +3.50%，同页冗余变化 +2.80%。

## 按问题类型

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cross_paper | 15 | 85.00% | 73.33% | 66.11% | 0.8833 | 0.6289 |
| fact | 9 | 100.00% | 100.00% | 88.89% | 0.8889 | 0.6556 |
| method | 26 | 100.00% | 100.00% | 100.00% | 0.9519 | 0.7929 |

## 按难度

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| hard | 36 | 93.75% | 88.89% | 83.10% | 0.9236 | 0.7259 |
| medium | 14 | 100.00% | 100.00% | 100.00% | 0.9107 | 0.7012 |

## 按 Evaluation Split

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| challenge | 25 | 93.00% | 88.00% | 85.67% | 0.8900 | 0.6920 |
| paired_anchor | 25 | 98.00% | 96.00% | 90.00% | 0.9500 | 0.7460 |

## 未完整覆盖的 Case

- Paper@10：DS-021, DS-044, DS-046, DS-049
- Exact Page@10：DS-008, DS-021, DS-022, DS-023, DS-044, DS-045, DS-046, DS-047, DS-049, DS-050

## 逐题 Top-1

| Case | Type | Top-1 paper | Page | Score | Paper hit | Exact page hit |
| --- | --- | --- | ---: | ---: | --- | --- |
| DS-001 | method | arxiv:2304.03442 | 13 | 0.6381 | False | False |
| DS-002 | fact | arxiv:2210.03629 | 4 | 0.5895 | True | True |
| DS-003 | fact | arxiv:2305.15334 | 1 | 0.6251 | False | False |
| DS-004 | method | arxiv:2302.04761 | 11 | 0.6316 | True | False |
| DS-005 | method | arxiv:2303.11366 | 2 | 0.6695 | True | False |
| DS-006 | fact | arxiv:2303.11366 | 2 | 0.5983 | True | True |
| DS-007 | method | arxiv:2310.04406 | 4 | 0.6418 | True | True |
| DS-008 | fact | arxiv:2310.04406 | 16 | 0.6030 | True | False |
| DS-009 | method | arxiv:2310.08560 | 1 | 0.5788 | True | True |
| DS-010 | method | arxiv:2310.08560 | 1 | 0.6223 | True | True |
| DS-011 | method | arxiv:2304.03442 | 2 | 0.6208 | True | True |
| DS-012 | fact | arxiv:2304.03442 | 15 | 0.5585 | True | True |
| DS-013 | method | arxiv:2305.16291 | 3 | 0.5741 | True | True |
| DS-014 | method | arxiv:2305.16291 | 2 | 0.6293 | True | True |
| DS-015 | method | arxiv:2303.17760 | 5 | 0.6839 | True | False |
| DS-016 | method | arxiv:2303.17760 | 7 | 0.6420 | True | False |
| DS-017 | method | arxiv:2308.08155 | 2 | 0.6751 | True | True |
| DS-018 | method | arxiv:2308.08155 | 2 | 0.6343 | True | False |
| DS-019 | fact | arxiv:2308.03688 | 1 | 0.5926 | True | True |
| DS-020 | method | arxiv:2308.03688 | 1 | 0.5933 | True | True |
| DS-021 | cross_paper | arxiv:2302.04761 | 3 | 0.6026 | True | True |
| DS-022 | cross_paper | arxiv:2310.04406 | 4 | 0.6046 | True | True |
| DS-023 | cross_paper | arxiv:2310.08560 | 1 | 0.5924 | True | True |
| DS-024 | cross_paper | arxiv:2303.17760 | 5 | 0.6370 | True | False |
| DS-025 | cross_paper | arxiv:2305.16291 | 3 | 0.5824 | True | True |
| DS-026 | method | arxiv:2205.00445 | 4 | 0.5982 | True | True |
| DS-027 | method | arxiv:2303.17651 | 2 | 0.6757 | True | True |
| DS-028 | method | arxiv:2305.10601 | 4 | 0.5731 | True | True |
| DS-029 | method | arxiv:2305.10250 | 4 | 0.7354 | True | True |
| DS-030 | method | arxiv:2303.17580 | 5 | 0.6294 | True | True |
| DS-031 | method | arxiv:2305.15334 | 5 | 0.6547 | True | True |
| DS-032 | method | arxiv:2305.15334 | 3 | 0.6124 | False | False |
| DS-033 | method | arxiv:2308.10848 | 3 | 0.6363 | True | True |
| DS-034 | method | arxiv:2308.00352 | 2 | 0.5586 | True | True |
| DS-035 | method | arxiv:2307.13854 | 2 | 0.5880 | True | True |
| DS-036 | method | arxiv:2303.17651 | 9 | 0.6335 | True | False |
| DS-037 | fact | arxiv:2305.10601 | 4 | 0.6507 | True | True |
| DS-038 | method | arxiv:2307.16789 | 5 | 0.6203 | True | True |
| DS-039 | fact | arxiv:2308.10848 | 2 | 0.5237 | True | False |
| DS-040 | fact | arxiv:2308.00352 | 24 | 0.6428 | False | False |
| DS-041 | cross_paper | arxiv:2303.11366 | 2 | 0.6387 | True | True |
| DS-042 | cross_paper | arxiv:2310.04406 | 4 | 0.6528 | True | True |
| DS-043 | cross_paper | arxiv:2310.08560 | 1 | 0.6161 | True | True |
| DS-044 | cross_paper | arxiv:2308.10848 | 16 | 0.5543 | False | False |
| DS-045 | cross_paper | arxiv:2305.15334 | 8 | 0.6149 | True | False |
| DS-046 | cross_paper | arxiv:2303.17760 | 5 | 0.6570 | True | False |
| DS-047 | cross_paper | arxiv:2307.13854 | 9 | 0.5907 | True | False |
| DS-048 | cross_paper | arxiv:2304.03442 | 8 | 0.6023 | True | False |
| DS-049 | cross_paper | arxiv:2303.17760 | 3 | 0.6221 | False | False |
| DS-050 | cross_paper | arxiv:2305.15334 | 9 | 0.5735 | True | False |

## 口径说明

- Paper Recall 对跨论文问题按目标论文覆盖比例计算。
- Exact Page 要求 `paper_id + page_number` 同时匹配人工标注。
- 标注页不是所有可能相关页面的穷举，因此 Exact Page 指标是严格下界。
- Same-page Redundancy 衡量同一论文同一页的多个 Chunk 占用 Top-K 的比例。
- 本报告没有调用 LLM，也没有使用 LLM-as-a-judge。
