# 基础 RAG 设计

## 目标

第一版不包含 Agent，只验证论文研究系统最基础且可复用的垂直链路：PDF 解析、Chunk、
metadata、Embedding、Vector Store、Retrieval、Prompt 和 Citation。

## 数据流

```text
PdfParser
  -> ParsedDocument
  -> PageAwareChunker
  -> PaperChunk[]
  -> EmbeddingProvider
  -> QdrantVectorStore
  -> RetrieverFactory(evidence=Dense, discovery=Hybrid RRF)
  -> RetrievedChunk[]
  -> AnswerGenerator
  -> Answer + Citation[]
```

## 核心约束

- `domain` 中的 Pydantic 模型是模块间唯一数据契约。
- Chunk 不跨越 PDF 页面，优先保证 Citation 定位准确。
- `document_id` 使用 PDF 文件 SHA-256，Chunk ID 根据文档、页码和字符区间稳定生成。
- Qdrant payload 保存完整 Chunk metadata，检索后不依赖额外映射表恢复来源。
- LLM 不直接访问 Vector Store，只接收编号后的 Evidence Context。
- Answer 中只允许引用本次检索返回的 Citation ID。

## 基线意义

Dense Retrieval 是已知论文 Evidence 定位基线；Hybrid RRF 是自然问题 Discovery 的当前
生产策略。两者由显式 `retrieval_mode` 选择，暂不自动路由。实验 Reranker 若进入生产时仍需
分别比较检索质量，避免在没有基线的情况下堆叠组件。

## 可观察性入口

```text
inspect-pdf    -> 观察 ParsedDocument 和每页文本统计
inspect-chunks -> 观察 PaperChunk、页码、字符区间和 Overlap
search         -> 观察指定 Retrieval Mode 的 Top-K RetrievedChunk
show-prompt    -> 观察 AnswerGenerator 接收的最终 System/User Prompt
```

前两个命令完全离线；后两个命令需要调用 Embedding Provider，但不会调用 LLM。通过这些
入口可以区分 Parse、Chunk、Retrieval、Context Construction 和 Generation 各层问题。
