# Retriever Baseline: hybrid_rrf_discovery_v3

- 评估日期：`2026-08-18`
- Dataset：`evals/datasets/retrieval_discovery_v3.jsonl`（100 cases）
- Corpus：`agent-seed-v3` / v3
- Collection：`agent_seed_v3_bge_m3_chunking_v1`
- Embedding：`BAAI/bge-m3`
- Chunking：`chunking_v1`
- Strategy：`hybrid_rrf`
- Strategy parameters：`{'bm25_k1': 1.5, 'bm25_b': 0.75, 'tokenizer': 'english_stopwords_porter_stemmer', 'candidate_pool_size': 50, 'rrf_k': 60}`
- First query / subsequent mean：410.86 / 289.8 ms
- P50 / P95 / Max latency：231.12 / 280.45 / 5510.49 ms

## 总体指标

| K | Paper Hit | Paper Recall | Complete Papers | Exact Page Hit | Exact Page Recall | Complete Pages | Same-page Redundancy |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 88.00% | 72.33% | 58.00% | 70.00% | 58.83% | 48.00% | 0.00% |
| 3 | 95.00% | 80.17% | 66.00% | 87.00% | 73.42% | 60.00% | 6.67% |
| 5 | 98.00% | 86.17% | 74.00% | 91.00% | 77.17% | 64.00% | 10.60% |
| 10 | 99.00% | 92.17% | 84.00% | 98.00% | 86.92% | 75.00% | 11.20% |

- Paper MRR@10：0.9194
- Exact Page MRR@10：0.7962

## 初步观察

- Top-10 Paper Recall 为 92.17%；完整覆盖率为 84.00%。
- Top-10 Exact Page Recall 为 86.92%；该指标受非穷举页码标注影响，是严格下界。
- Top-10 Same-page Redundancy 为 11.20%。
- 从 Top-5 增加到 Top-10，Paper Recall 变化 +6.00%，Exact Page Recall 变化 +9.75%，同页冗余变化 +0.60%。

## 按问题类型

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cross_paper | 35 | 80.48% | 57.14% | 68.33% | 0.9238 | 0.7615 |
| fact | 22 | 95.45% | 95.45% | 90.91% | 0.8311 | 0.7716 |
| method | 43 | 100.00% | 100.00% | 100.00% | 0.9610 | 0.8371 |

## 按难度

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| hard | 86 | 90.89% | 81.40% | 84.79% | 0.9156 | 0.8011 |
| medium | 14 | 100.00% | 100.00% | 100.00% | 0.9429 | 0.7662 |

## 按 Evaluation Split

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| challenge | 25 | 93.67% | 84.00% | 83.67% | 0.9300 | 0.8190 |
| paired_anchor | 25 | 98.00% | 96.00% | 96.00% | 0.9480 | 0.7957 |

## 未完整覆盖的 Case

- Paper@10：DS-021, DS-044, DS-045, DS-046, DS-049, DS-072, DS-082, DS-083, DS-085, DS-086, DS-087, DS-093, DS-095, DS-097, DS-098, DS-100
- Exact Page@10：DS-021, DS-022, DS-040, DS-041, DS-044, DS-045, DS-046, DS-047, DS-049, DS-050, DS-072, DS-081, DS-082, DS-083, DS-085, DS-086, DS-087, DS-088, DS-092, DS-093, DS-094, DS-095, DS-097, DS-098, DS-100

## 逐题 Top-1

