# gpt-5.5 Answer Judge v1 对照

## 实验口径

- Dataset：`answer_generation_v1.jsonl`，20 Cases，SHA-256
  `97bd4526459f3f2f721b0690f576f449ec767817d9766efe3e67051fa110ddf8`。
- Judge：`gpt-5.5`，Prompt `answer_judge_v1`，三维 0-4 Rubric。
- Judge 只读取 Candidate Answer、Reference Answer/Key Points 和 Candidate 实际引用的 Evidence。
- 正确拒答确定性记 `4/4/4`；Generation Failure、错误拒答与 Judge Failure 记 `0/0/0`。
- Overall 使用全部 20 Cases，不能只对成功 LLM 调用取平均。

## 结果

| Answer Strategy | LLM / Deterministic | Correctness | Faithfulness | Citation Completeness | Overall | Judge P50/P95 | Input/Output Tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Hybrid RRF | 15 / 5 | 85.00% | 83.75% | 85.00% | 84.58% | 20553 / 24617 ms | 38327 / 12145 |
| Hybrid + Reranker | 17 / 3 | **95.00%** | **93.75%** | **95.00%** | **94.58%** | 21002 / 27195 ms | 51071 / 14337 |

两组 Judge 调用均一次成功，`response_model` 均为 `gpt-5.5`，Judge Failure 和 Human Review
均为 0。Token 总数是完整 Trace 的累计用量；缓存命中会复用原始 Token/延迟记录，不代表
本次重放产生了相同成本。

## Case 分析

- `AE-017`：Hybrid 错误拒答，确定性 0 分；Reranker 补入 Self-Refine 证据后得到 `4/4/4`。
- `AE-018`：Hybrid 错误拒答，确定性 0 分；Reranker 补入 Voyager 证据后得到 `4/4/4`。
- `AE-016`：两组均为 Generation Failure，保持 `0/0/0`，未被成功样本平均掩盖。
- Hybrid 的 `AE-007` Faithfulness=3：答案对 MemGPT 队列管理器与外部存储的关系表述略
  不精确。
- Reranker 的 `AE-001` Faithfulness=3：答案称模型生成 Observation，而证据表明 Observation
  由环境返回。两题 Correctness 仍为 4，体现“结论正确”和“每个陈述被证据精确支撑”是
  不同指标。

## 结论与限制

Judge 结果支持上一层确定性结论：Reranker 的检索增益确实转化为更完整、可引用的跨论文
回答，而不是只提升词面 Key Point。但当前数据仅 20 Cases，每个 Answer 只生成一次，且使用
单一 Judge。LLM Judge 可能受 reference answer、Rubric 理解和自一致性影响，因此它是确定性
指标的补充，不是替代；进入简历或演示前应人工抽查全部低分 Case，并扩展重复生成实验。
