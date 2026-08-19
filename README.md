# Paper Research Copilot

Paper Research Copilot 是一个面向学术论文研究的 Agentic RAG 项目。项目先完成可评估的
基础 RAG，再在不改写 Retriever 和 Answer 契约的前提下加入薄 LangGraph Runtime，确保
Agent 的每个决策和最终答案都能追溯到 PDF 页码与原始文本片段。

当前稳定版本为 `v1.0.0`，使用 40 篇固定版本的 Agent 论文构建 Corpus v3，并完成
Retrieval、Answer/Citation、LLM Judge 和 Agent-vs-Fixed-RAG 三层评测。

## 快速导航

- [系统架构](docs/architecture.md)
- [五分钟演示流程](docs/demo.md)
- [面试讲解与简历表述](docs/interview.md)
- [Retrieval 设计](docs/retrieval.md)
- [Evaluation 设计](docs/evaluation.md)
- [完整开发记录](开发过程.md)

## 当前能力

```text
PDF
  -> Parse
  -> chunking_v1 (Page-aware + Paragraph-first + Section metadata)
  -> SiliconFlow Embedding
  -> Qdrant Vector Store
  -> Retriever Factory
       evidence  -> Dense
       discovery -> Dense + BM25 + RRF
       experiment -> Top-50 Candidate Pool + BGE Reranker
       cross-paper -> Query Decomposition + Hybrid RRF + Coverage Merge
  -> DeepSeek LLM
  -> Answer + Citations

LangGraph Agent Runtime
  -> gpt-5.5 Research Plan
  -> single_paper: Hybrid RRF
     cross_paper: Task Hybrid RRF + Coverage Merge
  -> Evidence Gate
  -> optional Query Revision (max 1)
  -> Answer + Citation Validation

FastAPI Task Layer
  -> POST asynchronous research task
  -> in-memory single-worker execution
  -> live LangGraph node events over SSE
  -> task status + complete AgentResult

React Research Workspace
  -> research question + task status
  -> live SSE Agent Timeline
  -> Report / Evidence / Plan views
  -> citation-to-evidence navigation
```

- 使用 `pypdf` 按页提取论文文本和 PDF metadata。
- `chunking_v1` 使用 `3200 chars / 400 overlap`，优先按段落和句子边界切分且不跨页。
- Chunk 保存 Corpus、arXiv revision、PDF SHA-256、Section、页码和字符区间。
- 使用 SiliconFlow `BAAI/bge-m3` 生成 1024 维向量。
- 使用 Qdrant 本地持久化模式保存 Chunk、metadata 和向量。
- 通过显式 `retrieval_mode` 选择 Dense 或 Hybrid RRF，并为结果分配 `[C1]`、`[C2]` 等
  Citation ID。
- LLM 只能基于检索证据回答；未知引用或无引用回答会被拒绝。

当前版本已将评测后的 Dense 与 Hybrid RRF 接入主链路，并实现可观测的 Cross-Encoder
Reranker 实验层，是后续 Answer Evaluation 和 Agent Runtime 的基础。

当前保留 `agent-seed-v1` 作为对照，并已完成更困难的 `agent-seed-v2`：
20 篇固定 arXiv revision、604 页、971 个 `chunking_v1` Chunk，以及 50 条 Discovery v2
问题。v2 已通过 Parse、视觉和 Dataset 校验，使用 `BAAI/bge-m3` 写入独立 Qdrant
Collection；两次导入点数均为 971。Dense、BM25、Hybrid RRF 已按 paired anchors 与
challenge 分组评测，详细结果见 `evals/baselines/retrieval_discovery_v2_comparison.md`。
额外的 Hybrid RRF + MMR v2 消融表明 `lambda=0.70 / 0.85 / 0.95` 均未改善多论文完整
覆盖，因此 MMR 不进入默认 Discovery 链路。

