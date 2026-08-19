# Retriever Baseline: reranker_fast_bge_v2

- 评估日期：`2026-08-17`
- Dataset：`evals/datasets/retrieval_discovery_v2.jsonl`（50 cases）
- Corpus：`agent-seed-v2` / v2
- Collection：`agent_seed_v2_bge_m3_chunking_v1`
- Embedding：`BAAI/bge-m3`
- Chunking：`chunking_v1`
- Strategy：`reranker_fast_bge`
- Strategy parameters：`{'candidate_pool_size': 50, 'rrf_k': 60, 'fusion': 'original_query_rrf', 'query_rewrite': False, 'reranker': True, 'reranker_model': 'BAAI/bge-reranker-v2-m3', 'reranker_mean_ms': 1394.26}`
- First query / subsequent mean：1955.96 / 1756.11 ms
- P50 / P95 / Max latency：1748.11 / 1955.96 / 2217.12 ms

## 总体指标

| K | Paper Hit | Paper Recall | Complete Papers | Exact Page Hit | Exact Page Recall | Complete Pages | Same-page Redundancy |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 98.00% | 83.17% | 70.00% | 72.00% | 60.67% | 50.00% | 0.00% |
| 3 | 100.00% | 88.17% | 78.00% | 96.00% | 84.17% | 74.00% | 5.33% |
| 5 | 100.00% | 97.00% | 94.00% | 98.00% | 90.17% | 84.00% | 10.40% |
| 10 | 100.00% | 98.50% | 96.00% | 100.00% | 98.00% | 96.00% | 15.40% |

- Paper MRR@10：0.9900
- Exact Page MRR@10：0.8412

## 初步观察

- Top-10 Paper Recall 为 98.50%；完整覆盖率为 96.00%。
- Top-10 Exact Page Recall 为 98.00%；该指标受非穷举页码标注影响，是严格下界。
- Top-10 Same-page Redundancy 为 15.40%。
- 从 Top-5 增加到 Top-10，Paper Recall 变化 +1.50%，Exact Page Recall 变化 +7.83%，同页冗余变化 +5.00%。

## 按问题类型

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cross_paper | 15 | 95.00% | 86.67% | 93.33% | 0.9667 | 0.8500 |
| fact | 9 | 100.00% | 100.00% | 100.00% | 1.0000 | 0.7381 |
| method | 26 | 100.00% | 100.00% | 100.00% | 1.0000 | 0.8718 |

## 按难度

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| hard | 36 | 97.92% | 94.44% | 97.22% | 0.9861 | 0.8720 |
| medium | 14 | 100.00% | 100.00% | 100.00% | 1.0000 | 0.7619 |

## 按 Evaluation Split

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| challenge | 25 | 99.00% | 96.00% | 98.00% | 0.9800 | 0.8700 |
| paired_anchor | 25 | 98.00% | 96.00% | 98.00% | 1.0000 | 0.8124 |

## 未完整覆盖的 Case

- Paper@10：DS-021, DS-046
- Exact Page@10：DS-021, DS-046

## 逐题 Top-1

