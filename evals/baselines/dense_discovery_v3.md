# Retriever Baseline: dense_discovery_v3

- 评估日期：`2026-08-19`
- Dataset：`evals/datasets/retrieval_discovery_v3.jsonl`（100 cases）
- Corpus：`agent-seed-v3` / v3
- Collection：`agent_seed_v3_bge_m3_chunking_v1`
- Embedding：`BAAI/bge-m3`
- Chunking：`chunking_v1`
- Strategy：`dense`
- Strategy parameters：`{}`
- First query / subsequent mean：314.89 / 258.81 ms
- P50 / P95 / Max latency：256.53 / 283.38 / 483.18 ms

## 总体指标

| K | Paper Hit | Paper Recall | Complete Papers | Exact Page Hit | Exact Page Recall | Complete Pages | Same-page Redundancy |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 82.00% | 67.83% | 55.00% | 62.00% | 53.50% | 45.00% | 0.00% |
| 3 | 93.00% | 80.42% | 68.00% | 81.00% | 69.42% | 58.00% | 6.00% |
| 5 | 95.00% | 84.17% | 73.00% | 88.00% | 75.42% | 63.00% | 9.00% |
| 10 | 98.00% | 92.00% | 85.00% | 93.00% | 83.92% | 74.00% | 10.10% |

- Paper MRR@10：0.8835
- Exact Page MRR@10：0.7264

## 初步观察

- Top-10 Paper Recall 为 92.00%；完整覆盖率为 85.00%。
- Top-10 Exact Page Recall 为 83.92%；该指标受非穷举页码标注影响，是严格下界。
- Top-10 Same-page Redundancy 为 10.10%。
- 从 Top-5 增加到 Top-10，Paper Recall 变化 +7.83%，Exact Page Recall 变化 +8.50%，同页冗余变化 +1.10%。

## 按问题类型

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cross_paper | 35 | 80.00% | 60.00% | 65.48% | 0.8600 | 0.6574 |
| fact | 22 | 95.45% | 95.45% | 81.82% | 0.8693 | 0.6856 |
| method | 43 | 100.00% | 100.00% | 100.00% | 0.9099 | 0.8035 |

## 按难度

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| hard | 86 | 90.70% | 82.56% | 81.30% | 0.8791 | 0.7314 |
| medium | 14 | 100.00% | 100.00% | 100.00% | 0.9107 | 0.6958 |

## 按 Evaluation Split

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| challenge | 25 | 89.00% | 80.00% | 77.67% | 0.8290 | 0.6733 |
| paired_anchor | 25 | 98.00% | 96.00% | 90.00% | 0.9100 | 0.7197 |

## 未完整覆盖的 Case

- Paper@10：DS-021, DS-043, DS-044, DS-046, DS-049, DS-050, DS-072, DS-082, DS-086, DS-093, DS-095, DS-096, DS-097, DS-098, DS-100
- Exact Page@10：DS-008, DS-021, DS-022, DS-023, DS-040, DS-043, DS-044, DS-045, DS-046, DS-047, DS-049, DS-050, DS-072, DS-080, DS-081, DS-082, DS-085, DS-086, DS-092, DS-093, DS-095, DS-096, DS-097, DS-098, DS-099, DS-100

## 逐题 Top-1

