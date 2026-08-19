# Structured Parse Benchmark：mineru_structured_v1

- 评估日期：`2026-08-19`
- Dataset：`evals/datasets/structured_parse_benchmark_v1.jsonl`（11 cases）
- Parser：`MinerU 3.4.5` / `pipeline` / `cpu`
- Worker：`isolated subprocess + in-process PDF render compatibility`
- Formula policy：`formula_dense only; table model only when required`
- 边界：只解析隔离的单页 Case，不修改 Corpus、Chunk、Embedding 或 Qdrant。

## 总体指标

| Case pass | Text anchor recall | Block type | BBox provenance | Page provenance | Table QA | OCR recovery | P50 / P95 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 63.64% | 61.54% | 72.73% | 100.00% | 100.00% | 100.00% | 40.00% | 24102.91 / 120148.88 ms |

Table QA 按行标签与一层或多层列头定位交叉单元格；答案出现在错误列不会得分。

## 逐 Case 结果

| Case | Category | Method | Status | Anchors | Blocks | BBox | Table | Latency |
| --- | --- | --- | --- | ---: | ---: | ---: | --- | ---: |
| SPB-001 | normal_text | auto | pass | 100.00% | 12 | 100.00% | - | 24102.91 ms |
| SPB-002 | two_column_text | auto | pass | 100.00% | 10 | 100.00% | - | 21717.72 ms |
| SPB-003 | garbled_text | ocr | error | 0.00% | 0 | 0.00% | - | 120136.88 ms |

`SPB-003` error：StructuredParserError: MinerU timed out after 120s: 2210.03629_react.pdf:p2

| SPB-004 | mixed_text_and_garbled_figure | ocr | error | 0.00% | 0 | 0.00% | - | 120148.88 ms |

`SPB-004` error：StructuredParserError: MinerU timed out after 120s: 2305.10601_tree-of-thoughts.pdf:p5

| SPB-005 | formula_dense | auto | error | 0.00% | 0 | 0.00% | - | 120140.39 ms |

`SPB-005` error：StructuredParserError: MinerU timed out after 120s: 2401.13178_agentboard.pdf:p5

| SPB-006 | native_table_simple | auto | pass | 100.00% | 14 | 100.00% | True | 25192.50 ms |
| SPB-007 | native_table_multicolumn | auto | pass | 100.00% | 11 | 100.00% | True | 23955.67 ms |
| SPB-008 | native_table_complex | auto | pass | 100.00% | 5 | 100.00% | True | 27050.11 ms |
| SPB-009 | short_visual_page | ocr | pass | 100.00% | 2 | 100.00% | - | 18796.89 ms |
| SPB-010 | image_only | ocr | fail | 0.00% | 3 | 100.00% | - | 19806.46 ms |
| SPB-011 | scanned_table | ocr | pass | 100.00% | 4 | 100.00% | True | 22233.00 ms |

## 解释边界

- 当前 Runner 每个 Case 启动一个隔离进程，因此延迟包含 Python、PyTorch 与模型冷启动。
- `OCR recovery` 代表强制 OCR Case 的全部人工 Anchor 被恢复，不代表全文字符完全正确。
- `Table QA` 验证结构关系；它比只判断答案字符串是否出现更严格。
- Formula Case 单独启用公式模型，其余 Case 关闭公式模型以降低无关资源消耗。
