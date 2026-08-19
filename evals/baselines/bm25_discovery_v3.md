# Retriever Baseline: bm25_discovery_v3

- 评估日期：`2026-08-19`
- Dataset：`evals/datasets/retrieval_discovery_v3.jsonl`（100 cases）
- Corpus：`agent-seed-v3` / v3
- Collection：`agent_seed_v3_bge_m3_chunking_v1`
- Embedding：`BAAI/bge-m3`
- Chunking：`chunking_v1`
- Strategy：`bm25`
- Strategy parameters：`{'bm25_k1': 1.5, 'bm25_b': 0.75, 'tokenizer': 'english_stopwords_porter_stemmer'}`
- First query / subsequent mean：0.49 / 0.29 ms
- P50 / P95 / Max latency：0.28 / 0.38 / 1.32 ms

## 总体指标

| K | Paper Hit | Paper Recall | Complete Papers | Exact Page Hit | Exact Page Recall | Complete Pages | Same-page Redundancy |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 68.00% | 55.08% | 43.00% | 46.00% | 36.83% | 28.00% | 0.00% |
| 3 | 72.00% | 60.08% | 49.00% | 62.00% | 49.58% | 38.00% | 8.00% |
| 5 | 75.00% | 64.33% | 54.00% | 73.00% | 60.58% | 49.00% | 8.80% |
| 10 | 77.00% | 67.92% | 58.00% | 76.00% | 65.67% | 55.00% | 10.52% |

- Paper MRR@10：0.7078
- Exact Page MRR@10：0.5579

## 初步观察

- Top-10 Paper Recall 为 67.92%；完整覆盖率为 58.00%。
- Top-10 Exact Page Recall 为 65.67%；该指标受非穷举页码标注影响，是严格下界。
- Top-10 Same-page Redundancy 为 10.52%。
- 从 Top-5 增加到 Top-10，Paper Recall 变化 +3.59%，Exact Page Recall 变化 +5.09%，同页冗余变化 +1.72%。

## 按问题类型

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cross_paper | 35 | 48.33% | 20.00% | 44.76% | 0.7200 | 0.6057 |
| fact | 22 | 77.27% | 77.27% | 77.27% | 0.6436 | 0.4723 |
| method | 43 | 79.07% | 79.07% | 76.74% | 0.7306 | 0.5628 |

## 按难度

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| hard | 86 | 63.86% | 52.33% | 61.24% | 0.6718 | 0.5456 |
| medium | 14 | 92.86% | 92.86% | 92.86% | 0.9286 | 0.6333 |

## 按 Evaluation Split

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| challenge | 25 | 85.67% | 72.00% | 84.67% | 0.8513 | 0.6860 |
| paired_anchor | 25 | 84.00% | 80.00% | 76.00% | 0.7947 | 0.5527 |

## 未完整覆盖的 Case

- Paper@10：DS-002, DS-019, DS-020, DS-021, DS-025, DS-041, DS-043, DS-045, DS-046, DS-047, DS-049, DS-050, DS-051, DS-052, DS-053, DS-056, DS-064, DS-070, DS-071, DS-072, DS-073, DS-075, DS-076, DS-081, DS-082, DS-083, DS-084, DS-085, DS-086, DS-087, DS-088, DS-089, DS-090, DS-091, DS-092, DS-093, DS-094, DS-095, DS-097, DS-098, DS-099, DS-100
- Exact Page@10：DS-002, DS-016, DS-019, DS-020, DS-021, DS-022, DS-024, DS-025, DS-041, DS-043, DS-045, DS-046, DS-047, DS-049, DS-050, DS-051, DS-052, DS-053, DS-056, DS-064, DS-070, DS-071, DS-072, DS-073, DS-075, DS-076, DS-081, DS-082, DS-083, DS-084, DS-085, DS-086, DS-087, DS-088, DS-089, DS-090, DS-091, DS-092, DS-093, DS-094, DS-095, DS-097, DS-098, DS-099, DS-100

## 逐题 Top-1

