"""Tests for app.notes — load, save, parse, and validate manual market notes."""

from __future__ import annotations

import tempfile
from pathlib import Path

from app.notes import load_notes, parse_notes, save_notes, validate_notes


# ---------------------------------------------------------------------------
# load_notes
# ---------------------------------------------------------------------------


def test_load_notes_missing_file_returns_empty_string():
    assert load_notes(Path("/nonexistent/path/notes.txt")) == ""


def test_load_notes_existing_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "notes.txt"
        path.write_text("Treasury yields rose.\nYield curve inverted.", encoding="utf-8")
        assert load_notes(path) == "Treasury yields rose.\nYield curve inverted."


def test_load_notes_empty_file_returns_empty_string():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "notes.txt"
        path.write_text("", encoding="utf-8")
        assert load_notes(path) == ""


# ---------------------------------------------------------------------------
# save_notes
# ---------------------------------------------------------------------------


def test_save_notes_creates_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "notes.txt"
        save_notes(path, "Basis Point")
        assert path.read_text(encoding="utf-8") == "Basis Point"


def test_save_notes_creates_parent_directories():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "nested" / "dirs" / "notes.txt"
        save_notes(path, "test content")
        assert path.exists()


def test_save_notes_overwrites_existing_content():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "notes.txt"
        save_notes(path, "original")
        save_notes(path, "updated")
        assert path.read_text(encoding="utf-8") == "updated"


def test_save_notes_empty_string_writes_empty_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "notes.txt"
        save_notes(path, "")
        assert path.read_text(encoding="utf-8") == ""


def test_save_and_load_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "notes.txt"
        text = "- Treasury yields rose.\n- Yield curve inverted.\n"
        save_notes(path, text)
        assert load_notes(path) == text


# ---------------------------------------------------------------------------
# parse_notes
# ---------------------------------------------------------------------------


def test_parse_notes_strips_dash_prefix():
    assert parse_notes("- Treasury yields rose.") == ["Treasury yields rose."]


def test_parse_notes_strips_star_prefix():
    assert parse_notes("* Yield curve inverted.") == ["Yield curve inverted."]


def test_parse_notes_handles_no_prefix():
    assert parse_notes("Basis point") == ["Basis point"]


def test_parse_notes_skips_blank_lines():
    assert parse_notes("First note.\n\n\nSecond note.") == ["First note.", "Second note."]


def test_parse_notes_skips_whitespace_only_lines():
    assert parse_notes("First note.\n   \nSecond note.") == ["First note.", "Second note."]


def test_parse_notes_empty_string_returns_empty_list():
    assert parse_notes("") == []


def test_parse_notes_multiple_notes():
    assert parse_notes("- Term A\n- Term B\n- Term C") == ["Term A", "Term B", "Term C"]


def test_parse_notes_preserves_order():
    assert parse_notes("- First\n- Second\n- Third") == ["First", "Second", "Third"]


def test_parse_notes_strips_leading_spaces_from_bullets():
    assert parse_notes("  - Indented note") == ["Indented note"]


# ---------------------------------------------------------------------------
# validate_notes
# ---------------------------------------------------------------------------


def test_validate_notes_valid_single_line():
    valid, reason = validate_notes("Treasury yields rose.")
    assert valid is True
    assert reason == ""


def test_validate_notes_valid_multiple_lines():
    valid, _ = validate_notes("- Term A\n- Term B\n- Term C")
    assert valid is True


def test_validate_notes_empty_string_is_invalid():
    valid, reason = validate_notes("")
    assert valid is False
    assert reason != ""


def test_validate_notes_whitespace_only_is_invalid():
    valid, reason = validate_notes("   \n  \n  ")
    assert valid is False
    assert reason != ""


def test_validate_notes_too_long_is_invalid():
    valid, reason = validate_notes("x" * 10_001)
    assert valid is False
    assert "10,000" in reason or "limit" in reason.lower()


def test_validate_notes_exact_max_length_is_valid():
    # 100 lines × 99 'a' chars + newline = 10,000 chars total
    text = ("a" * 99 + "\n") * 100
    valid, _ = validate_notes(text)
    assert valid is True


def test_validate_notes_line_too_long_is_invalid():
    valid, reason = validate_notes("a" * 501)
    assert valid is False
    assert "500" in reason or "line" in reason.lower()


def test_validate_notes_all_blank_lines_is_invalid():
    valid, reason = validate_notes("\n\n\n   \n")
    assert valid is False
    assert reason != ""
