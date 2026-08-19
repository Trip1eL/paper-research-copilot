# Retriever Baseline: hybrid_rrf_discovery_v1

- 评估日期：`2026-08-16`
- Dataset：`evals/datasets/retrieval_discovery_v1.jsonl`（25 cases）
- Corpus：`agent-seed-v1` / v1
- Collection：`agent_seed_v1_bge_m3_chunking_v1`
- Embedding：`BAAI/bge-m3`
- Chunking：`chunking_v1`
- Strategy：`hybrid_rrf`
- Strategy parameters：`{'bm25_k1': 1.5, 'bm25_b': 0.75, 'tokenizer': 'english_stopwords_porter_stemmer', 'candidate_pool_size': 50, 'rrf_k': 60}`
- First query / subsequent mean：470.97 / 253.67 ms
- P50 / P95 / Max latency：243.02 / 333.89 / 470.97 ms

## 总体指标

| K | Paper Hit | Paper Recall | Complete Papers | Exact Page Hit | Exact Page Recall | Complete Pages | Same-page Redundancy |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 100.00% | 90.00% | 80.00% | 72.00% | 64.00% | 56.00% | 0.00% |
| 3 | 100.00% | 92.00% | 84.00% | 88.00% | 78.00% | 68.00% | 9.33% |
| 5 | 100.00% | 96.00% | 92.00% | 96.00% | 90.00% | 84.00% | 10.40% |
| 10 | 100.00% | 100.00% | 100.00% | 100.00% | 96.00% | 92.00% | 16.80% |

- Paper MRR@10：1.0000
- Exact Page MRR@10：0.8170

## 初步观察

- Top-10 Paper Recall 为 100.00%；完整覆盖率为 100.00%。
- Top-10 Exact Page Recall 为 96.00%；该指标受非穷举页码标注影响，是严格下界。
- Top-10 Same-page Redundancy 为 16.80%。
- 从 Top-5 增加到 Top-10，Paper Recall 变化 +4.00%，Exact Page Recall 变化 +6.00%，同页冗余变化 +6.40%。

## 按问题类型

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cross_paper | 5 | 100.00% | 100.00% | 80.00% | 1.0000 | 0.9000 |
| fact | 6 | 100.00% | 100.00% | 100.00% | 1.0000 | 0.7833 |
| method | 14 | 100.00% | 100.00% | 100.00% | 1.0000 | 0.8019 |

## 按难度

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| hard | 11 | 100.00% | 100.00% | 90.91% | 1.0000 | 0.8312 |
| medium | 14 | 100.00% | 100.00% | 100.00% | 1.0000 | 0.8060 |

## 未完整覆盖的 Case

- Paper@10：无
- Exact Page@10：DS-021, DS-022

## 逐题 Top-1

| Case | Type | Top-1 paper | Page | Score | Paper hit | Exact page hit |
| --- | --- | --- | ---: | ---: | --- | --- |
| DS-001 | method | arxiv:2210.03629 | 3 | 0.0317 | True | True |
| DS-002 | fact | arxiv:2210.03629 | 4 | 0.0164 | True | True |
| DS-003 | fact | arxiv:2302.04761 | 11 | 0.0284 | True | False |
| DS-004 | method | arxiv:2302.04761 | 3 | 0.0323 | True | True |
| DS-005 | method | arxiv:2303.11366 | 4 | 0.0323 | True | True |
| DS-006 | fact | arxiv:2303.11366 | 2 | 0.0318 | True | True |
| DS-007 | method | arxiv:2310.04406 | 4 | 0.0328 | True | True |
| DS-008 | fact | arxiv:2310.04406 | 16 | 0.0305 | True | False |
| DS-009 | method | arxiv:2310.08560 | 1 | 0.0328 | True | True |
| DS-010 | method | arxiv:2310.08560 | 3 | 0.0323 | True | True |
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

## 口径说明

- Paper Recall 对跨论文问题按目标论文覆盖比例计算。
- Exact Page 要求 `paper_id + page_number` 同时匹配人工标注。
- 标注页不是所有可能相关页面的穷举，因此 Exact Page 指标是严格下界。
- Same-page Redundancy 衡量同一论文同一页的多个 Chunk 占用 Top-K 的比例。
- 本报告没有调用 LLM，也没有使用 LLM-as-a-judge。
