"""Tests for the VieNeu-TTS text pre-processor (_clean_text_for_tts).

Only exercises the pure-function text sanitizer — does not load the
llama.cpp model or hit the network.
"""

import pytest

from app.services.vieneu_tts import _clean_text_for_tts


# ---------------------------------------------------------------------------
# Short all-caps → spaced letters (Roman-numeral mitigation)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        # Classic Roman-numeral trap — CV used to be read as 105.
        ("CV", "C V"),
        # 2-char acronyms
        ("IT", "I T"),
        ("PR", "P R"),
        ("HR", "H R"),
        ("TV", "T V"),
        ("AI", "A I"),
        # 3-char acronyms — also Roman-numeral valid.
        ("MIX", "M I X"),
        ("DIV", "D I V"),
        ("SQL", "S Q L"),
    ],
)
def test_short_allcaps_are_spaced(raw: str, expected: str) -> None:
    """2-3 char all-caps words get spaced to prevent Roman-numeral reading."""
    assert _clean_text_for_tts(raw) == expected


def test_short_allcaps_inside_sentence() -> None:
    """Short acronyms inside Vietnamese text are still spaced."""
    got = _clean_text_for_tts("Gửi CV cho HR nhé")
    assert got == "Gửi C V cho H R nhé"


def test_short_allcaps_after_markdown_strip() -> None:
    """Short acronym wrapped in bold markdown is still spaced."""
    assert _clean_text_for_tts("**CV** của tôi") == "C V của tôi"


# ---------------------------------------------------------------------------
# Long all-caps → title case (unchanged behavior)
# ---------------------------------------------------------------------------


def test_long_allcaps_become_title_case() -> None:
    """≥4 char all-caps become title case so TTS reads them as words."""
    assert _clean_text_for_tts("JARVIS agent") == "Jarvis agent"


def test_long_then_short_mixed() -> None:
    """Long acronym gets title-cased first, short acronyms get spaced."""
    got = _clean_text_for_tts("HTTPS + SSH")
    assert got == "Https + S S H"


# ---------------------------------------------------------------------------
# Edge cases — must NOT be touched
# ---------------------------------------------------------------------------


def test_mixed_case_word_untouched() -> None:
    """Mixed-case words (PhD, iOS) don't match the all-caps regex."""
    assert _clean_text_for_tts("PhD Ok") == "PhD Ok"


def test_single_letter_untouched() -> None:
    """Single capital letter (not ≥2 chars) stays unchanged."""
    assert _clean_text_for_tts("A and B") == "A and B"


def test_url_untouched() -> None:
    """URLs containing lowercase acronyms aren't affected."""
    got = _clean_text_for_tts("Website https://example.com")
    assert got == "Website https://example.com"


def test_empty_string() -> None:
    """Empty input returns empty output."""
    assert _clean_text_for_tts("") == ""
