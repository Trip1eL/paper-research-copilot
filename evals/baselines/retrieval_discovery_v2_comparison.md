# Retrieval Discovery v2 对照报告

## 实验设置

```text
Corpus: agent-seed-v2（20 papers / 604 pages / 971 chunks）
Collection: agent_seed_v2_bge_m3_chunking_v1
Embedding: BAAI/bge-m3（1024 dimensions）
Chunking: chunking_v1（3200 chars / 400 overlap）
Top-K: 10
Hybrid: Dense pool=50 / BM25 pool=50 / RRF k=60
Dataset: retrieval_discovery_v2（50 cases）
```

`DS-001..025` 是与 v1 问题和 Relevant Pages 完全相同的 `paired_anchor`；
`DS-026..050` 是新增的 `challenge`。Exact Page 标注不是所有相关页面的穷举，因此相关
指标是严格下界。

## v2 总体结果

| Strategy | Paper@1 | Paper@5 | Paper@10 | Exact Page@5 | Exact Page@10 | Paper MRR | Page MRR | Redundancy@10 | P50 / P95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense | 74.17% | 90.33% | 95.50% | 84.33% | 87.83% | 0.9200 | 0.7190 | 12.80% | 267 / 307 ms |
| BM25 | 70.17% | 84.67% | 86.83% | 78.17% | 81.33% | 0.8620 | 0.6493 | 13.04% | 0.29 / 0.60 ms |
| Hybrid RRF | **79.17%** | **92.33%** | **95.83%** | 80.83% | **91.83%** | **0.9640** | **0.8099** | 15.20% | 265 / 298 ms |

Hybrid RRF 的 Paper 与页码 Top-10、MRR 最好，但 Exact Page@5 低于 Dense，且同页冗余最高。
这说明融合改善了整体排序和长列表覆盖，尚不能证明每个截断位置都优于 Dense。

## Paired Anchors：新增语料干扰

| Strategy | v1 -> v2 Paper@1 | v1 -> v2 Paper@10 | v1 -> v2 Exact Page@5 | v1 -> v2 Exact Page@10 | v1 -> v2 Paper MRR |
| --- | ---: | ---: | ---: | ---: | ---: |
| Dense | 86% -> 82% | 98% -> 98% | 90% -> 90% | 96% -> 90% | 0.9733 -> 0.9500 |
| BM25 | 70% -> 70% | 88% -> 88% | 74% -> 74% | 82% -> 78% | 0.8300 -> 0.8160 |
| Hybrid RRF | 90% -> 86% | 100% -> 98% | 90% -> 84% | 96% -> 96% | 1.0000 -> 0.9680 |

新增 10 篇同主题论文后，三种方法的 Top-10 Paper Recall 最多下降 2 个百分点，但早期排序、
页码定位和 MRR 有可见退化。v1 高分并非完全由 Retriever 稳健性带来，较小的候选空间也是
原因之一。

## Challenge Cases

| Strategy | Paper@1 | Paper@5 | Paper@10 | Complete Papers@10 | Exact Page@5 | Exact Page@10 | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense | 66.33% | 84.67% | 93.00% | 88% | **78.67%** | 85.67% | 0.8900 | 0.6920 |
| BM25 | 70.33% | 83.33% | 85.67% | 72% | 82.33% | 84.67% | 0.9080 | 0.7313 |
| Hybrid RRF | **72.33%** | **88.67%** | **93.67%** | 84% | 77.67% | **87.67%** | **0.9600** | **0.8133** |

Hybrid 在 challenge 上提高 Top-1、Top-10 和 MRR，但 Complete Papers@10 低于 Dense。主要
原因是跨论文问题中一个主题或一篇论文占据多个候选位置，导致另一个目标论文未进入 Top-10。

## 失败 Case

- Dense 未完整覆盖目标论文：`DS-021`、`DS-044`、`DS-046`、`DS-049`。
- BM25 未完整覆盖目标论文：`DS-002`、`DS-019`、`DS-020`、`DS-041`、`DS-043`、
  `DS-045`、`DS-046`、`DS-047`、`DS-049`、`DS-050`。
- Hybrid RRF 未完整覆盖目标论文：`DS-021`、`DS-041`、`DS-045`、`DS-046`、`DS-049`。
- BM25 在 `DS-002`、`DS-019`、`DS-020`、`DS-047` 上没有正分结果，反映当前英文
  tokenizer 对纯中文概念表述的词面召回缺口。
- `DS-045` 与 `DS-046` 分别要求覆盖 3 篇和 4 篇论文，Top-10 容易被已命中论文的多个
  Chunk 占满；`DS-041` 则暴露 Reflection 与 Self-Refine 相邻机制的区分问题。

## 当前结论