`agent-seed-v3` 已进一步扩展为 40 篇固定 revision PDF（216.79 MiB、1,387 页、
2,152 chunks），Parse 为 31 verified / 9 warning / 0 failed，分块统计中没有 oversized、
duplicate ID 或 missing metadata。配套 Golden Data 已扩展为 100 条 Discovery v3、
32 条 Answer v2 和 12 条 Agent Runtime v2。全部 Chunk 已使用 `BAAI/bge-m3` 向量化并
写入独立 Collection `agent_seed_v3_bge_m3_chunking_v1`，实际点数为 2,152。
Discovery v3 的 100 条问题已完成 Dense、BM25、Hybrid RRF 三路评测：Hybrid 的
Paper Recall@10 为 `92.17%`，与 Dense 的 `92.00%` 基本持平；Exact Page Recall@10 从
Dense 的 `83.92%` 提升到 `86.92%`。同一批旧 50 题扩库后，Hybrid 的 Paper Recall 和
Complete Papers 没有下降，说明其对新增同主题干扰比 Dense 更稳健。新增跨论文题上 Hybrid
Complete Papers@10 仍只有 `50%`，因此单论文 Discovery 继续使用 Hybrid RRF，跨论文任务
继续使用 Query Decomposition + Coverage Merge。完整对照见
`evals/baselines/retrieval_discovery_v3_comparison.md`。

Corpus v3 的 Answer v2 固定 Hybrid Baseline 在 32 条问题上达到 `78.12%` Answerability，
`gpt-5.5` Judge Overall 为 `74.22%`；主要失败是一次生成截断和跨论文目标覆盖不足。随后在
12 条 Agent Runtime v2 上，LangGraph Agent 相比同一批 Fixed Hybrid，将跨论文 Complete
Papers@10 从 `40%` 提升到 `80%`、Answerability 从 `75%` 提升到 `100%`、Strict Run 从
`66.67%` 提升到 `91.67%`，P50 代价从 `7.1 s` 增至 `18.7 s`。这证明 Planning 与
Coverage-aware Retrieval 的收益能够传递到最终答案，而不只是改善离线 Recall。生产演示现已
切换到 Corpus v3；剩余回退为 1 条错误路由、1 条跨论文半覆盖，以及一次可恢复的 Answer 截断。
Query Rewrite 对照使用原始中文 Query 和 3 条英文互补 Query 做 8 路 RRF，将 challenge
Complete Papers@10 从 `84%` 提升到 `96%`，但带来 paired 回退和约 6.6 秒 Rewrite 生成
延迟，因此目前仍是实验策略，不替换默认 Hybrid RRF。
`BAAI/bge-reranker-v2-m3` 对 Top-50 重排后，Fast Hybrid 的 Paper@10 从 `95.83%` 提升到
`98.50%`、Exact Page@10 从 `91.83%` 提升到 `98.00%`，代价是约 `1.4 s` 的 Reranker
P50。Deep Query Rewrite + Max-over-query + Reranker 修复了 `DS-041`，但引入 `DS-021/046`
回退，因此不替换默认链路。

Answer Evaluation v1 已加入 20 条 Golden Cases、结构化拒答和确定性 Answer/Citation 指标。
端到端对照中，Fast Hybrid + Reranker 将 Answerability 从 `85%` 提升到 `95%`、Key Point
Recall 从 `80.56%` 提升到 `93.06%`、Citation Paper Recall 从 `83.33%` 提升到 `94.44%`，
Total P50 从 `4319 ms` 增至 `5679 ms`。这说明 Reranker 的部分 Retrieval 增益能够转化为
真实答案收益，但当前 20 Case 单次实验仍不足以替换默认低延迟模式。

