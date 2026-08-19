# Retriever Baseline: query_fusion_max_over_query_v2

- 评估日期：`2026-08-17`
- Dataset：`evals/datasets/retrieval_discovery_v2.jsonl`（50 cases）
- Corpus：`agent-seed-v2` / v2
- Collection：`agent_seed_v2_bge_m3_chunking_v1`
- Embedding：`BAAI/bge-m3`
- Chunking：`chunking_v1`
- Strategy：`max_over_query_rrf`
- Strategy parameters：`{'candidate_pool_size': 50, 'rrf_k': 60, 'shared_branch_rankings': True, 'fusion_mean_ms': 0.4634, 'rewrite_model': 'deepseek-v4-flash', 'rewrite_prompt_version': 'query_rewrite_v1', 'rewrite_title_leak_hits': 0}`
- First query / subsequent mean：1570.16 / 1427.89 ms
- P50 / P95 / Max latency：1402.9 / 1674.78 / 1961.48 ms

## 总体指标

| K | Paper Hit | Paper Recall | Complete Papers | Exact Page Hit | Exact Page Recall | Complete Pages | Same-page Redundancy |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 100.00% | 84.17% | 70.00% | 66.00% | 54.67% | 44.00% | 0.00% |
| 3 | 100.00% | 95.00% | 90.00% | 94.00% | 85.33% | 76.00% | 9.33% |
| 5 | 100.00% | 96.50% | 92.00% | 96.00% | 89.83% | 82.00% | 11.20% |
| 10 | 100.00% | 99.00% | 98.00% | 100.00% | 97.00% | 94.00% | 16.00% |

- Paper MRR@10：1.0000
- Exact Page MRR@10：0.8055

## 初步观察

- Top-10 Paper Recall 为 99.00%；完整覆盖率为 98.00%。
- Top-10 Exact Page Recall 为 97.00%；该指标受非穷举页码标注影响，是严格下界。
- Top-10 Same-page Redundancy 为 16.00%。
- 从 Top-5 增加到 Top-10，Paper Recall 变化 +2.50%，Exact Page Recall 变化 +7.17%，同页冗余变化 +4.80%。

## 按问题类型

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cross_paper | 15 | 96.67% | 93.33% | 90.00% | 1.0000 | 0.8667 |
| fact | 9 | 100.00% | 100.00% | 100.00% | 1.0000 | 0.7492 |
| method | 26 | 100.00% | 100.00% | 100.00% | 1.0000 | 0.7897 |

## 按难度

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| hard | 36 | 98.61% | 97.22% | 95.83% | 1.0000 | 0.8454 |
| medium | 14 | 100.00% | 100.00% | 100.00% | 1.0000 | 0.7031 |

## 按 Evaluation Split

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| challenge | 25 | 98.00% | 96.00% | 94.00% | 1.0000 | 0.8733 |
| paired_anchor | 25 | 100.00% | 100.00% | 100.00% | 1.0000 | 0.7377 |

## 未完整覆盖的 Case

- Paper@10：DS-041
- Exact Page@10：DS-041, DS-044, DS-047

## 逐题 Top-1

