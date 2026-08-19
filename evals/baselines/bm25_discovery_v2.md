# Retriever Baseline: bm25_discovery_v2

- 评估日期：`2026-08-17`
- Dataset：`evals/datasets/retrieval_discovery_v2.jsonl`（50 cases）
- Corpus：`agent-seed-v2` / v2
- Collection：`agent_seed_v2_bge_m3_chunking_v1`
- Embedding：`BAAI/bge-m3`
- Chunking：`chunking_v1`
- Strategy：`bm25`
- Strategy parameters：`{'bm25_k1': 1.5, 'bm25_b': 0.75, 'tokenizer': 'english_stopwords_porter_stemmer'}`
- First query / subsequent mean：0.51 / 0.34 ms
- P50 / P95 / Max latency：0.29 / 0.6 / 0.78 ms

## 总体指标

| K | Paper Hit | Paper Recall | Complete Papers | Exact Page Hit | Exact Page Recall | Complete Pages | Same-page Redundancy |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 84.00% | 70.17% | 58.00% | 50.00% | 39.67% | 30.00% | 0.00% |
| 3 | 86.00% | 75.17% | 66.00% | 78.00% | 65.17% | 54.00% | 8.67% |
| 5 | 92.00% | 84.67% | 78.00% | 90.00% | 78.17% | 68.00% | 10.00% |
| 10 | 92.00% | 86.83% | 80.00% | 90.00% | 81.33% | 72.00% | 13.04% |

- Paper MRR@10：0.8620
- Exact Page MRR@10：0.6493

## 初步观察

- Top-10 Paper Recall 为 86.83%；完整覆盖率为 80.00%。
- Top-10 Exact Page Recall 为 81.33%；该指标受非穷举页码标注影响，是严格下界。
- Top-10 Same-page Redundancy 为 13.04%。
- 从 Top-5 增加到 Top-10，Paper Recall 变化 +2.16%，Exact Page Recall 变化 +3.16%，同页冗余变化 +3.04%。

## 按问题类型

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cross_paper | 15 | 76.11% | 53.33% | 64.44% | 0.8800 | 0.7578 |
| fact | 9 | 77.78% | 77.78% | 77.78% | 0.6333 | 0.4204 |
| method | 26 | 96.15% | 96.15% | 92.31% | 0.9308 | 0.6660 |

## 按难度

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| hard | 36 | 84.49% | 75.00% | 76.85% | 0.8361 | 0.6486 |
| medium | 14 | 92.86% | 92.86% | 92.86% | 0.9286 | 0.6512 |

## 按 Evaluation Split

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| challenge | 25 | 85.67% | 72.00% | 84.67% | 0.9080 | 0.7313 |
| paired_anchor | 25 | 88.00% | 88.00% | 78.00% | 0.8160 | 0.5673 |

## 未完整覆盖的 Case

- Paper@10：DS-002, DS-019, DS-020, DS-041, DS-043, DS-045, DS-046, DS-047, DS-049, DS-050
- Exact Page@10：DS-002, DS-016, DS-019, DS-020, DS-021, DS-022, DS-024, DS-041, DS-043, DS-045, DS-046, DS-047, DS-049, DS-050

## 逐题 Top-1

