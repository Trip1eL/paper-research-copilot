# 种子语料库

`corpus/` 保存可进入 Git 的语料定义与检查结果，原始 PDF 保存在被 Git 忽略的
`data/corpus/`。这样既能固定论文版本和内容指纹，也不需要在仓库中提交大体积 PDF。

## v1：Agent Seed Corpus

`v1` 包含 10 篇代表性 Agent 论文，覆盖 Reasoning/Acting、Tool Use、Reflection、
Planning、Memory、Embodied Agent、Multi-Agent 和 Evaluation。每篇论文固定到具体的
arXiv revision。

- `v1/corpus.json`：人工维护的论文清单、主题标签和固定下载地址。
- `v1/manifest.jsonl`：机器可读的本地路径、SHA-256、页数和 Parse 指标。
- `v1/parse_report.md`：供人工检查的中文汇总报告。
- `v1/chunking_v1/stats.json`：机器可读的 Chunk 长度和 Metadata 统计。
- `v1/chunking_v1/chunk_report.md`：逐论文 Chunk 分布与质量检查报告。

在项目 Conda 环境中构建或重新检查：

```powershell
conda run -n paper-research-copilot python scripts/build_seed_corpus.py --download
```

已有 PDF 时可以省略 `--download`，只重新生成 Manifest 和 Parse 报告。使用
`--force --download` 可按固定 revision 重新下载并覆盖本地副本。

Parse 检查只验证当前 `pypdf` 基线能否稳定提取文本。`warning` 论文仍可进入语料库，
但异常页需要在后续 Parser 对比和 Retrieval Evaluation 中重点观察。

只重新执行 Parse、Chunk 和统计，不调用 Embedding API：

```powershell
conda run -n paper-research-copilot paper-rag corpus-stats --version 1
```

## v2：Hard-Negative Agent Corpus

`v2` 保留 v1 的 10 篇论文，并加入 10 篇同主题干扰论文：MRKL、Self-Refine、Tree of
Thoughts、MemoryBank、HuggingGPT、Gorilla、ToolLLM、AgentVerse、MetaGPT 和 WebArena。
它重点增加 Reflection、Planning、Memory、Tool/API Use、Multi-Agent 与 Evaluation 方向的
概念重叠，用于测量 Retriever 在相似论文之间的区分能力。

```text
Papers: 20
Pages: 604
Chunks: 971
Chunking: chunking_v1
Parse: 14 verified / 6 warning / 0 failed
Visual check: passed
```

v2 的 20 篇 PDF 均无空页。新增论文的 10 个首页和 Tree of Thoughts 的 4 个异常文本页已
使用 Poppler 渲染核验；v1 的 10 个首页和 6 个异常页沿用已经完成的视觉检查结果。

重新验证和生成统计：

```powershell
conda run -n paper-research-copilot python scripts/build_seed_corpus.py `
  --spec corpus/v2/corpus.json
conda run -n paper-research-copilot paper-rag corpus-stats --version 2
```

原始 PDF 位于被 Git 忽略的 `data/corpus/v2/papers/`。进入 Qdrant 前必须使用独立的 v2
Collection，不能把 v2 写入 `agent_seed_v1_bge_m3_chunking_v1`。

## v3：Expanded Agent Research Corpus

`v3` 保留 v2 的 20 篇论文，并加入 20 篇 Architecture/Reflection、Tool Interaction、
Web/Computer Agent、Agent Evaluation、Software Engineering Agent 和 Agentic RAG 论文。

```text
Papers: 40
PDF size: 216.79 MiB
Pages: 1387
Chunks: 2152
Chunking: chunking_v1
Parse: 31 verified / 9 warning / 0 failed
Visual check: passed
```

40 个固定 revision PDF 的文件大小和 SHA-256 均与 manifest 一致。20 篇新增论文首页和
10 个新增异常/短文本页已完成 Poppler 视觉核验；warning 来自图形页、公式或特殊符号文本映射，
不是 PDF 损坏。ExpeL 的纯图片页不进入 Evaluation 页码标注。

```powershell
conda run -n paper-research-copilot python scripts/build_seed_corpus.py `
  --spec corpus/v3/corpus.json
conda run -n paper-research-copilot paper-rag corpus-stats --version 3
```

2,152 个 Chunk 已使用 `BAAI/bge-m3` 生成 1024 维向量，并写入独立 Qdrant Collection：

```text
Collection: agent_seed_v3_bge_m3_chunking_v1
Points: 2152
Distance: Cosine
```

Discovery v3 已完成 Dense、BM25、Hybrid RRF 三路 100 Case 对照。Hybrid 的总体 Paper
Recall@10 为 92.17%，Exact Page Recall@10 为 86.92%，作为单论文 Discovery 的默认策略；
新增跨论文题的 Complete Papers@10 只有 50%，因此跨论文任务仍使用 Query Decomposition +
Coverage Merge。Answer v2、`gpt-5.5` Judge 和 Agent Runtime v2 均已完成正式 Baseline；
Agent 相比 Fixed Hybrid 将 Strict Run 从 66.67% 提升到 91.67%，生产演示已切换到 v3。
