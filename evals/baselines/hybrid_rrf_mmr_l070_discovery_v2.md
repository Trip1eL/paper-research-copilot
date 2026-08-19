# Retriever Baseline: hybrid_rrf_mmr_l070_discovery_v2

- 评估日期：`2026-08-17`
- Dataset：`evals/datasets/retrieval_discovery_v2.jsonl`（50 cases）
- Corpus：`agent-seed-v2` / v2
- Collection：`agent_seed_v2_bge_m3_chunking_v1`
- Embedding：`BAAI/bge-m3`
- Chunking：`chunking_v1`
- Strategy：`hybrid_rrf_mmr`
- Strategy parameters：`{'bm25_k1': 1.5, 'bm25_b': 0.75, 'tokenizer': 'english_stopwords_porter_stemmer', 'candidate_pool_size': 50, 'rrf_k': 60, 'lambda_mult': 0.7, 'rrf_score_normalization': 'min_max'}`
- First query / subsequent mean：2848.16 / 426.18 ms
- P50 / P95 / Max latency：405.18 / 609.84 / 2848.16 ms

## 总体指标

| K | Paper Hit | Paper Recall | Complete Papers | Exact Page Hit | Exact Page Recall | Complete Pages | Same-page Redundancy |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 94.00% | 79.17% | 66.00% | 70.00% | 59.67% | 50.00% | 0.00% |
| 3 | 98.00% | 88.33% | 78.00% | 88.00% | 75.17% | 64.00% | 6.00% |
| 5 | 100.00% | 94.83% | 88.00% | 92.00% | 83.33% | 74.00% | 10.80% |
| 10 | 100.00% | 95.83% | 90.00% | 98.00% | 89.83% | 80.00% | 14.40% |

- Paper MRR@10：0.9650
- Exact Page MRR@10：0.8047

## 初步观察

- Top-10 Paper Recall 为 95.83%；完整覆盖率为 90.00%。
- Top-10 Exact Page Recall 为 89.83%；该指标受非穷举页码标注影响，是严格下界。
- Top-10 Same-page Redundancy 为 14.40%。
- 从 Top-5 增加到 Top-10，Paper Recall 变化 +1.00%，Exact Page Recall 变化 +6.50%，同页冗余变化 +3.60%。

## 按问题类型

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cross_paper | 15 | 86.11% | 66.67% | 72.78% | 0.9667 | 0.7972 |
| fact | 9 | 100.00% | 100.00% | 88.89% | 0.8611 | 0.6512 |
| method | 26 | 100.00% | 100.00% | 100.00% | 1.0000 | 0.8622 |

## 按难度

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| hard | 36 | 94.21% | 86.11% | 88.66% | 0.9722 | 0.8052 |
| medium | 14 | 100.00% | 100.00% | 92.86% | 0.9464 | 0.8036 |

## 按 Evaluation Split

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| challenge | 25 | 93.67% | 84.00% | 87.67% | 0.9600 | 0.8028 |
| paired_anchor | 25 | 98.00% | 96.00% | 92.00% | 0.9700 | 0.8067 |

## 未完整覆盖的 Case

- Paper@10：DS-021, DS-041, DS-045, DS-046, DS-049
- Exact Page@10：DS-003, DS-021, DS-022, DS-041, DS-044, DS-045, DS-046, DS-047, DS-049, DS-050

## 逐题 Top-1