| Case | Type | Top-1 paper | Page | Score | Paper hit | Exact page hit |
| --- | --- | --- | ---: | ---: | --- | --- |
| DS-001 | method | arxiv:2210.03629 | 26 | 4.1548 | True | False |
| DS-002 | fact | - | - | - | False | False |
| DS-003 | fact | arxiv:2302.04761 | 2 | 1.6134 | True | True |
| DS-004 | method | arxiv:2302.04761 | 3 | 6.5775 | True | True |
| DS-005 | method | arxiv:2303.11366 | 4 | 7.9731 | True | True |
| DS-006 | fact | arxiv:2303.11366 | 9 | 4.8643 | True | False |
| DS-007 | method | arxiv:2310.04406 | 4 | 12.1992 | True | True |
| DS-008 | fact | arxiv:2308.00352 | 7 | 2.7612 | False | False |
| DS-009 | method | arxiv:2310.08560 | 1 | 6.4155 | True | True |
| DS-010 | method | arxiv:2307.16789 | 24 | 2.7905 | False | False |
| DS-011 | method | arxiv:2304.03442 | 13 | 7.8127 | True | False |
| DS-012 | fact | arxiv:2304.03442 | 15 | 3.7233 | True | True |
| DS-013 | method | arxiv:2305.16291 | 8 | 10.5844 | True | False |
| DS-014 | method | arxiv:2305.16291 | 39 | 5.8561 | True | False |
| DS-015 | method | arxiv:2303.17760 | 5 | 10.9322 | True | False |
| DS-016 | method | arxiv:2303.17760 | 5 | 0.8587 | True | False |
| DS-017 | method | arxiv:2308.08155 | 1 | 5.1225 | True | True |
| DS-018 | method | arxiv:2308.08155 | 25 | 5.4558 | True | False |
| DS-019 | fact | - | - | - | False | False |
| DS-020 | method | - | - | - | False | False |
| DS-021 | cross_paper | arxiv:2302.04761 | 3 | 6.5775 | True | True |
| DS-022 | cross_paper | arxiv:2310.04406 | 4 | 10.6239 | True | True |
| DS-023 | cross_paper | arxiv:2310.08560 | 2 | 7.8226 | True | True |
| DS-024 | cross_paper | arxiv:2303.17760 | 5 | 8.3238 | True | False |
| DS-025 | cross_paper | arxiv:2305.16291 | 3 | 9.2429 | True | True |
| DS-026 | method | arxiv:2205.00445 | 4 | 8.2710 | True | True |
| DS-027 | method | arxiv:2303.17651 | 6 | 2.4358 | True | False |
| DS-028 | method | arxiv:2305.10601 | 2 | 8.2130 | True | True |
| DS-029 | method | arxiv:2305.10250 | 9 | 11.9086 | True | False |
| DS-030 | method | arxiv:2303.17580 | 7 | 6.5226 | True | False |
| DS-031 | method | arxiv:2305.15334 | 5 | 3.8428 | True | True |
| DS-032 | method | arxiv:2307.16789 | 1 | 8.3374 | True | True |
| DS-033 | method | arxiv:2308.10848 | 3 | 10.9672 | True | True |
| DS-034 | method | arxiv:2308.00352 | 2 | 9.7938 | True | True |
| DS-035 | method | arxiv:2307.13854 | 2 | 3.5083 | True | True |
| DS-036 | method | arxiv:2303.17651 | 9 | 7.5375 | True | False |
| DS-037 | fact | arxiv:2305.10601 | 14 | 8.3998 | True | False |
| DS-038 | method | arxiv:2307.16789 | 6 | 10.1224 | True | True |
| DS-039 | fact | arxiv:2308.10848 | 2 | 8.3960 | True | False |
| DS-040 | fact | arxiv:2308.00352 | 25 | 3.3374 | False | False |
| DS-041 | cross_paper | arxiv:2303.11366 | 2 | 6.0348 | True | True |
| DS-042 | cross_paper | arxiv:2305.10601 | 4 | 8.9226 | True | True |
| DS-043 | cross_paper | arxiv:2310.08560 | 1 | 4.8143 | True | True |
| DS-044 | cross_paper | arxiv:2205.00445 | 4 | 5.7861 | True | True |
| DS-045 | cross_paper | arxiv:2302.04761 | 3 | 8.1378 | True | True |
| DS-046 | cross_paper | arxiv:2303.17760 | 5 | 5.3177 | True | False |
| DS-047 | cross_paper | - | - | - | False | False |
| DS-048 | cross_paper | arxiv:2304.03442 | 13 | 7.3742 | True | False |
| DS-049 | cross_paper | arxiv:2303.17760 | 5 | 1.4800 | False | False |
| DS-050 | cross_paper | arxiv:2205.00445 | 4 | 2.9150 | True | True |

## 口径说明

- Paper Recall 对跨论文问题按目标论文覆盖比例计算。
- Exact Page 要求 `paper_id + page_number` 同时匹配人工标注。
- 标注页不是所有可能相关页面的穷举，因此 Exact Page 指标是严格下界。
- Same-page Redundancy 衡量同一论文同一页的多个 Chunk 占用 Top-K 的比例。
- 本报告没有调用 LLM，也没有使用 LLM-as-a-judge。
