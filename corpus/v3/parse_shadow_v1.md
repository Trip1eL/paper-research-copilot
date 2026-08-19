# Corpus Parse Shadow：parse_shadow_v1

- Corpus：`agent-seed-v3` / v3
- Primary：`pypdf==6.10.2`
- Secondary：`pymupdf==1.28.2`
- Mode：Shadow；不执行 Chunk、Embedding 或 Qdrant 写入。

## 汇总

| Papers | Open rate | Pages | Primary flagged | Secondary selected | Recovered | Warning | Quarantined | Quarantine rate | P50 / P95 document |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 40 | 100.00% | 1387 | 22 | 8 | 0 | 7 | 15 | 1.0815% | 2608.46 / 7624.02 ms |

## 逐篇结果

| Paper | Status | Pages | Primary flagged | Secondary pages | Recovered | Warning pages | Structured fallback pages | Latency |
| --- | --- | ---: | ---: | --- | ---: | --- | --- | ---: |
| arxiv:2210.03629 | succeeded | 33 | 3 | p2, p14, p15 | 0 | - | p2, p14, p15 | 2340.32 ms |
| arxiv:2302.04761 | succeeded | 17 | 0 | - | 0 | - | - | 1596.86 ms |
| arxiv:2303.11366 | succeeded | 19 | 2 | p3 | 0 | p16 | p3 | 1966.13 ms |
| arxiv:2310.04406 | succeeded | 23 | 0 | - | 0 | - | - | 2818.78 ms |
| arxiv:2310.08560 | succeeded | 13 | 0 | - | 0 | - | - | 1336.68 ms |
| arxiv:2304.03442 | succeeded | 22 | 0 | - | 0 | - | - | 2608.46 ms |
| arxiv:2305.16291 | succeeded | 42 | 0 | - | 0 | - | - | 6621.04 ms |
| arxiv:2303.17760 | succeeded | 77 | 0 | - | 0 | - | - | 4660.55 ms |
| arxiv:2308.08155 | succeeded | 43 | 0 | - | 0 | - | - | 4138.87 ms |
| arxiv:2308.03688 | succeeded | 58 | 0 | - | 0 | - | - | 4397.83 ms |
| arxiv:2205.00445 | succeeded | 19 | 0 | - | 0 | - | - | 963.26 ms |
| arxiv:2303.17651 | succeeded | 54 | 0 | - | 0 | - | - | 3001.81 ms |
| arxiv:2305.10601 | succeeded | 14 | 4 | p2, p5, p7, p8 | 0 | - | p2, p5, p7, p8 | 1386.08 ms |
| arxiv:2305.10250 | succeeded | 11 | 0 | - | 0 | - | - | 995.05 ms |
| arxiv:2303.17580 | succeeded | 27 | 0 | - | 0 | - | - | 2511.39 ms |
| arxiv:2305.15334 | succeeded | 18 | 0 | - | 0 | - | - | 1530.31 ms |
| arxiv:2307.16789 | succeeded | 24 | 0 | - | 0 | - | - | 2085.82 ms |
| arxiv:2308.10848 | succeeded | 39 | 0 | - | 0 | - | - | 4222.44 ms |
| arxiv:2308.00352 | succeeded | 29 | 0 | - | 0 | - | - | 1729.92 ms |
| arxiv:2307.13854 | succeeded | 22 | 0 | - | 0 | - | - | 1695.67 ms |
| arxiv:2305.11738 | succeeded | 78 | 0 | - | 0 | - | - | 6632.30 ms |
| arxiv:2305.14992 | succeeded | 20 | 0 | - | 0 | - | - | 2845.31 ms |
| arxiv:2308.10144 | succeeded | 38 | 11 | - | 0 | p20, p31, p34, p37 | p16, p17, p28, p29, p30, p32, p33 | 2105.03 ms |
| arxiv:2309.02427 | succeeded | 32 | 0 | - | 0 | - | - | 3259.99 ms |
| arxiv:2310.12823 | succeeded | 31 | 0 | - | 0 | - | - | 2373.28 ms |
| arxiv:2309.10691 | succeeded | 35 | 0 | - | 0 | - | - | 5921.58 ms |
| arxiv:2309.15817 | succeeded | 70 | 0 | - | 0 | - | - | 8292.25 ms |
| arxiv:2306.06070 | succeeded | 24 | 0 | - | 0 | - | - | 2348.06 ms |
| arxiv:2401.13919 | succeeded | 27 | 0 | - | 0 | - | - | 2451.39 ms |
| arxiv:2403.07718 | succeeded | 21 | 0 | - | 0 | - | - | 3478.93 ms |
| arxiv:2404.07972 | succeeded | 51 | 0 | - | 0 | - | - | 4252.63 ms |
| arxiv:2311.12983 | succeeded | 24 | 1 | - | 0 | p16 | - | 2860.67 ms |
| arxiv:2401.13178 | succeeded | 38 | 0 | - | 0 | - | - | 6221.21 ms |
| arxiv:2406.12045 | succeeded | 50 | 0 | - | 0 | - | - | 3395.41 ms |
| arxiv:2310.06770 | succeeded | 52 | 1 | - | 0 | p22 | - | 7624.02 ms |
| arxiv:2405.15793 | succeeded | 118 | 0 | - | 0 | - | - | 14187.23 ms |
| arxiv:2307.07924 | succeeded | 13 | 0 | - | 0 | - | - | 1380.05 ms |
| arxiv:2310.11511 | succeeded | 30 | 0 | - | 0 | - | - | 4685.55 ms |
| arxiv:2401.15884 | succeeded | 16 | 0 | - | 0 | - | - | 1533.39 ms |
| arxiv:2403.14403 | succeeded | 15 | 0 | - | 0 | - | - | 2075.01 ms |

## 结论边界

- Primary flagged 表示需要对照，不等同于页面不可用。
- Quarantined 页面必须经过 Structured Parser 或人工处理后才能进入未来索引。
- 本报告不改变 Corpus v3 Manifest、Chunk 或现有 Qdrant Collection。