| Case | Type | Top-1 paper | Page | Score | Paper hit | Exact page hit |
| --- | --- | --- | ---: | ---: | --- | --- |
| DS-001 | method | arxiv:2210.03629 | 3 | 0.0315 | True | True |
| DS-002 | fact | arxiv:2210.03629 | 4 | 0.0164 | True | True |
| DS-003 | fact | arxiv:2305.15334 | 9 | 0.0267 | False | False |
| DS-004 | method | arxiv:2302.04761 | 3 | 0.0323 | True | True |
| DS-005 | method | arxiv:2303.11366 | 4 | 0.0323 | True | True |
| DS-006 | fact | arxiv:2303.11366 | 2 | 0.0318 | True | True |
| DS-007 | method | arxiv:2310.04406 | 4 | 0.0328 | True | True |
| DS-008 | fact | arxiv:2310.04406 | 16 | 0.0299 | True | False |
| DS-009 | method | arxiv:2310.08560 | 1 | 0.0328 | True | True |
| DS-010 | method | arxiv:2310.08560 | 3 | 0.0315 | True | True |
| DS-011 | method | arxiv:2304.03442 | 2 | 0.0323 | True | True |
| DS-012 | fact | arxiv:2304.03442 | 15 | 0.0328 | True | True |
| DS-013 | method | arxiv:2305.16291 | 3 | 0.0325 | True | True |
| DS-014 | method | arxiv:2305.16291 | 6 | 0.0320 | True | False |
| DS-015 | method | arxiv:2303.17760 | 5 | 0.0328 | True | False |
| DS-016 | method | arxiv:2303.17760 | 5 | 0.0325 | True | False |
| DS-017 | method | arxiv:2308.08155 | 2 | 0.0323 | True | True |
| DS-018 | method | arxiv:2308.08155 | 5 | 0.0317 | True | False |
| DS-019 | fact | arxiv:2308.03688 | 1 | 0.0164 | True | True |
| DS-020 | method | arxiv:2308.03688 | 1 | 0.0164 | True | True |
| DS-021 | cross_paper | arxiv:2302.04761 | 3 | 0.0328 | True | True |
| DS-022 | cross_paper | arxiv:2310.04406 | 4 | 0.0328 | True | True |
| DS-023 | cross_paper | arxiv:2310.08560 | 1 | 0.0325 | True | True |
| DS-024 | cross_paper | arxiv:2303.17760 | 5 | 0.0328 | True | False |
| DS-025 | cross_paper | arxiv:2305.16291 | 3 | 0.0328 | True | True |
| DS-026 | method | arxiv:2205.00445 | 4 | 0.0328 | True | True |
| DS-027 | method | arxiv:2303.17651 | 4 | 0.0304 | True | True |
| DS-028 | method | arxiv:2305.10601 | 4 | 0.0325 | True | True |
| DS-029 | method | arxiv:2305.10250 | 9 | 0.0325 | True | False |
| DS-030 | method | arxiv:2303.17580 | 5 | 0.0323 | True | True |
| DS-031 | method | arxiv:2305.15334 | 5 | 0.0328 | True | True |
| DS-032 | method | arxiv:2307.16789 | 1 | 0.0320 | True | True |
| DS-033 | method | arxiv:2308.10848 | 3 | 0.0328 | True | True |
| DS-034 | method | arxiv:2308.00352 | 2 | 0.0328 | True | True |
| DS-035 | method | arxiv:2307.13854 | 2 | 0.0328 | True | True |
| DS-036 | method | arxiv:2303.17651 | 9 | 0.0328 | True | False |
| DS-037 | fact | arxiv:2305.10601 | 4 | 0.0325 | True | True |
| DS-038 | method | arxiv:2307.16789 | 6 | 0.0325 | True | True |
| DS-039 | fact | arxiv:2308.10848 | 2 | 0.0328 | True | False |
| DS-040 | fact | arxiv:2308.00352 | 25 | 0.0320 | False | False |
| DS-041 | cross_paper | arxiv:2303.11366 | 2 | 0.0328 | True | True |
| DS-042 | cross_paper | arxiv:2305.10601 | 4 | 0.0325 | True | True |
| DS-043 | cross_paper | arxiv:2310.08560 | 1 | 0.0328 | True | True |
| DS-044 | cross_paper | arxiv:2205.00445 | 4 | 0.0301 | True | True |
| DS-045 | cross_paper | arxiv:2302.04761 | 3 | 0.0325 | True | True |
| DS-046 | cross_paper | arxiv:2303.17760 | 5 | 0.0328 | True | False |
| DS-047 | cross_paper | arxiv:2307.13854 | 9 | 0.0164 | True | False |
| DS-048 | cross_paper | arxiv:2304.03442 | 8 | 0.0313 | True | False |
| DS-049 | cross_paper | arxiv:2303.17760 | 3 | 0.0315 | False | False |
| DS-050 | cross_paper | arxiv:2205.00445 | 4 | 0.0307 | True | True |

## 口径说明

- Paper Recall 对跨论文问题按目标论文覆盖比例计算。
- Exact Page 要求 `paper_id + page_number` 同时匹配人工标注。
- 标注页不是所有可能相关页面的穷举，因此 Exact Page 指标是严格下界。
- Same-page Redundancy 衡量同一论文同一页的多个 Chunk 占用 Top-K 的比例。
- 本报告没有调用 LLM，也没有使用 LLM-as-a-judge。
