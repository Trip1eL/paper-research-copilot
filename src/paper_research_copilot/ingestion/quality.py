"""Deterministic page-text quality scoring for parser routing."""

import re
import unicodedata

from paper_research_copilot.domain import (
    PageQualityFeatures,
    PageQualityResult,
    PageTextExtraction,
    ParseQualityStatus,
)


class PageQualityScorer:
    """Score extraction risk without calling an LLM or OCR engine."""

    def __init__(self, *, accepted_threshold: float = 0.75, warning_threshold: float = 0.50):
        if not 0 <= warning_threshold < accepted_threshold <= 1:
            raise ValueError("Quality thresholds must satisfy 0 <= warning < accepted <= 1")
        self.accepted_threshold = accepted_threshold
        self.warning_threshold = warning_threshold

    def score(self, extraction: PageTextExtraction) -> PageQualityResult:
        features = calculate_page_quality_features(extraction)
        score = 1.0
        signals: list[str] = []

        if features.char_count == 0:
            score = 0.0
            signals.append("empty_text")
            if features.image_count:
                signals.append("image_only_candidate")
        elif features.char_count < 100:
            score -= 0.60
            signals.append("very_short_text")
        elif features.char_count < 200:
            score -= 0.40
            signals.append("short_text")

        if features.control_char_ratio > 0.05:
            score -= 0.80
            signals.append("severe_control_characters")
        elif features.control_char_ratio > 0.01:
            score -= 0.65
            signals.append("high_control_characters")
        elif features.control_char_ratio > 0.005:
            score -= 0.35
            signals.append("control_characters")

        mapped_char_ratio = features.replacement_char_ratio + features.private_use_char_ratio
        if mapped_char_ratio > 0.01:
            score -= 0.60
            signals.append("severe_character_mapping_risk")
        elif mapped_char_ratio > 0.001:
            score -= 0.20
            signals.append("character_mapping_risk")

        if features.char_count >= 200 and features.alphanumeric_ratio < 0.15:
            score -= 0.25
            signals.append("low_alphanumeric_ratio")

        if features.uppercase_word_ratio > 0.20 and features.vowelless_word_ratio > 0.05:
            score -= 0.65
            signals.append("cipher_like_word_distribution")

        if features.extended_latin_letter_ratio > 0.03:
            score -= 0.65
            signals.append("abnormal_extended_latin_distribution")

        bounded_score = round(max(0.0, min(1.0, score)), 4)
        status: ParseQualityStatus
        if bounded_score >= self.accepted_threshold:
            status = "accepted"
        elif bounded_score >= self.warning_threshold:
            status = "warning"
        else:
            status = "quarantined"
        return PageQualityResult(
            score=bounded_score,
            status=status,
            features=features,
            signals=tuple(signals),
        )


def calculate_page_quality_features(extraction: PageTextExtraction) -> PageQualityFeatures:
    text = extraction.text
    length = len(text)
    denominator = max(length, 1)
    alphanumeric_count = sum(character.isalnum() for character in text)
    ascii_words = re.findall(r"[A-Za-z]{4,}", text)
    uppercase_word_count = sum(word.isupper() for word in ascii_words)
    vowelless_word_count = sum(
        not set(word.casefold()).intersection("aeiouy") for word in ascii_words
    )
    letters = [character for character in text if character.isalpha()]
    extended_latin_letter_count = sum(
        ord(character) > 127 and "LATIN" in unicodedata.name(character, "") for character in letters
    )
    control_count = sum(
        unicodedata.category(character) == "Cc" and character not in "\n\t" for character in text
    )
    replacement_count = text.count("\ufffd")
    private_use_count = sum(unicodedata.category(character) == "Co" for character in text)
    non_printable_count = sum(
        not character.isprintable() and character not in "\n\t" for character in text
    )
    return PageQualityFeatures(
        char_count=length,
        line_count=len(text.splitlines()) if text else 0,
        alphanumeric_ratio=round(alphanumeric_count / denominator, 6),
        uppercase_word_ratio=round(uppercase_word_count / max(len(ascii_words), 1), 6),
        vowelless_word_ratio=round(vowelless_word_count / max(len(ascii_words), 1), 6),
        extended_latin_letter_ratio=round(extended_latin_letter_count / max(len(letters), 1), 6),
        control_char_ratio=round(control_count / denominator, 6),
        replacement_char_ratio=round(replacement_count / denominator, 6),
        private_use_char_ratio=round(private_use_count / denominator, 6),
        non_printable_char_ratio=round(non_printable_count / denominator, 6),
        image_count=extraction.image_count,
    )
