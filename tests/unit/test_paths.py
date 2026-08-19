from pathlib import Path

from pytest import MonkeyPatch

from paper_research_copilot.cli import _resolve_pdf_paths
from paper_research_copilot.config import PROJECT_ROOT, Settings


def test_relative_qdrant_path_is_resolved_from_project_root(tmp_path: Path) -> None:
    settings = Settings(
        qdrant_path=Path("runtime/qdrant"),
        dynamic_qdrant_path=Path("runtime/qdrant_dynamic"),
        dynamic_assets_path=Path("runtime/papers"),
    )

    assert settings.resolved_qdrant_path() == PROJECT_ROOT / "runtime/qdrant"
    assert settings.resolved_dynamic_qdrant_path() == PROJECT_ROOT / "runtime/qdrant_dynamic"
    assert settings.resolved_dynamic_assets_path() == PROJECT_ROOT / "runtime/papers"


def test_cli_falls_back_to_project_root_for_relative_pdf(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    project_root = tmp_path / "project"
    pdf_path = project_root / "data" / "papers" / "paper.pdf"
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(b"test")
    working_directory = tmp_path / "elsewhere"
    working_directory.mkdir()
    monkeypatch.chdir(working_directory)
    monkeypatch.setattr("paper_research_copilot.cli.PROJECT_ROOT", project_root)

    resolved = _resolve_pdf_paths((Path("data/papers/paper.pdf"),))

    assert resolved == (pdf_path.resolve(),)
