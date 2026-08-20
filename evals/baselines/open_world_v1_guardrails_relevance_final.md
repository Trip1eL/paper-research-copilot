# Open-world Evaluation：open_world_v1_guardrails_relevance_final

- Dataset：`evals/datasets/open_world_v1.jsonl`（16 Cases）
- Curated Collection：`agent_seed_v3_bge_m3_chunking_v1`
- Dynamic State：每个 Case 使用独立且初始为空的 Qdrant、SQLite 与 PDF 目录
- Planner / Answer：`gpt-5.5` / `deepseek-v4-flash`

## 总体指标

| Strict Pass | Trigger Precision | Trigger Recall | In-corpus False Trigger | Recoverable Success | Unrecoverable Abstention | Unrecoverable No-index | Ambiguous Abstention |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 100.00% | 62.50% | 100.00% | 0.00% | 100.00% | 100.00% | 100.00% | 100.00% |

| Dynamic Evidence Hit | Target Citation Hit | Parser Provenance | Bounded Acquisition | Answer Behavior | In-corpus Dynamic Evidence | P50 / P95 | Downloaded / Indexed | Point Delta |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 100.00% | 100.00% | 100.00% | 100.00% | 100.00% | 0.00% | 10061 / 50629 ms | 5 / 5 | 116 |

## 分类结果

| Category | Cases | Strict Pass | Acquisition | Answer Behavior | P50 / P95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| in_corpus | 5 | 100.00% | 0.00% | 100.00% | 10106 / 18912 ms |
| recoverable | 5 | 100.00% | 100.00% | 100.00% | 20067 / 106902 ms |
| unrecoverable | 3 | 100.00% | 100.00% | 100.00% | 7068 / 7383 ms |
| ambiguous | 3 | 100.00% | 0.00% | 100.00% | 830 / 964 ms |

## 逐题诊断

| Case | Category | Acquire | Answer | Dynamic Evidence | Target Citation | Points | Strict |
| --- | --- | --- | --- | ---: | --- | ---: | ---: |
| OW-IC-001 | in_corpus | 0:- | answered | 0/10 | N/A | 0->0 | True |
| OW-IC-002 | in_corpus | 0:- | answered | 0/10 | N/A | 0->0 | True |
| OW-IC-003 | in_corpus | 0:- | answered | 0/10 | N/A | 0->0 | True |
| OW-IC-004 | in_corpus | 0:- | answered | 0/10 | N/A | 0->0 | True |
| OW-IC-005 | in_corpus | 0:- | answered | 0/10 | N/A | 0->0 | True |
| OW-RC-001 | recoverable | 1:succeeded | answered | 5/10 | yes | 0->24 | True |
| OW-RC-002 | recoverable | 1:succeeded | answered | 5/10 | yes | 0->33 | True |
| OW-RC-003 | recoverable | 1:succeeded | answered | 5/10 | yes | 0->11 | True |
| OW-RC-004 | recoverable | 1:succeeded | answered | 5/10 | yes | 0->20 | True |
| OW-RC-005 | recoverable | 1:succeeded | answered | 5/10 | yes | 0->28 | True |
| OW-UR-001 | unrecoverable | 1:failed | insufficient_evidence | 0/10 | N/A | 0->0 | True |
| OW-UR-002 | unrecoverable | 1:failed | insufficient_evidence | 0/10 | N/A | 0->0 | True |
| OW-UR-003 | unrecoverable | 1:failed | insufficient_evidence | 0/10 | N/A | 0->0 | True |
| OW-AM-001 | ambiguous | 0:- | insufficient_evidence | 0/0 | N/A | 0->0 | True |
| OW-AM-002 | ambiguous | 0:- | insufficient_evidence | 0/0 | N/A | 0->0 | True |
| OW-AM-003 | ambiguous | 0:- | insufficient_evidence | 0/0 | N/A | 0->0 | True |

## 解释边界

- 指标为确定性行为评估，不替代 Answer Semantic LLM Judge。
- Trigger Precision 将 Recoverable 视为唯一必须扩库类别；Unrecoverable 的一次有界搜索仍计入触发分母。
- 运行缓存包含完整 AgentResult，位于 Git ignored 的 data/evaluation 目录。
- Run Cache：D:/AI开发/Paper Research Copilot/data/evaluation/open_world/open_world_v1_guardrails_relevance_final/runs.jsonl
