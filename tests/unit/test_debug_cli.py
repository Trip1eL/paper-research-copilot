from pathlib import Path

import pytest
from pytest import CaptureFixture, MonkeyPatch

from paper_research_copilot import cli
from paper_research_copilot.agent import (
    AgentEvent,
    AgentResult,
    EvidenceAssessment,
    ResearchPlan,
    ResearchTask,
)
from paper_research_copilot.domain import (
    Answer,
    PaperChunk,
    PaperMetadata,
    ParsedDocument,
    ParsedPage,
    RetrievedChunk,
)
from paper_research_copilot.retrieval import RetrievalMode


def _document() -> ParsedDocument:
    return ParsedDocument(
        metadata=PaperMetadata(
            document_sha256="a" * 64,
            title="Agent Paper",
            authors=("Ada", "Bob"),
            source_path="agent.pdf",
            page_count=1,
        ),
        pages=(
            ParsedPage(
                page_number=1,
                text="Agents use external tools to gather evidence. " * 10,
            ),
        ),
    )


def _evidence() -> tuple[RetrievedChunk, ...]:
    return (
        RetrievedChunk(
            citation_id="C1",
            score=0.91,
            chunk=PaperChunk(
                chunk_id="89dc7b16-6840-50ef-9850-e1a521ca24ac",
                document_sha256="a" * 64,
                chunk_index=0,
                chunking_version="chunking_v1",
                title="Agent Paper",
                source_path="agent.pdf",
                page_number=1,
                char_start=0,
                char_end=45,
                text="Agents use external tools to gather evidence.",
            ),
        ),
    )


@pytest.mark.parametrize(
    ("arguments", "command"),
    [
        (["inspect-pdf", "paper.pdf"], "inspect-pdf"),
        (["inspect-chunks", "paper.pdf"], "inspect-chunks"),
        (["search", "tool use", "--top-k", "3"], "search"),
        (
            ["search", "tool use", "--retrieval-mode", "discovery"],
            "search",
        ),
        (["show-prompt", "tool use", "--top-k", "3"], "show-prompt"),
        (
            ["ask", "tool use", "--retrieval-mode", "discovery"],
            "ask",
        ),
        (["evaluate-retriever", "--top-k", "10"], "evaluate-retriever"),
        (
            ["evaluate-retriever", "--strategy", "mmr_dense", "--mmr-lambda", "0.7"],
            "evaluate-retriever",
        ),
        (["evaluate-retriever", "--strategy", "bm25"], "evaluate-retriever"),
        (
            ["ingest-corpus", "--version", "2", "--collection", "agent_seed_v2"],
            "ingest-corpus",
        ),
        (
            ["evaluate-retriever", "--collection", "agent_seed_v2"],
            "evaluate-retriever",
        ),
        (["evaluate-retriever", "--strategy", "hybrid_rrf"], "evaluate-retriever"),
        (
            ["evaluate-retriever", "--strategy", "hybrid_rrf_mmr"],
            "evaluate-retriever",
        ),
        (
            [
                "evaluate-retriever",
                "--strategy",
                "hybrid_rrf_query_rewrite",
                "--rewrite-count",
                "3",
            ],
            "evaluate-retriever",
        ),
        (["agent", "Compare two methods", "--show-trace"], "agent"),
    ],
)
def test_parser_supports_debug_commands(arguments: list[str], command: str) -> None:
    args = cli.build_parser().parse_args(arguments)

    assert args.command == command


def test_parser_rejects_invalid_mmr_lambda() -> None:
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(
            ["evaluate-retriever", "--strategy", "mmr_dense", "--mmr-lambda", "1.1"]
        )


def test_inspect_pdf_is_offline(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli.PdfParser, "parse", lambda self, path: _document())
    monkeypatch.setattr(
        cli,
        "build_pipeline",
        lambda settings: pytest.fail("inspect-pdf must not build the model pipeline"),
    )

    result = cli.main(["inspect-pdf", str(tmp_path / "paper.pdf")])

    output = capsys.readouterr().out
    assert result == 0
    assert "Title: Agent Paper" in output
    assert "Page 1: chars=" in output


def test_inspect_chunks_shows_chunk_metadata(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli.PdfParser, "parse", lambda self, path: _document())

    result = cli.main(["inspect-chunks", str(tmp_path / "paper.pdf"), "--limit", "1"])

    output = capsys.readouterr().out
    assert result == 0
    assert "Chunks: showing 1 of 1" in output
    assert "page=1" in output
    assert "chars=0:" in output


