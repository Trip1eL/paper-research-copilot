# Answer 低分与稳定性审计 v1

## 审计口径

本报告是工程侧 Evidence Audit，不冒充独立 Human Gold。审计对象为原始 Answer、冻结的
Top-10 Evidence、实际 Citation、Judge rationale 和 3 次重复生成结果。需要主观裁决的项目
明确标记为后续人工复核。

## 结论

| Case | Evidence 组成与重复结果 | 审计结论 | 后续动作 |
| --- | --- | --- | --- |
| AE-001 | 两组都有 ReAct 直接证据；每组 3 次均回答，但最低 C/F 为 3/4 | 主要是措辞波动。题面“生成 Observation”容易诱导模型忽略 Observation 来自环境 | 在 Dataset v2 改写题面；保留当前 v1 SHA，不回改历史 Baseline |
| AE-007 | 两组 3 次均为 4/4/4，引用集合基本稳定 | 原始单次 Faithfulness=3 未复现，不是稳定 Retrieval 缺陷 | 不修改 Retriever，仅保留为回归 Case |
| AE-016 | 两组 Top-10 都没有 ReAct 论文；Hybrid 为一次严格通过、一次低分、一次空 content，Reranker 为一次严格通过、一次无 Citation、一次空 content | 检索只完整覆盖 Toolformer，模型偶尔依赖常识补出 ReAct，不能视为可靠回答 | 最高优先级：sub-query decomposition + coverage-aware merge |
| AE-017 | Hybrid 只有 Reflexion，无 Self-Refine，3 次全部错误/拒答；Reranker 同时覆盖两篇目标论文，2 次 4/4/4、1 次空 content | Reranker 修复 Evidence 覆盖；剩余失败属于 Answer Provider 波动 | 保留 Reranker 回归；记录 empty content rate |
| AE-018 | Hybrid 有 HuggingGPT、无 Voyager，3 次全部拒答；Reranker 同时覆盖两篇目标论文，3 次都通过，最低 F/CC 为 3/4 | Reranker 修复覆盖；一次回答疑似在长度上限附近截断，造成完整性下降 | 增加 finish_reason、truncation detection 和输出长度约束 |
| AE-019/020 | 两组共 12 次均返回结构化拒答 | Corpus 外拒答稳定，当前契约有效 | 保留为每次生成改动的 Guard Cases |

## Judge 审计

- `AE-001` 的降分在语义上有依据，但题面本身存在歧义，不能只归因于模型；Dataset v2 应把
  问题改成“交错生成 Thought/Action 并接收 Observation”。
- `AE-016` 的 Correctness 偶尔较高，是因为答案语义接近 reference answer；Faithfulness 和
  Completeness 降到 2-3，反映引用只部分支持 ReAct 一侧。该 Case 必须结合目标论文覆盖指标
  解读，不能只看 Judge Correctness。
- `AE-007` 原始降分未在 6 次新生成中复现，说明单次 Judge 低分可以来自 Answer wording，而
  不是固定系统缺陷。
- 所有新 LLM Judge 调用均一次通过 Schema；当前不确定性主要来自 Answer Generation，不是
  Judge JSON 解析失败。

## 决策

本轮结果支持将 Hybrid + Reranker 保留为高质量模式候选，但不能宣称它已稳定解决所有跨论文
问题。进入 Agent Runtime 前先完成两项收尾：一是记录 `finish_reason` 并拒绝或重试截断回答；
二是针对 `AE-016` 实现按子意图覆盖目标的 Retrieval 实验。独立人工评分仍需由项目作者对
所有低分输出逐条确认，本报告只提供可审查证据和初步工程判断。
