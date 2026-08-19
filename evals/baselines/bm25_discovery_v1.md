# Retriever Baseline: bm25_discovery_v1

- 评估日期：`2026-08-16`
- Dataset：`evals/datasets/retrieval_discovery_v1.jsonl`（25 cases）
- Corpus：`agent-seed-v1` / v1
- Collection：`agent_seed_v1_bge_m3_chunking_v1`
- Embedding：`BAAI/bge-m3`
- Chunking：`chunking_v1`
- Strategy：`bm25`
- Strategy parameters：`{'bm25_k1': 1.5, 'bm25_b': 0.75, 'tokenizer': 'english_stopwords_porter_stemmer'}`
- First query / subsequent mean：1.66 / 0.35 ms
- P50 / P95 / Max latency：0.31 / 0.55 / 1.66 ms

## 总体指标

| K | Paper Hit | Paper Recall | Complete Papers | Exact Page Hit | Exact Page Recall | Complete Pages | Same-page Redundancy |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 80.00% | 70.00% | 60.00% | 44.00% | 36.00% | 28.00% | 0.00% |
| 3 | 84.00% | 74.00% | 64.00% | 72.00% | 62.00% | 52.00% | 8.00% |
| 5 | 88.00% | 84.00% | 80.00% | 84.00% | 74.00% | 64.00% | 10.40% |
| 10 | 88.00% | 88.00% | 88.00% | 88.00% | 82.00% | 76.00% | 13.20% |

- Paper MRR@10：0.8300
- Exact Page MRR@10：0.5853

## 初步观察

- Top-10 Paper Recall 为 88.00%；完整覆盖率为 88.00%。
- Top-10 Exact Page Recall 为 82.00%；该指标受非穷举页码标注影响，是严格下界。
- Top-10 Same-page Redundancy 为 13.20%。
- 从 Top-5 增加到 Top-10，Paper Recall 变化 +4.00%，Exact Page Recall 变化 +8.00%，同页冗余变化 +2.80%。

## 按问题类型

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cross_paper | 5 | 100.00% | 100.00% | 70.00% | 1.0000 | 0.8667 |
| fact | 6 | 66.67% | 66.67% | 66.67% | 0.5417 | 0.4306 |
| method | 14 | 92.86% | 92.86% | 92.86% | 0.8929 | 0.5512 |

## 按难度

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| hard | 11 | 81.82% | 81.82% | 68.18% | 0.7045 | 0.5015 |
| medium | 14 | 92.86% | 92.86% | 92.86% | 0.9286 | 0.6512 |

## 未完整覆盖的 Case

- Paper@10：DS-002, DS-019, DS-020
- Exact Page@10：DS-002, DS-019, DS-020, DS-021, DS-022, DS-024

## 逐题 Top-1

| Case | Type | Top-1 paper | Page | Score | Paper hit | Exact page hit |
| --- | --- | --- | ---: | ---: | --- | --- |
| DS-001 | method | arxiv:2210.03629 | 26 | 3.5312 | True | False |
| DS-002 | fact | - | - | - | False | False |
| DS-003 | fact | arxiv:2302.04761 | 2 | 1.6321 | True | True |
| DS-004 | method | arxiv:2302.04761 | 3 | 6.3750 | True | True |
| DS-005 | method | arxiv:2303.11366 | 4 | 7.4910 | True | True |
| DS-006 | fact | arxiv:2303.11366 | 9 | 4.6514 | True | False |
| DS-007 | method | arxiv:2310.04406 | 4 | 11.6284 | True | True |
| DS-008 | fact | arxiv:2303.11366 | 8 | 2.6459 | False | False |
| DS-009 | method | arxiv:2310.08560 | 1 | 6.2195 | True | True |
| DS-010 | method | arxiv:2308.08155 | 5 | 2.6597 | False | False |
| DS-011 | method | arxiv:2304.03442 | 13 | 7.2551 | True | False |
| DS-012 | fact | arxiv:2304.03442 | 15 | 3.5400 | True | True |
| DS-013 | method | arxiv:2305.16291 | 8 | 9.9881 | True | False |
| DS-014 | method | arxiv:2305.16291 | 39 | 5.4061 | True | False |
| DS-015 | method | arxiv:2303.17760 | 5 | 9.7171 | True | False |
| DS-016 | method | arxiv:2303.17760 | 5 | 0.8002 | True | False |
| DS-017 | method | arxiv:2308.08155 | 1 | 4.6111 | True | True |
| DS-018 | method | arxiv:2308.08155 | 25 | 4.9514 | True | False |
| DS-019 | fact | - | - | - | False | False |
| DS-020 | method | - | - | - | False | False |
| DS-021 | cross_paper | arxiv:2302.04761 | 3 | 6.3750 | True | True |
| DS-022 | cross_paper | arxiv:2310.04406 | 4 | 10.0032 | True | True |
| DS-023 | cross_paper | arxiv:2310.08560 | 2 | 7.3821 | True | True |
| DS-024 | cross_paper | arxiv:2303.17760 | 5 | 7.5553 | True | False |
| DS-025 | cross_paper | arxiv:2305.16291 | 3 | 8.4611 | True | True |

## 口径说明

- Paper Recall 对跨论文问题按目标论文覆盖比例计算。
- Exact Page 要求 `paper_id + page_number` 同时匹配人工标注。
- 标注页不是所有可能相关页面的穷举，因此 Exact Page 指标是严格下界。
- Same-page Redundancy 衡量同一论文同一页的多个 Chunk 占用 Top-K 的比例。
- 本报告没有调用 LLM，也没有使用 LLM-as-a-judge。
