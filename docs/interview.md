# 面试讲解与简历表述

## 一分钟项目介绍

Paper Research Copilot 是一个面向 Agent 研究论文的 Agentic RAG 系统。它管理 40 篇固定版本
论文和 2,152 个带页码 Chunk，支持 Dense、BM25、Hybrid RRF、Reranker 与 Coverage-aware
Retrieval。对于复杂问题，`gpt-5.5` Planner 会生成结构化 Research Tasks，LangGraph 根据
single/cross-paper Route 选择检索策略，通过 Evidence Gate 判断证据是否充分，最多修订一次
Query，再由 DeepSeek 生成带 Citation 的回答。系统提供 FastAPI、SSE 和 React 工作台，并使用
Retrieval、确定性 Answer/Citation 指标和独立 LLM Judge 三层 Evaluation 验证效果。

## 与普通聊天 Agent 的区别

差异不在“也能搜索论文并写报告”，而在以下可验证的工程契约：

1. Corpus、PDF revision、SHA-256、Chunking 和 Qdrant Collection 全部版本化，实验可以复现。
2. 单论文和跨论文问题使用不同 Retrieval 目标；跨论文任务通过 Query Decomposition 和配额合并
   显式保证多目标覆盖。
3. Evidence 不足时系统有有界 Reflection，最多修订一次；仍不足则拒答，不允许无限循环。
4. Citation 必须映射到最终 Evidence 的 Chunk 与页码，未知或无法映射的引用会被拒绝。
5. Evaluation 不只看最终文本，而是分别测 Retrieval Coverage、Answer/Citation 契约和语义
   Correctness/Faithfulness。

## 最关键的技术决策

### 为什么 Hybrid RRF 不是所有问题的答案

Corpus v3 上 Hybrid 的总体 Paper Recall@10 为 92.17%，Exact Page Recall@10 为 86.92%，适合
单论文 Discovery。但新增跨论文题的 Complete Papers@10 只有 50%，说明全局 Top-K 容易被一个
子主题占满。因此跨论文 Route 使用 per-task Hybrid Retrieval，再按任务配额 Coverage Merge。

### 为什么不默认使用 Reranker

Reranker 在部分 Retrieval 和 Answer Case 上有收益，但增加约 1.4 秒 P50，且不能稳定修复多目标
覆盖。当前默认低延迟链路保留 Hybrid RRF；Reranker 作为高质量实验模式，而跨论文覆盖由任务分解
解决。

### Reflection 为什么是确定性 Gate

当前 Reflection 的目标是判断“每个 Research Task 是否有足够 Chunk、跨论文来源是否完整”，这类
条件可以确定性计算。只有 Gate 不通过时才调用 Planner 修订 Query，最多一次。这样比开放式
Self-Reflection 更可解释、可测试，也能限制模型调用成本。

### 为什么使用 LangGraph，但不强依赖 LangChain

LangGraph 用于 State、条件边、节点 Trace 和有界循环；Retriever、RRF、Coverage Merge、
AnswerGenerator 与 Citation Validation 都保留为项目自己的接口。这样可以体现 Agent Runtime 的
编排价值，同时避免业务逻辑被框架抽象吞没。

## Evaluation 如何解释

```text
Retrieval Evaluation
  -> 目标论文和标注页是否进入 Top-K

Deterministic Answer/Citation Evaluation
  -> 是否回答或正确拒答、关键点是否覆盖、引用是否映射到目标论文和页码

Semantic LLM Judge
  -> 回答是否语义正确、Claim 是否被 Evidence 支撑、引用是否完整
```

三层不能互相替代。例如 `AE-027` 已完整召回目标论文和页码，但 Answer 模型仍错误拒答，这是
Generation 问题；多条跨论文失败只召回一个目标，则是 Retrieval Coverage 问题。

## 核心结果

| 指标 | Fixed Hybrid | LangGraph Agent |
| --- | ---: | ---: |
| Paper Recall@10 | 86.36% | 95.45% |
| 跨论文 Complete Papers@10 | 40.00% | 80.00% |
| Answerability | 75.00% | 100.00% |
| Correctness | 68.75% | 93.75% |
| Faithfulness | 66.67% | 89.58% |
| Strict Run | 66.67% | 91.67% |
| Workflow P50 | 7.1 s | 18.7 s |

结论应表述为：Agent 在当前 12 条代表性 Case 上显著改善跨论文覆盖和最终答案质量，但增加模型
调用和延迟；数据集仍是人工开发集，不能外推为通用 Benchmark 上的统计显著提升。

## 常见追问

### 强模型会不会掩盖 RAG 优化？

会。因此项目先测 Retrieval Coverage，并把它与 Answer/Judge 并列。缺少目标论文证据时，即使
强模型回答正确，也不能算 Retrieval 成功；Evidence Gate 还会阻止模型依赖参数知识补全。

### 为什么不直接让 Planner 写论文标题？

这会造成 Title Leakage，让 Evaluation 退化成标题匹配。Planner Query 禁止加入用户问题中没有
出现的论文名、方法名和 arXiv ID，并使用 Corpus alias 做泄漏检查。

### 当前最大的工程缺口是什么？

任务存储和 Planner Cache 仍是本地内存/JSONL，只支持单 Worker；没有认证、持久化 Checkpointer、
长期用户 Memory 和生产级队列。这些是部署扩展项，不影响当前作品验证的 RAG 与 Agent 核心。

## 简历项目描述

项目名称：`Paper Research Copilot | Agentic RAG 论文研究助手`

- 基于 LangGraph、FastAPI、React 和 Qdrant 构建可观测 Agentic RAG 系统，实现结构化研究规划、
  Dense/BM25 Hybrid RRF、跨论文 Coverage Retrieval、有界 Reflection 与页码级 Citation。
- 建立 40 篇固定 arXiv revision、2,152 Chunks 的版本化 Agent 论文库，使用 `BAAI/bge-m3`
  Embedding，并对 Corpus、PDF SHA-256、Parse、Chunk Metadata 和幂等导入执行自动校验。
- 构建 Retrieval、Deterministic Answer/Citation、`gpt-5.5` Semantic Judge 三层 Evaluation；
  在 12 条 Agent 对照 Case 上将跨论文完整覆盖从 40% 提升到 80%，Strict Run 从 66.67%
  提升到 91.67%，并量化 7.1 秒到 18.7 秒的延迟取舍。
- 实现 FastAPI 异步任务和 SSE 节点事件，React 工作台实时展示 Plan、Evidence Gate、Report 与
  Citation-to-Evidence 跳转；使用 Pydantic、pytest、Ruff、mypy 和前端 TypeScript Build 保证契约。

简历中不要写“提升 100%”或“达到行业领先”。应保留 Dataset 规模和对照口径，避免把开发集结果
包装成公开 Benchmark 结论。