`gpt-5.5` LLM Judge v1 已进一步评估 Correctness、Claim-Evidence Faithfulness 与 Citation
Completeness，并与确定性指标并列保留。Hybrid RRF 的 Judge Overall 为 `84.58%`，Hybrid +
Reranker 为 `94.58%`；后者修复 `AE-017/018`，但 `AE-016` 仍为 0 分。Judge 使用输入哈希、
逐 Case 缓存、Pydantic Schema 校验、有限重试和 Token/延迟追踪，完整对照见
`evals/baselines/answer_judge_v1_comparison.md`。

Answer Stability v1 进一步冻结两组 Baseline 各自的 Top-10 Evidence，对 8 条代表性 Case
分别重复生成 3 次。Reranker 将 Strict Run Pass 从 `66.67%` 提升到 `87.50%`，Fully Stable
Cases 从 `62.50%` 提升到 `75.00%`；同时暴露 `AE-016/017` 的空 content、无 Citation 和
错误拒答波动。完整结果见 `evals/baselines/answer_stability_v1.md`。

Generation Observability v2 已记录每次生成的 `finish_reason`、响应模型、Token usage、耗时与
结果分类，并对 `finish_reason=length` 执行一次压缩重试。真实调用发现 Relay 可能返回
`length + empty content`，因此必须优先判定为截断；`ANSWER_MAX_TOKENS` 已提升到 `2400`。
在三条跨论文题上，Hybrid + Reranker 达到 9/9 生成成功、9/9 Strict Run。

Coverage-aware Retrieval v1 将跨论文问题拆成两个不含目标论文名的子查询，各自执行 Hybrid
RRF Top-30，再按 `5/5` 配额轮转合并为 Top-10。三条困难比较题的 Complete Papers@10 从
Hybrid 的 `0%`、Global Reranker 的 `66.67%` 提升到 `100%`。不加 per-subquery Reranker 的
Coverage 方案已达到 `100%` Strict Runs，检索约 `0.46 s`；继续加 Reranker 没有质量增益，
耗时约增至 `2.0 s`，因此当前选择更简单的 Coverage 方案。完整消融见
`evals/baselines/coverage_aware_ablation_v1.md`。

LangGraph Agent Runtime 已实现结构化 `ResearchPlan`、单/跨论文条件路由、确定性 Evidence
Gate、最多一次 Query Revision、Citation Validation 和逐节点 Trace。真实 Smoke 中，单论文
问题只生成 1 个任务并使用 Hybrid；跨论文问题自动生成 2 个匿名任务，以 `5/5` 配额同时
召回多个比较目标。Agent Runtime v2 的 12 Case 对照中，跨论文完整覆盖从 `40%` 提升到
`80%`，Strict Run 从 `66.67%` 提升到 `91.67%`；Planning P50 约 `10.7 s`，仍是主要延迟。
完整结果见 `evals/baselines/agent_runtime_v2.md`。

## 环境

项目使用独立 Conda 环境：

```powershell
conda activate paper-research-copilot
```

完整学习环境来自 `requirements_full.txt`，项目实际运行依赖维护在
`pyproject.toml`。首次安装流程：

```powershell
conda create -n paper-research-copilot python=3.12 pip -y
conda activate paper-research-copilot
python -m pip install -r requirements_full.txt
python -m pip install -e ".[dev]"
```

`.env` 至少需要配置：

```dotenv
DEEPSEEK_API_KEY=
DEEPSEEK_API_URL=
DEEPSEEK_MODEL=deepseek-v4-flash

SILICONFLOW_API_KEY=
SILICONFLOW_BASE_URL=
SILICONFLOW_EMBEDDING_MODEL=BAAI/bge-m3
SILICONFLOW_RERANKER_MODEL=BAAI/bge-reranker-v2-m3

QDRANT_COLLECTION=agent_seed_v3_bge_m3_chunking_v1
CHUNKING_VERSION=chunking_v1
CHUNK_SIZE_CHARS=3200
CHUNK_OVERLAP_CHARS=400

RELAY_API_KEY=
RELAY_BASE_URL=
GPT_MODEL_NAME=gpt-5.5
```

