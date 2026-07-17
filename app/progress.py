from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path


# ---------------------------------------------------------------------------
# Mastery formula
# ---------------------------------------------------------------------------
#
# mastery_score = round(correct_count / review_count * 100), clamped to [0, 100]
#
# A score of 0 is returned when no reviews exist.
#
# Next-review scheduling uses four bands (simple spaced repetition):
#   0  – 33  → +1  day   (needs work)
#   34 – 66  → +3  days  (learning)
#   67 – 84  → +7  days  (confident)
#   85 – 100 → +14 days  (mastered)
# ---------------------------------------------------------------------------

_REVIEW_INTERVALS: list[tuple[int, int]] = [
    (85, 14),
    (67, 7),
    (34, 3),
    (0, 1),
]


def compute_mastery(correct: int, total: int) -> int:
    """Return mastery score in [0, 100]. Returns 0 when total is 0."""
    if total == 0:
        return 0
    return min(100, max(0, round(correct / total * 100)))


def compute_next_review(mastery_score: int, today: str) -> str:
    """Return ISO-date string for the next scheduled review."""
    today_date = date.fromisoformat(today)
    for threshold, days in _REVIEW_INTERVALS:
        if mastery_score >= threshold:
            return (today_date + timedelta(days=days)).isoformat()
    return (today_date + timedelta(days=1)).isoformat()


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TermRecord:
    term: str
    first_seen: str
    last_reviewed: str
    review_count: int = 0
    correct_count: int = 0
    incorrect_count: int = 0
    mastery_score: int = 0
    next_review_date: str = ""

    def record_answer(self, correct: bool, today: str) -> None:
        self.last_reviewed = today
        self.review_count += 1
        if correct:
            self.correct_count += 1
        else:
            self.incorrect_count += 1
        self.mastery_score = compute_mastery(self.correct_count, self.review_count)
        self.next_review_date = compute_next_review(self.mastery_score, today)


@dataclass
class ProgressStore:
    schema_version: str = "0.2"
    terms: dict[str, TermRecord] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.terms is None:
            self.terms = {}

    # --- persistence -------------------------------------------------------

    @classmethod
    def load(cls, path: Path) -> ProgressStore:
        """Load from JSON. Returns empty store on missing or corrupted file."""
        if not path.exists():
            return cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            terms = {
                k: TermRecord(**v)
                for k, v in raw.get("terms", {}).items()
            }
            return cls(
                schema_version=raw.get("schema_version", "0.2"),
                terms=terms,
            )
        except (json.JSONDecodeError, TypeError, KeyError):
            return cls()

    def save(self, path: Path) -> None:
        """Write progress to JSON, creating parent directories if needed."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "schema_version": self.schema_version,
            "terms": {k: asdict(v) for k, v in self.terms.items()},
        }
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # --- term operations ---------------------------------------------------

    def ensure_term(self, term: str, today: str) -> TermRecord:
        """Add a term record if not already present; return the record."""
        if term not in self.terms:
            self.terms[term] = TermRecord(
                term=term,
                first_seen=today,
                last_reviewed=today,
                next_review_date=(
                    date.fromisoformat(today) + timedelta(days=1)
                ).isoformat(),
            )
        return self.terms[term]

    def record_quiz_result(
        self, term: str, correct: bool, today: str
    ) -> TermRecord:
        """Record one quiz attempt for a term and return the updated record."""
        record = self.ensure_term(term, today)
        record.record_answer(correct=correct, today=today)
        return record

    # --- reporting queries -------------------------------------------------

    def total_terms(self) -> int:
        return len(self.terms)

    def mastered_terms(self) -> list[TermRecord]:
        """Return terms with mastery_score >= 85."""
        return [r for r in self.terms.values() if r.mastery_score >= 85]

    def due_for_review(self, today: str) -> list[TermRecord]:
        """Return terms whose next_review_date is on or before today."""
        return [
            r for r in self.terms.values()
            if r.next_review_date <= today
        ]

    def weakest_terms(self, n: int = 5) -> list[TermRecord]:
        """Return up to n reviewed terms sorted by mastery score ascending."""
        reviewed = [r for r in self.terms.values() if r.review_count > 0]
        return sorted(reviewed, key=lambda r: r.mastery_score)[:n]
