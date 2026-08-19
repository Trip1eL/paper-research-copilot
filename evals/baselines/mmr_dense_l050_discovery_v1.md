# Retriever Baseline: mmr_dense_l050_discovery_v1

- 评估日期：`2026-08-16`
- Dataset：`evals/datasets/retrieval_discovery_v1.jsonl`（25 cases）
- Corpus：`agent-seed-v1` / v1
- Collection：`agent_seed_v1_bge_m3_chunking_v1`
- Embedding：`BAAI/bge-m3`
- Chunking：`chunking_v1`
- Strategy：`mmr_dense`
- Strategy parameters：`{'candidate_pool_size': 50, 'lambda_mult': 0.5}`
- First query / subsequent mean：556.4 / 261.54 ms
- P50 / P95 / Max latency：265.09 / 320.9 / 556.4 ms

## 总体指标

| K | Paper Hit | Paper Recall | Complete Papers | Exact Page Hit | Exact Page Recall | Complete Pages | Same-page Redundancy |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 96.00% | 86.00% | 76.00% | 64.00% | 56.00% | 48.00% | 0.00% |
| 3 | 100.00% | 100.00% | 100.00% | 76.00% | 66.00% | 56.00% | 0.00% |
| 5 | 100.00% | 100.00% | 100.00% | 76.00% | 66.00% | 56.00% | 0.00% |
| 10 | 100.00% | 100.00% | 100.00% | 88.00% | 82.00% | 76.00% | 0.40% |

- Paper MRR@10：0.9800
- Exact Page MRR@10：0.7168

## 初步观察

- Top-10 Paper Recall 为 100.00%；完整覆盖率为 100.00%。
- Top-10 Exact Page Recall 为 82.00%；该指标受非穷举页码标注影响，是严格下界。
- Top-10 Same-page Redundancy 为 0.40%。
- 从 Top-5 增加到 Top-10，Paper Recall 变化 +0.00%，Exact Page Recall 变化 +16.00%，同页冗余变化 +0.40%。

## 按问题类型

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cross_paper | 5 | 100.00% | 100.00% | 70.00% | 1.0000 | 0.9000 |
| fact | 6 | 100.00% | 100.00% | 83.33% | 1.0000 | 0.6852 |
| method | 14 | 100.00% | 100.00% | 85.71% | 0.9643 | 0.6650 |

## 按难度

| Group | Cases | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| hard | 11 | 100.00% | 100.00% | 77.27% | 1.0000 | 0.7879 |
| medium | 14 | 100.00% | 100.00% | 85.71% | 0.9643 | 0.6610 |

## 未完整覆盖的 Case

- Paper@10：无
- Exact Page@10：DS-005, DS-008, DS-018, DS-021, DS-022, DS-023

## 逐题 Top-1

| Case | Type | Top-1 paper | Page | Score | Paper hit | Exact page hit |
| --- | --- | --- | ---: | ---: | --- | --- |
| DS-001 | method | arxiv:2304.03442 | 13 | 0.6382 | False | False |
| DS-002 | fact | arxiv:2210.03629 | 4 | 0.5895 | True | True |
| DS-003 | fact | arxiv:2302.04761 | 4 | 0.6209 | True | False |
| DS-004 | method | arxiv:2302.04761 | 11 | 0.6316 | True | False |
| DS-005 | method | arxiv:2303.11366 | 2 | 0.6691 | True | False |
| DS-006 | fact | arxiv:2303.11366 | 2 | 0.5981 | True | True |
| DS-007 | method | arxiv:2310.04406 | 4 | 0.6418 | True | True |
| DS-008 | fact | arxiv:2310.04406 | 16 | 0.6030 | True | False |
| DS-009 | method | arxiv:2310.08560 | 1 | 0.5788 | True | True |
| DS-010 | method | arxiv:2310.08560 | 1 | 0.6216 | True | True |
| DS-011 | method | arxiv:2304.03442 | 2 | 0.6203 | True | True |
| DS-012 | fact | arxiv:2304.03442 | 15 | 0.5575 | True | True |
| DS-013 | method | arxiv:2305.16291 | 3 | 0.5741 | True | True |
| DS-014 | method | arxiv:2305.16291 | 2 | 0.6293 | True | True |
| DS-015 | method | arxiv:2303.17760 | 5 | 0.6848 | True | False |
| DS-016 | method | arxiv:2303.17760 | 7 | 0.6423 | True | False |
| DS-017 | method | arxiv:2308.08155 | 2 | 0.6751 | True | True |
| DS-018 | method | arxiv:2308.08155 | 2 | 0.6343 | True | False |
| DS-019 | fact | arxiv:2308.03688 | 1 | 0.5926 | True | True |
| DS-020 | method | arxiv:2308.03688 | 1 | 0.5933 | True | True |
| DS-021 | cross_paper | arxiv:2302.04761 | 3 | 0.6026 | True | True |
| DS-022 | cross_paper | arxiv:2310.04406 | 4 | 0.6046 | True | True |
| DS-023 | cross_paper | arxiv:2310.08560 | 1 | 0.5920 | True | True |
| DS-024 | cross_paper | arxiv:2303.17760 | 5 | 0.6360 | True | False |
| DS-025 | cross_paper | arxiv:2305.16291 | 3 | 0.5824 | True | True |

## 口径说明

- Paper Recall 对跨论文问题按目标论文覆盖比例计算。
- Exact Page 要求 `paper_id + page_number` 同时匹配人工标注。
- 标注页不是所有可能相关页面的穷举，因此 Exact Page 指标是严格下界。
- Same-page Redundancy 衡量同一论文同一页的多个 Chunk 占用 Top-K 的比例。
- 本报告没有调用 LLM，也没有使用 LLM-as-a-judge。
