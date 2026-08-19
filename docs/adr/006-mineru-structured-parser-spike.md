# ADR 006: MinerU 作为隔离实验能力，不进入当前生产 Fallback

- Status: Accepted for v2.0 Phase 2
- Date: 2026-08-19

## Context

Fast Parser Router 可以检出并隔离字体映射乱码、无文本层和复杂页面，但 `pypdf` 与 PyMuPDF 无法
恢复这些页面。MinerU 提供 OCR、Layout、Table 和 Formula 结构，可能成为 Structured Fallback；
同时它引入大模型文件、PyTorch、平台兼容和长延迟风险，必须先用固定 Dataset 验证。

## Decision

- 保留 MinerU 3.4.5 Adapter、领域 block 模型、Benchmark Runner 和独立 Conda 环境说明。
- MinerU 不接入当前生产 `PdfParser`、Chunker、Dynamic Ingestion 或默认 Demo Runtime。
- 原生表格和扫描表格能力判定为 Conditional Go，可继续作为离线/显式实验工具。
- Windows CPU Demo 环境判定为 No-Go：连续运行稳定性、Formula page file 和 image-only 恢复未达标。
- Fast Path 仍负责低延迟文本解析；异常页面继续 quarantine，不用低质量 MinerU 结果自动替换。
- 下一步验证 RapidOCR 作为纯 OCR 轻量 fallback；若未来提供 Linux GPU/远程 Parser 服务，再重新评估
  MinerU，并沿用同一 11 Case Dataset 和 Table QA Gate。

## Evidence

- 11 Case 连续基线：Case pass `63.64%`，Table QA `100%`，OCR recovery `40%`，P95 `120.15 s`。
- 三类原生表格与 synthetic 扫描表格的 6 条行列关系全部正确。
- ReAct 乱码页独立运行可在 `26.91 s` 恢复，但连续运行超时，说明部署不稳定。
- Formula 独立运行触发 Windows `os error 1455`。
- 无文本截图页只恢复局部内容，目标 Anchor 为 `0/3`。

完整实验说明见 `docs/mineru-spike.md`，机器可读结果见
`evals/baselines/mineru_structured_v1.json`。

## Consequences

生产链路不会因为 Phase 2 增加 PyTorch/MinerU 依赖、24 秒级冷启动或不稳定进程。项目保留了可审计
的结构化 Parser 接口和严格 Table QA，为后续替换 Runtime 或 Parser 提供相同验收标准。代价是当前
扫描页仍不会自动进入索引；它们会被明确隔离，直到轻量 OCR 或新的 MinerU 部署通过 Gate。
