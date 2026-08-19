from paper_research_copilot.domain import PaperMetadata, ParsedDocument, ParsedPage
from paper_research_copilot.ingestion import PageAwareChunker


def test_chunker_preserves_pages_and_overlap() -> None:
    page_one = " ".join(f"agent-{index}" for index in range(100))
    page_two = "Reflection evaluates evidence. " * 20
    document = ParsedDocument(
        metadata=PaperMetadata(
            document_sha256="a" * 64,
            title="Agent Paper",
            source_path="agent.pdf",
            page_count=2,
        ),
        pages=(
            ParsedPage(page_number=1, text=page_one),
            ParsedPage(page_number=2, text=page_two),
        ),
    )

    chunks = PageAwareChunker(chunk_size=240, overlap=40).split(document)

    assert len(chunks) > 2
    assert {chunk.page_number for chunk in chunks} == {1, 2}
    assert all(chunk.text in document.pages[chunk.page_number - 1].text for chunk in chunks)
    page_one_chunks = [chunk for chunk in chunks if chunk.page_number == 1]
    assert page_one_chunks[1].char_start < page_one_chunks[0].char_end
    assert len({chunk.chunk_id for chunk in chunks}) == len(chunks)


def test_section_detection_rejects_sentence_starting_with_article_a() -> None:
    assert (
        PageAwareChunker._as_section_title(
            "A unique feature of human intelligence is the ability to combine actions with"
        )
        is None
    )
    assert PageAwareChunker._as_section_title("A ADDITIONAL RESULTS") == "A ADDITIONAL RESULTS"
    assert (
        PageAwareChunker._as_section_title(
            "5 Behavioral responses: In addition to these physiological responses"
        )
        is None
    )
    assert (
        PageAwareChunker._as_section_title("3 Reflexion: reinforcement via verbal reflection")
        == "3 Reflexion: reinforcement via verbal reflection"
    )