| Case | Type | Top-1 paper | Page | Score | Paper hit | Exact page hit |
| --- | --- | --- | ---: | ---: | --- | --- |
| DS-001 | method | arxiv:2304.03442 | 13 | 0.6384 | False | False |
| DS-002 | fact | arxiv:2210.03629 | 4 | 0.5900 | True | True |
| DS-003 | fact | arxiv:2305.15334 | 1 | 0.6251 | False | False |
| DS-004 | method | arxiv:2302.04761 | 11 | 0.6321 | True | False |
| DS-005 | method | arxiv:2303.11366 | 2 | 0.6697 | True | False |
| DS-006 | fact | arxiv:2303.11366 | 2 | 0.5983 | True | True |
| DS-007 | method | arxiv:2310.04406 | 4 | 0.6418 | True | True |
| DS-008 | fact | arxiv:2310.04406 | 16 | 0.6030 | True | False |
| DS-009 | method | arxiv:2310.08560 | 1 | 0.5788 | True | True |
| DS-010 | method | arxiv:2310.08560 | 1 | 0.6223 | True | True |
| DS-011 | method | arxiv:2304.03442 | 2 | 0.6203 | True | True |
| DS-012 | fact | arxiv:2304.03442 | 15 | 0.5572 | True | True |
| DS-013 | method | arxiv:2305.16291 | 3 | 0.5744 | True | True |
| DS-014 | method | arxiv:2305.16291 | 2 | 0.6288 | True | True |
| DS-015 | method | arxiv:2303.17760 | 5 | 0.6848 | True | False |
| DS-016 | method | arxiv:2307.07924 | 4 | 0.6523 | False | False |
| DS-017 | method | arxiv:2308.08155 | 2 | 0.6752 | True | True |
| DS-018 | method | arxiv:2308.08155 | 2 | 0.6344 | True | False |
| DS-019 | fact | arxiv:2308.03688 | 1 | 0.5926 | True | True |
| DS-020 | method | arxiv:2308.03688 | 1 | 0.5933 | True | True |
| DS-021 | cross_paper | arxiv:2302.04761 | 3 | 0.6026 | True | True |
| DS-022 | cross_paper | arxiv:2310.04406 | 4 | 0.6046 | True | True |
| DS-023 | cross_paper | arxiv:2309.02427 | 9 | 0.5930 | False | False |
| DS-024 | cross_paper | arxiv:2303.17760 | 5 | 0.6372 | True | False |
| DS-025 | cross_paper | arxiv:2305.16291 | 3 | 0.5818 | True | True |
| DS-026 | method | arxiv:2205.00445 | 4 | 0.5982 | True | True |
| DS-027 | method | arxiv:2303.17651 | 2 | 0.6757 | True | True |
| DS-028 | method | arxiv:2305.10601 | 4 | 0.5741 | True | True |
| DS-029 | method | arxiv:2305.10250 | 4 | 0.7358 | True | True |
| DS-030 | method | arxiv:2303.17580 | 5 | 0.6294 | True | True |
| DS-031 | method | arxiv:2305.15334 | 5 | 0.6547 | True | True |
| DS-032 | method | arxiv:2305.15334 | 3 | 0.6124 | False | False |
| DS-033 | method | arxiv:2308.10848 | 3 | 0.6363 | True | True |
| DS-034 | method | arxiv:2308.00352 | 2 | 0.5586 | True | True |
| DS-035 | method | arxiv:2307.13854 | 2 | 0.5876 | True | True |
| DS-036 | method | arxiv:2303.17651 | 9 | 0.6342 | True | False |
| DS-037 | fact | arxiv:2305.10601 | 4 | 0.6511 | True | True |
| DS-038 | method | arxiv:2307.16789 | 5 | 0.6203 | True | True |
| DS-039 | fact | arxiv:2308.10848 | 2 | 0.5237 | True | False |
| DS-040 | fact | arxiv:2401.13919 | 8 | 0.6656 | False | False |
| DS-041 | cross_paper | arxiv:2303.11366 | 2 | 0.6383 | True | True |
| DS-042 | cross_paper | arxiv:2310.04406 | 4 | 0.6540 | True | True |
| DS-043 | cross_paper | arxiv:2310.08560 | 1 | 0.6161 | True | True |
| DS-044 | cross_paper | arxiv:2310.06770 | 29 | 0.5598 | False | False |
| DS-045 | cross_paper | arxiv:2305.15334 | 8 | 0.6157 | True | False |
| DS-046 | cross_paper | arxiv:2303.17760 | 5 | 0.6565 | True | False |
| DS-047 | cross_paper | arxiv:2404.07972 | 9 | 0.6091 | False | False |
| DS-048 | cross_paper | arxiv:2304.03442 | 8 | 0.6021 | True | False |
| DS-049 | cross_paper | arxiv:2303.17760 | 3 | 0.6210 | False | False |
| DS-050 | cross_paper | arxiv:2310.06770 | 29 | 0.5825 | False | False |
| DS-051 | method | arxiv:2305.11738 | 1 | 0.6121 | True | True |
| DS-052 | method | arxiv:2310.04406 | 3 | 0.6256 | False | False |
| DS-053 | method | arxiv:2308.10144 | 3 | 0.6156 | True | True |
| DS-054 | method | arxiv:2309.02427 | 9 | 0.6825 | True | True |
| DS-055 | method | arxiv:2310.12823 | 3 | 0.5849 | True | True |
| DS-056 | method | arxiv:2309.10691 | 2 | 0.6301 | True | True |
| DS-057 | method | arxiv:2309.15817 | 1 | 0.6270 | True | True |
| DS-058 | fact | arxiv:2306.06070 | 2 | 0.5989 | True | False |
| DS-059 | method | arxiv:2401.13919 | 1 | 0.6172 | True | True |
| DS-060 | fact | arxiv:2403.07718 | 2 | 0.6109 | True | True |
| DS-061 | fact | arxiv:2404.07972 | 6 | 0.6067 | True | True |
| DS-062 | fact | arxiv:2311.12983 | 6 | 0.6158 | True | True |
| DS-063 | method | arxiv:2401.13178 | 2 | 0.5752 | True | True |
| DS-064 | method | arxiv:2406.12045 | 4 | 0.6185 | True | True |
| DS-065 | fact | arxiv:2310.06770 | 2 | 0.6060 | True | True |
| DS-066 | method | arxiv:2310.06770 | 1 | 0.6049 | False | False |
| DS-067 | method | arxiv:2308.08155 | 9 | 0.5910 | False | False |
| DS-068 | method | arxiv:2310.11511 | 1 | 0.6684 | True | True |
| DS-069 | method | arxiv:2401.15884 | 5 | 0.6771 | True | True |
| DS-070 | method | arxiv:2403.14403 | 5 | 0.6319 | True | True |
| DS-071 | method | arxiv:2305.11738 | 1 | 0.6167 | True | False |
| DS-072 | fact | arxiv:2308.03688 | 26 | 0.5628 | False | False |
| DS-073 | method | arxiv:2310.12823 | 2 | 0.5533 | True | True |
| DS-074 | fact | arxiv:2309.15817 | 31 | 0.6415 | True | False |
| DS-075 | fact | arxiv:2306.06070 | 7 | 0.5985 | True | True |
| DS-076 | fact | arxiv:2401.13919 | 2 | 0.5882 | True | True |
| DS-077 | fact | arxiv:2404.07972 | 10 | 0.5895 | True | True |
| DS-078 | fact | arxiv:2406.12045 | 7 | 0.6608 | True | True |
| DS-079 | fact | arxiv:2310.06770 | 6 | 0.6603 | True | True |
| DS-080 | fact | arxiv:2309.15817 | 24 | 0.5601 | False | False |
| DS-081 | cross_paper | arxiv:2303.17651 | 15 | 0.5975 | True | False |
| DS-082 | cross_paper | arxiv:2305.10601 | 4 | 0.6594 | True | True |
| DS-083 | cross_paper | arxiv:2303.11366 | 2 | 0.5916 | True | True |
| DS-084 | cross_paper | arxiv:2310.11511 | 22 | 0.5934 | False | False |
| DS-085 | cross_paper | arxiv:2310.12823 | 5 | 0.5631 | True | True |
| DS-086 | cross_paper | arxiv:2307.16789 | 16 | 0.6336 | False | False |
| DS-087 | cross_paper | arxiv:2406.12045 | 2 | 0.5993 | True | True |
| DS-088 | cross_paper | arxiv:2404.07972 | 9 | 0.5770 | False | False |
| DS-089 | cross_paper | arxiv:2307.13854 | 5 | 0.5308 | True | True |
| DS-090 | cross_paper | arxiv:2306.06070 | 5 | 0.6085 | True | True |
| DS-091 | cross_paper | arxiv:2404.07972 | 26 | 0.5489 | True | False |
| DS-092 | cross_paper | arxiv:2311.12983 | 9 | 0.5951 | True | False |
| DS-093 | cross_paper | arxiv:2401.13178 | 19 | 0.5739 | True | False |
| DS-094 | cross_paper | arxiv:2406.12045 | 6 | 0.6403 | True | True |
| DS-095 | cross_paper | arxiv:2310.06770 | 16 | 0.6074 | True | False |
| DS-096 | cross_paper | arxiv:2307.07924 | 3 | 0.5548 | True | True |
| DS-097 | cross_paper | arxiv:2310.11511 | 6 | 0.5974 | True | True |
| DS-098 | cross_paper | arxiv:2403.14403 | 5 | 0.5739 | True | True |
| DS-099 | cross_paper | arxiv:2403.14403 | 5 | 0.6372 | True | True |
| DS-100 | cross_paper | arxiv:2404.07972 | 26 | 0.6146 | True | False |

## 口径说明

- Paper Recall 对跨论文问题按目标论文覆盖比例计算。
- Exact Page 要求 `paper_id + page_number` 同时匹配人工标注。
- 标注页不是所有可能相关页面的穷举，因此 Exact Page 指标是严格下界。
- Same-page Redundancy 衡量同一论文同一页的多个 Chunk 占用 Top-K 的比例。
- 本报告没有调用 LLM，也没有使用 LLM-as-a-judge。