Hybrid RRF 仍是 Discovery 的最佳总体 Baseline，Dense 仍保留为 Evidence 定位与关键对照。
当前结果只定位了 Query 词面缺口与跨论文候选挤占，尚未分别测量 Query Rewrite 和 Reranker
能否稳定修复这些 Case，因此本轮不引入二者。下一步应先按失败类型设计消融实验，再决定
增加哪一种复杂度。

## Hybrid RRF + MMR 消融

固定 Candidate Pool 为 50、RRF `k=60`，分别测试 MMR `lambda=0.70 / 0.85 / 0.95`。

| Strategy | Paper@10 | Exact Page@5 | Exact Page@10 | Redundancy@10 | Challenge Complete Papers@10 | Challenge Redundancy@10 | P50 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Hybrid RRF | 95.83% | 80.83% | **91.83%** | 15.20% | 84% | 16.80% | 265 ms |
| + MMR 0.70 | 95.83% | **83.33%** | 89.83% | **14.40%** | 84% | **16.00%** | 405 ms |
| + MMR 0.85 | 95.83% | 80.83% | **91.83%** | 15.00% | 84% | 16.40% | 369 ms |
| + MMR 0.95 | 95.83% | 80.83% | **91.83%** | 15.60% | 84% | 16.80% | 357 ms |

三个 Lambda 都没有修复 `DS-021`、`DS-041`、`DS-045`、`DS-046`、`DS-049` 中任何一个
缺失目标论文，Challenge Paper Recall@10 均保持 `93.67%`。`lambda=0.70` 的冗余下降只有
0.8 个百分点，同时 paired anchors 的 Exact Page@10 从 `96%` 降到 `92%`；`0.85` 基本
复现原始排序；`0.95` 的总体冗余反而升高。MMR 还需要读取候选向量并执行二次选择，本次
P50 增加约 90--140 ms。

因此 MMR 不接入默认 Discovery 链路，只保留为消融策略。当前多论文失败并非仅由候选间
语义重复造成，至少还包含 Query 对多个子意图表达不充分、融合候选中目标论文排名过低等
问题。下一步优先验证 Query Rewrite，再用 Reranker 处理已经召回但排序靠后的相邻机制。

## Query Rewrite 对照

`query_rewrite_v1` 使用 `deepseek-v4-flash` 为每个中文问题生成 3 条互补英文 Query，同时
保留原始 Query。4 个 Query 分别执行 Dense 与 BM25，最终对 8 路 Ranking 使用相同的
RRF `k=60` 融合。Rewrite 在检索计时前生成并缓存，因此 LLM 生成延迟与纯检索延迟分开。

| Strategy | Paper@1 | Paper@10 | Exact Page@5 | Exact Page@10 | Paper MRR | Page MRR | Redundancy@10 | Retrieval P50 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Hybrid RRF | 79.17% | 95.83% | 80.83% | 91.83% | 0.9640 | 0.8099 | **15.20%** | **265 ms** |
| + Query Rewrite | **82.17%** | **97.00%** | **90.17%** | **92.33%** | **0.9767** | **0.8340** | 16.20% | 1451 ms |

Rewrite 平均生成耗时为 `6615.84 ms/case`，不包含在表中的 Retrieval P50；若端到端串行执行，
两者都属于用户延迟。50 条记录共 150 条 Rewrite，对 Corpus slug、完整标题及标题前缀的自动
检查均为 0 命中，因此没有通过猜测论文名破坏 Discovery 的无标题泄漏约束。

### 分组变化

| Split | Strategy | Paper@10 | Complete Papers@10 | Exact Page@5 | Exact Page@10 | Redundancy@10 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Paired | Hybrid | **98%** | **96%** | 84% | **96%** | **13.60%** |
| Paired | + Rewrite | 96% | 92% | **90%** | 92% | 17.20% |
| Challenge | Hybrid | 93.67% | 84% | 77.67% | 87.67% | 16.80% |
| Challenge | + Rewrite | **98%** | **96%** | **90.33%** | **92.67%** | **15.20%** |

Query Rewrite 修复了 challenge 中的 `DS-045`、`DS-046`、`DS-049`，这些问题分别包含多个
API Tool Use、多智能体和模型编排子意图。英文分解 Query 让每个子意图获得独立 Ranking，
证明此前失败确实包含 Query 表达和跨语言词面缺口，而不只是结果多样性不足。

仍未修复 `DS-021` 和 `DS-041`，并新增 paired `DS-025` 回退。`DS-025` 的 3 条 Rewrite 都
强调 open-world、continuous learning 和 skill library，使 Voyager 的 Chunk 占满 Top-10，
原本由 Hybrid 召回的 Tree Search 目标被挤出。这说明简单地把所有 Query 等权 RRF 会放大
重复子意图，后续需要研究 Query 级权重、意图覆盖或 Reranker，而不是继续增加 Rewrite 数量。

### 当前决策

