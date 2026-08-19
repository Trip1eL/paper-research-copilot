# Corpus v3 Retriever 对照

## 实验设置

- Dataset：`evals/datasets/retrieval_discovery_v3.jsonl`（100 cases）
- Corpus：`agent-seed-v3`，40 篇、1,387 页、2,152 Chunks
- Collection：`agent_seed_v3_bge_m3_chunking_v1`
- Dense Embedding：`BAAI/bge-m3`；Hybrid 使用 Dense + BM25 + RRF
- Top-K：10；本报告只使用已保存结果，不调用 LLM 或 Embedding API

## 总体结果

| Strategy | Paper Recall | Complete Papers | Exact Page Recall | Complete Pages | Paper MRR | Page MRR | Redundancy | P50 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense | 92.00% | 85.00% | 83.92% | 74.00% | 0.8835 | 0.7264 | 10.10% | 256.75 ms |
| BM25 | 67.92% | 58.00% | 65.67% | 55.00% | 0.7078 | 0.5579 | 10.52% | 0.28 ms |
| Hybrid RRF | 92.17% | 84.00% | 86.92% | 75.00% | 0.9194 | 0.7962 | 11.20% | 231.12 ms |

## 分组结果

### 旧 50 题（DS-001..050）

| Strategy | Paper Recall | Complete Papers | Exact Page Recall | Complete Pages | Paper MRR | Page MRR | Redundancy | P50 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense | 93.50% | 88.00% | 83.83% | 76.00% | 0.8695 | 0.6965 | 11.60% | 258.85 ms |
| BM25 | 84.83% | 76.00% | 80.33% | 70.00% | 0.8230 | 0.6193 | 12.20% | 0.29 ms |
| Hybrid RRF | 95.83% | 90.00% | 89.83% | 80.00% | 0.9390 | 0.8074 | 12.80% | 235.55 ms |

### 新增 50 题（DS-051..100）

| Strategy | Paper Recall | Complete Papers | Exact Page Recall | Complete Pages | Paper MRR | Page MRR | Redundancy | P50 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense | 90.50% | 82.00% | 84.00% | 72.00% | 0.8975 | 0.7564 | 8.60% | 252.99 ms |
| BM25 | 51.00% | 40.00% | 51.00% | 40.00% | 0.5925 | 0.4965 | 8.84% | 0.27 ms |
| Hybrid RRF | 88.50% | 78.00% | 84.00% | 70.00% | 0.8998 | 0.7851 | 9.60% | 229.74 ms |

### 新增单论文题（DS-051..080）

| Strategy | Paper Recall | Complete Papers | Exact Page Recall | Complete Pages | Paper MRR | Page MRR | Redundancy | P50 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense | 96.67% | 96.67% | 93.33% | 93.33% | 0.8792 | 0.7881 | 10.00% | 252.63 ms |
| BM25 | 63.33% | 63.33% | 63.33% | 63.33% | 0.5875 | 0.4997 | 9.33% | 0.27 ms |
| Hybrid RRF | 96.67% | 96.67% | 96.67% | 96.67% | 0.8886 | 0.8192 | 10.67% | 229.95 ms |

### 新增跨论文题（DS-081..100）

| Strategy | Paper Recall | Complete Papers | Exact Page Recall | Complete Pages | Paper MRR | Page MRR | Redundancy | P50 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense | 81.25% | 60.00% | 70.00% | 40.00% | 0.9250 | 0.7088 | 6.50% | 256.95 ms |
| BM25 | 32.50% | 5.00% | 32.50% | 5.00% | 0.6000 | 0.4917 | 8.11% | 0.26 ms |
| Hybrid RRF | 76.25% | 50.00% | 65.00% | 30.00% | 0.9167 | 0.7338 | 8.00% | 229.74 ms |

## 扩库漂移

同一批 DS-001..050 在 v2（20 篇）和 v3（40 篇）中的 Top-10 指标差值：

| Strategy | Paper Recall | Complete Papers | Exact Page Recall | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: |
| Dense | -2.00% | -4.00% | -4.00% | -0.0505 | -0.0225 |
| BM25 | -2.00% | -4.00% | -1.00% | -0.0390 | -0.0300 |
| Hybrid RRF | +0.00% | +0.00% | -2.00% | -0.0250 | -0.0025 |

## 结论

- Hybrid RRF 的总体 Paper Recall@10 为 92.17%，与 Dense 的 92.00% 基本持平；Exact Page Recall@10 从 83.92% 提升到 86.92%。
- BM25 在中文问题、英文正文的跨语言设置下经常没有有效词项匹配，不适合作为独立默认 Retriever；其价值是为 Hybrid 补充公式名、指标名和精确术语。
- 新增跨论文题上 Hybrid Complete Papers@10 仅为 50.00%，说明全局 Hybrid 仍会被一个子主题占满；这支持 Agent Runtime 对跨论文任务继续使用 Query Decomposition + Coverage Merge。
- 因此 v3 不触发新的参数微调：单论文 Discovery 保持 Hybrid RRF，跨论文保持 Coverage-aware Retrieval。
