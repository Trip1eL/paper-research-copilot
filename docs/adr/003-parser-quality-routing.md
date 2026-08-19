# ADR 003: Page-level Parser Quality Routing

- Status: Accepted for v2.0
- Date: 2026-08-19

## Context

v1 使用 `pypdf.page.extract_text()` 处理全部页面。该路径无法可靠处理错误字体映射、扫描页、复杂
双栏阅读顺序和部分公式页。现有 Parse QA 可以发现空页、控制字符和部分 Unicode 异常，但不能选择
更好的提取结果，也不能阻止所有低质量页面进入 Embedding。

动态扩库会放大这一风险：自动下载越多，未经 Gate 的乱码越容易污染 Retriever。

## Decision

- 保留 `pypdf` 作为 Primary Extractor。
- 增加 `PyMuPDF` 作为 Secondary Extractor，只对低质量页面触发。
- 使用确定性 `PageQualityScorer` 对候选文本评分并逐页择优。
- 两个文本 Parser 都低于阈值时，通过可插拔 `OcrEngine` 处理；首选实现验证 `RapidOCR`。
- `accepted/warning` 页面可以进入 Chunking，`quarantined` 页面禁止 Embedding。
- 每页保存 Parser、版本、quality score、OCR 标记和 warning。
- Corpus v3 只做 shadow parse，不覆盖原文本或 Collection；新输出使用新的 Parse/Corpus 版本。

## Rejected alternatives

- **全量 OCR**：延迟和依赖成本高，并会破坏本来正确的文本层。
- **只替换成 PyMuPDF**：不同 Parser 在不同 PDF 上各有失败模式，无法形成质量 Gate。
- **由 LLM 判断乱码**：成本高、不可重复，并且不能安全处理大规模逐页输入。
- **直接引入 Docling/Marker/GROBID**：第一阶段依赖和行为面过大，应在双 Parser Benchmark 后再评估。

## Consequences

解析延迟会增加，但只在可疑页面支付 Secondary/OCR 成本。领域模型和 Chunk metadata 会扩展；原有
Chunker 保持对 `page.text` 的依赖，不承担 Parser 选择逻辑。公式精确还原仍不是 v2.0 承诺。

