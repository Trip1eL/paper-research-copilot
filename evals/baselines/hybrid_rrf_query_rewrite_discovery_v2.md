# Retriever Baseline: hybrid_rrf_query_rewrite_discovery_v2

- 评估日期：`2026-08-17`
- Dataset：`evals/datasets/retrieval_discovery_v2.jsonl`（50 cases）
- Corpus：`agent-seed-v2` / v2
- Collection：`agent_seed_v2_bge_m3_chunking_v1`
- Embedding：`BAAI/bge-m3`
- Chunking：`chunking_v1`
- Strategy：`hybrid_rrf_query_rewrite`
- Strategy parameters：`{'bm25_k1': 1.5, 'bm25_b': 0.75, 'tokenizer': 'english_stopwords_porter_stemmer', 'candidate_pool_size': 50, 'rrf_k': 60, 'rewrite_model': 'deepseek-v4-flash', 'rewrite_count': 3, 'rewrite_retry_attempts': 3, 'rewrite_prompt_version': 'query_rewrite_v1', 'rewrite_cache': 'evals/query_rewrites/retrieval_discovery_v2_deepseek-v4-flash_query_rewrite_v1.jsonl', 'rewrite_generation_mean_ms': 6615.84, 'rewrite_title_leak_hits': 0}`
- First query / subsequent mean：1548.56 / 1592.01 ms
- P50 / P95 / Max latency：1450.51 / 2591.44 / 4325.52 ms

## 总体指标

| K | Paper Hit | Paper Recall | Complete Papers | Exact Page Hit | Exact Page Recall | Complete Pages | Same-page Redundancy |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 96.00% | 82.17% | 70.00% | 72.00% | 60.17% | 50.00% | 0.00% |
| 3 | 100.00% | 91.17% | 82.00% | 96.00% | 83.67% | 72.00% | 6.67% |
| 5 | 100.00% | 95.33% | 90.00% | 98.00% | 90.17% | 82.00% | 12.80% |
| 10 | 100.00% | 97.00% | 94.00% | 98.00% | 92.33% | 86.00% | 16.20% |

- Paper MRR@10：0.9767
- Exact Page MRR@10：0.8340

## 初步观察

- Top-10 Paper Recall 为 97.00%；完整覆盖率为 94.00%。
- Top-10 Exact Page Recall 为 92.33%；该指标受非穷举页码标注影响，是严格下界。
- Top-10 Same-page Redundancy 为 16.20%。
- 从 Top-5 增加到 Top-10，Paper Recall 变化 +1.67%，Exact Page Recall 变化 +2.16%，同页冗余变化 +3.40%。

## 按问题类型

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cross_paper | 15 | 90.00% | 80.00% | 81.11% | 0.9222 | 0.8556 |
| fact | 9 | 100.00% | 100.00% | 88.89% | 1.0000 | 0.6481 |
| method | 26 | 100.00% | 100.00% | 100.00% | 1.0000 | 0.8859 |

## 按难度

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| hard | 36 | 95.83% | 91.67% | 92.13% | 0.9676 | 0.8796 |
| medium | 14 | 100.00% | 100.00% | 92.86% | 1.0000 | 0.7167 |

## 按 Evaluation Split

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| challenge | 25 | 98.00% | 96.00% | 92.67% | 0.9533 | 0.8933 |
| paired_anchor | 25 | 96.00% | 92.00% | 92.00% | 1.0000 | 0.7747 |

## 未完整覆盖的 Case

- Paper@10：DS-021, DS-025, DS-041
- Exact Page@10：DS-003, DS-021, DS-025, DS-041, DS-044, DS-045, DS-047

## 逐题 Top-1

