# PDF Parse Baseline：parse_pypdf_v1

- 评估日期：`2026-08-19`
- Dataset：`evals/datasets/parse_benchmark_v1.jsonl`（10 cases）
- Parser：`pypdf==6.10.2`
- Normalization：`pdf_text_v1`
- 运行边界：只读取本地 PDF，不调用 Embedding、LLM 或 Qdrant。

## 总体指标

| Empty | Short | Suspicious chars | Text-layer expectation | Text anchors | Table anchors | P50 / P95 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 10.00% | 10.00% | 40.00% | 100.00% | 100.00% | 100.00% | 70.50 / 163.22 ms |

Table anchors 只验证答案字符串和行列上下文仍在抽取文本中，不代表 Parser 已恢复表格结构。

## 逐页结果

| Case | Category | Page | Status | Chars | Control | Private use | Anchors | Table | Latency |
| --- | --- | ---: | --- | ---: | ---: | ---: | --- | --- | ---: |
| PB-001 | normal_text | 2 | ok | 5810 | 0.0000% | 0.0000% | True | - | 95.55 ms |
| PB-002 | two_column_text | 3 | ok | 4913 | 0.0000% | 0.0000% | True | - | 72.30 ms |
| PB-003 | garbled_text | 2 | suspicious | 5759 | 14.7421% | 0.0000% | True | - | 163.22 ms |
| PB-004 | mixed_text_and_garbled_figure | 5 | suspicious | 4602 | 0.5867% | 0.0000% | True | - | 70.83 ms |
| PB-005 | formula_dense | 5 | suspicious | 5134 | 0.0000% | 0.1753% | True | - | 70.50 ms |
| PB-006 | native_table_simple | 5 | suspicious | 4138 | 0.3383% | 0.0000% | True | True | 49.30 ms |
| PB-007 | native_table_multicolumn | 6 | ok | 3522 | 0.0000% | 0.0000% | True | True | 78.08 ms |
| PB-008 | native_table_complex | 10 | ok | 4043 | 0.0000% | 0.0000% | True | True | 60.01 ms |
| PB-009 | short_visual_page | 16 | short | 83 | 0.0000% | 0.0000% | True | - | 20.05 ms |
| PB-010 | image_only | 30 | empty | 0 | 0.0000% | 0.0000% | True | - | 14.19 ms |

## Baseline 解释

- `empty` 和 `short` 直接暴露纯图片页或只抽取到 Caption 的页面。
- `suspicious` 使用确定性的控制字符、替代字符和 Private Use 字符比例；它不能识别所有语义乱码。
- 表格、公式和双栏即使 Anchor 通过，也可能丢失二维布局或 reading order，需在后续 Parser 对照中验证。
- 该报告冻结 v1 现状，Phase 1 的 Quality Router 不会回写或美化本结果。
