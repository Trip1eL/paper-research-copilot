# MinerU Structured Parser Technical Spike

## 1. 结论

本次 Spike 对 `MinerU 3.4.5 / pipeline / CPU` 的结论分为两层：

- **解析能力 Conditional Go**：原生表格与扫描表格的 6 条 Table QA 全部通过，HTML 行列结构、
  page number 和 bbox provenance 可用；ReAct 字体映射乱码页在独立 Probe 中恢复成功。
- **当前 Demo 机器生产接入 No-Go**：4 GB VRAM 的 Windows 机器上，CPU pipeline 存在进程初始化、
  page file 和连续运行稳定性问题；无文本截图页也只恢复了局部内容。因此 MinerU 不进入生产
  `PdfParser` 或默认 Structured Fallback。

Fast Path 继续使用 `pypdf + PyMuPDF + Quality Gate`。异常页保持 quarantine；下一步验证
RapidOCR 作为纯 OCR 轻量 fallback，MinerU 保留为隔离的 Table/Structured Parser 实验能力。

## 2. 实验边界

- 未修改 Corpus v3、Chunk、Embedding、Qdrant Collection 或生产 `PdfParser`。
- MinerU 安装在 `tmp/mineru/env` 的独立 Conda prefix，模型位于 ignored 的 `tmp/mineru/models`。
- 主环境通过 subprocess 调用隔离 Worker，不 import MinerU Python package。
- 只解析固定 Benchmark 的目标单页；每个 Case 有 PDF SHA-256、页码和人工 Anchor。
- 普通、双栏、公式和原生表格使用 `method=auto`；已知乱码、图片页和扫描表格强制 OCR。
- Formula 模型只在 `formula_dense` 启用；Table 模型只在要求 table block 的 Case 启用。

运行环境实测占用约为：隔离环境 `1.26 GB`，pipeline 模型 `2.48 GB`。当前安装解析版本为
`MinerU 3.4.5`、`torch 2.13.0+cpu`。

## 3. Benchmark

`structured_parse_benchmark_v1.jsonl` 共 11 个 Case：

| 类别 | Case |
| --- | --- |
| 文本对照 | 正常正文、双栏正文 |
| 已知异常 | 字体映射乱码、正文与乱码 Figure 混合页 |
| 结构内容 | 公式密集页、简单/多级列头/复杂原生表格 |
| 视觉/OCR | 短视觉页、无文本截图页、synthetic 扫描表格 |

扫描表格 fixture 是确定性的无文本层 PDF，包含 4×4 金标表格。Table QA 不做字符串包含判断，
而是展开 `rowspan/colspan`，按行标签和一层或多层列头找到交叉单元格。答案数字出现在错误列不会得分。

## 4. 正式结果

连续运行 11 个 Case、单 Case 120 秒预算：

| Case pass | Anchor recall | Block type | BBox | Page | Table QA | OCR recovery | P50 / P95 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 63.64% | 61.54% | 72.73% | 100% | 100% | 100% | 40% | 24.10 / 120.15 s |

通过项：

- 正常正文、双栏正文和短视觉页全部恢复目标 Anchor。
- 简单、两级列头和复杂原生表格全部通过 Table QA。
- synthetic 扫描表格恢复完整 HTML，三条交叉单元格 QA 全部正确。
- 只要 MinerU 产出 block，bbox 和原始页 provenance 完整率均为 100%。

失败项：

- ReAct 乱码页在连续运行中超时，但独立 Probe 在 `26.91 s` 内以 2/2 Anchor 通过，说明能力存在，
  当前部署稳定性不足。
- Tree of Thoughts 混合页在 OCR 阶段出现资源停滞并超时。
- 公式页独立 Probe 在加载 UniMERNet 时稳定触发 Windows `os error 1455`。
- ExpeL 无文本截图页只恢复局部思维文本，3 个目标 Anchor 均未恢复。

正式产物：

- `evals/baselines/mineru_structured_v1.json|md`：11 Case 连续运行基线。
- `evals/baselines/mineru_structured_v1_recovery_probe.json|md`：ReAct 独立恢复 Probe。
- `evals/baselines/mineru_structured_v1_formula.json|md`：公式模型 page file 故障 Probe。

## 5. Windows 兼容问题

MinerU 3.4.5 CLI 会先启动临时 FastAPI，再使用 `ProcessPoolExecutor` 渲染 PDF。Windows `spawn`
会在渲染子进程中再次导入完整 API 与 PyTorch，在低内存机器上触发 `MemoryError` 或
`BrokenProcessPool`，且失败后临时 API 偶尔不能退出。

Spike Worker 只替换 PDF 渲染执行位置：单页仍由 MinerU 的 pdfium 逻辑渲染，但留在当前隔离进程；
Layout、OCR、Table、Formula 与 Markdown/JSON 生成仍使用 MinerU 原 pipeline。该兼容层用于获得
质量数据，不掩盖原生 CLI 的部署问题，也不作为全平台通用承诺。

另一个依赖问题是 MinerU 3.4.5 pipeline 会 import `six`，但 package metadata 未声明它。
`requirements_mineru.txt` 因此显式固定 `six==1.17.0`。

## 6. 复现

独立环境安装：

```powershell
conda create --prefix .\tmp\mineru\env python=3.12 pip -y
conda run --prefix .\tmp\mineru\env python -m pip install -r requirements_mineru.txt
conda run --prefix .\tmp\mineru\env mineru-models-download --source modelscope --model_type pipeline
```

根据模型实际下载目录创建 `tmp/mineru/mineru.json`，设置 `models-dir.pipeline`，再运行：

```powershell
python scripts/run_structured_parse_benchmark.py --timeout-seconds 120
```

主环境不要通过已激活的 MinerU 环境运行项目；Adapter 会清除主 Conda 注入变量，并把隔离环境路径
放到子进程 PATH 前部。

## 7. License

本 Spike 使用 [OpenDataLab MinerU](https://github.com/opendatalab/MinerU)。`MinerU Open Source
License` 基于 Apache 2.0 并包含附加条款：超大规模商业使用需要另行授权；向第三方提供在线服务时，
界面或公开文档需明确标注使用 MinerU。当前作品仓库已在本文件与 README 中保留 attribution。