| Case | Type | Top-1 paper | Page | Score | Paper hit | Exact page hit |
| --- | --- | --- | ---: | ---: | --- | --- |
| DS-001 | method | arxiv:2210.03629 | 8 | 0.0328 | True | False |
| DS-002 | fact | arxiv:2210.03629 | 4 | 0.0318 | True | True |
| DS-003 | fact | arxiv:2302.04761 | 10 | 0.0323 | True | False |
| DS-004 | method | arxiv:2302.04761 | 11 | 0.0325 | True | False |
| DS-005 | method | arxiv:2303.11366 | 2 | 0.0328 | True | False |
| DS-006 | fact | arxiv:2303.11366 | 2 | 0.0328 | True | True |
| DS-007 | method | arxiv:2310.04406 | 4 | 0.0328 | True | True |
| DS-008 | fact | arxiv:2310.04406 | 2 | 0.0318 | True | False |
| DS-009 | method | arxiv:2310.08560 | 1 | 0.0328 | True | True |
| DS-010 | method | arxiv:2310.08560 | 3 | 0.0325 | True | True |
| DS-011 | method | arxiv:2304.03442 | 2 | 0.0328 | True | True |
| DS-012 | fact | arxiv:2304.03442 | 15 | 0.0328 | True | True |
| DS-013 | method | arxiv:2305.16291 | 3 | 0.0328 | True | True |
| DS-014 | method | arxiv:2305.16291 | 6 | 0.0323 | True | False |
| DS-015 | method | arxiv:2303.17760 | 5 | 0.0328 | True | False |
| DS-016 | method | arxiv:2303.17760 | 8 | 0.0328 | True | False |
| DS-017 | method | arxiv:2308.08155 | 1 | 0.0325 | True | True |
| DS-018 | method | arxiv:2308.08155 | 2 | 0.0323 | True | False |
| DS-019 | fact | arxiv:2308.03688 | 2 | 0.0328 | True | True |
| DS-020 | method | arxiv:2308.03688 | 1 | 0.0328 | True | True |
| DS-021 | cross_paper | arxiv:2302.04761 | 3 | 0.0328 | True | True |
| DS-022 | cross_paper | arxiv:2303.11366 | 2 | 0.0328 | True | False |
| DS-023 | cross_paper | arxiv:2310.08560 | 1 | 0.0325 | True | True |
| DS-024 | cross_paper | arxiv:2303.17760 | 5 | 0.0328 | True | False |
| DS-025 | cross_paper | arxiv:2310.04406 | 4 | 0.0328 | True | True |
| DS-026 | method | arxiv:2205.00445 | 5 | 0.0328 | True | True |
| DS-027 | method | arxiv:2303.17651 | 2 | 0.0328 | True | True |
| DS-028 | method | arxiv:2305.10601 | 2 | 0.0325 | True | True |
| DS-029 | method | arxiv:2305.10250 | 9 | 0.0328 | True | False |
| DS-030 | method | arxiv:2303.17580 | 5 | 0.0323 | True | True |
| DS-031 | method | arxiv:2305.15334 | 5 | 0.0328 | True | True |
| DS-032 | method | arxiv:2307.16789 | 8 | 0.0328 | True | False |
| DS-033 | method | arxiv:2308.10848 | 3 | 0.0328 | True | True |
| DS-034 | method | arxiv:2308.00352 | 2 | 0.0328 | True | True |
| DS-035 | method | arxiv:2307.13854 | 2 | 0.0328 | True | True |
| DS-036 | method | arxiv:2303.17651 | 9 | 0.0328 | True | False |
| DS-037 | fact | arxiv:2305.10601 | 4 | 0.0328 | True | True |
| DS-038 | method | arxiv:2307.16789 | 6 | 0.0325 | True | True |
| DS-039 | fact | arxiv:2308.10848 | 2 | 0.0328 | True | False |
| DS-040 | fact | arxiv:2307.13854 | 8 | 0.0323 | True | True |
| DS-041 | cross_paper | arxiv:2303.11366 | 2 | 0.0328 | True | True |
| DS-042 | cross_paper | arxiv:2310.04406 | 4 | 0.0328 | True | True |
| DS-043 | cross_paper | arxiv:2310.08560 | 1 | 0.0328 | True | True |
| DS-044 | cross_paper | arxiv:2205.00445 | 4 | 0.0328 | True | True |
| DS-045 | cross_paper | arxiv:2302.04761 | 3 | 0.0325 | True | True |
| DS-046 | cross_paper | arxiv:2303.17760 | 5 | 0.0328 | True | False |
| DS-047 | cross_paper | arxiv:2307.13854 | 1 | 0.0328 | True | True |
| DS-048 | cross_paper | arxiv:2304.03442 | 2 | 0.0325 | True | True |
| DS-049 | cross_paper | arxiv:2303.17580 | 4 | 0.0323 | True | True |
| DS-050 | cross_paper | arxiv:2305.15334 | 8 | 0.0317 | True | False |

## 口径说明

- Paper Recall 对跨论文问题按目标论文覆盖比例计算。
- Exact Page 要求 `paper_id + page_number` 同时匹配人工标注。
- 标注页不是所有可能相关页面的穷举，因此 Exact Page 指标是严格下界。
- Same-page Redundancy 衡量同一论文同一页的多个 Chunk 占用 Top-K 的比例。
- 本报告没有调用 LLM，也没有使用 LLM-as-a-judge。