`.env` 已被 Git 忽略，不应提交密钥。

## 使用

### 生产演示模式（推荐）

在项目根目录执行一个命令，脚本会检查依赖、构建 React，并由 FastAPI 同源托管完整工作台：

```powershell
.\scripts\start_demo.ps1
```

访问 `http://127.0.0.1:8000`。API、SSE 和前端使用同一 Origin，不需要额外配置 CORS；OpenAPI
仍位于 `/docs`。已经构建前端且只想重新启动服务时可执行
`.\scripts\start_demo.ps1 -SkipBuild`。

### API 与前端开发模式

单独启动 FastAPI 服务：

```powershell
paper-research-api
```

服务默认监听 `http://127.0.0.1:8000`，OpenAPI 位于 `/docs`。`POST /api/v1/research` 创建异步
研究任务，`GET /api/v1/research/{task_id}` 查询结果，`GET .../events` 通过 SSE 推送每个
LangGraph 节点的 outcome、latency 和 details。`GET /health` 会实际构建 Runtime，检查 Corpus v3
和 Qdrant Collection。完整契约与 MVP 边界见 `docs/api.md`。

另开终端启动 React 研究工作台：

```powershell
cd frontend
npm install
npm run dev
```

访问 `http://127.0.0.1:5173`。桌面端按 Query、Agent Trace、Research Output 三栏组织，移动端
重排为单列；任务通过 SSE 实时更新，断线时自动降级为状态轮询。结果区包含 Report、Evidence、
Plan 三个 Tab，点击 Citation 会定位对应 Evidence Chunk。完整说明见 `docs/frontend.md`。

运行有界 LangGraph Agent，并显示 Plan、Evidence Assessment 和逐节点 Trace：

```powershell
paper-rag agent "交错生成 Thought、Action、Observation 的提示方法，与通过采样和 loss 过滤来学习 API calls 的方法有何差异？" `
  --show-trace
```

默认使用 Corpus v3、Hybrid RRF、Top-10、每 Task Top-30 Candidate Pool 和最多一次 Query
Revision。Planner 使用 `gpt-5.5`，Answer 使用 `deepseek-v4-flash`；计划缓存在
`data/agent/`，重复问题可复用精确 Plan。

离线检查并生成整个种子语料库的 Chunk 统计，不调用模型 API：

```powershell
paper-rag corpus-stats --version 1
```

校验 Corpus/Manifest/PDF SHA-256，批量 Embedding，并幂等写入版本化 Collection：

```powershell
paper-rag ingest-corpus --version 1
paper-rag ingest-corpus --version 2 --collection agent_seed_v2_bge_m3_chunking_v1
```

该命令重复执行会按 `corpus_id + corpus_version + paper_id + chunking_version` 替换旧点，
不会产生重复 Chunk。

索引一篇或多篇论文：

```powershell
paper-rag ingest .\data\papers\paper-a.pdf .\data\papers\paper-b.pdf
```

从已经索引的论文中提问：

```powershell
paper-rag ask "ReAct 的核心方法是什么？" --top-k 5 --retrieval-mode evidence
paper-rag ask "哪些方法使用环境反馈改进后续决策？" --top-k 5 --retrieval-mode discovery
```

一次完成索引和提问：

```powershell
paper-rag run "这篇论文的核心方法是什么？" .\data\papers\paper-a.pdf
```

### 调试与观察

检查 PDF Parse 结果，不调用任何外部 API：

```powershell
paper-rag inspect-pdf .\data\papers\react.pdf
```

输出论文 metadata、Document ID、每页字符数和文本预览。

检查 Page-aware Chunk 结果，不调用任何外部 API：

```powershell
paper-rag inspect-chunks .\data\papers\react.pdf
```

默认显示前 10 个 Chunk，可以进一步筛选：

```powershell
paper-rag inspect-chunks .\data\papers\react.pdf --page 2 --limit 5 --full-text
```

只执行 Retrieval，不调用 LLM：

```powershell
paper-rag search "ReAct 如何使用外部工具？" --top-k 5 --retrieval-mode evidence
paper-rag search "哪些方法通过外部工具扩展能力？" --top-k 5 --retrieval-mode discovery
```

输出每个 Top-K 结果的相似度、页码、Chunk ID、原始路径和完整 Evidence。

查看真正发送给 LLM 的 Prompt，但不调用 LLM：

```powershell
paper-rag show-prompt "ReAct 如何使用外部工具？" --top-k 5 --retrieval-mode evidence
paper-rag show-prompt "哪些方法通过外部工具扩展能力？" --top-k 5 `
  --retrieval-mode discovery
```

