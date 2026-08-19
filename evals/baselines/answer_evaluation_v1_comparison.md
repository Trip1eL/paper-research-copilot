# Answer Evaluation v1 对照

## 实验设置

- Dataset：`answer_generation_v1.jsonl`，20 Cases，SHA-256
  `97bd4526459f3f2f721b0690f576f449ec767817d9766efe3e67051fa110ddf8`
- 18 条可回答问题：15 条单论文、3 条跨论文。
- 2 条语料外问题：要求系统返回 `INSUFFICIENT_EVIDENCE`。
- Corpus：`agent-seed-v2`，Collection：`agent_seed_v2_bge_m3_chunking_v1`。
- Answer model：`deepseek-v4-flash`，Prompt：`answer_v1`，Top-K：10。
- 两组只改变 Retrieval：Hybrid RRF 与 Hybrid RRF + `BAAI/bge-reranker-v2-m3`。

## 总体结果

| Strategy | Generation Success | Answerability | Key Point Recall | Citation Paper P/R | Strict Page P/R | Sentence Citation | Retrieval P50 | Total P50 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Hybrid RRF | 90.00% | 85.00% | 80.56% | 83.33% / 83.33% | 66.67% / 83.33% | 61.64% | 410 ms | 4319 ms |
| Hybrid RRF + Reranker | **95.00%** | **95.00%** | **93.06%** | **94.44% / 94.44%** | **70.83% / 94.44%** | **74.35%** | 1731 ms | 5679 ms |

两组都正确拒答 `AE-019/020`。Reranker 组的 Retrieval P50 增加约 `1321 ms`，端到端 P50
增加约 `1360 ms`；Generation P50 基本接近（Hybrid `3630 ms`，Reranker `3936 ms`）。

## 关键 Case

`AE-017` 比较 Reflexion 与 Self-Refine。Hybrid Top-10 只有 Reflexion，模型无法获得
Self-Refine 的直接证据；Reranker 将两篇目标论文都放入 Top-10，回答覆盖反馈来源、episodic
memory 和迭代对象，Citation Paper/Strict Page Recall 均为 `100%`。

`AE-018` 比较 Voyager 与 HuggingGPT。Hybrid Top-10 缺少 Voyager，因此模型拒答；Reranker
补入 Voyager 第 3 页与 HuggingGPT 多个目标页，回答的 Key Point、Citation Paper 和 Strict
Page Recall 均为 `100%`。

`AE-016` 比较 ReAct 与 Toolformer。两组 Top-10 都没有 ReAct 的直接证据，且
`deepseek-v4-flash` 连续两次返回空 content，因此两组都失败。这与 Retrieval v2 的诊断一致：
Fast Reranker 没有把该问题的 ReAct 提升到 Top-10。下一步不能靠 Prompt 弥补，需要改善
多目标 coverage 或给每个比较子意图分配证据配额。

## 当前结论

Reranker 的 Retrieval 增益在高 Baseline 下看似有限，但已经转化为明显的 Answer 层收益：
它让两个本来缺失一半直接证据的跨论文问题变得可回答。当前可以把 Hybrid + Reranker 视为
高质量模式候选，但仍不直接替换低延迟默认模式，原因包括：

- Dataset 只有 20 条，当前结果是单次生成实验，尚未报告置信区间或多次运行方差。
- Key Point 是词面别名覆盖，不等于语义正确性。
- Strict Page 使用非穷举页码，是引用正确性的严格下界。
- Sentence Citation 只检查 marker，不验证 Claim-Evidence entailment。
- DeepSeek 在长跨论文问题上仍出现连续空 content，说明 Answer Provider 稳定性需要单独评估。

下一步加入独立 LLM Judge，评估 Correctness、Claim-Evidence Faithfulness 和 Citation
Completeness；Judge 必须读取 reference answer、实际 answer 和 cited evidence，并与这些
确定性指标并列报告，不能覆盖原始失败和延迟数据。
