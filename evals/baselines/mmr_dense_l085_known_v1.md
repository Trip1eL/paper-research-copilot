# Retriever Baseline: mmr_dense_l085_known_v1

- 评估日期：`2026-08-16`
- Dataset：`evals/datasets/retrieval_diagnostic_v1.jsonl`（25 cases）
- Corpus：`agent-seed-v1` / v1
- Collection：`agent_seed_v1_bge_m3_chunking_v1`
- Embedding：`BAAI/bge-m3`
- Chunking：`chunking_v1`
- Strategy：`mmr_dense`
- Strategy parameters：`{'candidate_pool_size': 50, 'lambda_mult': 0.85}`
- First query / subsequent mean：458.54 / 245.91 ms
- P50 / P95 / Max latency：246.13 / 298.76 / 458.54 ms

## 总体指标

| K | Paper Hit | Paper Recall | Complete Papers | Exact Page Hit | Exact Page Recall | Complete Pages | Same-page Redundancy |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 96.00% | 86.00% | 76.00% | 68.00% | 62.00% | 56.00% | 0.00% |
| 3 | 100.00% | 98.00% | 96.00% | 80.00% | 74.00% | 68.00% | 6.67% |
| 5 | 100.00% | 98.00% | 96.00% | 88.00% | 82.00% | 76.00% | 8.80% |
| 10 | 100.00% | 98.00% | 96.00% | 92.00% | 84.00% | 76.00% | 16.40% |

- Paper MRR@10：0.9800
- Exact Page MRR@10：0.7560

## 初步观察

- Top-10 Paper Recall 为 98.00%；完整覆盖率为 96.00%。
- Top-10 Exact Page Recall 为 84.00%；该指标受非穷举页码标注影响，是严格下界。
- Top-10 Same-page Redundancy 为 16.40%。
- 从 Top-5 增加到 Top-10，Paper Recall 变化 +0.00%，Exact Page Recall 变化 +2.00%，同页冗余变化 +7.60%。

## 按问题类型

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cross_paper | 5 | 90.00% | 80.00% | 60.00% | 1.0000 | 0.6733 |
| fact | 6 | 100.00% | 100.00% | 100.00% | 1.0000 | 0.7000 |
| method | 14 | 100.00% | 100.00% | 85.71% | 0.9643 | 0.8095 |

## 按难度

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| easy | 8 | 100.00% | 100.00% | 100.00% | 1.0000 | 0.9375 |
| hard | 5 | 90.00% | 80.00% | 60.00% | 1.0000 | 0.6733 |
| medium | 12 | 100.00% | 100.00% | 83.33% | 0.9583 | 0.6694 |

## 未完整覆盖的 Case

- Paper@10：RD-024
- Exact Page@10：RD-004, RD-016, RD-021, RD-022, RD-023, RD-024

## 逐题 Top-1

| Case | Type | Top-1 paper | Page | Score | Paper hit | Exact page hit |
| --- | --- | --- | ---: | ---: | --- | --- |
| RD-001 | method | arxiv:2210.03629 | 3 | 0.6949 | True | True |
| RD-002 | fact | arxiv:2210.03629 | 3 | 0.6520 | True | False |
| RD-003 | fact | arxiv:2302.04761 | 11 | 0.6752 | True | False |
| RD-004 | method | arxiv:2302.04761 | 11 | 0.6453 | True | False |
| RD-005 | method | arxiv:2303.11366 | 2 | 0.7993 | True | False |
| RD-006 | fact | arxiv:2303.11366 | 2 | 0.6840 | True | True |
| RD-007 | method | arxiv:2310.04406 | 2 | 0.7665 | True | True |
| RD-008 | fact | arxiv:2310.04406 | 7 | 0.6857 | True | True |
| RD-009 | method | arxiv:2310.08560 | 1 | 0.6947 | True | True |
| RD-010 | method | arxiv:2310.08560 | 3 | 0.6566 | True | True |
| RD-011 | method | arxiv:2304.03442 | 2 | 0.6820 | True | True |
| RD-012 | fact | arxiv:2304.03442 | 13 | 0.6741 | True | False |
| RD-013 | method | arxiv:2305.16291 | 3 | 0.7200 | True | True |
| RD-014 | method | arxiv:2305.16291 | 2 | 0.6204 | True | True |
| RD-015 | method | arxiv:2303.17760 | 3 | 0.6378 | True | True |
| RD-016 | method | arxiv:2308.08155 | 14 | 0.6937 | False | False |
| RD-017 | method | arxiv:2308.08155 | 3 | 0.7089 | True | True |
| RD-018 | method | arxiv:2308.08155 | 3 | 0.7554 | True | True |
| RD-019 | fact | arxiv:2308.03688 | 2 | 0.7528 | True | True |
| RD-020 | method | arxiv:2308.03688 | 3 | 0.6564 | True | True |
| RD-021 | cross_paper | arxiv:2210.03629 | 3 | 0.5871 | True | True |
| RD-022 | cross_paper | arxiv:2310.04406 | 8 | 0.7025 | True | False |
| RD-023 | cross_paper | arxiv:2304.03442 | 8 | 0.6287 | True | False |
| RD-024 | cross_paper | arxiv:2308.08155 | 2 | 0.7056 | True | True |
| RD-025 | cross_paper | arxiv:2305.16291 | 2 | 0.5813 | True | True |

## 口径说明

- Paper Recall 对跨论文问题按目标论文覆盖比例计算。
- Exact Page 要求 `paper_id + page_number` 同时匹配人工标注。
- 标注页不是所有可能相关页面的穷举，因此 Exact Page 指标是严格下界。
- Same-page Redundancy 衡量同一论文同一页的多个 Chunk 占用 Top-K 的比例。
- 本报告没有调用 LLM，也没有使用 LLM-as-a-judge。
