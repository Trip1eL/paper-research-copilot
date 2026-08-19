# Evaluation 设计

## 目标

Evaluation 必须区分 Paper Retrieval、Evidence 定位、Citation、Answer Quality 和 Agent
Orchestration，不能只观察最终回答是否流畅。当前阶段已覆盖 Retriever、确定性 Answer 指标和
独立 LLM Judge；Agent Runtime v2 已完成 Golden Dataset 上的 Agent-vs-Fixed-RAG 对照，
并通过真实 UI Smoke 验证结果展示与 Citation 导航。

## 数据集

| Dataset | Cases | 用途 | 标题泄漏 |
| --- | ---: | --- | --- |
| `retrieval_diagnostic_v1` | 25 | 已知论文条件下的论文内证据定位 | 有，问题包含论文名 |
| `retrieval_discovery_v1` | 25 | 自然问题下的论文发现与跨论文覆盖 | 无，加载时自动检查 |
| `retrieval_discovery_v2` | 50 | 25 条 paired anchors + 25 条 challenge | 无，加载时自动检查 |
| `retrieval_discovery_v3` | 100 | 50 条 v2 anchors + 50 条 v3 challenge | 无，加载时自动检查 |

Discovery v1 包含 20 条单论文问题和 5 条跨论文 Hard Negative。每条数据都记录目标论文、
参考页码、难度和 Evidence Hint；加载器会根据 Corpus 中的 slug、完整标题和简称拒绝目标
论文名泄漏。

共同实验环境：

```text
Corpus: agent-seed-v1（10 papers / 571 chunks）
Embedding: BAAI/bge-m3
Chunking: chunking_v1
Collection: agent_seed_v1_bge_m3_chunking_v1
Top-K: 10
```

## 指标口径

| Metric | 含义 |
| --- | --- |
| Paper Hit@K | Top-K 是否至少包含一篇标注论文 |
| Paper Recall@K | 标注论文被 Top-K 覆盖的比例 |
| Complete Paper Coverage@K | Top-K 是否覆盖全部标注论文 |
| Exact Page Recall@K | `paper_id + page_number` 同时匹配的目标组比例 |
| Paper / Page MRR | 第一个正确论文或严格页码结果的倒数排名 |
| Same-page Redundancy | 同一论文同一页的多个 Chunk 占用 Top-K 的比例 |

页码标注不是所有相关页面的穷举，因此 Exact Page Recall 是严格下界。没有完整的
Chunk-level relevance labels 前，不报告 Precision@K 或 nDCG。

## 已知论文 Baseline

`dense_v1` 在含论文名的诊断集上达到 Paper Recall@5 `98%`、Exact Page Recall@5
`82%`。该实验只证明已知论文内定位能力，不能用于证明开放式论文发现能力。详细结果见
`evals/baselines/dense_v1.md`。

## Discovery 对照实验

运行命令：

```powershell
paper-rag evaluate-retriever --dataset .\evals\datasets\retrieval_discovery_v1.jsonl `
  --version 1 --top-k 10 --strategy dense --baseline-id dense_discovery_v1

paper-rag evaluate-retriever --dataset .\evals\datasets\retrieval_discovery_v1.jsonl `
  --version 1 --top-k 10 --strategy diversified_dense --candidate-pool 50 `
  --max-per-paper 3 --max-per-page 1 --baseline-id diversified_dense_discovery_v1

paper-rag evaluate-retriever --dataset .\evals\datasets\retrieval_discovery_v1.jsonl `
  --version 1 --top-k 10 --strategy mmr_dense --candidate-pool 50 `
  --mmr-lambda 0.85 --baseline-id mmr_dense_l085_discovery_v1