该命令按照指定模式检索，再输出完整的 System Prompt 和 User Prompt。它用于检查最终
上下文是否包含正确 Evidence，以及 Citation ID 是否和检索结果一致。

`evidence` 适合已知论文或明确主题内的证据定位，映射到 Dense；`discovery` 适合不含论文名
的自然问题和跨论文发现，映射到 Hybrid RRF。系统当前不自动判断模式，调用方必须显式选择；
省略参数时默认使用 `evidence`。Hybrid 所需 BM25 索引在 Runtime 中延迟构建一次并复用。

默认 Qdrant 数据保存在 `data/qdrant/`。该目录属于运行数据，不进入 Git。
种子语料默认 Collection 为 `agent_seed_v3_bge_m3_chunking_v1`。

Chunk 分布报告保存在 `corpus/v1/chunking_v1/`。Retrieval Evaluation 分为两套数据：
`retrieval_diagnostic_v1.jsonl` 用于已知论文内定位，`retrieval_discovery_v1.jsonl` 用于
不含目标论文名的自然问题与跨论文发现。

运行当前 Dense Retrieval Baseline：

```powershell
paper-rag evaluate-retriever --version 1 --top-k 10 --baseline-id dense_v1
```

当前结果为 Paper Recall@5 `98%`、Exact Page Recall@5 `82%`。由于诊断问题均包含论文名，
该结果主要衡量已知论文内定位能力，不能代表开放式论文发现能力。

运行无标题泄漏的 Discovery Baseline：

```powershell
paper-rag evaluate-retriever --dataset .\evals\datasets\retrieval_discovery_v1.jsonl `
  --version 1 --top-k 10 --strategy dense --baseline-id dense_discovery_v1
```

运行论文/页面约束的 Dense Retrieval：

```powershell
paper-rag evaluate-retriever --dataset .\evals\datasets\retrieval_discovery_v1.jsonl `
  --version 1 --top-k 10 --strategy diversified_dense --candidate-pool 50 `
  --max-per-paper 3 --max-per-page 1 --baseline-id diversified_dense_discovery_v1
```

运行 MMR Dense Retrieval：

```powershell
paper-rag evaluate-retriever --dataset .\evals\datasets\retrieval_discovery_v1.jsonl `
  --version 1 --top-k 10 --strategy mmr_dense --candidate-pool 50 `
  --mmr-lambda 0.85 --baseline-id mmr_dense_l085_discovery_v1
```

`lambda=0.5/0.7/0.85` 对照中，`0.85` 的折中最好：Paper Recall@10 `100%`、Exact Page
Recall@10 `94%`、Same-page Redundancy@10 `6.8%`。规则版 Diversified Dense 保留为可解释
Baseline。

运行 BM25、Hybrid RRF 和 Hybrid RRF + MMR：

```powershell
paper-rag evaluate-retriever --dataset .\evals\datasets\retrieval_discovery_v1.jsonl `
  --strategy bm25 --baseline-id bm25_discovery_v1

paper-rag evaluate-retriever --dataset .\evals\datasets\retrieval_discovery_v1.jsonl `
  --strategy hybrid_rrf --candidate-pool 50 --rrf-k 60 `
  --baseline-id hybrid_rrf_discovery_v1

paper-rag evaluate-retriever --dataset .\evals\datasets\retrieval_discovery_v1.jsonl `
  --strategy hybrid_rrf_mmr --candidate-pool 50 --rrf-k 60 --mmr-lambda 0.85 `
  --baseline-id hybrid_rrf_mmr_discovery_v1
```

