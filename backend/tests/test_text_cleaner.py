"""
Unit tests for text cleaning.

Regression coverage for the NUL-byte bug: real PDFs embed C0 control
characters, and Postgres rejects 0x00 in text columns, so ingestion failed on
insert for any genuine document.
"""

from backend.src.ai.processing.text_cleaner import clean_text


def test_removes_nul_and_control_characters():
    dirty = "Step function:\x00 step(z) =\x0e 0 if z < 0"
    cleaned = clean_text(dirty)

    assert "\x00" not in cleaned
    assert "\x0e" not in cleaned
    assert "Step function" in cleaned


def test_no_control_characters_survive_any_c0_byte():
    dirty = "".join(chr(code) for code in range(0, 32)) + "text" + chr(127)
    cleaned = clean_text(dirty)

    assert all(ord(char) >= 32 for char in cleaned)
    assert "text" in cleaned


def test_strips_non_ascii():
    assert "—" not in clean_text("an em—dash")


def test_collapses_whitespace():
    assert clean_text("a   b\n\n\tc") == "a b c"


def test_preserves_page_markers_for_the_chunker():
    """The chunker parses these markers, so cleaning must not destroy them."""
    cleaned = clean_text("\n\n--- PAGE 12 ---\n\nSome content.")
    assert "--- PAGE 12 ---" in cleaned


def test_empty_input():
    assert clean_text("") == ""
    assert clean_text(None) == ""
