# Fast Parser Shadow Baseline：parse_router_shadow_v1

- Dataset：`evals/datasets/parse_benchmark_v1.jsonl`（10 cases）
- Primary：`pypdf==6.10.2`
- Secondary：`pymupdf==1.28.2`
- Mode：Shadow，只生成对照结果，不进入 Chunking、Embedding 或 Qdrant。

## 总体指标

| Issue detection | Recoverable issue recovery | Clean primary retention | Secondary selected | Accepted | Structured fallback | Text anchors | Table anchors |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 100.00% | N/A | 100.00% | 20.00% | 60.00% | 40.00% | 100.00% | 100.00% |

- Per-page extraction P50/P95：86.29 / 173.62 ms

## 逐页路由

| Case | Category | pypdf | PyMuPDF | Selected | Route | Text | Table |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PB-001 | normal_text | accepted/1.00 | accepted/1.00 | pypdf/accepted | primary_accepted | True | - |
| PB-002 | two_column_text | accepted/1.00 | accepted/1.00 | pypdf/accepted | primary_accepted | True | - |
| PB-003 | garbled_text | quarantined/0.00 | quarantined/0.35 | pymupdf/quarantined | structured_fallback_required | True | - |
| PB-004 | mixed_text_and_garbled_figure | quarantined/0.00 | quarantined/0.35 | pymupdf/quarantined | structured_fallback_required | True | - |
| PB-005 | formula_dense | accepted/0.80 | accepted/0.80 | pypdf/accepted | primary_accepted | True | - |
| PB-006 | native_table_simple | accepted/1.00 | accepted/1.00 | pypdf/accepted | primary_accepted | True | True |
| PB-007 | native_table_multicolumn | accepted/1.00 | accepted/1.00 | pypdf/accepted | primary_accepted | True | True |
| PB-008 | native_table_complex | accepted/1.00 | accepted/1.00 | pypdf/accepted | primary_accepted | True | True |
| PB-009 | short_visual_page | quarantined/0.40 | quarantined/0.40 | pypdf/quarantined | structured_fallback_required | True | - |
| PB-010 | image_only | quarantined/0.00 | quarantined/0.00 | pypdf/quarantined | structured_fallback_required | True | - |

## 解释边界

- Secondary selection 表示文本质量信号改善，不表示二维表格结构已经恢复。
- Structured fallback 页面不会被允许进入索引；MinerU 尚未接入本报告。
- Shadow 结果只用于校准 Router，生产 `PdfParser` 和 Corpus v3 Collection 保持不变。
