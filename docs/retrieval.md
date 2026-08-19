# Retrieval 设计

## 当前目标

当前阶段建立可重复的多策略 Retrieval Baseline。检索对象是固定版本的 Agent 论文语料，
而不是临时上传且无法复现的一组 PDF。

```text
agent-seed-v1
  -> Parse + SHA-256 verification
  -> chunking_v1
  -> BAAI/bge-m3 Embedding
  -> agent_seed_v1_bge_m3_chunking_v1
  -> Dense / BM25 / RRF / MMR
```

v2 已使用相同 Embedding 与 Chunking 写入独立的
`agent_seed_v2_bge_m3_chunking_v1`（20 papers / 971 chunks）。两次完整导入后的点数均为
971，没有与 v1 混写。`ingest-corpus` 和 `evaluate-retriever` 支持显式 `--collection`，无需
修改 `.env` 即可复现实验。

当前生产语料为 v3：40 papers / 1,387 pages / 2,152 chunks，独立 Collection 为
`agent_seed_v3_bge_m3_chunking_v1`。Discovery v3 的 100 Case 对照中，Hybrid RRF 的 Paper
Recall@10 / Exact Page Recall@10 为 `92.17% / 86.92%`；单论文 Discovery 使用 Hybrid，
跨论文 Agent 使用 Query Decomposition + Coverage Merge。

## chunking_v1

- `chunk_size_chars = 3200`
- `chunk_overlap_chars = 400`
- 优先使用段落边界，其次是句子、换行和空格。
- Chunk 不跨页，确保 Citation 可以定位到单一 PDF 页码。
- Overlap 起点对齐到词边界，避免从单词中间开始。
- Section title 使用确定性规则识别，允许为空，不使用 LLM 推断。
- Chunk ID 由 PDF SHA-256、策略版本、窗口参数、页码和字符区间共同生成。

字符窗口只是首个可复现 Baseline，并不代表最优策略。是否改为 tokenizer-aware、
section-aware 或 semantic chunking，必须由后续 Retrieval Evaluation 决定。

## Chunk Metadata

种子语料中的每个 Qdrant Payload 包含：

```text
chunk_id
document_sha256
chunk_index
chunking_version
corpus_id / corpus_version
paper_id
arxiv_id / arxiv_version
title
source_path
page_number
section_title
char_start / char_end
text
```

其中 `source_path` 使用项目相对路径，避免本地机器路径进入可持久化 Metadata。

## Collection 与幂等性

默认 Collection：

```text
agent_seed_v3_bge_m3_chunking_v1
```

批量导入会先验证 Corpus、Manifest、PDF 文件及 SHA-256，然后逐论文生成 Embedding。
写入时按照 `corpus_id + corpus_version + paper_id + chunking_version` 替换旧点，重复执行
不会增加点数。当前 v3 完整语料为 2,152 点；v1/v2 Collection 仅用于历史 Baseline。

## 可观察性

```powershell
paper-rag corpus-stats --version 1
paper-rag ingest-corpus --version 1
paper-rag inspect-chunks .\data\corpus\v1\papers\2210.03629_react.pdf
paper-rag search "ReAct 如何使用外部工具？" --top-k 5
```

`corpus-stats` 完全离线，报告长度分位数、短 Chunk、超长 Chunk、重复 ID、Metadata
缺失、Section 覆盖率和逐论文分布。

## 检索策略

当前实现六种可对照策略：

| Strategy | 用途 | 实现 |
| --- | --- | --- |
| `dense` | 单论文证据定位、默认问答 | 直接按向量相似度返回 Top-K |
| `diversified_dense` | 可解释的来源多样化 Baseline | Dense Top-50 后执行同页去重和单论文数量限制 |
| `mmr_dense` | Discovery、跨论文候选组织 | 兼顾 Query 相关性和已选 Chunk 的语义新颖性 |
| `bm25` | 词面检索 Baseline | 英文停用词过滤、Porter stemming、BM25 Lucene 公式 |
| `hybrid_rrf` | Discovery 首选实验策略 | Dense Top-50 + BM25 Top-50 + RRF |
| `hybrid_rrf_mmr` | 融合后多样化实验 | 对归一化 RRF 候选执行 MMR |
| `hybrid_rrf_query_rewrite` | 跨语言、多子意图实验 | 原始 Query + 3 条英文 Rewrite，8 路 RRF |
| `RerankingRetriever` | 高质量增强实验 | 任意候选 Retriever Top-50 + Cross-Encoder 重排 |