| Case | Type | Top-1 paper | Page | Score | Paper hit | Exact page hit |
| --- | --- | --- | ---: | ---: | --- | --- |
| DS-001 | method | arxiv:2210.03629 | 26 | 4.0444 | True | False |
| DS-002 | fact | - | - | - | False | False |
| DS-003 | fact | arxiv:2302.04761 | 2 | 1.8195 | True | True |
| DS-004 | method | arxiv:2302.04761 | 3 | 6.7306 | True | True |
| DS-005 | method | arxiv:2303.11366 | 4 | 8.6818 | True | True |
| DS-006 | fact | arxiv:2309.02427 | 28 | 5.4565 | False | False |
| DS-007 | method | arxiv:2310.04406 | 4 | 12.8672 | True | True |
| DS-008 | fact | arxiv:2308.00352 | 7 | 3.1588 | False | False |
| DS-009 | method | arxiv:2310.08560 | 1 | 6.5079 | True | True |
| DS-010 | method | arxiv:2307.16789 | 24 | 2.9370 | False | False |
| DS-011 | method | arxiv:2304.03442 | 13 | 8.6160 | True | False |
| DS-012 | fact | arxiv:2304.03442 | 15 | 4.0749 | True | True |
| DS-013 | method | arxiv:2305.16291 | 8 | 12.0477 | True | False |
| DS-014 | method | arxiv:2305.16291 | 39 | 5.6365 | True | False |
| DS-015 | method | arxiv:2303.17760 | 5 | 12.4201 | True | False |
| DS-016 | method | arxiv:2303.17760 | 5 | 1.0983 | True | False |
| DS-017 | method | arxiv:2308.08155 | 1 | 5.7601 | True | True |
| DS-018 | method | arxiv:2308.08155 | 25 | 6.4592 | True | False |
| DS-019 | fact | - | - | - | False | False |
| DS-020 | method | - | - | - | False | False |
| DS-021 | cross_paper | arxiv:2302.04761 | 3 | 6.7306 | True | True |
| DS-022 | cross_paper | arxiv:2310.04406 | 4 | 10.5455 | True | True |
| DS-023 | cross_paper | arxiv:2310.08560 | 2 | 8.4047 | True | True |
| DS-024 | cross_paper | arxiv:2303.17760 | 5 | 9.9853 | True | False |
| DS-025 | cross_paper | arxiv:2305.16291 | 3 | 10.5360 | True | True |
| DS-026 | method | arxiv:2205.00445 | 4 | 9.1142 | True | True |
| DS-027 | method | arxiv:2309.10691 | 17 | 2.5182 | False | False |
| DS-028 | method | arxiv:2305.10601 | 2 | 9.2963 | True | True |
| DS-029 | method | arxiv:2305.10250 | 9 | 13.8486 | True | False |
| DS-030 | method | arxiv:2303.17580 | 7 | 7.1808 | True | False |
| DS-031 | method | arxiv:2305.15334 | 5 | 4.0274 | True | True |
| DS-032 | method | arxiv:2307.16789 | 1 | 8.7549 | True | True |
| DS-033 | method | arxiv:2308.10848 | 3 | 12.2108 | True | True |
| DS-034 | method | arxiv:2308.00352 | 2 | 10.5887 | True | True |
| DS-035 | method | arxiv:2403.07718 | 4 | 3.5903 | False | False |
| DS-036 | method | arxiv:2303.17651 | 9 | 7.9822 | True | False |
| DS-037 | fact | arxiv:2305.10601 | 14 | 9.2415 | True | False |
| DS-038 | method | arxiv:2307.16789 | 6 | 10.5223 | True | True |
| DS-039 | fact | arxiv:2308.10848 | 2 | 8.8440 | True | False |
| DS-040 | fact | arxiv:2308.00352 | 25 | 3.4417 | False | False |
| DS-041 | cross_paper | arxiv:2303.11366 | 2 | 5.9512 | True | True |
| DS-042 | cross_paper | arxiv:2305.10601 | 4 | 10.0422 | True | True |
| DS-043 | cross_paper | arxiv:2310.08560 | 1 | 4.7402 | True | True |
| DS-044 | cross_paper | arxiv:2205.00445 | 4 | 6.5309 | True | True |
| DS-045 | cross_paper | arxiv:2302.04761 | 3 | 8.4905 | True | True |
| DS-046 | cross_paper | arxiv:2303.17760 | 5 | 6.3159 | True | False |
| DS-047 | cross_paper | - | - | - | False | False |
| DS-048 | cross_paper | arxiv:2304.03442 | 13 | 8.0969 | True | False |
| DS-049 | cross_paper | arxiv:2303.17760 | 5 | 1.7908 | False | False |
| DS-050 | cross_paper | arxiv:2205.00445 | 4 | 3.2367 | True | True |
| DS-051 | method | - | - | - | False | False |
| DS-052 | method | - | - | - | False | False |
| DS-053 | method | - | - | - | False | False |
| DS-054 | method | arxiv:2309.02427 | 11 | 14.7996 | True | True |
| DS-055 | method | arxiv:2310.12823 | 5 | 2.8667 | True | True |
| DS-056 | method | arxiv:2405.15793 | 28 | 2.1288 | False | False |
| DS-057 | method | arxiv:2309.15817 | 8 | 5.7816 | True | True |
| DS-058 | fact | arxiv:2306.06070 | 5 | 7.0262 | True | True |
| DS-059 | method | arxiv:2401.13919 | 3 | 2.4504 | True | True |
| DS-060 | fact | arxiv:2403.07718 | 2 | 11.8138 | True | True |
| DS-061 | fact | arxiv:2404.07972 | 6 | 9.8045 | True | True |
| DS-062 | fact | arxiv:2305.11738 | 13 | 2.7064 | False | False |
| DS-063 | method | arxiv:2401.13178 | 3 | 8.2643 | True | True |
| DS-064 | method | arxiv:2310.06770 | 21 | 2.4706 | False | False |
| DS-065 | fact | arxiv:2310.06770 | 1 | 10.3957 | True | True |
| DS-066 | method | arxiv:2310.06770 | 41 | 4.9801 | False | False |
| DS-067 | method | arxiv:2307.07924 | 3 | 3.7909 | True | True |
| DS-068 | method | arxiv:2310.11511 | 5 | 4.0388 | True | True |
| DS-069 | method | arxiv:2401.15884 | 5 | 6.2430 | True | True |
| DS-070 | method | - | - | - | False | False |
| DS-071 | method | - | - | - | False | False |
| DS-072 | fact | - | - | - | False | False |
| DS-073 | method | - | - | - | False | False |
| DS-074 | fact | arxiv:2309.15817 | 3 | 11.7326 | True | True |
| DS-075 | fact | - | - | - | False | False |
| DS-076 | fact | arxiv:2305.15334 | 7 | 3.5514 | False | False |
| DS-077 | fact | arxiv:2404.07972 | 23 | 4.0782 | True | False |
| DS-078 | fact | arxiv:2406.12045 | 7 | 9.5960 | True | True |
| DS-079 | fact | arxiv:2310.06770 | 24 | 6.4502 | True | False |
| DS-080 | fact | arxiv:2405.15793 | 67 | 5.9084 | True | False |
| DS-081 | cross_paper | - | - | - | False | False |
| DS-082 | cross_paper | arxiv:2305.10601 | 4 | 8.9080 | True | True |
| DS-083 | cross_paper | arxiv:2303.11366 | 2 | 5.9512 | True | True |
| DS-084 | cross_paper | - | - | - | False | False |
| DS-085 | cross_paper | arxiv:2307.16789 | 4 | 5.2227 | True | False |
| DS-086 | cross_paper | - | - | - | False | False |
| DS-087 | cross_paper | arxiv:2310.06770 | 21 | 2.4706 | False | False |
| DS-088 | cross_paper | arxiv:2306.06070 | 2 | 2.9184 | True | False |
| DS-089 | cross_paper | arxiv:2401.13919 | 3 | 2.4504 | True | True |
| DS-090 | cross_paper | arxiv:2306.06070 | 2 | 4.5286 | True | False |
| DS-091 | cross_paper | arxiv:2404.07972 | 8 | 2.8212 | True | True |
| DS-092 | cross_paper | - | - | - | False | False |
| DS-093 | cross_paper | arxiv:2401.13178 | 3 | 8.2643 | True | True |
| DS-094 | cross_paper | arxiv:2405.15793 | 28 | 2.1288 | False | False |
| DS-095 | cross_paper | arxiv:2310.06770 | 17 | 6.6779 | True | False |
| DS-096 | cross_paper | arxiv:2308.00352 | 1 | 7.8795 | True | True |
| DS-097 | cross_paper | arxiv:2310.11511 | 4 | 2.2241 | True | True |
| DS-098 | cross_paper | - | - | - | False | False |
| DS-099 | cross_paper | arxiv:2310.11511 | 4 | 8.1880 | True | True |
| DS-100 | cross_paper | - | - | - | False | False |

## 口径说明

- Paper Recall 对跨论文问题按目标论文覆盖比例计算。
- Exact Page 要求 `paper_id + page_number` 同时匹配人工标注。
- 标注页不是所有可能相关页面的穷举，因此 Exact Page 指标是严格下界。
- Same-page Redundancy 衡量同一论文同一页的多个 Chunk 占用 Top-K 的比例。
- 本报告没有调用 LLM，也没有使用 LLM-as-a-judge。