运行 v2 Query Rewrite 对照：

```powershell
paper-rag evaluate-retriever --version 2 `
  --collection agent_seed_v2_bge_m3_chunking_v1 `
  --dataset .\evals\datasets\retrieval_discovery_v2.jsonl `
  --strategy hybrid_rrf_query_rewrite --rewrite-count 3 `
  --candidate-pool 50 --rrf-k 60 `
  --baseline-id hybrid_rrf_query_rewrite_discovery_v2
```

Rewrite 缓存在 `evals/query_rewrites/`，重复实验会复用完全相同的 Query，不重复调用 LLM。
在固定候选上的 Fusion 消融中，`Max-over-query RRF` 将 Paper@10 提升到 `99%`、Exact
Page@10 提升到 `97%`，并修复两个剩余多意图 Case；但 Page MRR 有所下降，因此尚未替换
默认 Discovery。

运行真实 Reranker 连通性检查和 v2 四组消融：

```powershell
python .\scripts\smoke_reranker.py
python .\scripts\run_reranker_ablation.py
```

消融比较 Fast Base、Fast + Reranker、Deep Max Base 和 Deep Max + Reranker，并输出总体、
paired/challenge、逐 Case 排名变化及独立 Reranker 延迟。完整结论见
`evals/baselines/reranker_ablation_v2.md`。

运行 Answer Evaluation v1：

```powershell
paper-rag evaluate-answer --strategy hybrid_rrf `
  --baseline-id answer_hybrid_rrf_v1

paper-rag evaluate-answer --strategy hybrid_rrf_rerank `
  --baseline-id answer_hybrid_rrf_rerank_v1
```

该命令分别记录 Answer、实际 Evidence、Citation、Key Point 命中、论文/严格页码引用指标、
拒答结果以及 Retrieval/Generation/Total latency。完整对照见
`evals/baselines/answer_evaluation_v1_comparison.md`。

对保存的 Answer Result 运行 `gpt-5.5` Judge：

```powershell
paper-rag evaluate-judge `
  --baseline-id answer_hybrid_rrf_gpt55_judge_v1

paper-rag evaluate-judge `
  --answer-baseline .\evals\baselines\answer_hybrid_rrf_rerank_v1.json `
  --answer-results .\evals\results\answer_hybrid_rrf_rerank_v1.jsonl `
  --baseline-id answer_hybrid_rrf_rerank_gpt55_judge_v1
```

Judge 只接收候选答案实际引用的 Evidence。正确拒答直接记 `4/4/4`，Generation Failure、
错误拒答和 Judge Failure 直接记 `0/0/0`，且全部进入总体分母。逐条可审计缓存位于
`evals/judges/`，正式对照见 `evals/baselines/answer_judge_v1_comparison.md`。

运行 Generation Observability 与 Coverage-aware Retrieval 消融：

```powershell
python .\scripts\run_answer_stability.py `
  --case-id AE-016 --case-id AE-017 --case-id AE-018 `
  --baseline-id answer_generation_observability_v2 `
  --judge-cache-tag generation_v2b

python .\scripts\run_coverage_ablation.py
```

后一个脚本会先审计 Query Decomposition 是否引入 Corpus title/slug；只有零泄漏才继续运行
四组 Retrieval、Answer 重复生成和 `gpt-5.5` Judge。Answer、Judge 与 Decomposition 都有
JSONL 缓存，可在中断后继续。

运行 Agent-vs-Fixed-RAG Evaluation：

```powershell
python .\scripts\run_agent_evaluation.py
```