| Case | Type | Top-1 paper | Page | Score | Paper hit | Exact page hit |
| --- | --- | --- | ---: | ---: | --- | --- |
| DS-001 | method | arxiv:2210.03629 | 3 | 0.0315 | True | True |
| DS-002 | fact | arxiv:2210.03629 | 4 | 0.0164 | True | True |
| DS-003 | fact | arxiv:2305.15334 | 9 | 0.0258 | False | False |
| DS-004 | method | arxiv:2302.04761 | 3 | 0.0323 | True | True |
| DS-005 | method | arxiv:2303.11366 | 4 | 0.0323 | True | True |
| DS-006 | fact | arxiv:2303.11366 | 2 | 0.0315 | True | True |
| DS-007 | method | arxiv:2310.04406 | 4 | 0.0328 | True | True |
| DS-008 | fact | arxiv:2308.00352 | 7 | 0.0296 | False | False |
| DS-009 | method | arxiv:2310.08560 | 1 | 0.0328 | True | True |
| DS-010 | method | arxiv:2310.08560 | 3 | 0.0313 | True | True |
| DS-011 | method | arxiv:2304.03442 | 13 | 0.0325 | True | False |
| DS-012 | fact | arxiv:2304.03442 | 15 | 0.0328 | True | True |
| DS-013 | method | arxiv:2305.16291 | 3 | 0.0325 | True | True |
| DS-014 | method | arxiv:2305.16291 | 1 | 0.0320 | True | False |
| DS-015 | method | arxiv:2303.17760 | 5 | 0.0328 | True | False |
| DS-016 | method | arxiv:2303.17760 | 5 | 0.0323 | True | False |
| DS-017 | method | arxiv:2308.08155 | 2 | 0.0323 | True | True |
| DS-018 | method | arxiv:2308.08155 | 5 | 0.0317 | True | False |
| DS-019 | fact | arxiv:2308.03688 | 1 | 0.0164 | True | True |
| DS-020 | method | arxiv:2308.03688 | 1 | 0.0164 | True | True |
| DS-021 | cross_paper | arxiv:2302.04761 | 3 | 0.0328 | True | True |
| DS-022 | cross_paper | arxiv:2310.04406 | 4 | 0.0328 | True | True |
| DS-023 | cross_paper | arxiv:2310.08560 | 1 | 0.0315 | True | True |
| DS-024 | cross_paper | arxiv:2303.17760 | 5 | 0.0328 | True | False |
| DS-025 | cross_paper | arxiv:2305.16291 | 3 | 0.0328 | True | True |
| DS-026 | method | arxiv:2205.00445 | 4 | 0.0328 | True | True |
| DS-027 | method | arxiv:2303.17651 | 4 | 0.0302 | True | True |
| DS-028 | method | arxiv:2305.10601 | 4 | 0.0325 | True | True |
| DS-029 | method | arxiv:2305.10250 | 4 | 0.0325 | True | True |
| DS-030 | method | arxiv:2303.17580 | 5 | 0.0323 | True | True |
| DS-031 | method | arxiv:2305.15334 | 5 | 0.0328 | True | True |
| DS-032 | method | arxiv:2307.16789 | 1 | 0.0320 | True | True |
| DS-033 | method | arxiv:2308.10848 | 3 | 0.0328 | True | True |
| DS-034 | method | arxiv:2308.00352 | 2 | 0.0328 | True | True |
| DS-035 | method | arxiv:2307.13854 | 2 | 0.0320 | True | True |
| DS-036 | method | arxiv:2303.17651 | 9 | 0.0328 | True | False |
| DS-037 | fact | arxiv:2305.10601 | 4 | 0.0325 | True | True |
| DS-038 | method | arxiv:2307.16789 | 6 | 0.0325 | True | True |
| DS-039 | fact | arxiv:2308.10848 | 2 | 0.0328 | True | False |
| DS-040 | fact | arxiv:2403.07718 | 7 | 0.0318 | False | False |
| DS-041 | cross_paper | arxiv:2303.11366 | 2 | 0.0328 | True | True |
| DS-042 | cross_paper | arxiv:2305.10601 | 4 | 0.0325 | True | True |
| DS-043 | cross_paper | arxiv:2310.08560 | 1 | 0.0328 | True | True |
| DS-044 | cross_paper | arxiv:2205.00445 | 4 | 0.0279 | True | True |
| DS-045 | cross_paper | arxiv:2302.04761 | 3 | 0.0325 | True | True |
| DS-046 | cross_paper | arxiv:2303.17760 | 5 | 0.0328 | True | False |
| DS-047 | cross_paper | arxiv:2404.07972 | 9 | 0.0164 | False | False |
| DS-048 | cross_paper | arxiv:2304.03442 | 8 | 0.0311 | True | False |
| DS-049 | cross_paper | arxiv:2303.17760 | 3 | 0.0315 | False | False |
| DS-050 | cross_paper | arxiv:2205.00445 | 4 | 0.0297 | True | True |
| DS-051 | method | arxiv:2305.11738 | 1 | 0.0164 | True | True |
| DS-052 | method | arxiv:2310.04406 | 3 | 0.0164 | False | False |
| DS-053 | method | arxiv:2308.10144 | 3 | 0.0164 | True | True |
| DS-054 | method | arxiv:2309.02427 | 11 | 0.0323 | True | True |
| DS-055 | method | arxiv:2310.12823 | 3 | 0.0325 | True | True |
| DS-056 | method | arxiv:2309.10691 | 24 | 0.0241 | True | False |
| DS-057 | method | arxiv:2309.15817 | 8 | 0.0323 | True | True |
| DS-058 | fact | arxiv:2306.06070 | 5 | 0.0325 | True | True |
| DS-059 | method | arxiv:2401.13919 | 3 | 0.0325 | True | True |
| DS-060 | fact | arxiv:2403.07718 | 2 | 0.0328 | True | True |
| DS-061 | fact | arxiv:2404.07972 | 6 | 0.0328 | True | True |
| DS-062 | fact | arxiv:2311.12983 | 6 | 0.0311 | True | True |
| DS-063 | method | arxiv:2401.13178 | 3 | 0.0311 | True | True |
| DS-064 | method | arxiv:2406.12045 | 4 | 0.0303 | True | True |
| DS-065 | fact | arxiv:2310.06770 | 2 | 0.0325 | True | True |
| DS-066 | method | arxiv:2310.06770 | 2 | 0.0298 | False | False |
| DS-067 | method | arxiv:2307.07924 | 3 | 0.0325 | True | True |
| DS-068 | method | arxiv:2310.11511 | 1 | 0.0320 | True | True |
| DS-069 | method | arxiv:2401.15884 | 5 | 0.0325 | True | True |
| DS-070 | method | arxiv:2403.14403 | 5 | 0.0164 | True | True |
| DS-071 | method | arxiv:2305.11738 | 1 | 0.0164 | True | False |
| DS-072 | fact | arxiv:2308.03688 | 26 | 0.0164 | False | False |
| DS-073 | method | arxiv:2310.12823 | 2 | 0.0164 | True | True |
| DS-074 | fact | arxiv:2309.15817 | 10 | 0.0304 | True | True |
| DS-075 | fact | arxiv:2306.06070 | 7 | 0.0164 | True | True |
| DS-076 | fact | arxiv:2401.13178 | 8 | 0.0311 | False | False |
| DS-077 | fact | arxiv:2404.07972 | 11 | 0.0310 | True | True |
| DS-078 | fact | arxiv:2406.12045 | 7 | 0.0328 | True | True |
| DS-079 | fact | arxiv:2310.06770 | 6 | 0.0313 | True | True |
| DS-080 | fact | arxiv:2405.15793 | 67 | 0.0323 | True | False |
| DS-081 | cross_paper | arxiv:2303.17651 | 15 | 0.0164 | True | False |
| DS-082 | cross_paper | arxiv:2305.10601 | 4 | 0.0328 | True | True |
| DS-083 | cross_paper | arxiv:2303.11366 | 2 | 0.0328 | True | True |
| DS-084 | cross_paper | arxiv:2310.11511 | 22 | 0.0164 | False | False |
| DS-085 | cross_paper | arxiv:2307.16789 | 4 | 0.0307 | True | False |
| DS-086 | cross_paper | arxiv:2307.16789 | 16 | 0.0164 | False | False |
| DS-087 | cross_paper | arxiv:2406.12045 | 4 | 0.0300 | True | True |
| DS-088 | cross_paper | arxiv:2306.06070 | 5 | 0.0320 | True | True |
| DS-089 | cross_paper | arxiv:2401.13919 | 3 | 0.0309 | True | True |
| DS-090 | cross_paper | arxiv:2306.06070 | 5 | 0.0325 | True | True |
| DS-091 | cross_paper | arxiv:2404.07972 | 2 | 0.0320 | True | True |
| DS-092 | cross_paper | arxiv:2311.12983 | 9 | 0.0164 | True | False |
| DS-093 | cross_paper | arxiv:2401.13178 | 3 | 0.0309 | True | True |
| DS-094 | cross_paper | arxiv:2303.17760 | 4 | 0.0252 | False | False |
| DS-095 | cross_paper | arxiv:2310.06770 | 17 | 0.0320 | True | False |
| DS-096 | cross_paper | arxiv:2307.07924 | 3 | 0.0313 | True | True |
| DS-097 | cross_paper | arxiv:2310.11511 | 6 | 0.0320 | True | True |
| DS-098 | cross_paper | arxiv:2403.14403 | 5 | 0.0164 | True | True |
| DS-099 | cross_paper | arxiv:2403.14403 | 4 | 0.0300 | True | True |
| DS-100 | cross_paper | arxiv:2404.07972 | 26 | 0.0164 | True | False |

## 口径说明

- Paper Recall 对跨论文问题按目标论文覆盖比例计算。
- Exact Page 要求 `paper_id + page_number` 同时匹配人工标注。
- 标注页不是所有可能相关页面的穷举，因此 Exact Page 指标是严格下界。
- Same-page Redundancy 衡量同一论文同一页的多个 Chunk 占用 Top-K 的比例。
- 本报告没有调用 LLM，也没有使用 LLM-as-a-judge。