`diversified_dense` 默认实验参数为 `candidate_pool=50`、`max_per_paper=3`、
`max_per_page=1`。它不计算 Document-Document 相似度，因此不称为 MMR，也不改变原始
Dense score，只按原排名确定性过滤并重新生成连续 Citation ID。

`mmr_dense` 使用 Qdrant 已保存的候选向量，不会重新 Embedding 候选 Chunk。当前参数为
`candidate_pool=50`、`lambda=0.85`，并用 NumPy 矩阵运算计算候选与已选结果的余弦相似度。
它把 Discovery Paper Recall@10 提升到 `100%`，同时保留 `94%` Exact Page Recall。

BM25 索引从 Qdrant 当前 Collection 读取 571 个 Payload，并按稳定 `chunk_id` 排序。BM25
参数为 `k1=1.5`、`b=0.75`；没有正分的结果不会进入候选池。RRF 参数为 `k=60`，使用排名
而不是原始分数，因此不需要直接归一化 cosine 和 BM25 score。

Hybrid RRF 在 Discovery 集上将 Paper MRR 从 `0.9733` 提升到 `1.0000`，Exact Page MRR
从 `0.7543` 提升到 `0.8170`，并修复 `DS-001` Top-1。但它在已知论文集上没有超过 Dense，
因为论文名的词面匹配可能提升非目标证据页。

v2 上 Hybrid RRF 的总体 Paper Recall@10 为 `95.83%`，略高于 Dense 的 `95.50%`；Exact
Page Recall@10 为 `91.83%`，高于 Dense 的 `87.83%`，但冗余也从 `12.80%` 增至 `15.20%`。
当前决策仍是 Evidence 定位使用 Dense，默认 Discovery 使用 Hybrid RRF；Query Rewrite 和
Reranker 已完成独立消融，作为可复现实验能力保留，不直接改变默认链路。

v2 的 Hybrid RRF + MMR 消融进一步测试了 `lambda=0.70 / 0.85 / 0.95`。三组均未改善
Challenge Complete Papers@10，也没有修复五个多论文覆盖失败；最大冗余下降只有 0.8 个
百分点，并伴随页码覆盖退化和额外延迟。因此默认 Discovery 不增加 MMR，后续优先验证
Query Rewrite 是否能改善跨语言词面召回和多子意图候选覆盖。

`query_rewrite_v1` 已完成该验证：DeepSeek 生成 3 条禁止猜测论文名的英文互补 Query，保留
原始中文 Query，每个 Query 分别执行 Dense/BM25，再对 8 路 Ranking 做 RRF。Rewrite 缓存
记录模型、Prompt 版本、生成耗时和精确 Query；Evaluation Raw Result 记录每题实际使用的
`retrieval_queries`。Challenge Complete Papers@10 从 `84%` 提升到 `96%`，但 paired 降至
`92%`，且串行端到端延迟较高，所以它暂时不进入生产模式。

共享 OpenAI-compatible Transport 对网络错误、429 和 5xx 执行最多 3 次指数退避重试，其他
4xx 和业务校验错误立即失败。Query Rewriter 另外只对 Provider 空内容执行有限重试，并在每题
完成后落盘，以支持长实验断点续跑。

候选诊断工具 `scripts/diagnose_query_rewrite_candidates.py` 会对每个目标记录原始/Rewrite
融合排名、每条 Query 的 Dense/BM25 Paper Rank 和 Exact Page Rank，并分类为 Top-10、
11-50 可重排、Top-50 外或分支未召回。当前三个剩余失败的目标页均在 Top-50，证明
Candidate Pool 足够；但八路分数累加会让跨 Query 重复出现的竞争论文获得过高权重。

`fuse_query_rankings_max` 将每个候选的跨 Query 分数从求和改为取最佳 per-query RRF score。
共享候选消融中，它把 Paper@10 提升到 `99%`、Exact Page@10 提升到 `97%`，同时将 paired
和 challenge Complete Papers@10 提升到 `100%/96%`。计算开销不足 1 ms，不增加模型调用；
但 Page MRR 有回退，因此只用于 Query Rewrite 实验链路。

`RerankingRetriever` 是 Candidate Retriever 的可组合装饰器：先取 Top-50，再通过
SiliconFlow `BAAI/bge-reranker-v2-m3` 对原始 Query 与每个完整 Chunk 做 Cross-Encoder
相关性打分，按新分数返回 Top-K。Trace 保留原始排名/分数、重排分数/排名、模型名和调用
延迟，便于逐 Case 解释排序变化。Provider 会校验响应数量、index、重复 index 和 score，
并复用共享 Transport 的网络错误、429、5xx 重试策略。