该实验在 8 条代表题上比较 Fixed Hybrid、Fixed Hybrid + Reranker、Oracle Route 和 LangGraph
Agent，同时报告 Router、Task Coverage、Title Leakage、跨论文 Complete Papers@10、Answer/
Citation Judge、节点延迟与模型调用成本。当前 Agent 的跨论文 Complete Papers@10 和 Strict
Run 均为 100%，但 Workflow P50 约 18.1 秒，下一步重点是 Planner 模型消融。完整报告见
`evals/baselines/agent_runtime_v1.md`。

运行 Planner 模型消融：

```powershell
python .\scripts\run_planner_ablation.py
```

当前 `deepseek-v4-flash` 的 Planner P50 为 5.1 秒，明显快于 `gpt-5.5` 的 10.7 秒，但未通过
Router、Task Count 和 Task Coverage 的零回退门槛，P95 也达到 23.9 秒。因此生产 Planner
暂时继续使用 `gpt-5.5`。完整结果见 `evals/baselines/planner_model_ablation_v1.md`。

Planner/Router Evaluation v2 已扩展到 40 条，覆盖单意图定位、双论文比较、3/4 方法综合、
语料级核验和路由边界题，并为歧义 Case 分开记录 Strict 与 Acceptable 标签。数据位于
`evals/datasets/planner_routing_v2.jsonl`，可通过
`python scripts/validate_planner_routing_dataset.py` 校验。运行 v2 模型消融：

```powershell
python .\scripts\run_planner_ablation_v2.py
```

40 条真实结果中，DeepSeek 的 Core Route/Task/Coverage 均为 100%，P50/P95 为
`5.0/10.8 s`；GPT 为 `97.3%/97.3%/100%`，P50/P95 为 `10.7/13.6 s`。但 DeepSeek 在
`PR-032` 漏掉表格/评测段落复核 Facet，总体 Coverage 为 98.75%，并有 5% Schema Retry；
GPT 则在 `PR-016` 将同一基准中的两个数值过度拆为两路。两者都未通过零回退 Gate，生产
Planner 暂时保留 `gpt-5.5`。完整报告见 `evals/baselines/planner_model_ablation_v2.md`。

针对 corpus verification 的 Prompt v2 消融可通过以下命令复现：

```powershell
python .\scripts\run_planner_prompt_ablation.py
```

Prompt v2 明确要求“正文直接检索 + 结果表/评测段落复核”，使 DeepSeek 在 40 条全集上的
Facet Coverage 从 98.75% 提升到 100%，修复了 `PR-032` 验证缺失，并保持 `PR-016` 的正确
单任务规划；后者是防止过度拆分的 Guardrail，不是相对 DeepSeek v1 的新增提升。
但 Core Task Count 降至 94.59%，Retry 升至 7.50%，P95 恶化到 25.8 秒；10 条高风险样本
的三次独立重复也只有一次通过全部 Gate。因此它没有接入生产 Factory，生产 Planner 仍使用
`gpt-5.5 + research_planner_v1`。完整对照见
`evals/baselines/planner_prompt_ablation_v2.md`。

Planner Attempt Observability 已进一步记录每次尝试的 outcome、finish reason、响应长度、错误类型、
Token、延迟和响应 SHA256；原始失败响应只保存在 ignored 的 `data/agent/`。针对
`PR-030/033/039` 各独立复跑 3 次后，9 个 Plan 全部最终成功，但 3 个 Plan 触发重试，共出现
4 个 `truncated` attempt。4 次的 `output_tokens` 都恰好达到 `AGENT_PLANNER_MAX_TOKENS=1800`，
其中 3 次返回空 content，未观察到 invalid JSON、Schema、Task Shape、Leakage 或 Provider Error。
完整报告见 `evals/baselines/planner_retry_diagnostics_v1.md`。