| Case | Type | Top-1 paper | Page | Score | Paper hit | Exact page hit |
| --- | --- | --- | ---: | ---: | --- | --- |
| DS-001 | method | arxiv:2210.03629 | 2 | 0.9570 | True | True |
| DS-002 | fact | arxiv:2210.03629 | 2 | 0.2655 | True | False |
| DS-003 | fact | arxiv:2302.04761 | 1 | 0.9842 | True | True |
| DS-004 | method | arxiv:2302.04761 | 2 | 0.9645 | True | True |
| DS-005 | method | arxiv:2303.11366 | 2 | 0.9429 | True | False |
| DS-006 | fact | arxiv:2303.11366 | 2 | 0.9016 | True | True |
| DS-007 | method | arxiv:2310.04406 | 4 | 0.9900 | True | True |
| DS-008 | fact | arxiv:2310.04406 | 1 | 0.9756 | True | True |
| DS-009 | method | arxiv:2310.08560 | 1 | 0.8917 | True | True |
| DS-010 | method | arxiv:2310.08560 | 3 | 0.5854 | True | True |
| DS-011 | method | arxiv:2304.03442 | 13 | 0.8874 | True | False |
| DS-012 | fact | arxiv:2304.03442 | 13 | 0.6381 | True | False |
| DS-013 | method | arxiv:2305.16291 | 2 | 0.9945 | True | True |
| DS-014 | method | arxiv:2305.16291 | 1 | 0.9965 | True | False |
| DS-015 | method | arxiv:2303.17760 | 7 | 0.9815 | True | False |
| DS-016 | method | arxiv:2303.17760 | 2 | 0.8223 | True | True |
| DS-017 | method | arxiv:2308.08155 | 2 | 0.9749 | True | True |
| DS-018 | method | arxiv:2308.08155 | 16 | 0.8576 | True | False |
| DS-019 | fact | arxiv:2308.03688 | 1 | 0.9760 | True | True |
| DS-020 | method | arxiv:2308.03688 | 1 | 0.9704 | True | True |
| DS-021 | cross_paper | arxiv:2302.04761 | 2 | 0.8229 | True | True |
| DS-022 | cross_paper | arxiv:2303.11366 | 2 | 0.7397 | True | False |
| DS-023 | cross_paper | arxiv:2310.08560 | 2 | 0.6268 | True | True |
| DS-024 | cross_paper | arxiv:2303.17760 | 2 | 0.8769 | True | True |
| DS-025 | cross_paper | arxiv:2305.16291 | 2 | 0.8666 | True | True |
| DS-026 | method | arxiv:2205.00445 | 4 | 0.9620 | True | True |
| DS-027 | method | arxiv:2303.17651 | 2 | 0.9877 | True | True |
| DS-028 | method | arxiv:2305.10601 | 4 | 0.9242 | True | True |
| DS-029 | method | arxiv:2305.10250 | 2 | 0.9941 | True | True |
| DS-030 | method | arxiv:2303.17580 | 4 | 0.9777 | True | True |
| DS-031 | method | arxiv:2305.15334 | 2 | 0.9859 | True | True |
| DS-032 | method | arxiv:2307.16789 | 1 | 0.9987 | True | True |
| DS-033 | method | arxiv:2308.10848 | 3 | 0.9946 | True | True |
| DS-034 | method | arxiv:2308.00352 | 4 | 0.8944 | True | True |
| DS-035 | method | arxiv:2307.13854 | 1 | 0.9275 | True | True |
| DS-036 | method | arxiv:2303.17651 | 9 | 0.8862 | True | False |
| DS-037 | fact | arxiv:2305.10601 | 14 | 0.9796 | True | False |
| DS-038 | method | arxiv:2307.16789 | 3 | 0.9807 | True | True |
| DS-039 | fact | arxiv:2308.10848 | 7 | 0.8257 | True | True |
| DS-040 | fact | arxiv:2307.13854 | 1 | 0.9974 | True | False |
| DS-041 | cross_paper | arxiv:2303.11366 | 2 | 0.7585 | True | True |
| DS-042 | cross_paper | arxiv:2310.04406 | 4 | 0.9619 | True | True |
| DS-043 | cross_paper | arxiv:2310.08560 | 1 | 0.8210 | True | True |
| DS-044 | cross_paper | arxiv:2307.16789 | 9 | 0.1165 | False | False |
| DS-045 | cross_paper | arxiv:2302.04761 | 2 | 0.5735 | True | True |
| DS-046 | cross_paper | arxiv:2303.17760 | 7 | 0.6489 | True | False |
| DS-047 | cross_paper | arxiv:2307.13854 | 9 | 0.7909 | True | False |
| DS-048 | cross_paper | arxiv:2304.03442 | 2 | 0.8020 | True | True |
| DS-049 | cross_paper | arxiv:2303.17580 | 2 | 0.9706 | True | True |
| DS-050 | cross_paper | arxiv:2205.00445 | 4 | 0.8836 | True | True |

## 口径说明

- Paper Recall 对跨论文问题按目标论文覆盖比例计算。
- Exact Page 要求 `paper_id + page_number` 同时匹配人工标注。
- 标注页不是所有可能相关页面的穷举，因此 Exact Page 指标是严格下界。
- Same-page Redundancy 衡量同一论文同一页的多个 Chunk 占用 Top-K 的比例。
- 本报告没有调用 LLM，也没有使用 LLM-as-a-judge。
