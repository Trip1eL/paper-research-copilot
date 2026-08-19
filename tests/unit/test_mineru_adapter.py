import json
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from paper_research_copilot.ingestion.structured import (
    MineruCliAdapter,
    StructuredParserError,
)


class _FakeMineruRunner:
    def __init__(self, *, returncode: int = 0) -> None:
        self.returncode = returncode
        self.command: tuple[str, ...] = ()
        self.environment: Mapping[str, str] = {}

    def __call__(
        self,
        command: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        self.command = tuple(command)
        self.environment = env
        if self.returncode:
            return subprocess.CompletedProcess(command, self.returncode, "", "model failed")
        output = Path(command[command.index("--output") + 1])
        pdf_path = Path(command[command.index("--path") + 1])
        method = command[command.index("--method") + 1]
        parse_dir = output / pdf_path.stem / method
        parse_dir.mkdir(parents=True)
        content = [
            {
                "type": "title",
                "text": "Agent Evaluation Results",
                "bbox": [100, 80, 700, 150],
                "page_idx": 0,
            },
            {
                "type": "table",
                "table_caption": ["Evaluation table"],
                "table_body": (
                    "<table><tr><th>System</th><th>Score</th></tr>"
                    "<tr><td>Research Copilot</td><td>96.2</td></tr></table>"
                ),
                "bbox": [100, 200, 900, 600],
                "page_idx": 0,
            },
        ]
        (parse_dir / f"{pdf_path.stem}_content_list.json").write_text(
            json.dumps(content), encoding="utf-8"
        )
        (parse_dir / f"{pdf_path.stem}.md").write_text(
            "# Agent Evaluation Results", encoding="utf-8"
        )
        return subprocess.CompletedProcess(command, 0, "ok", "")


def _adapter(tmp_path: Path, runner: _FakeMineruRunner) -> MineruCliAdapter:
    executable = tmp_path / "mineru.exe"
    executable.write_bytes(b"fake")
    config = tmp_path / "mineru.json"
    config.write_text("{}", encoding="utf-8")
    return MineruCliAdapter(
        executable=executable,
        parser_version="3.4.5",
        project_root=tmp_path,
        config_path=config,
        command_runner=runner,
    )


def test_mineru_adapter_maps_page_blocks_and_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-structured-test")
    runner = _FakeMineruRunner()
    monkeypatch.setenv("CONDA_PREFIX", "wrong-main-environment")

    result = _adapter(tmp_path, runner).parse_page(
        pdf_path,
        page_number=3,
        output_dir=tmp_path / "outputs",
        method="ocr",
    )

    assert result.page_number == 3
    assert result.parser_name == "mineru"
    assert result.parse_method == "ocr"
    assert result.blocks[1].block_type == "table"
    assert result.blocks[1].bbox == (100, 200, 900, 600)
    assert "Research Copilot 96.2" in result.blocks[1].text
    assert all(block.page_number == 3 for block in result.blocks)
    assert runner.command[runner.command.index("--start") + 1] == "2"
    assert runner.command[runner.command.index("--end") + 1] == "2"
    assert runner.command[runner.command.index("--formula") + 1] == "false"
    assert runner.command[runner.command.index("--table") + 1] == "true"
    assert runner.environment["MINERU_DEVICE_MODE"] == "cpu"
    assert "CONDA_PREFIX" not in runner.environment
    assert runner.environment["PATH"].startswith(str(tmp_path))


def test_mineru_adapter_can_enable_formula_and_disable_table(tmp_path: Path) -> None:
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-structured-test")
    runner = _FakeMineruRunner()
    executable = tmp_path / "mineru.exe"
    executable.write_bytes(b"fake")
    config = tmp_path / "mineru.json"
    config.write_text("{}", encoding="utf-8")
    adapter = MineruCliAdapter(
        executable=executable,
        parser_version="3.4.5",
        project_root=tmp_path,
        config_path=config,
        formula_enabled=True,
        table_enabled=False,
        command_runner=runner,
    )

    adapter.parse_page(
        pdf_path,
        page_number=1,
        output_dir=tmp_path / "outputs",
        method="auto",
    )

    assert runner.command[runner.command.index("--formula") + 1] == "true"
    assert runner.command[runner.command.index("--table") + 1] == "false"


def test_mineru_adapter_can_invoke_isolated_worker_script(tmp_path: Path) -> None:
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-structured-test")
    runner = _FakeMineruRunner()
    worker = tmp_path / "worker.py"
    worker.write_text("# fake worker", encoding="utf-8")
    adapter = _adapter(tmp_path, runner)
    adapter.worker_script = worker

    adapter.parse_page(
        pdf_path,
        page_number=1,
        output_dir=tmp_path / "outputs",
        method="ocr",
    )

    assert runner.command[0].endswith("mineru.exe")
    assert runner.command[1] == str(worker)
    assert "--backend" not in runner.command


def test_mineru_adapter_surfaces_subprocess_failure(tmp_path: Path) -> None:
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-structured-test")

    with pytest.raises(StructuredParserError, match="model failed"):
        _adapter(tmp_path, _FakeMineruRunner(returncode=1)).parse_page(
            pdf_path,
            page_number=1,
            output_dir=tmp_path / "outputs",
            method="auto",
        )
