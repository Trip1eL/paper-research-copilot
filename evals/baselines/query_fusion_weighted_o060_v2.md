# Retriever Baseline: query_fusion_weighted_o060_v2

- 评估日期：`2026-08-17`
- Dataset：`evals/datasets/retrieval_discovery_v2.jsonl`（50 cases）
- Corpus：`agent-seed-v2` / v2
- Collection：`agent_seed_v2_bge_m3_chunking_v1`
- Embedding：`BAAI/bge-m3`
- Chunking：`chunking_v1`
- Strategy：`group_weighted_rrf`
- Strategy parameters：`{'candidate_pool_size': 50, 'rrf_k': 60, 'shared_branch_rankings': True, 'fusion_mean_ms': 0.3396, 'rewrite_model': 'deepseek-v4-flash', 'rewrite_prompt_version': 'query_rewrite_v1', 'rewrite_title_leak_hits': 0, 'original_query_weight': 0.6, 'rewrite_group_weight': 0.4}`
- First query / subsequent mean：1570.23 / 1427.76 ms
- P50 / P95 / Max latency：1402.84 / 1674.64 / 1961.35 ms

## 总体指标

| K | Paper Hit | Paper Recall | Complete Papers | Exact Page Hit | Exact Page Recall | Complete Pages | Same-page Redundancy |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 94.00% | 80.17% | 68.00% | 70.00% | 60.00% | 50.00% | 0.00% |
| 3 | 98.00% | 89.17% | 80.00% | 92.00% | 78.17% | 66.00% | 6.67% |
| 5 | 100.00% | 93.83% | 86.00% | 98.00% | 89.33% | 80.00% | 12.00% |
| 10 | 100.00% | 95.83% | 90.00% | 98.00% | 90.83% | 82.00% | 17.40% |

- Paper MRR@10：0.9617
- Exact Page MRR@10：0.8130

## 初步观察

- Top-10 Paper Recall 为 95.83%；完整覆盖率为 90.00%。
- Top-10 Exact Page Recall 为 90.83%；该指标受非穷举页码标注影响，是严格下界。
- Top-10 Same-page Redundancy 为 17.40%。
- 从 Top-5 增加到 Top-10，Paper Recall 变化 +2.00%，Exact Page Recall 变化 +1.50%，同页冗余变化 +5.40%。

## 按问题类型

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cross_paper | 15 | 86.11% | 66.67% | 76.11% | 0.9222 | 0.8111 |
| fact | 9 | 100.00% | 100.00% | 88.89% | 0.9167 | 0.6944 |
| method | 26 | 100.00% | 100.00% | 100.00% | 1.0000 | 0.8551 |

## 按难度

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| hard | 36 | 94.21% | 86.11% | 90.05% | 0.9676 | 0.8366 |
| medium | 14 | 100.00% | 100.00% | 92.86% | 0.9464 | 0.7524 |

## 按 Evaluation Split

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| challenge | 25 | 93.67% | 84.00% | 89.67% | 0.9533 | 0.8667 |
| paired_anchor | 25 | 98.00% | 96.00% | 92.00% | 0.9700 | 0.7593 |

## 未完整覆盖的 Case

- Paper@10：DS-021, DS-041, DS-045, DS-046, DS-049
- Exact Page@10：DS-003, DS-021, DS-022, DS-041, DS-044, DS-045, DS-046, DS-047, DS-049

## 逐题 Top-1

