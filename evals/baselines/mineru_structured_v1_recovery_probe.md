# Structured Parse Benchmark：mineru_structured_v1_recovery_probe

- 评估日期：`2026-08-19`
- Dataset：`evals/datasets/structured_parse_benchmark_v1.jsonl`（1 cases）
- Parser：`MinerU 3.4.5` / `pipeline` / `cpu`
- Worker：`isolated subprocess + in-process PDF render compatibility`
- Formula policy：`formula_dense only; table model only when required`
- 边界：只解析隔离的单页 Case，不修改 Corpus、Chunk、Embedding 或 Qdrant。

## 总体指标

| Case pass | Text anchor recall | Block type | BBox provenance | Page provenance | Table QA | OCR recovery | P50 / P95 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 100.00% | 100.00% | 100.00% | 100.00% | 100.00% | N/A | 100.00% | 26906.50 / 26906.50 ms |

Table QA 按行标签与一层或多层列头定位交叉单元格；答案出现在错误列不会得分。

## 逐 Case 结果

| Case | Category | Method | Status | Anchors | Blocks | BBox | Table | Latency |
| --- | --- | --- | --- | ---: | ---: | ---: | --- | ---: |
| SPB-003 | garbled_text | ocr | pass | 100.00% | 5 | 100.00% | - | 26906.50 ms |

## 解释边界

- 当前 Runner 每个 Case 启动一个隔离进程，因此延迟包含 Python、PyTorch 与模型冷启动。
- `OCR recovery` 代表强制 OCR Case 的全部人工 Anchor 被恢复，不代表全文字符完全正确。
- `Table QA` 验证结构关系；它比只判断答案字符串是否出现更严格。
- Formula Case 单独启用公式模型，其余 Case 关闭公式模型以降低无关资源消耗。