```

Top-10 严格对照：

| Strategy | Paper Recall | Cross-paper Complete | Exact Page@5 | Exact Page@10 | Same-page Redundancy | P50 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense | 98% | 80% | 90% | 96% | 13.6% | 230 ms |
| Diversified Dense（paper=3） | 100% | 100% | 86% | 86% | 0% | 238 ms |
| MMR（lambda=0.50） | 100% | 100% | 66% | 82% | 0.4% | 265 ms |
| MMR（lambda=0.70） | 100% | 100% | 82% | 82% | 2.0% | 271 ms |
| MMR（lambda=0.85） | 100% | 100% | 86% | 94% | 6.8% | 254 ms |

`paper=3` 修复了 Dense 在 `DS-021` 中被单一高相似论文占满的问题；P50 延迟只增加约
8 ms。但单论文数量上限也可能在正确论文的标注页出现前截断候选，使 Exact Page Recall
下降。MMR 不设置单论文硬上限，其中 `lambda=0.85` 在保持完整论文覆盖的同时把 Exact
Page Recall 恢复到 `94%`，明显优于规则版的 `86%`。

`lambda=0.5` 和 `0.7` 对语义新颖性权重过高，容易把高相关的互补证据提前排除；`0.85`
更偏重 Query relevance，因此在当前 Corpus 和 Embedding 上形成更合理的平衡。三组 MMR
的 Cross-paper Exact Page Recall 都为 `70%`，仍低于 Dense 的 `80%`，不能把总体指标
提升解释为所有子集都提升。

## 已知论文集交叉验证

| Strategy | Paper Recall@10 | Cross-paper Complete@10 | Exact Page@5 | Exact Page@10 | Same-page Redundancy@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Dense | 98% | 80% | 82% | 86% | 19.6% |
| MMR（lambda=0.50） | 100% | 100% | 74% | 86% | 1.2% |
| MMR（lambda=0.70） | 100% | 100% | 78% | 82% | 8.0% |
| MMR（lambda=0.85） | 98% | 80% | 82% | 84% | 16.4% |

这组结果说明 `lambda=0.85` 并没有全面替代 Dense：在问题已经给出论文名时，原始 Dense
仍有更好的 Top-10 页码定位。因此 Lambda 选择必须与检索目标绑定，不能只报告 Discovery
集上的最好结果。

## Hybrid Retrieval 对照

统一参数：BM25 `k1=1.5`、`b=0.75`，Dense/BM25 Candidate Pool 均为 50，RRF `k=60`，
可选 MMR `lambda=0.85`。

Discovery：

| Strategy | Paper@1 | Paper@10 | Cross Complete@10 | Exact Page@5 | Exact Page@10 | Paper MRR | Page MRR | P50 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense | 86% | 98% | 80% | 90% | 96% | 0.9733 | 0.7543 | 230 ms |
| BM25 | 70% | 88% | 100% | 74% | 82% | 0.8300 | 0.5853 | 0.31 ms |
| Hybrid RRF | 90% | 100% | 100% | 90% | 96% | 1.0000 | 0.8170 | 243 ms |
| Hybrid RRF + MMR | 90% | 100% | 100% | 90% | 96% | 1.0000 | 0.8247 | 258 ms |

BM25 在三个纯中文概念问题上没有正分结果，但 Hybrid 仍可依赖 Dense 分支召回。RRF 修复
`DS-001` Top-1，并完整覆盖全部目标论文。MMR 只带来 `0.0077` Page MRR 提升，同页冗余
仅从 16.8% 降到 16.0%，当前不作为默认融合后处理。

已知论文集：

| Strategy | Paper@10 | Cross Complete@10 | Exact Page@5 | Exact Page@10 | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense | 98% | 80% | 82% | 86% | 0.9733 | 0.7670 |
| BM25 | 94% | 40% | 60% | 70% | 1.0000 | 0.4808 |
| Hybrid RRF | 96% | 60% | 76% | 84% | 0.9800 | 0.6447 |
| Hybrid RRF + MMR | 98% | 80% | 76% | 84% | 0.9800 | 0.6447 |

问题直接包含论文名时，BM25 容易把包含标题但不是目标证据页的 Chunk 提前，导致 Page MRR
明显下降。该结果再次证明不同检索目标需要不同策略。

## 决策

1. 已知论文 Evidence 定位继续使用原始 Dense Retriever。
2. `hybrid_rrf` 作为当前 Discovery 首选策略，已通过显式 `retrieval_mode=discovery` 接入
   主链路，但尚未实现自动路由。
3. `hybrid_rrf_mmr` 当前收益较小，保留为实验策略，不设置为默认。
4. `diversified_dense` 和 `mmr_dense` 保留为消融及历史 Baseline。
5. 报告必须记录 Dataset SHA-256、Collection、Embedding、Chunking、Strategy 和参数，确保
   实验可复现。
6. Corpus v2 已写入独立 Collection 并完成两次幂等导入；Dense、BM25、Hybrid RRF、Query
   Rewrite、Reranker 与 Coverage-aware Retrieval 的消融均已有可复现 Baseline。

## 当前限制

- v1 两套数据集各 25 条，Discovery v2 为 50 条；它们仍是开发诊断集，不是统计显著的
  公开 Benchmark。
- Discovery 问题由项目开发阶段人工编写，仍可能与语料措辞接近。
- Exact Page 标注不是穷举，不能直接推导 Precision 或 nDCG。
- Same-page Redundancy 只衡量页面重复，不等价于语义层面的 Intra-list Diversity。
- v2 已增加同义改写、同主题 Hard Negative、Reranker 和 Query Rewrite 对照；尚未加入
  时间外问题，Coverage 定向实验也只有 3 条跨论文 Case。

## Corpus v3 / Evaluation v3

`agent-seed-v3` 扩展到 40 篇、1,387 页和 2,152 个 `chunking_v1` Chunk。Parse 为
31 verified / 9 warning / 0 failed；Chunk 统计为 0 oversized、0 duplicate ID、0 missing
required metadata，Section coverage 99.72%。40 个 PDF 的大小与 SHA-256 均通过独立校验。

`retrieval_discovery_v3` 在不修改前 50 条 v2 anchors 的前提下增加 30 条单论文和 20 条
跨论文 challenge，总计 100 条、35 条 cross-paper、80 条 Hard Negative，覆盖全部 40 篇。
`answer_generation_v2` 包含 32 条（31 可回答/1 拒答），`agent_runtime_v2` 包含 12 条
（11 可回答/1 拒答）。`AE-020` 随 tau-bench 入库转为可回答；`AE-019` 仍是有效负例，
因为 Corpus v3 不包含 GPT-5.5 在 SWE-bench Verified 上的结果。

v3 的 2,152 个 Chunk 已使用 `BAAI/bge-m3` 写入独立 Collection
`agent_seed_v3_bge_m3_chunking_v1`，并完成 Discovery v3 的三路 100 Case Baseline：

| Strategy | Paper Recall@10 | Complete Papers@10 | Exact Page Recall@10 | Complete Pages@10 | Paper MRR | Page MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense | 92.00% | 85.00% | 83.92% | 74.00% | 0.8835 | 0.7264 |
| BM25 | 67.92% | 58.00% | 65.67% | 55.00% | 0.7078 | 0.5579 |
| Hybrid RRF | **92.17%** | 84.00% | **86.92%** | **75.00%** | **0.9194** | **0.7962** |

同一批 DS-001..050 从 20 篇扩到 40 篇后，Dense 的 Paper Recall / Complete Papers /
Exact Page Recall 分别下降 `2 / 4 / 4` 个百分点；Hybrid 分别变化 `0 / 0 / -2` 个百分点，
说明 Hybrid 对扩库后的同主题干扰更稳健。新增单论文题上 Hybrid Complete Papers 与 Complete
Pages 均为 `96.67%`；新增跨论文题上则分别只有 `50%` 和 `30%`。因此 v3 不继续做全局融合
参数微调：单论文 Discovery 保持 Hybrid RRF，跨论文 Agent 保持 Query Decomposition +
Coverage Merge。完整分组和扩库漂移见 `retrieval_discovery_v3_comparison.md`。

Answer v2 的 Fixed Hybrid Baseline 在 32 条问题上取得 `78.12%` Answerability、`71.24%`
Key Point Recall 和 `74.19%` Strict Page Recall；一次 `length` 截断及多条跨论文半覆盖导致
明显回退。`gpt-5.5` Judge 对 24 条有效回答执行语义评分、对 8 条错误或拒答执行确定性评分，
Overall 为 `74.22%`，Judge failures 为 0。

Agent Runtime v2 在 12 条代表性问题上与同一批 Fixed Hybrid 保存结果对照：

| Variant | Paper Recall@10 | Cross Complete@10 | Answerability | Correctness | Strict Run | Workflow P50 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Fixed Hybrid | 86.36% | 40.00% | 75.00% | 68.75% | 66.67% | 7.1 s |
| LangGraph Agent | **95.45%** | **80.00%** | **100.00%** | **93.75%** | **91.67%** | 18.7 s |

Agent 的 Router、Task Count 与 Retrieval Strategy Accuracy 均为 `91.67%`，Title Leakage 为
0，Citation Validation 为 100%。失败边界是 AE-025 被错误路由为 cross-paper，以及 AE-032
只覆盖一半目标论文；AE-032 首次运行还发生两次 Answer 截断，恢复运行后虽回答成功，
Correctness 仍只有 `2/4`。这组结果支持生产切换到 Corpus v3，同时保留延迟与稳定性限制。
历史 v1/v2 数据集和报告保持不可变。

## Corpus v2 / Discovery v2

`agent-seed-v2` 包含 20 篇论文、604 页和 971 个 `chunking_v1` Chunk。新增 10 篇论文与
v1 主题高度相邻，用于制造真实的检索干扰。

`retrieval_discovery_v2` 共 50 条：前 25 条保留 v1 Question 与 Relevant Pages，后 25 条
为新增 Hard Negative；合计 15 条 cross-paper、30 条 Hard Negative，覆盖全部 20 篇论文。
独立 Collection 为 `agent_seed_v2_bge_m3_chunking_v1`。两次完整导入后点数均为 `971`，
验证了按论文替换写入的幂等性。

v2 总体结果：

| Strategy | Paper@10 | Exact Page@10 | Paper MRR | Page MRR | Redundancy@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Dense | 95.50% | 87.83% | 0.9200 | 0.7190 | 12.80% |
| BM25 | 86.83% | 81.33% | 0.8620 | 0.6493 | 13.04% |
| Hybrid RRF | **95.83%** | **91.83%** | **0.9640** | **0.8099** | 15.20% |

paired anchors 上，Dense、BM25、Hybrid 的 Paper@10 分别为 `98% / 88% / 98%`；challenge
上分别为 `93.00% / 85.67% / 93.67%`。Hybrid 的 challenge Paper MRR 为 `0.9600`，但
Complete Papers@10 为 `84%`，低于 Dense 的 `88%`，主要失败集中在多目标跨论文问题。
完整分组、v1 差值和失败 Case 见 `evals/baselines/retrieval_discovery_v2_comparison.md`。

### Hybrid RRF + MMR v2 消融

在 v2 上测试 `lambda=0.70 / 0.85 / 0.95` 后，三组 Challenge Complete Papers@10 均保持
`84%`，也都没有修复原始 Hybrid 缺失的五个目标论文 Case。`0.70` 将总体冗余从 `15.20%`
降到 `14.40%`，但 paired Exact Page@10 从 `96%` 降到 `92%`；`0.85` 基本无变化；`0.95`
反而把总体冗余提高到 `15.60%`。因此 MMR 继续作为实验策略，不进入默认 Discovery 链路。

### Query Rewrite v2 对照

`deepseek-v4-flash` 按 `query_rewrite_v1` 为每题生成 3 条英文互补 Query，与原始 Query 一起
执行 8 路 Dense/BM25 RRF。总体 Paper@10 从 `95.83%` 提升到 `97.00%`，Exact Page@5 从
`80.83%` 提升到 `90.17%`，Paper MRR 从 `0.9640` 提升到 `0.9767`。

收益集中在 challenge：Complete Papers@10 从 `84%` 提升到 `96%`，修复 `DS-045/046/049`；
paired Complete Papers@10 则从 `96%` 降到 `92%`，新增 `DS-025` 回退。150 条 Rewrite 的
标题泄漏检查为 0 命中。平均 Rewrite 生成耗时约 `6.6 s`，纯检索 P50 从 `265 ms` 增至
`1451 ms`，因此当前只保留实验策略，不切换默认 Discovery。

Candidate Pool 诊断显示剩余失败并非 Recall 问题：`DS-021` 的缺失目标 Paper/Exact Page 位于
Rewrite 融合第 `31/39`，`DS-025` 位于 `14/14`，`DS-041` 位于 `18/18`，全部处于 Top-50。
其中 `DS-025` 目标在原始 Hybrid 为第 4，说明等权多 Query RRF 本身造成了回退。Reranker
理论上可以看到这些候选，但下一步先验证不增加模型调用的 Query-aware Fusion，避免在高延迟
链路上过早叠加 Cross-Encoder。

Query-aware Fusion 消融复用同一批分支 Ranking，对比 No Rewrite、Flat Sum、三组 Original
权重和 Max-over-query。只有 Max-over-query 通过预设验收：Paper@10 `99%`、Exact Page@10
`97%`、paired/challenge Complete `100%/96%`，修复 `DS-021/025` 并保持三个 guard Case。
Fusion 平均约 `0.46 ms`，但 Page MRR 降至 `0.8055`，说明长列表覆盖提升伴随首个严格页码
位置回退。它保留为最佳 Query Rewrite Fusion 实验策略，不替换默认 Hybrid。

### BGE Reranker v2 消融

使用 SiliconFlow `BAAI/bge-reranker-v2-m3` 对 Top-50 完整 Chunk 重排。四组实验共享相同
Corpus、Dataset、候选池和 Top-10 口径：

| Strategy | Paper@10 | Page@10 | Paper MRR | Page MRR | Paired Complete | Challenge Complete | Retrieval P50 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Fast Base | 95.83% | 91.83% | 0.9640 | 0.8099 | 96% | 84% | 349 ms |
| Fast + Reranker | **98.50%** | **98.00%** | **0.9900** | **0.8412** | 96% | **96%** | 1748 ms |
| Deep Max Base | **99.00%** | 97.00% | **1.0000** | 0.8055 | **100%** | 96% | 1416 ms |
| Deep Max + Reranker | 98.50% | **98.00%** | 0.9867 | **0.8492** | 96% | 96% | 2781 ms |

Reranker 调用本身 P50/P95 为 Fast `1390/1579 ms`、Deep `1361/1726 ms`。Deep Retrieval
数字不含平均约 `6.6 s` 的 Rewrite 生成耗时。

Fast 组合获得稳定总体提升；Deep 组合将 `DS-041` 的 Self-Refine 从第 24 提升到第 5，但
将 `DS-021` 的 ReAct 从第 4 降到第 16，并使 `DS-046` 的一个目标从第 2 降到第 14。
因此 Deep + Reranker 未通过“修复 DS-041 且 guard cases 不回退”的预设验收。完整四组报告、
逐 Case 排名变化和原始结果分别保存于 `evals/baselines/reranker_ablation_v2.md`、
`evals/diagnostics/reranker_ablation_v2.json` 和 `evals/results/`。

### Answer Evaluation v1

`answer_generation_v1.jsonl` 包含 20 条人工可审查 Case：18 条可回答问题（15 条单论文、3 条
跨论文）和 2 条语料外拒答问题。每条可回答 Case 记录 reference answer、目标论文/页码和
Key Point aliases；拒答使用结构化状态 `insufficient_evidence`，不是普通无引用文本。

第一层不依赖 LLM Judge，分别测量：

- Generation Success 与 Answerability Accuracy。
- Key Point Recall：人工别名的词面覆盖。
- Citation Paper Precision/Recall：引用是否来自目标论文。
- Strict Page Precision/Recall：引用是否命中人工标注页，作为严格下界。
- Sentence Citation Coverage：回答句子是否带 Citation marker。
- Retrieval、Generation 和端到端延迟。

真实端到端对照结果：

| Strategy | Answerability | Key Point | Citation Paper Recall | Strict Page Recall | Retrieval P50 | Total P50 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Hybrid RRF | 85.00% | 80.56% | 83.33% | 83.33% | 410 ms | 4319 ms |
| Hybrid + Reranker | **95.00%** | **93.06%** | **94.44%** | **94.44%** | 1731 ms | 5679 ms |

Reranker 补齐 `AE-017/018` 缺失的 Self-Refine 与 Voyager 直接证据，使两题从失败/拒答变为
完整引用回答。两组都没有召回 `AE-016` 的 ReAct 直接证据，且 Answer Provider 连续返回空
content，因此该题仍失败。完整对照与限制见
`evals/baselines/answer_evaluation_v1_comparison.md`。

### gpt-5.5 LLM Judge v1

确定性 Key Point 与 Citation marker 指标不能判断语义正确性或 Claim-Evidence entailment，
因此增加独立 `gpt-5.5` Judge。每个维度按 0-4 评分，报告中除以 4 归一化：

- Correctness：答案是否正确并覆盖 reference answer 的核心内容。
- Faithfulness：每个 material claim 是否由它实际引用的 Evidence 支撑。
- Citation Completeness：所有需要外部验证的 material claim 是否具有充分引用。

Judge 只读取 candidate answer 实际引用的 Chunk，不读取 Top-K 中未引用的其他 Evidence。
每次调用保存 input SHA-256、model、prompt version、raw response、解析结果、attempts、Token
usage 与 latency。输出采用 JSON Prompt + Pydantic 严格解析；Schema 失败执行有限重试，逐
Case 缓存支持中断续跑与输入变更失效。

为避免幸存者偏差，以下 Case 不调用 LLM，而是使用确定性规则：

- Generation Failure 或可回答题错误拒答：`0/0/0`。
- 语料外问题正确拒答：`4/4/4`。
- Judge 调用或 Schema 最终失败：`0/0/0` 并记录 Judge Failure。

真实对照：

| Strategy | Correctness | Faithfulness | Citation Completeness | Overall | Judge P50/P95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Hybrid RRF | 85.00% | 83.75% | 85.00% | 84.58% | 20553 / 24617 ms |
| Hybrid + Reranker | **95.00%** | **93.75%** | **95.00%** | **94.58%** | 21002 / 27195 ms |

Reranker 组的提升来自 `AE-017/018` 从错误拒答变为三维 `4/4/4`；`AE-016` 在两组中仍为
0 分。两组各有一条 Faithfulness=3，说明语义正确与引用完全支撑被分开评估。该结果不能
消除单 Judge 偏差、自一致性不足或 reference answer 偏差，正式结论仍需人工抽查。

### Answer Stability v1

单次 Answer 可能受生成随机性和 Provider 空 content 影响，因此选择 8 条代表性 Case：
`AE-001/007/014/016/017/018/019/020`。每个策略冻结原 Answer Baseline 的 Top-10 Evidence，
每题重新生成 3 次并逐次运行同一 Judge。这样 Retrieval 完全不变，观察到的差异只来自 Answer
Generation、Citation 选择和 Judge。

新增稳定性指标：

- Strict Run：Generation Success、Answerability 正确且 Judge 三维均不低于 3/4。
- Fully Stable Case：同一 Case 的 3 次运行全部通过 Strict Run。
- Status Consistency：3 次 answer status 完全一致。
- Citation Consistency：3 次引用的论文/页码集合完全一致。
- Case Mean/Minimum：同时报告均值和最差一次，防止平均值掩盖偶发失败。

| Strategy | Gen Success | Answerability | Correctness | Faithfulness | Strict Runs | Stable Cases |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Hybrid RRF | 87.50% | 70.83% | 68.75% | 66.67% | 66.67% | 62.50% |
| Hybrid + Reranker | 87.50% | **87.50%** | **86.46%** | **83.33%** | **87.50%** | **75.00%** |

Reranker 的收益在重复实验中仍存在，但并非完全稳定：`AE-017` 为两次满分回答和一次空
content；`AE-018` 三次回答均通过 Strict Run，但一次 Faithfulness/Completeness 为 3/4。
`AE-016` 两组都不稳定，且两组 Top-10 都没有 ReAct 论文，继续确认它是 multi-target
coverage 问题。`AE-019/020` 共 12 次均正确拒答。

本实验还发现两项生成层问题：DeepSeek 偶发连续返回空 content；长 cross-paper 回答可能在
`max_tokens=1200` 附近截断。后续 Generation Observability v2 与 Coverage-aware Retrieval v1
已完成对这两项问题的验证。完整结果和审计分别见
`evals/baselines/answer_stability_v1.md` 与 `answer_low_score_audit_v1.md`。

### Generation Observability v2

Chat Completion Provider 和 AnswerGenerator 现在记录每次 attempt 的 `finish_reason`、outcome、
content length、response model、Token usage、latency 和 error。outcome 区分 `accepted`、
`empty`、`truncated`、`provider_error` 与 `invalid_citation`。

真实调用发现 Relay 会返回 `finish_reason=length` 且 content 为空。若先判断空内容，会把输出
上限问题误报为 Provider 空响应；因此 AnswerGenerator 改为先判断 `length`，再判断 empty。
截断后最多执行一次压缩重试，要求答案不超过 500 个中文字符或 300 个英文词，并保留重要
Claim 的 Citation。连续两次截断抛出 `TruncatedAnswerError`，不能把不完整答案送给用户。
默认 `ANSWER_MAX_TOKENS` 从 1200 提升到 `2400`。

针对 `AE-016/017/018`，每题重复 3 次：

| Strategy | Gen Success | Answerability | Strict Runs | Truncated | Retry Recovery |
| --- | ---: | ---: | ---: | ---: | ---: |
| Hybrid RRF | 88.89% | 22.22% | 0.00% | 22.22% | 50.00% |
| Hybrid + Reranker | **100%** | **100%** | **100%** | 11.11% | **100%** |

该实验把“空响应”和“被 Token 上限截断”分开，使生成失败可以定位和统计；但它也确认
`AE-016` 的 Evidence 仍缺 ReAct，生成成功不能替代 Retrieval coverage。

### Coverage-aware Retrieval v1

四组消融固定三条跨论文题和各自 Top-10 Evidence，每组生成 3 次，并统一使用 `gpt-5.5`
Judge。Query Decomposition 生成两个保留原描述、禁止补论文名的子查询；Corpus v2 alias
审计为 0 泄漏。每个子查询独立 Hybrid Top-30，最终按轮转配额合并为 `5/5`。

| Strategy | Complete Papers@10 | Correctness | Faithfulness | Citation Completeness | Strict Runs |
| --- | ---: | ---: | ---: | ---: | ---: |
| Hybrid RRF | 0.00% | 16.67% | 11.11% | 11.11% | 0.00% |
| Hybrid + Global Reranker | 66.67% | 97.22% | 83.33% | 94.44% | 100% |
| Decomposition + Hybrid + Coverage | **100%** | **100%** | **91.67%** | **94.44%** | **100%** |
| Coverage + per-subquery Reranker | **100%** | **100%** | 88.89% | 91.67% | **100%** |

Coverage 修复了 `AE-016` 的 ReAct 缺失，并保持 `AE-017/018` 不回退。Global Reranker 即使
没有 ReAct Evidence 也得到较高 Answer 分，说明强模型参数知识会掩盖 Retrieval 缺陷；因此
Retrieval Coverage 与 Answer Judge 必须并列报告。per-subquery Reranker 没有质量增益，
还把检索从约 0.46 秒增加到约 2.0 秒，当前不采用。

正式产物为 `evals/baselines/coverage_aware_ablation_v1.json|md`、
`evals/diagnostics/coverage_aware_retrieval_v1.json` 和逐样本 JSONL。结论只适用于当前 3 条
定向 Case；进入生产前仍需扩展 cross-paper Dataset 并评估自动 Query Router。

### Agent Runtime Evaluation v1

使用 `AE-001/007/014/016/017/018/019/020` 对比 Fixed Hybrid、Fixed Hybrid + Reranker、
Oracle Route 和 LangGraph Agent。固定组复用历史冻结样本，Agent 使用相同 Answer/Judge 口径。

Agent 专项指标包括 Router、Task Count、Task Facet Coverage、Title Leakage、Strategy、
Unnecessary Revision、Citation Validation、节点延迟、Token 和模型调用数。当前 Agent 的前五项
质量指标均为 100%（Title Leakage 为 0%），Cross Complete Papers@10 和 Strict Run 均为
100%；Workflow P50/P95 为 `18.1/58.5 s`，主要瓶颈是 Planner `10.7/14.7 s`。

完整结果见 `evals/baselines/agent_runtime_v1.md`。v1 是单次运行，不能替代多次 Stability；数据
中也没有 `should_retry=true` Case，因此 Revision Recovery 仍未得到实证。

### Planner Model Ablation v1

固定 Agent Runtime v1 的 8 条问题和 `research_planner_v1` Prompt，对比 `gpt-5.5` 与
`deepseek-v4-flash`。质量门槛要求 Success、Router、Task Count、Task Coverage 均为 100%，
Title Leakage 为 0%。

GPT 全部通过，P50/P95 为 `10.7/14.7 s`。DeepSeek 的 P50 降到 `5.1 s`，但 Router/Task Count
为 `87.5%`、Task Coverage 为 `93.75%`，且一次 Schema Retry 使 P95 达到 `23.9 s`。当前保留
GPT Planner。完整逐题 Plan 和指标见 `evals/baselines/planner_model_ablation_v1.md` 与
`evals/diagnostics/planner_model_ablation_v1.json`。

### Planner/Router Dataset v2

`planner_routing_v2.jsonl` 将 Planner Eval 从 8 条扩大到 40 条：16 条 single lookup、13 条
cross comparison、2 条 multi-method synthesis、5 条 corpus verification 和 4 条 routing
boundary。34 条原样复用已有 `DS/AE` 人工问题，6 条补充语料级核验和边界情况。

v2 同时记录 Strict Route、Acceptable Routes、Strict/Acceptable Task Counts、Task Facets 和
label-sensitive 标记。后续报告必须分开计算 Strict、Acceptable 和 Core（排除敏感标签）指标，
避免用单一标签评价本身存在合理歧义的问题。

### Planner Model Ablation v2

使用 40 条 `planner_routing_v2.jsonl` 对 `gpt-5.5` 和 `deepseek-v4-flash` 进行真实调用。
报告同时给出 Strict、Acceptable、Core、Label-sensitive/Boundary 和 Category 指标，并记录
attempts、Token、原始 generation latency、标题泄漏及逐题结构化 Plan。

质量门槛要求：调用成功率、Core Route、Core Task Count、全体 Task Facet Coverage、Acceptable
Route、Acceptable Task Count 均为 100%，Title Leakage 为 0%。Route 和 Task Count 可以采用
人工标注的合理替代，但 label-sensitive Case 仍不能漏掉要求核验的证据 Facet。

| Model | Core Route/Task/Coverage | Acceptable Route/Task | Overall Coverage | Retry | P50/P95 | Gate |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| gpt-5.5 | 97.30% / 97.30% / 100% | 97.50% / 97.50% | 100% | 0% | 10.7 / 13.6 s | Fail |
| deepseek-v4-flash | 100% / 100% / 100% | 100% / 100% | 98.75% | 5% | 5.0 / 10.8 s | Fail |

GPT 的核心错误 `PR-016` 是过度拆分：同一论文、同一基准中的 Agent 与人类成功率被拆成两条
Retrieval Task；它没有漏掉证据。DeepSeek 的 `PR-032` 虽采用可接受的单任务 Route，却只检索
目标数值，没有覆盖“从结果表或评测段落复核”的第二个 Facet；`PR-030/032` 还各发生一次结构
重试。两者均无标题泄漏。

因此 v2 不切换生产 Planner，继续使用 `gpt-5.5`。下一轮应针对 corpus verification 引入显式
路由信号或专用 Prompt，再对 DeepSeek 做小范围稳定性复测，而不是仅凭更低 P50 替换关键模型。
完整结果见 `evals/baselines/planner_model_ablation_v2.md` 和
`evals/diagnostics/planner_model_ablation_v2.json`。

### Corpus Verification Prompt Ablation v2

`research_planner_corpus_verification_v2` 在不修改 `ResearchPlan` Schema 和 LangGraph Runtime 的
情况下，为 Planner 增加两条通用约束：语料级存在性/缺失核验必须分别规划正文检索与结果表/
评测段落复核；同一论文、同一基准中的多个数值保持一个任务，不能仅因请求两个数值而拆分。
Prompt Version 参与缓存键，v1/v2 记录可共存；生产默认值仍为 v1。

实验先在 40 条全集运行一次，再对全部 5 条 corpus verification、4 条 routing boundary 和
`PR-016` 使用独立缓存重复 3 次。生产切换要求同时满足：全集质量 Gate、三次稳定性 Gate、
Retry 不高于 DeepSeek v1，并且 P95 低于当前生产 GPT。

| Variant | Core Route/Task/Coverage | Overall Coverage | Retry | P50/P95 | Gate |
| --- | ---: | ---: | ---: | ---: | --- |
| Production GPT Prompt v1 | 97.30% / 97.30% / 100% | 100% | 0% | 10.7 / 13.6 s | Fail |
| DeepSeek Prompt v1 | 100% / 100% / 100% | 98.75% | 5% | 5.0 / 10.8 s | Fail |
| DeepSeek Prompt v2 | 100% / 94.59% / 100% | 100% | 7.50% | 5.0 / 25.8 s | Fail |

Prompt v2 修复了 DeepSeek v1 在 `PR-032` 的验证缺失，三次均生成正文和表格/评测复核通道；
`PR-016` 也保持正确的同论文单任务规划，但 DeepSeek v1 原本已做对，因此只作为防过度拆分的
Guardrail。第二次 `PR-032` 最初被判 50% Coverage；人工审计发现 T2 明确包含
“实验 结果 表格”，因此补充组合 alias `结果 表格`。这是确定性匹配修正，没有改变模型输出。

真正回退是 `PR-034/036` 的 Task Count 在两次或三次之间波动。虽然二者都在数据集的
Acceptable Task Counts 内，但 Core Strict Task Count 不稳定，表明一个 Prompt 同时承担 Route
分类与 Task Decomposition 时会发生规则干扰。结构重试也从 5% 上升至 7.5%，使尾延迟失去优势。
三次定向重复只有第 3 次通过质量 Gate，因此 Production switch review 为 False。

结论是不继续在同一数据集上追加 Prompt 条款。下一步应拆分轻量 Router 与 Task Generator，或
先增强结构化输出/重试诊断，再做新的独立验证集；生产继续使用 GPT Prompt v1。完整结果见
`evals/baselines/planner_prompt_ablation_v2.md`、`planner_prompt_ablation_v2_full.md` 和
`planner_prompt_ablation_v2_stability.md`。

### Planner Retry Diagnostics v1

Prompt v2 实验只记录了总 attempts，无法知道重试由 JSON、Schema、Task Shape、泄漏、截断还是
Provider Error 触发。`CachedResearchPlanner` 因此新增 `PlannerAttemptTrace` 和
`PlannerGenerationTrace`，逐 attempt 记录：

- `outcome`、`finish_reason`、content length、latency 和 response model；
- Input/Output/Total Token、错误类型和错误信息；
- 原始响应，用于本地诊断；正式 Diagnostics 只保留 SHA256，不保存原文。

Outcome 区分 `accepted`、`empty`、`truncated`、`provider_error`、`invalid_json`、
`schema_validation_error`、`invalid_task_shape`、`invalid_plan`、`unchanged_revision` 和
`title_leakage`。重试后的 Usage 现在汇总全部 attempts，而不是只统计最终成功响应。Trace 随
Planner Cache 存在 ignored 的 `data/agent/`，旧缓存没有 trace 时仍可兼容读取。

使用全新独立缓存，对 `PR-030/033/039` 各重复 3 次：

| 指标 | 结果 |
| --- | ---: |
| Final Success | 100%（9/9） |
| Retry Rate | 33.33%（3/9） |
| Retry Recovery | 100% |
| Accepted Attempts | 9 |
| Truncated Attempts | 4 |
| P50/P95 | 13.1 / 49.8 s |

4 个失败 attempts 全部为 `finish_reason=length`，Output Token 都等于上限 1800；其中 3 个返回
空 content，另一个返回 322 字符的半段 JSON。没有观察到 invalid JSON、Schema Validation、
Task Shape、Title Leakage 或 Provider Error。`PR-030` 一次连续截断两次，第三次才成功，说明
当前“用相同 Prompt 原样重试”不能稳定恢复截断，也是 49.8 秒 P95 的直接原因。

因此暂缓 Router/Task Generator 拆分。下一步先做 Truncation Recovery 消融，对比原样重试、
只在截断后追加 compact JSON 指令、以及提高 Planner max_tokens；质量相同的前提下按 Retry 和
P95 选择方案。正式报告为 `evals/baselines/planner_retry_diagnostics_v1.md`，脱敏逐 attempt
数据为 `evals/diagnostics/planner_retry_diagnostics_v1.json`。

### Planner Truncation Recovery Ablation v1

固定 `deepseek-v4-flash`、`research_planner_corpus_verification_v2`、`PR-030/033/039` 和最多
3 attempts，按 repetition → case → strategy 交错执行，每种策略每题独立重复 3 次：

| Strategy | Success | Acceptable Route/Task | Coverage | Retry/Recovery | P50/P95 | Gate |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| same_1800 | 88.89% | 88.89% / 88.89% | 88.89% | 55.56% / 80.00% | 25.1 / 60.9 s | Fail |
| compact_1800 | 88.89% | 77.78% / 77.78% | 88.89% | 11.11% / 0.00% | 11.7 / 64.2 s | Fail |
| same_2400 | **100%** | **100% / 100%** | **100%** | 44.44% / **100%** | 12.1 / 68.8 s | **Pass** |

`same_1800` 的 `PR-030 r1` 与 `compact_1800` 的 `PR-039 r1` 都连续三次截断并终态失败。
Compact 指令仅在首轮截断后追加，但该失败样本的后两次仍用满 1800 Token，因此没有形成可靠
恢复。`compact_1800` 的 `PR-030 r3` 首轮未截断却生成不可接受的 single-paper Route；由于首轮
Prompt 与 Baseline 相同，这应视为随机生成波动，不能归因于 Compact 指令。

`same_2400` 是唯一通过预设质量 Gate 的方案，9 个 Plan 全部恢复成功；但仍发生 5 个截断
attempt，Retry Rate 44.44%，P95 反而达到 68.8 秒。结论是 2400 Token 在当前小样本中提高了
最终可靠性，却没有解决模型过度生成和尾延迟。该实验只覆盖 DeepSeek Prompt v2，不足以修改
当前 `gpt-5.5 + Prompt v1` 生产配置。下一步应测试 `2400 + compact-on-truncation` 或从 Provider
侧启用更强的结构化输出约束，并扩大独立稳定性样本。

正式报告为 `evals/baselines/planner_truncation_recovery_v1.json|md`，脱敏逐样本数据为
`evals/diagnostics/planner_truncation_recovery_v1.json`；原始响应只位于 ignored 的
`data/agent/planner_truncation_recovery_v1_raw.jsonl`。

### Compact 2400 停止实验

为验证 Compact 是否只因 1800 上限过低而失效，重新交错运行 `same_2400` 与
`compact_2400`，仍使用 3 Cases × 3 次，共 18 个 Plan：

| Strategy | Success | Acceptable Route/Task | Retry/Recovery | P50/P95 | Output Tokens | Gate |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| same_2400 | 100% | 88.89% / 77.78% | 0% / N/A | 10.2 / 20.2 s | 9,229 | Fail |
| compact_2400 | 88.89% | 77.78% / 77.78% | 33.33% / 66.67% | 16.3 / 73.1 s | 25,735 | Fail |

`compact_2400` 在 `PR-033 r1` 连续三次截断并终态失败，`PR-033 r2` 也到第三次才恢复；其
P95 和 Output Token 都显著高于对照，证明截断后追加自然语言 Compact 指令不是可靠恢复机制。
`same_2400` 本轮没有截断，却在 `PR-030 r3` 生成不可接受的 single-paper Route，并在
`PR-033 r3` 生成不可接受的 3 Tasks，说明 DeepSeek Prompt v2 还存在随机规划波动。

因此停止这条微调路线，不再继续测试更多 Token/措辞组合。生产仍使用已验证的
`gpt-5.5 + Prompt v1`；后续只有在主链路确实需要切换 DeepSeek Planner 时，才评估结构化输出或
Router/Task Generator 分离。正式报告为
`evals/baselines/planner_compact_2400_ablation_v1.json|md`。
