# Retriever Baseline: hybrid_rrf_mmr_known_v1

- 评估日期：`2026-08-16`
- Dataset：`evals/datasets/retrieval_diagnostic_v1.jsonl`（25 cases）
- Corpus：`agent-seed-v1` / v1
- Collection：`agent_seed_v1_bge_m3_chunking_v1`
- Embedding：`BAAI/bge-m3`
- Chunking：`chunking_v1`
- Strategy：`hybrid_rrf_mmr`
- Strategy parameters：`{'bm25_k1': 1.5, 'bm25_b': 0.75, 'tokenizer': 'english_stopwords_porter_stemmer', 'candidate_pool_size': 50, 'rrf_k': 60, 'lambda_mult': 0.85, 'rrf_score_normalization': 'min_max'}`
- First query / subsequent mean：468.23 / 246.39 ms
- P50 / P95 / Max latency：246.96 / 303.87 / 468.23 ms

## 总体指标

| K | Paper Hit | Paper Recall | Complete Papers | Exact Page Hit | Exact Page Recall | Complete Pages | Same-page Redundancy |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 96.00% | 86.00% | 76.00% | 56.00% | 54.00% | 52.00% | 0.00% |
| 3 | 100.00% | 92.00% | 84.00% | 64.00% | 62.00% | 60.00% | 6.67% |
| 5 | 100.00% | 92.00% | 84.00% | 80.00% | 76.00% | 72.00% | 11.20% |
| 10 | 100.00% | 98.00% | 96.00% | 88.00% | 84.00% | 80.00% | 17.20% |

- Paper MRR@10：0.9800
- Exact Page MRR@10：0.6447

## 初步观察

- Top-10 Paper Recall 为 98.00%；完整覆盖率为 96.00%。
- Top-10 Exact Page Recall 为 84.00%；该指标受非穷举页码标注影响，是严格下界。
- Top-10 Same-page Redundancy 为 17.20%。
- 从 Top-5 增加到 Top-10，Paper Recall 变化 +6.00%，Exact Page Recall 变化 +8.00%，同页冗余变化 +6.00%。

## 按问题类型

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cross_paper | 5 | 90.00% | 80.00% | 60.00% | 1.0000 | 0.3050 |
| fact | 6 | 100.00% | 100.00% | 100.00% | 1.0000 | 0.7238 |
| method | 14 | 100.00% | 100.00% | 85.71% | 0.9643 | 0.7321 |

## 按难度

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| easy | 8 | 100.00% | 100.00% | 100.00% | 1.0000 | 0.7750 |
| hard | 5 | 90.00% | 80.00% | 60.00% | 1.0000 | 0.3050 |
| medium | 12 | 100.00% | 100.00% | 83.33% | 0.9583 | 0.6994 |

## 未完整覆盖的 Case

- Paper@10：RD-024
- Exact Page@10：RD-004, RD-016, RD-022, RD-023, RD-024

## 逐题 Top-1

| Case | Type | Top-1 paper | Page | Score | Paper hit | Exact page hit |
| --- | --- | --- | ---: | ---: | --- | --- |
| RD-001 | method | arxiv:2210.03629 | 8 | 0.0315 | True | False |
| RD-002 | fact | arxiv:2210.03629 | 8 | 0.0311 | True | False |
| RD-003 | fact | arxiv:2302.04761 | 11 | 0.0323 | True | False |
| RD-004 | method | arxiv:2302.04761 | 11 | 0.0323 | True | False |
| RD-005 | method | arxiv:2303.11366 | 2 | 0.0309 | True | False |
| RD-006 | fact | arxiv:2303.11366 | 2 | 0.0320 | True | True |
| RD-007 | method | arxiv:2310.04406 | 2 | 0.0328 | True | True |
| RD-008 | fact | arxiv:2310.04406 | 7 | 0.0328 | True | True |
| RD-009 | method | arxiv:2310.08560 | 1 | 0.0328 | True | True |
| RD-010 | method | arxiv:2310.08560 | 3 | 0.0328 | True | True |
| RD-011 | method | arxiv:2304.03442 | 2 | 0.0325 | True | True |
| RD-012 | fact | arxiv:2304.03442 | 15 | 0.0325 | True | True |
| RD-013 | method | arxiv:2305.16291 | 3 | 0.0325 | True | True |
| RD-014 | method | arxiv:2305.16291 | 2 | 0.0320 | True | True |
| RD-015 | method | arxiv:2303.17760 | 5 | 0.0320 | True | False |
| RD-016 | method | arxiv:2308.08155 | 14 | 0.0318 | False | False |
| RD-017 | method | arxiv:2308.08155 | 1 | 0.0323 | True | True |
| RD-018 | method | arxiv:2308.08155 | 3 | 0.0323 | True | True |
| RD-019 | fact | arxiv:2308.03688 | 1 | 0.0325 | True | True |
| RD-020 | method | arxiv:2308.03688 | 3 | 0.0325 | True | True |
| RD-021 | cross_paper | arxiv:2302.04761 | 8 | 0.0320 | True | False |
| RD-022 | cross_paper | arxiv:2310.04406 | 8 | 0.0328 | True | False |
| RD-023 | cross_paper | arxiv:2310.08560 | 5 | 0.0320 | True | False |
| RD-024 | cross_paper | arxiv:2308.08155 | 14 | 0.0325 | True | False |
| RD-025 | cross_paper | arxiv:2305.16291 | 2 | 0.0315 | True | True |

## 口径说明

- Paper Recall 对跨论文问题按目标论文覆盖比例计算。
- Exact Page 要求 `paper_id + page_number` 同时匹配人工标注。
- 标注页不是所有可能相关页面的穷举，因此 Exact Page 指标是严格下界。
- Same-page Redundancy 衡量同一论文同一页的多个 Chunk 占用 Top-K 的比例。
- 本报告没有调用 LLM，也没有使用 LLM-as-a-judge。