针对该根因，Planner Truncation Recovery v1 进一步交错运行 27 个 Plan，对比 `same_1800`、
`compact_1800` 和 `same_2400`。前两组各有 1/9 样本连续三次截断并最终失败；`same_2400`
达到 9/9 成功、100% Acceptable Route/Task Count/Facet Coverage 和 0 标题泄漏，是唯一通过质量
Gate 的策略。不过它仍有 44.44% Retry Rate 和 68.8 秒 P95，说明提高上限改善的是最终恢复率，
尚未消除长尾。实验对象是 `DeepSeek + Prompt v2`，当前生产 `gpt-5.5 + Prompt v1` 及全局
`AGENT_PLANNER_MAX_TOKENS=1800` 暂不改动。完整报告见
`evals/baselines/planner_truncation_recovery_v1.md`。

后续 `same_2400` 与 `compact_2400` 的 18-Plan 直接对照进一步确认 Compact 不值得采用：
`compact_2400` Success 88.89%、Retry Recovery 66.67%、P95 73.1 秒，并产生 25,735 Output
Tokens；`same_2400` 本轮没有截断，但 Route/Task Count 仍有随机波动。当前停止截断 Prompt 微调，
保留生产配置，把工程投入转回 Agent 产品化主线。报告见
`evals/baselines/planner_compact_2400_ablation_v1.md`。

Hybrid RRF 在 Discovery 集上达到 Paper Recall@10 `100%`、Paper MRR `1.0000`、Exact
Page Recall@10 `96%` 和 Exact Page MRR `0.8170`，修复了 Dense 的 `DS-001` Top-1 错误。
Hybrid+MMR 的 Page MRR 小幅增加到 `0.8247`，但多样性收益不足以抵消额外复杂度。

当前实验决策是已知论文 Evidence 定位使用 Dense，自然问题 Discovery 使用 Hybrid RRF。
`ask/search/show-prompt` 已通过显式 `--retrieval-mode` 接入这两种生产策略，但尚未实现自动
Query Router。

CLI 固定从项目根目录读取 `.env` 和相对 `QDRANT_PATH`。PDF 相对路径优先按当前终端
目录解析；如果当前目录不存在该文件，则回退到项目根目录。因此在项目目录或其他目录
执行上述命令都可以访问同一份开发数据。

## 测试

```powershell
python -m pytest -q
```

测试不会调用真实模型，Provider 使用 Fake 实现；真实模型与真实 PDF 使用单独的
Smoke Test 验证。

## 当前限制

- 只支持包含可提取文本的 PDF，扫描件暂不执行 OCR。
- Chunk 长度目前按字符而非模型 tokenizer 计算；Section title 使用确定性启发式识别。
- ReAct 等少数页存在 `pypdf` 字体到 Unicode 映射乱码，已在 Parse 报告中标记。
- 当前支持 Dense、BM25、RRF、MMR、Query Rewrite 与 Reranker 实验；生产 Factory 仍只暴露
  通过低延迟验收的 Dense/Hybrid，不自动启用高延迟实验策略。
- Coverage-aware Retrieval 已通过三条困难跨论文题的定向消融，但尚未接入自动 Query Router；
  固定 RAG 仍由实验脚本显式调用，Agent Runtime 则根据结构化 Plan 自动选择 Coverage。
- Citation 契约负责引用存在性与定位；LLM Judge 已补充 Claim-Evidence entailment 评估，
  但单 Judge 仍可能有偏差，需要人工抽查。
- 当前提供 CLI、LangGraph Agent Runtime、单机 FastAPI/SSE Task Layer 和 React Research
  Workspace；持久化 Task Store、LangGraph Checkpointer、认证与长期 Memory 尚未实现。

设计文档见 [docs/architecture.md](docs/architecture.md)、
[docs/retrieval.md](docs/retrieval.md)、[docs/evaluation.md](docs/evaluation.md) 和
[docs/api.md](docs/api.md)、[docs/frontend.md](docs/frontend.md)。
