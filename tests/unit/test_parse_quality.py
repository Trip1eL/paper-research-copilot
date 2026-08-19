import pytest

from paper_research_copilot.domain import PageTextExtraction, ParserName
from paper_research_copilot.ingestion import PageQualityScorer


def _extraction(
    text: str,
    *,
    parser_name: ParserName = "pypdf",
    image_count: int = 0,
) -> PageTextExtraction:
    return PageTextExtraction(
        page_number=1,
        text=text,
        parser_name=parser_name,
        parser_version="test",
        latency_ms=1,
        width=612,
        height=792,
        image_count=image_count,
    )


def test_quality_scorer_accepts_clean_text() -> None:
    result = PageQualityScorer().score(
        _extraction("Agent systems retrieve evidence and validate citations. " * 10)
    )

    assert result.status == "accepted"
    assert result.score == 1
    assert not result.signals


def test_quality_scorer_quarantines_empty_image_page() -> None:
    result = PageQualityScorer().score(_extraction("", image_count=1))

    assert result.status == "quarantined"
    assert result.score == 0
    assert result.signals == ("empty_text", "image_only_candidate")


def test_quality_scorer_quarantines_severe_control_character_garbling() -> None:
    result = PageQualityScorer().score(_extraction(("readable text " * 20) + ("\x03" * 100)))

    assert result.status == "quarantined"
    assert "severe_control_characters" in result.signals


def test_quality_scorer_quarantines_caesar_like_font_mapping() -> None:
    cipher = " ".join(("7KRXJKW", "5HDVRQLQJ", "PDNLQJ", "SURJUDP") * 80)

    result = PageQualityScorer().score(_extraction(cipher))

    assert result.status == "quarantined"
    assert "cipher_like_word_distribution" in result.signals


def test_quality_scorer_quarantines_abnormal_unicode_font_mapping() -> None:
    corrupted = "GĮŔũƜʝ ĦòƙƜ ŝŤòŔŝ ŗòÊçĎ Įũĭæòŗŝ " * 100

    result = PageQualityScorer().score(_extraction(corrupted))

    assert result.status == "quarantined"
    assert "abnormal_extended_latin_distribution" in result.signals


def test_quality_scorer_does_not_treat_cjk_as_corrupted_latin() -> None:
    result = PageQualityScorer().score(
        _extraction("杭州到深圳的航班信息。Agent uses multilingual evidence. " * 100)
    )

    assert result.status == "accepted"
    assert "abnormal_extended_latin_distribution" not in result.signals


def test_quality_scorer_keeps_low_private_use_ratio_as_accepted_warning_signal() -> None:
    result = PageQualityScorer().score(
        _extraction(("formula and explanation " * 100) + ("\ue000" * 3))
    )

    assert result.status == "accepted"
    assert result.score == pytest.approx(0.8)
    assert result.signals == ("character_mapping_risk",)


def test_quality_scorer_validates_threshold_order() -> None:
    with pytest.raises(ValueError, match="warning < accepted"):
        PageQualityScorer(accepted_threshold=0.5, warning_threshold=0.5)