class _FakeRetriever:
    def retrieve(self, question: str, top_k: int) -> tuple[RetrievedChunk, ...]:
        assert question == "How do agents use tools?"
        assert top_k == 3
        return _evidence()


class _FakeRuntime:
    def __init__(self) -> None:
        self.retriever = _FakeRetriever()
        self.mode: RetrievalMode | None = None
        self.closed = False

    def retrieve(
        self,
        question: str,
        top_k: int,
        mode: RetrievalMode,
    ) -> tuple[RetrievedChunk, ...]:
        self.mode = mode
        return self.retriever.retrieve(question, top_k)

    def close(self) -> None:
        self.closed = True


@pytest.mark.parametrize("command", ["search", "show-prompt"])
def test_retrieval_debug_commands_do_not_build_llm_pipeline(
    command: str,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    runtime = _FakeRuntime()
    monkeypatch.setattr(cli, "build_retrieval_runtime", lambda settings: runtime)
    monkeypatch.setattr(
        cli,
        "build_pipeline",
        lambda settings: pytest.fail(f"{command} must not build the LLM pipeline"),
    )

    result = cli.main(
        [
            command,
            "How do agents use tools?",
            "--top-k",
            "3",
            "--retrieval-mode",
            "discovery",
        ]
    )

    output = capsys.readouterr().out
    assert result == 0
    assert runtime.closed
    assert runtime.mode is RetrievalMode.DISCOVERY
    assert "[C1]" in output
    if command == "search":
        assert "score=0.9100" in output
        assert "Evidence:" in output
    else:
        assert "===== SYSTEM PROMPT =====" in output
        assert "===== USER PROMPT =====" in output


def test_ask_forwards_retrieval_mode_to_answer_pipeline(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    class _FakePipeline:
        def __init__(self) -> None:
            self.mode: RetrievalMode | None = None
            self.closed = False

        def ask(
            self,
            question: str,
            top_k: int | None,
            retrieval_mode: RetrievalMode,
        ) -> Answer:
            self.mode = retrieval_mode
            return Answer(question=question, text="Answer [C1].", citations=())

        def close(self) -> None:
            self.closed = True

    pipeline = _FakePipeline()
    monkeypatch.setattr(cli, "build_pipeline", lambda settings: pipeline)

    result = cli.main(["ask", "How do agents use tools?", "--retrieval-mode", "discovery"])

    assert result == 0
    assert pipeline.mode is RetrievalMode.DISCOVERY
    assert pipeline.closed
    assert "Answer [C1]." in capsys.readouterr().out


def test_agent_command_uses_langgraph_runtime_and_prints_trace(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    question = "How does the described memory mechanism work?"
    plan = ResearchPlan(
        question=question,
        question_type="single_paper",
        rationale="One mechanism is requested",
        tasks=(
            ResearchTask(
                task_id="T1",
                query="described memory mechanism",
                goal="Find direct mechanism evidence",
            ),
        ),
    )
    result = AgentResult(
        question=question,
        plan=plan,
        evidence=_evidence(),
        assessment=EvidenceAssessment(
            sufficient=True,
            reason="The task met its evidence quota",
            task_candidate_counts={"T1": 1},
            task_selected_counts={"T1": 1},
            distinct_paper_count=1,
            retry_recommended=False,
        ),
        answer=Answer(question=question, text="Agent answer [C1].", citations=()),
        retry_count=0,
        trace=(
            AgentEvent(
                sequence=1,
                node="plan_research",
                outcome="planned",
                latency_ms=10,
            ),
        ),
    )

    class _FakeAgentRuntime:
        def __init__(self) -> None:
            self.closed = False

        def run(self, actual_question: str) -> AgentResult:
            assert actual_question == question
            return result

        def close(self) -> None:
            self.closed = True

    runtime = _FakeAgentRuntime()
    monkeypatch.setattr(cli, "build_agent_runtime", lambda *args, **kwargs: runtime)
    monkeypatch.setattr(
        cli,
        "build_pipeline",
        lambda settings: pytest.fail("agent must not build the fixed RAG pipeline"),
    )

    exit_code = cli.main(["agent", question, "--show-trace"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert runtime.closed
    assert "Agent answer [C1]." in output
    assert "Agent Plan:" in output
    assert "plan_research: planned" in output
