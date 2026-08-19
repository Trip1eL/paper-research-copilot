# Coverage-aware Retrieval 消融实验 v1

## 实验设置

- Cases：`AE-016`、`AE-017`、`AE-018`，均为匿名描述的跨论文比较题。
- 每种策略冻结各自 Top-10 Evidence，Answer 重复生成 3 次。
- Answer：`deepseek-v4-flash`；Semantic Judge：`gpt-5.5`。
- Query Decomposition 禁止补充原问题未出现的论文名，并通过 Corpus alias 审计。

## Retrieval Coverage

| Strategy | Paper Recall@10 | Exact Page Recall@10 | Complete Papers@10 |
| --- | ---: | ---: | ---: |
| Hybrid RRF | 50.00% | 50.00% | 0.00% |
| Hybrid + Global Reranker | 83.33% | 83.33% | 66.67% |
| Decomposition + Hybrid + Coverage | 100.00% | 100.00% | 100.00% |
| Decomposition + Hybrid + Per-subquery Reranker + Coverage | 100.00% | 100.00% | 100.00% |

## Answer Stability + LLM Judge

| Strategy | Gen Success | Answerability | Correctness | Faithfulness | Citation Completeness | Strict Runs | Stable Cases | Truncation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Hybrid RRF | 88.89% | 22.22% | 16.67% | 11.11% | 11.11% | 0.00% | 0.00% | 22.22% |
| Hybrid + Global Reranker | 100.00% | 100.00% | 97.22% | 83.33% | 94.44% | 100.00% | 100.00% | 11.11% |
| Decomposition + Hybrid + Coverage | 100.00% | 100.00% | 100.00% | 91.67% | 94.44% | 100.00% | 100.00% | 11.11% |
| Decomposition + Hybrid + Per-subquery Reranker + Coverage | 100.00% | 100.00% | 100.00% | 88.89% | 91.67% | 100.00% | 100.00% | 22.22% |

## 逐题 Coverage

| Strategy | Case | Target Papers | Paper Recall | Exact Page Recall | Quota |
| --- | --- | --- | ---: | ---: | --- |
| Hybrid RRF | AE-016 | arxiv:2210.03629=N, arxiv:2302.04761=Y | 50.00% | 50.00% | `-` |
| Hybrid RRF | AE-017 | arxiv:2303.11366=Y, arxiv:2303.17651=N | 50.00% | 50.00% | `-` |
| Hybrid RRF | AE-018 | arxiv:2305.16291=N, arxiv:2303.17580=Y | 50.00% | 50.00% | `-` |
| Hybrid + Global Reranker | AE-016 | arxiv:2210.03629=N, arxiv:2302.04761=Y | 50.00% | 50.00% | `-` |
| Hybrid + Global Reranker | AE-017 | arxiv:2303.11366=Y, arxiv:2303.17651=Y | 100.00% | 100.00% | `-` |
| Hybrid + Global Reranker | AE-018 | arxiv:2305.16291=Y, arxiv:2303.17580=Y | 100.00% | 100.00% | `-` |
| Decomposition + Hybrid + Coverage | AE-016 | arxiv:2210.03629=Y, arxiv:2302.04761=Y | 100.00% | 100.00% | `(5, 5)` |
| Decomposition + Hybrid + Coverage | AE-017 | arxiv:2303.11366=Y, arxiv:2303.17651=Y | 100.00% | 100.00% | `(5, 5)` |
| Decomposition + Hybrid + Coverage | AE-018 | arxiv:2305.16291=Y, arxiv:2303.17580=Y | 100.00% | 100.00% | `(5, 5)` |
| Decomposition + Hybrid + Per-subquery Reranker + Coverage | AE-016 | arxiv:2210.03629=Y, arxiv:2302.04761=Y | 100.00% | 100.00% | `(5, 5)` |
| Decomposition + Hybrid + Per-subquery Reranker + Coverage | AE-017 | arxiv:2303.11366=Y, arxiv:2303.17651=Y | 100.00% | 100.00% | `(5, 5)` |
| Decomposition + Hybrid + Per-subquery Reranker + Coverage | AE-018 | arxiv:2305.16291=Y, arxiv:2303.17580=Y | 100.00% | 100.00% | `(5, 5)` |

## Coverage 额外延迟

| Strategy | Case | Decomposition Generate | Cache Lookup | Hybrid Total | Reranker Total | Retrieval Total |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Decomposition + Hybrid + Coverage | AE-016 | 3114 ms | 0 ms | 481 ms | 0 ms | 481 ms |
| Decomposition + Hybrid + Coverage | AE-017 | 6787 ms | 0 ms | 458 ms | 0 ms | 458 ms |
| Decomposition + Hybrid + Coverage | AE-018 | 4793 ms | 0 ms | 455 ms | 0 ms | 455 ms |
| Decomposition + Hybrid + Per-subquery Reranker + Coverage | AE-016 | 3114 ms | 0 ms | 483 ms | 1551 ms | 2034 ms |
| Decomposition + Hybrid + Per-subquery Reranker + Coverage | AE-017 | 6787 ms | 0 ms | 565 ms | 1425 ms | 1991 ms |
| Decomposition + Hybrid + Per-subquery Reranker + Coverage | AE-018 | 4793 ms | 0 ms | 461 ms | 1535 ms | 1997 ms |

## Query Decomposition 审计

- Alias leakage：`无`
- `交错生成 Thought、Action、Observation 的提示方法，与通过采样和 loss 过滤来学习 API calls 的方法，在工具使用机制上有何差异？` -> `['交错生成 Thought、Action、Observation 的提示方法，在工具使用上的机制是什么？', '通过采样和 loss 过滤来学习 API calls 的方法，在工具使用上的机制是什么？']`
- `把环境评价转为 episodic verbal memory 的智能体反思方法，与让同一个模型直接批评并改写当前输出的方法，在反馈来源、记忆和迭代对象上有何区别？` -> `['把环境评价转为 episodic verbal memory 的智能体反思方法 反馈来源 记忆 迭代对象', '让同一个模型直接批评并改写当前输出的方法 反馈来源 记忆 迭代对象']`
- `依靠自动课程和可复用技能库持续探索开放世界的智能体，与把语言模型作为控制器选择多个现成 AI 模型完成多模态请求的系统，如何分别积累能力和编排任务？` -> `['依靠自动课程和可复用技能库持续探索开放世界的智能体，如何积累能力和编排任务？', '把语言模型作为控制器选择多个现成 AI 模型完成多模态请求的系统，如何积累能力和编排任务？']`

## 口径

- Complete Papers@10 要求一个比较题的两篇目标论文都出现在 Top-10。
- Exact Page Recall 使用人工标注的非穷举页码，因此是严格下界。
- Strict Run 要求生成和 Answerability 正确，且 Judge 三维均不低于 3/4。
- Baseline Answer/Judge 复用 Generation Observability v2；Coverage 两组为本实验新增调用。
