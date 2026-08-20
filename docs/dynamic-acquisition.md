# 动态论文扩库

## 当前能力

Phase 4 提供独立、受控、可持久化的动态扩库链路；Phase 5 已将其作为 opt-in 能力接入 Agent：

```text
Query
  -> arXiv Atom Metadata Search
  -> Deterministic Rank + identity/DOI Dedup
  -> Bounded PDF Downloader
  -> SHA-256 Dedup + Paper Registry
  -> Fast Parser Router + Quality Gate
  -> Page-aware Chunk
  -> BAAI/bge-m3 Embedding
  -> Dynamic Qdrant Collection
  -> active Paper Asset
```

Agent 默认不联网。启用后，它先完成本地 Query Revision；仍被 Evidence Gate 判定不足时，选择最弱
Research Task 的 Query，最多执行一次 Acquisition，再使用 Federated Retriever 重新检索。第二次
Assessment 无论充分与否都会停止，不存在开放式下载循环。

## 命令

只搜索 Metadata，不下载 PDF：

```powershell
paper-rag search-papers "agent memory retrieval" --limit 5
```

执行最多两篇论文的受控扩库：

```powershell
paper-rag acquire-papers "agent memory retrieval" --task-id demo-001 --round 1
```

允许 Agent 最多执行一次动态扩库：

```powershell
paper-rag agent "MemReranker 如何改进 Agent Memory Retrieval？" --allow-acquisition --show-trace
```

FastAPI 通过 `AGENT_DYNAMIC_ACQUISITION_ENABLED=true` 启用同一能力；默认值为 `false`。

相同 `task-id + round + normalized query` 生成稳定 Acquisition ID。已完成的 Run 再次执行只返回持久
结果，不重复 Search、Download、Embedding 或 Qdrant 写入。需要明确重试时增加 `--round`。

## 安全边界

- 只接受 `https://arxiv.org`、`www.arxiv.org`、`export.arxiv.org`。
- 每次 redirect 都重新验证 host、端口、URL identity，最多 3 次。
- PDF URL 必须与 Candidate 的 arXiv ID 和 revision 一致。
- 必须返回 `application/pdf` 且文件头为 `%PDF-`。
- 先检查 Content-Length，再流式限制实际字节数，默认上限 50 MiB。
- 下载先写 `data/dynamic/papers/.tmp/*.part`，完整验证后才原子移动。
- 远端文件名不会进入本地路径；路径由规范化 arXiv ID、revision 和 SHA-256 生成。
- 任意 quarantined 页面都会使资产进入 quarantine，不调用 Embedding。

## 持久状态

```text
discovered -> downloaded -> parsed -> indexed -> active
     |             |            |
download_failed  quarantined  indexing_failed

discovered -> duplicate
```

`paper_assets` 保存 Candidate JSON、下载 Hash/路径、Parse 摘要、Chunk 数、Embedding/Chunking 版本和
Collection。`acquisition_runs` 保存预算、候选/选择/下载/索引数量、状态和错误。失败不是日志字符串，
而是可以查询和重试的业务状态。

## 幂等与恢复

1. arXiv identity + revision 防止同一版本重复注册。
2. DOI 防止同一论文以不同 Metadata 重复注册。
3. SHA-256 防止不同 identity 指向同一 PDF 内容。
4. Chunk ID 由 PDF Hash、Chunking 参数、页码和字符区间稳定生成。
5. Qdrant 使用 Paper metadata replacement，Point 数在提交后校验。

如果进程在 Qdrant 成功写入后、Registry 标记 indexed 前退出，重试会按预期 Chunk ID 查询已有向量；
全部存在时跳过 Embedding，只补交 Registry 状态。这将不可避免的跨 SQLite/Qdrant 非原子窗口转换为
可检测、可收敛的恢复流程。

## 存储隔离

```text
Curated: agent_seed_v3_bge_m3_chunking_v1
Dynamic: paper_dynamic_bge_m3_chunking_v1
```

本地 embedded Qdrant 的 Dynamic 数据位于 `data/qdrant_dynamic`，避免与当前 Curated Client 的
文件锁冲突。使用远程 Qdrant 时，两者可以位于同一服务，但 Collection 仍然隔离。动态论文不会修改
Corpus v3 Manifest 或现有 Evaluation Baseline。

## Federated Retrieval 与 BM25 generation

Curated 与 Dynamic Collection 各自构建 Dense + BM25 Hybrid RRF，再通过第二层确定性 RRF 合并；相同
Chunk ID 只保留一个结果。两套 Dense Retriever 共享进程内查询向量缓存，因此同一个 Research Task
Query 不会重复调用两次 Embedding API。

Dynamic `RetrieverFactory` 使用 Dynamic Qdrant point count 作为 generation。Point 数变化时，下一次
检索自动重新读取 Dynamic Chunk 并重建内存 BM25；未变化时复用已有 snapshot。Acquisition 与
Retriever 共用同一个 Dynamic Qdrant Client，避免 embedded 模式重复打开目录导致文件锁冲突。
