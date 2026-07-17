from __future__ import annotations

from pathlib import Path

_MAX_NOTES_CHARS = 10_000
_MAX_NOTE_LINE_CHARS = 500


def load_notes(path: Path) -> str:
    """Return raw text from the notes file, or empty string if file is missing."""
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def save_notes(path: Path, text: str) -> None:
    """Write text to path, creating parent directories if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def parse_notes(text: str) -> list[str]:
    """Return non-empty note lines with leading bullet prefixes (-, *, spaces) stripped."""
    lines = []
    for line in text.splitlines():
        stripped = line.strip().lstrip("-* ").strip()
        if stripped:
            lines.append(stripped)
    return lines


def validate_notes(text: str) -> tuple[bool, str]:
    """
    Return (True, "") if notes are valid, or (False, reason) if not.

    Rules:
      - Must not be empty or whitespace-only.
      - Total character count must not exceed _MAX_NOTES_CHARS.
      - No single line may exceed _MAX_NOTE_LINE_CHARS characters.
      - At least one parseable note line must remain after stripping bullets.
    """
    if not text or not text.strip():
        return False, "Notes cannot be empty."
    if len(text) > _MAX_NOTES_CHARS:
        return False, f"Notes exceed the {_MAX_NOTES_CHARS:,}-character limit."
    for line in text.splitlines():
        if len(line) > _MAX_NOTE_LINE_CHARS:
            return False, (
                f"One or more lines exceed the {_MAX_NOTE_LINE_CHARS}-character limit."
            )
    if not parse_notes(text):
        return False, "No valid note lines found after parsing."
    return True, ""
