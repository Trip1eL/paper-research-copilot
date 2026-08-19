# Query-aware Fusion Ablation v2

所有策略复用同一批 Dense/BM25 Top-50，只改变离线融合算法。

| Strategy | Paper@10 | Exact Page@5 | Exact Page@10 | Page MRR | Redundancy@10 | Paired Complete | Challenge Complete | Fixed | Kept | Pass |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| No Rewrite | 95.83% | 80.83% | 91.83% | 0.8099 | 15.20% | 96% | 84% | 1/3 | 0/3 | False |
| Flat Sum | 97.00% | **90.17%** | 92.33% | **0.8340** | 16.20% | 92% | 96% | 0/3 | 3/3 | False |
| Weighted original=0.4 | 98.00% | 89.17% | 93.33% | 0.8190 | 16.20% | 96% | 96% | 1/3 | 3/3 | False |
| Weighted original=0.5 | 96.83% | 88.67% | 91.83% | 0.8273 | 16.20% | 96% | 88% | 1/3 | 1/3 | False |
| Weighted original=0.6 | 95.83% | 89.33% | 90.83% | 0.8130 | 17.40% | 96% | 84% | 1/3 | 0/3 | False |
| Max-over-query | **99.00%** | 89.83% | **97.00%** | 0.8055 | **16.00%** | **100%** | **96%** | **2/3** | **3/3** | **True** |

## 验收条件

- 修复 `DS-021/025/041` 至少 2 条。
- Challenge Complete Papers@10 不低于 96%。
- Paired Complete Papers@10 不低于 96%。
- Overall Exact Page@10 不低于 92.33%。
- `DS-045/046/049` 必须全部保持完整覆盖。

## 结果解释

`Max-over-query` 是唯一满足全部预设验收条件的策略：修复 `DS-021` 和 `DS-025`，保持
`DS-045/046/049`，只剩 `DS-041` 未完整覆盖。融合计算平均约 `0.46 ms`，没有新增模型调用。

它的代价是 Exact Page@1 从 Flat Sum 的 `60.17%` 降到 `54.67%`，Page MRR 从 `0.8340`
降到 `0.8055`；但 Exact Page@3 从 `83.67%` 提升到 `85.33%`，Exact Page@10 提升到
`97.00%`。因此它更擅长保证多意图覆盖和长列表证据召回，不一定把严格标注页排在第一位。

权重实验也给出清晰趋势：原始 Query 权重从 `0.4` 增至 `0.5/0.6` 后，Challenge Complete
从 `96%` 降到 `88%/84%`，说明 Rewrite 的总体贡献不能过度压低；`0.4` 能修复 `DS-025`，
但无法修复 `DS-021`，不如 Max-over-query。

当前将 Max-over-query 作为最佳 Query Rewrite Fusion 实验策略，但不替换低延迟的默认
Hybrid RRF。下一步针对 Top-50 内唯一剩余失败 `DS-041` 评估 Reranker，并单独观察 Page
MRR 和端到端延迟。
