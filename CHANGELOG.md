# 更新日志

本文件记录 Paper Research Copilot 的重要版本变化。版本号遵循 Semantic Versioning。

## 2.0.0 - 2026-08-20

### 新增

- 引入质量感知 PDF Parser Router，可在 PyMuPDF、PyPDF 与可选 MinerU Shadow Parser 之间比较候选
  结果，并保留页级质量、来源和回退信息。
- 引入 SQLite 业务存储、Alembic Migration、Repository Protocol 与 LangGraph SQLite
  Checkpointer，持久化 Task、Event、Result、动态资产和 Clarification 父子关系。
- 引入受控 Open-world Acquisition：arXiv Metadata Search、候选排序与去重、PDF 下载、质量检查、
  幂等 Dynamic Ingestion 和 Curated/Dynamic Federated Retrieval。
- 引入 Clarification Protocol。歧义问题在 Retrieval 前停止，用户补充信息后创建可追踪、幂等的
  Child Task；这不是通用多轮对话。
- 引入 Bounded Claim-level Verification。生产回答最多审核 8 个关键 Claim，可执行一次基于实际
  Evidence 的受控修订，并显式暴露错误与人工复核状态。
- 新增 Open-world、Clarification 与 Claim Verification 的独立 Evaluation Dataset、Runner、缓存和
  基线报告。

### 改进

- Corpus 扩展至 v3：40 篇固定版本 Agent 论文、2,152 个 Chunk，并使用 `BAAI/bge-m3` 写入独立
  Qdrant Collection。
- Agent Runtime 覆盖 Planning、Question Screening、Hybrid Retrieval、Evidence Assessment、受控
  Acquisition、Report Writing、Claim Verification 与 Citation Validation。
- React 工作台支持 SSE Timeline、Evidence、Citation、Dynamic Acquisition、Clarification 和
  Claim Verification 的结构化展示。

### 已知边界

- Dynamic Acquisition 默认关闭，需要显式配置后启用。
- MinerU 当前仅作为可选 Shadow Parser，不是默认生产 Parser。
- Claim Verification 只执行一次修订，不进行递归 Reflection；额外模型调用会带来明显延迟。
- 当前不提供通用多轮 Chat Memory。
