# Query Rewrite Candidate Pool 诊断

- Collection：`agent_seed_v2_bge_m3_chunking_v1`
- Candidate Pool：`50`
- RRF k：`60`
- Rewrite：`deepseek-v4-flash` / `query_rewrite_v1`

| Case | Target Paper | Original RRF Rank | Rewrite RRF Rank | Exact Page Rank | Classification |
| --- | --- | ---: | ---: | ---: | --- |
| DS-021 | arxiv:2210.03629 | 17 | 31 | 39 | rerankable_11_50 |
| DS-021 | arxiv:2302.04761 | 1 | 1 | 1 | top_10 |
| DS-025 | arxiv:2310.04406 | 4 | 14 | 14 | rerankable_11_50 |
| DS-025 | arxiv:2305.16291 | 1 | 1 | 1 | top_10 |
| DS-041 | arxiv:2303.11366 | 1 | 1 | 1 | top_10 |
| DS-041 | arxiv:2303.17651 | 15 | 18 | 18 | rerankable_11_50 |

## 口径

- `rerankable_11_50` 表示目标已进入融合 Top-50，Reranker 有机会提升到 Top-10。
- `outside_fused_top_50` 表示分支召回了目标，但当前 Top-50 Reranker 看不到它。
- `not_recalled_in_branches` 表示 8 路 Dense/BM25 Top-50 都没有目标论文。
- JSON 文件保留每条 Query 的 Dense/BM25 Paper Rank 与 Exact Page Rank。