v2 消融显示 Fast Hybrid + Reranker 将 Paper@10 从 `95.83%` 提升到 `98.50%`、Exact
Page@10 从 `91.83%` 提升到 `98.00%`、challenge Complete 从 `84%` 提升到 `96%`，但
Retrieval P50 从 `349 ms` 增至 `1748 ms`。Deep Max + Reranker 虽修复 `DS-041` 并将 Page
MRR 提升到 `0.8492`，却导致 `DS-021/046` 回退，未通过无回退验收。原因是 Chunk 级相关性
优化不能保证多论文 Query 的子意图完整覆盖。因此 Fast + Reranker 只作为高质量增强候选，
Deep 叠加保留为实验，默认低延迟 Discovery 不变。

## Coverage-aware Retrieval v1

普通 RRF 和 pointwise Reranker 都按整条 Query 的总体相关性排序，无法保证跨论文问题的每个
子意图都在 Top-K 中获得位置。`AE-016` 因此稳定召回 Toolformer，却缺失 ReAct；强 Answer
模型偶尔仍能依靠参数知识回答，但这不属于可靠的 Retrieval 成功。

当前实验链路为：

```text
Cross-paper Question
  -> deepseek-v4-flash Query Decomposition（2 个子查询）
  -> 每个子查询独立 Hybrid RRF Top-30
  -> 可选：每个子查询内部独立 BGE Reranker
  -> Coverage Round-robin（5/5 配额、Chunk 去重）
  -> Top-10 Evidence + 连续 Citation ID
```

Decomposition Prompt 禁止猜测原问题未出现的论文名、方法名、作者、数据集和 arXiv ID。缓存
记录模型、Prompt version、生成耗时和精确子查询；正式实验还会使用 Corpus v2 的全部 slug、
完整标题和冒号前简称做 alias leakage 审计，发现泄漏则在检索前终止。

`CoverageTrace` 记录子查询、每路候选数、最终配额、Decomposition 缓存/生成耗时、每路 Hybrid
与 Reranker 耗时及总耗时。Reranker 只在各自子查询内部排序，不做全局重排，避免合并后的
一个高相关论文再次占满 Top-K。

三条匿名跨论文比较题的结果：

| Strategy | Paper Recall@10 | Exact Page Recall@10 | Complete Papers@10 | Retrieval |
| --- | ---: | ---: | ---: | ---: |
| Hybrid RRF | 50.00% | 50.00% | 0.00% | 约 0.49 s |
| Hybrid + Global Reranker | 83.33% | 83.33% | 66.67% | 约 1.7 s |
| Decomposition + Hybrid + Coverage | **100%** | **100%** | **100%** | 约 0.46 s + 一次性分解 |
| 上述方案 + per-subquery Reranker | **100%** | **100%** | **100%** | 约 2.0 s + 一次性分解 |

一次性 Decomposition 生成耗时为 `3.1-6.8 s`，缓存命中接近 0 ms。per-subquery Reranker
没有继续改善覆盖或 Answer Judge，额外增加约 1.5 秒，因此当前实验决策是保留
`Decomposition + Hybrid + Coverage`，不叠加 Reranker。它尚未进入生产 Factory；应在后续
Query Router 能可靠识别 cross-paper 问题后再接入主链路。

## 生产模式与生命周期

`RetrieverFactory` 将评测结论映射为两个主链路模式：

```text
retrieval_mode=evidence
  -> DenseRetriever

retrieval_mode=discovery
  -> DenseRetriever + Bm25Retriever -> RrfFusionRetriever
```

`search`、`show-prompt` 和 `ask` 均支持显式 `--retrieval-mode evidence|discovery`，默认值为
`evidence`。当前不做自动 Query Routing，避免在没有 Router Evaluation 的情况下隐藏错误
路由行为。

Reranker 暂未加入这两个生产模式。这样保留了显式的 latency/quality 选择，也避免将尚未通过
无回退验收的 Deep 组合隐式送入 `ask`。后续若暴露增强模式，应单独命名并在 API 返回
Reranker latency 与 trace，而不是改变现有 `discovery` 语义。

Factory 对 `evidence` 直接复用 Dense 实例；第一次请求 `discovery` 时才从 Qdrant Payload
读取 Chunk、构建 BM25 和 Hybrid RRF，后续在同一 Runtime 生命周期内复用同一实例。因此
BM25 的约 600 ms 构建成本属于启动/首次使用成本，不会在每个 Query 内重复发生。完整实验
结果见 `docs/evaluation.md`。