| Case | Type | Top-1 paper | Page | Score | Paper hit | Exact page hit |
| --- | --- | --- | ---: | ---: | --- | --- |
| DS-001 | method | arxiv:2210.03629 | 3 | 0.1194 | True | True |
| DS-002 | fact | arxiv:2210.03629 | 3 | 0.1097 | True | False |
| DS-003 | fact | arxiv:2302.04761 | 4 | 0.1109 | True | False |
| DS-004 | method | arxiv:2302.04761 | 11 | 0.1211 | True | False |
| DS-005 | method | arxiv:2303.11366 | 2 | 0.1289 | True | False |
| DS-006 | fact | arxiv:2303.11366 | 2 | 0.1288 | True | True |
| DS-007 | method | arxiv:2310.04406 | 4 | 0.1306 | True | True |
| DS-008 | fact | arxiv:2310.04406 | 16 | 0.1208 | True | False |
| DS-009 | method | arxiv:2310.08560 | 1 | 0.1309 | True | True |
| DS-010 | method | arxiv:2310.08560 | 1 | 0.1219 | True | True |
| DS-011 | method | arxiv:2304.03442 | 2 | 0.1296 | True | True |
| DS-012 | fact | arxiv:2304.03442 | 18 | 0.1062 | True | False |
| DS-013 | method | arxiv:2305.16291 | 3 | 0.1299 | True | True |
| DS-014 | method | arxiv:2305.16291 | 1 | 0.1069 | True | False |
| DS-015 | method | arxiv:2303.17760 | 5 | 0.1296 | True | False |
| DS-016 | method | arxiv:2303.17760 | 2 | 0.1116 | True | True |
| DS-017 | method | arxiv:2308.08155 | 2 | 0.1276 | True | True |
| DS-018 | method | arxiv:2308.08155 | 3 | 0.1080 | True | True |
| DS-019 | fact | arxiv:2308.03688 | 1 | 0.1080 | True | True |
| DS-020 | method | arxiv:2308.03688 | 3 | 0.0968 | True | True |
| DS-021 | cross_paper | arxiv:2302.04761 | 3 | 0.0944 | True | True |
| DS-022 | cross_paper | arxiv:2310.04406 | 4 | 0.1106 | True | True |
| DS-023 | cross_paper | arxiv:2310.08560 | 1 | 0.1234 | True | True |
| DS-024 | cross_paper | arxiv:2303.17760 | 5 | 0.1301 | True | False |
| DS-025 | cross_paper | arxiv:2305.16291 | 3 | 0.1201 | True | True |
| DS-026 | method | arxiv:2205.00445 | 4 | 0.1269 | True | True |
| DS-027 | method | arxiv:2303.17651 | 2 | 0.1225 | True | True |
| DS-028 | method | arxiv:2305.10601 | 2 | 0.1263 | True | True |
| DS-029 | method | arxiv:2305.10250 | 4 | 0.1280 | True | True |
| DS-030 | method | arxiv:2303.17580 | 5 | 0.1102 | True | True |
| DS-031 | method | arxiv:2305.15334 | 2 | 0.1252 | True | True |
| DS-032 | method | arxiv:2307.16789 | 3 | 0.1182 | True | True |
| DS-033 | method | arxiv:2308.10848 | 3 | 0.1309 | True | True |
| DS-034 | method | arxiv:2308.00352 | 4 | 0.1260 | True | True |
| DS-035 | method | arxiv:2307.13854 | 2 | 0.1281 | True | True |
| DS-036 | method | arxiv:2303.17651 | 9 | 0.1209 | True | False |
| DS-037 | fact | arxiv:2305.10601 | 4 | 0.1275 | True | True |
| DS-038 | method | arxiv:2307.16789 | 6 | 0.1262 | True | True |
| DS-039 | fact | arxiv:2308.10848 | 2 | 0.1311 | True | False |
| DS-040 | fact | arxiv:2307.13854 | 8 | 0.1221 | True | True |
| DS-041 | cross_paper | arxiv:2303.11366 | 2 | 0.1259 | True | True |
| DS-042 | cross_paper | arxiv:2310.04406 | 4 | 0.1301 | True | True |
| DS-043 | cross_paper | arxiv:2310.08560 | 8 | 0.1162 | True | False |
| DS-044 | cross_paper | arxiv:2308.10848 | 17 | 0.1176 | False | False |
| DS-045 | cross_paper | arxiv:2305.15334 | 5 | 0.1176 | True | True |
| DS-046 | cross_paper | arxiv:2308.00352 | 4 | 0.1099 | True | True |
| DS-047 | cross_paper | arxiv:2307.13854 | 1 | 0.1102 | True | True |
| DS-048 | cross_paper | arxiv:2304.03442 | 2 | 0.1250 | True | True |
| DS-049 | cross_paper | arxiv:2303.17760 | 3 | 0.0892 | False | False |
| DS-050 | cross_paper | arxiv:2205.00445 | 4 | 0.1052 | True | True |

## 口径说明

- Paper Recall 对跨论文问题按目标论文覆盖比例计算。
- Exact Page 要求 `paper_id + page_number` 同时匹配人工标注。
- 标注页不是所有可能相关页面的穷举，因此 Exact Page 指标是严格下界。
- Same-page Redundancy 衡量同一论文同一页的多个 Chunk 占用 Top-K 的比例。
- 本报告没有调用 LLM，也没有使用 LLM-as-a-judge。