Query Rewrite 在困难集上有实质收益，但约 `6.6 s` 生成延迟、`1.45 s` 检索 P50、paired
回退和额外模型调用使其暂不替代默认 Hybrid。保留该策略和固定 Rewrite 缓存作为 Baseline；
下一步先检查融合 Candidate Pool 中缺失目标是否已经被召回，再决定引入 Reranker，或先做
轻量的子意图权重/去重。

## Query Rewrite Candidate Pool 诊断

对剩余失败 `DS-021/025/041` 复用固定 Rewrite，记录原始两路与 Rewrite 八路的 Dense/BM25
Top-50、融合 Paper Rank 和 Exact Page Rank：

| Case | 缺失目标 | Original RRF Rank | Rewrite RRF Rank | Exact Page Rank | 结论 |
| --- | --- | ---: | ---: | ---: | --- |
| DS-021 | ReAct | 17 | 31 | 39 | Top-50 内，可重排 |
| DS-025 | LATS | 4 | 14 | 14 | Top-50 内，可重排 |
| DS-041 | Self-Refine | 15 | 18 | 18 | Top-50 内，可重排 |

三个目标及其严格标注页都在融合 Top-50，没有 Branch Recall Failure。尤其 `DS-021` 的 ReAct
在第一个英文 Rewrite 上达到 Dense 第 3、BM25 第 1，却在八路融合后降到第 31；`DS-025`
的 LATS 在原始 Hybrid 中为第 4，Rewrite 后降到第 14。原因是其他 Rewrite 重复命中同一
竞争论文，当前按所有 Ranking 累加 RRF 分数会奖励跨 Query 重复，而不是奖励子意图覆盖。

因此 Reranker 在候选层面具有可行性，但根因首先是 Multi-query Fusion。考虑到 Query
Rewrite 已有约 8 秒串行前处理开销，下一轮应先对比无需新增模型调用的 `max-over-query RRF`
或 intent-balanced interleaving；若仍无法把三个目标提升到 Top-10，再引入 Cross-Encoder
Reranker，并将其增益和额外延迟单独报告。

## Query-aware Fusion 消融结果

六种策略复用完全相同的 Dense/BM25 Top-50，只离线改变融合算法。`Max-over-query RRF`
是唯一通过预设验收的策略：Paper@10 `99%`、Exact Page@10 `97%`、paired Complete `100%`、
challenge Complete `96%`，修复 `DS-021/025` 并保持 `DS-045/046/049`；只剩 `DS-041`。

Max-over-query 的 Fusion 平均只需约 `0.46 ms`，但 Page MRR 从 Flat Sum 的 `0.8340` 降至
`0.8055`，Exact Page@1 从 `60.17%` 降至 `54.67%`。它改善的是子意图覆盖和 Top-10
召回，不是所有前排页码指标。因此它成为最佳 Query Rewrite 实验 Fusion，但默认 Discovery
仍保留低延迟 Hybrid RRF。完整六组结果见 `query_fusion_ablation_v2.md`。

## BGE Reranker 消融结果

对固定 Top-50 Candidate Pool 使用 SiliconFlow `BAAI/bge-reranker-v2-m3` Cross-Encoder，
分别比较 Fast（原始 Query Hybrid RRF）和 Deep（Query Rewrite + Max-over-query）是否重排：

| Strategy | Paper@10 | Page@10 | Paper MRR | Page MRR | Paired Complete | Challenge Complete | Retrieval P50 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Fast Base | 95.83% | 91.83% | 0.9640 | 0.8099 | 96% | 84% | 349 ms |
| Fast + Reranker | **98.50%** | **98.00%** | **0.9900** | **0.8412** | 96% | **96%** | 1748 ms |
| Deep Max Base | **99.00%** | 97.00% | **1.0000** | 0.8055 | **100%** | 96% | 1416 ms |
| Deep Max + Reranker | 98.50% | **98.00%** | 0.9867 | **0.8492** | 96% | 96% | 2781 ms |

Fast + Reranker 在没有 Query Rewrite 的情况下修复 `DS-041/045/049` 等长尾目标，将 challenge
完整覆盖提升 12 个百分点，且 Page MRR 更高。Reranker 单次 P50 约 `1.4 s`，是主要新增
延迟。

Deep + Reranker 虽将 Self-Refine 在 `DS-041` 从第 24 提升到第 5，却把 `DS-021` 的 ReAct
从第 4 降到第 16、把 `DS-046` 的一个目标从第 2 降到第 14，未满足“不引入新回退”的验收。
这说明逐 Chunk Cross-Encoder 相关性不等于多论文子意图完整覆盖；对 cross-paper Query，仍需
在 Rerank 后保留 intent/paper coverage 约束，而不是继续盲目叠加模型。

当前决策：Fast + Reranker 作为可选高质量增强策略，Deep 叠加方案仅保留实验；默认低延迟
Discovery 不变。完整结果见 `reranker_ablation_v2.md`。
