# Reranker Ablation v2

| Strategy | Paper@1 | Paper@10 | Paper MRR | Page@1 | Page@10 | Page MRR | Paired Complete | Challenge Complete | DS-041 | Retrieval P50/P95 | Reranker P50/P95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| Fast Base | 79.17% | 95.83% | 0.9640 | 59.67% | 91.83% | 0.8099 | 96.00% | 84.00% | False | 349/479 ms | - |
| Fast + BGE Reranker | 83.17% | 98.50% | 0.9900 | 60.67% | 98.00% | 0.8412 | 96.00% | 96.00% | True | 1748/1956 ms | 1390/1579 ms |
| Deep Max Base | 84.17% | 99.00% | 1.0000 | 54.67% | 97.00% | 0.8055 | 100.00% | 96.00% | False | 1416/1700 ms | - |
| Deep Max + BGE Reranker | 83.17% | 98.50% | 0.9867 | 61.17% | 98.00% | 0.8492 | 96.00% | 96.00% | True | 2781/3297 ms | 1361/1726 ms |

## 结论

- `BAAI/bge-reranker-v2-m3` 对 50 个 Top-50 Candidate Pool 的单次重排 P50 约为 `1.4 s`。
- Fast + Reranker 将 challenge Complete Papers@10 从 `84%` 提升到 `96%`，并将 Page MRR
  从 `0.8099` 提升到 `0.8412`，但 Retrieval P50 从 `349 ms` 增至 `1748 ms`。
- Deep + Reranker 修复了 `DS-041`，并将 Page MRR 提升到 `0.8492`；但 `DS-021` 和
  `DS-046` 出现回退，使 Paper@10 从 `99.00%` 降到 `98.50%`、paired Complete 从
  `100%` 降到 `96%`，未通过预设验收。
- Fast + Reranker 保留为高质量增强模式候选；Deep 叠加方案保留为消融结果。默认低延迟
  Discovery 仍使用 Hybrid RRF。

这里的 Deep Retrieval 延迟不含约 `6.6 s` 的 Query Rewrite 生成耗时；完整在线链路还需将
该耗时相加。