| Case | Type | Top-1 paper | Page | Score | Paper hit | Exact page hit |
| --- | --- | --- | ---: | ---: | --- | --- |
| DS-001 | method | arxiv:2210.03629 | 3 | 0.0306 | True | True |
| DS-002 | fact | arxiv:2210.03629 | 3 | 0.0222 | True | False |
| DS-003 | fact | arxiv:2305.15334 | 2 | 0.0251 | False | False |
| DS-004 | method | arxiv:2302.04761 | 11 | 0.0292 | True | False |
| DS-005 | method | arxiv:2303.11366 | 2 | 0.0322 | True | False |
| DS-006 | fact | arxiv:2303.11366 | 2 | 0.0320 | True | True |
| DS-007 | method | arxiv:2310.04406 | 4 | 0.0327 | True | True |
| DS-008 | fact | arxiv:2310.04406 | 16 | 0.0301 | True | False |
| DS-009 | method | arxiv:2310.08560 | 1 | 0.0328 | True | True |
| DS-010 | method | arxiv:2310.08560 | 1 | 0.0304 | True | True |
| DS-011 | method | arxiv:2304.03442 | 2 | 0.0323 | True | True |
| DS-012 | fact | arxiv:2304.03442 | 15 | 0.0286 | True | True |
| DS-013 | method | arxiv:2305.16291 | 3 | 0.0325 | True | True |
| DS-014 | method | arxiv:2305.16291 | 1 | 0.0290 | True | False |
| DS-015 | method | arxiv:2303.17760 | 5 | 0.0326 | True | False |
| DS-016 | method | arxiv:2303.17760 | 5 | 0.0289 | True | False |
| DS-017 | method | arxiv:2308.08155 | 2 | 0.0321 | True | True |
| DS-018 | method | arxiv:2308.08155 | 3 | 0.0262 | True | True |
| DS-019 | fact | arxiv:2308.03688 | 1 | 0.0220 | True | True |
| DS-020 | method | arxiv:2308.03688 | 1 | 0.0205 | True | True |
| DS-021 | cross_paper | arxiv:2302.04761 | 3 | 0.0279 | True | True |
| DS-022 | cross_paper | arxiv:2310.04406 | 4 | 0.0300 | True | True |
| DS-023 | cross_paper | arxiv:2310.08560 | 1 | 0.0316 | True | True |
| DS-024 | cross_paper | arxiv:2303.17760 | 5 | 0.0326 | True | False |
| DS-025 | cross_paper | arxiv:2305.16291 | 3 | 0.0313 | True | True |
| DS-026 | method | arxiv:2205.00445 | 4 | 0.0322 | True | True |
| DS-027 | method | arxiv:2303.17651 | 4 | 0.0287 | True | True |
| DS-028 | method | arxiv:2305.10601 | 2 | 0.0319 | True | True |
| DS-029 | method | arxiv:2305.10250 | 4 | 0.0321 | True | True |
| DS-030 | method | arxiv:2303.17580 | 5 | 0.0298 | True | True |
| DS-031 | method | arxiv:2305.15334 | 2 | 0.0316 | True | True |
| DS-032 | method | arxiv:2307.16789 | 1 | 0.0305 | True | True |
| DS-033 | method | arxiv:2308.10848 | 3 | 0.0328 | True | True |
| DS-034 | method | arxiv:2308.00352 | 4 | 0.0304 | True | True |
| DS-035 | method | arxiv:2307.13854 | 2 | 0.0324 | True | True |
| DS-036 | method | arxiv:2303.17651 | 9 | 0.0314 | True | False |
| DS-037 | fact | arxiv:2305.10601 | 4 | 0.0322 | True | True |
| DS-038 | method | arxiv:2307.16789 | 6 | 0.0320 | True | True |
| DS-039 | fact | arxiv:2308.10848 | 2 | 0.0328 | True | False |
| DS-040 | fact | arxiv:2307.13854 | 8 | 0.0290 | True | True |
| DS-041 | cross_paper | arxiv:2303.11366 | 2 | 0.0321 | True | True |
| DS-042 | cross_paper | arxiv:2310.04406 | 4 | 0.0325 | True | True |
| DS-043 | cross_paper | arxiv:2310.08560 | 1 | 0.0302 | True | True |
| DS-044 | cross_paper | arxiv:2308.10848 | 17 | 0.0290 | False | False |
| DS-045 | cross_paper | arxiv:2305.15334 | 4 | 0.0294 | True | False |
| DS-046 | cross_paper | arxiv:2303.17760 | 5 | 0.0281 | True | False |
| DS-047 | cross_paper | arxiv:2307.13854 | 1 | 0.0222 | True | True |
| DS-048 | cross_paper | arxiv:2304.03442 | 2 | 0.0309 | True | True |
| DS-049 | cross_paper | arxiv:2303.17760 | 3 | 0.0266 | False | False |
| DS-050 | cross_paper | arxiv:2205.00445 | 4 | 0.0283 | True | True |

## 口径说明

- Paper Recall 对跨论文问题按目标论文覆盖比例计算。
- Exact Page 要求 `paper_id + page_number` 同时匹配人工标注。
- 标注页不是所有可能相关页面的穷举，因此 Exact Page 指标是严格下界。
- Same-page Redundancy 衡量同一论文同一页的多个 Chunk 占用 Top-K 的比例。
- 本报告没有调用 LLM，也没有使用 LLM-as-a-judge。
