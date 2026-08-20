# Open-world Evaluation：open_world_v1_smoke

- Dataset：`evals/datasets/open_world_v1.jsonl`（4 Cases）
- Curated Collection：`agent_seed_v3_bge_m3_chunking_v1`
- Dynamic State：每个 Case 使用独立且初始为空的 Qdrant、SQLite 与 PDF 目录
- Planner / Answer：`gpt-5.5` / `deepseek-v4-flash`

## 总体指标

| Strict Pass | Trigger Precision | Trigger Recall | In-corpus False Trigger | Recoverable Success | Unrecoverable Abstention | Unrecoverable No-index | Ambiguous Abstention |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 25.00% | N/A | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% |

| Dynamic Evidence Hit | Target Citation Hit | Parser Provenance | Bounded Acquisition | Answer Behavior | In-corpus Dynamic Evidence | P50 / P95 | Downloaded / Indexed | Point Delta |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.00% | 0.00% | 0.00% | 100.00% | 25.00% | 0.00% | 42473 / 47805 ms | 0 / 0 | 0 |

## 分类结果

| Category | Cases | Strict Pass | Acquisition | Answer Behavior | P50 / P95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| in_corpus | 1 | 100.00% | 0.00% | 100.00% | 20880 / 20880 ms |
| recoverable | 1 | 0.00% | 0.00% | 0.00% | 37627 / 37627 ms |
| unrecoverable | 1 | 0.00% | 0.00% | 0.00% | 47890 / 47890 ms |
| ambiguous | 1 | 0.00% | 0.00% | 0.00% | 47320 / 47320 ms |

## 逐题诊断

| Case | Category | Acquire | Answer | Dynamic Evidence | Target Citation | Points | Strict |
| --- | --- | --- | --- | ---: | --- | ---: | ---: |
| OW-IC-001 | in_corpus | 0:- | answered | 0/10 | N/A | 0->0 | True |
| OW-RC-001 | recoverable | 0:- | error | 0/0 | N/A | 0->0 | False |
| OW-UR-001 | unrecoverable | 0:- | error | 0/0 | N/A | 0->0 | False |
| OW-AM-001 | ambiguous | 0:- | error | 0/0 | N/A | 0->0 | False |

## 解释边界

- 指标为确定性行为评估，不替代 Answer Semantic LLM Judge。
- Trigger Precision 将 Recoverable 视为唯一必须扩库类别；Unrecoverable 的一次有界搜索仍计入触发分母。
- 运行缓存包含完整 AgentResult，位于 Git ignored 的 data/evaluation 目录。
- Run Cache：D:/AI开发/Paper Research Copilot/data/evaluation/open_world/open_world_v1_smoke/runs.jsonl
