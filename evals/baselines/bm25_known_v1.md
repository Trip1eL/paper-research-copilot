# Retriever Baseline: bm25_known_v1

- 评估日期：`2026-08-16`
- Dataset：`evals/datasets/retrieval_diagnostic_v1.jsonl`（25 cases）
- Corpus：`agent-seed-v1` / v1
- Collection：`agent_seed_v1_bge_m3_chunking_v1`
- Embedding：`BAAI/bge-m3`
- Chunking：`chunking_v1`
- Strategy：`bm25`
- Strategy parameters：`{'bm25_k1': 1.5, 'bm25_b': 0.75, 'tokenizer': 'english_stopwords_porter_stemmer'}`
- First query / subsequent mean：0.73 / 0.31 ms
- P50 / P95 / Max latency：0.27 / 0.62 / 0.73 ms

## 总体指标

| K | Paper Hit | Paper Recall | Complete Papers | Exact Page Hit | Exact Page Recall | Complete Pages | Same-page Redundancy |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 100.00% | 90.00% | 80.00% | 36.00% | 36.00% | 36.00% | 0.00% |
| 3 | 100.00% | 90.00% | 80.00% | 56.00% | 54.00% | 52.00% | 5.33% |
| 5 | 100.00% | 92.00% | 84.00% | 64.00% | 60.00% | 56.00% | 13.60% |
| 10 | 100.00% | 94.00% | 88.00% | 76.00% | 70.00% | 64.00% | 18.40% |

- Paper MRR@10：1.0000
- Exact Page MRR@10：0.4808

## 初步观察

- Top-10 Paper Recall 为 94.00%；完整覆盖率为 88.00%。
- Top-10 Exact Page Recall 为 70.00%；该指标受非穷举页码标注影响，是严格下界。
- Top-10 Same-page Redundancy 为 18.40%。
- 从 Top-5 增加到 Top-10，Paper Recall 变化 +2.00%，Exact Page Recall 变化 +10.00%，同页冗余变化 +4.80%。

## 按问题类型

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cross_paper | 5 | 70.00% | 40.00% | 30.00% | 1.0000 | 0.1786 |
| fact | 6 | 100.00% | 100.00% | 83.33% | 1.0000 | 0.5741 |
| method | 14 | 100.00% | 100.00% | 78.57% | 1.0000 | 0.5488 |

## 按难度

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| easy | 8 | 100.00% | 100.00% | 87.50% | 1.0000 | 0.5347 |
| hard | 5 | 70.00% | 40.00% | 30.00% | 1.0000 | 0.1786 |
| medium | 12 | 100.00% | 100.00% | 75.00% | 1.0000 | 0.5708 |

## 未完整覆盖的 Case

- Paper@10：RD-021, RD-022, RD-023
- Exact Page@10：RD-001, RD-002, RD-004, RD-016, RD-021, RD-022, RD-023, RD-024, RD-025

## 逐题 Top-1

| Case | Type | Top-1 paper | Page | Score | Paper hit | Exact page hit |
| --- | --- | --- | ---: | ---: | --- | --- |
| RD-001 | method | arxiv:2210.03629 | 8 | 1.3991 | True | False |
| RD-002 | fact | arxiv:2210.03629 | 8 | 1.3991 | True | False |
| RD-003 | fact | arxiv:2302.04761 | 8 | 3.9748 | True | False |
| RD-004 | method | arxiv:2302.04761 | 8 | 3.9748 | True | False |
| RD-005 | method | arxiv:2303.11366 | 15 | 2.1706 | True | False |
| RD-006 | fact | arxiv:2303.11366 | 9 | 6.5253 | True | False |
| RD-007 | method | arxiv:2310.04406 | 2 | 9.4804 | True | True |
| RD-008 | fact | arxiv:2310.04406 | 7 | 4.9450 | True | True |
| RD-009 | method | arxiv:2310.08560 | 1 | 6.9489 | True | True |
| RD-010 | method | arxiv:2310.08560 | 3 | 5.2183 | True | True |
| RD-011 | method | arxiv:2304.03442 | 13 | 5.2664 | True | False |
| RD-012 | fact | arxiv:2304.03442 | 15 | 4.8951 | True | True |
| RD-013 | method | arxiv:2305.16291 | 8 | 12.7328 | True | False |
| RD-014 | method | arxiv:2305.16291 | 9 | 3.0682 | True | False |
| RD-015 | method | arxiv:2303.17760 | 5 | 7.1814 | True | False |
| RD-016 | method | arxiv:2303.17760 | 53 | 3.0180 | True | False |
| RD-017 | method | arxiv:2308.08155 | 1 | 6.6065 | True | True |
| RD-018 | method | arxiv:2308.08155 | 3 | 3.8120 | True | True |
| RD-019 | fact | arxiv:2308.03688 | 1 | 4.5087 | True | True |
| RD-020 | method | arxiv:2308.03688 | 1 | 4.5087 | True | True |
| RD-021 | cross_paper | arxiv:2302.04761 | 7 | 2.7913 | True | False |
| RD-022 | cross_paper | arxiv:2310.04406 | 8 | 4.7371 | True | False |
| RD-023 | cross_paper | arxiv:2310.08560 | 5 | 3.6537 | True | False |
| RD-024 | cross_paper | arxiv:2308.08155 | 14 | 4.4537 | True | False |
| RD-025 | cross_paper | arxiv:2305.16291 | 9 | 3.0682 | True | False |

## 口径说明

- Paper Recall 对跨论文问题按目标论文覆盖比例计算。
- Exact Page 要求 `paper_id + page_number` 同时匹配人工标注。
- 标注页不是所有可能相关页面的穷举，因此 Exact Page 指标是严格下界。
- Same-page Redundancy 衡量同一论文同一页的多个 Chunk 占用 Top-K 的比例。
- 本报告没有调用 LLM，也没有使用 LLM-as-a-judge。
