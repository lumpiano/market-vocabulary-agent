"""Tests for app.progress — mastery formula, scheduling, and persistence."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from app.progress import (
    ProgressStore,
    TermRecord,
    compute_mastery,
    compute_next_review,
)


# ---------------------------------------------------------------------------
# compute_mastery
# ---------------------------------------------------------------------------

def test_mastery_zero_reviews():
    assert compute_mastery(0, 0) == 0


def test_mastery_all_correct():
    assert compute_mastery(5, 5) == 100


def test_mastery_all_incorrect():
    assert compute_mastery(0, 5) == 0


def test_mastery_partial_75():
    assert compute_mastery(3, 4) == 75


def test_mastery_partial_67():
    # round(2/3 * 100) == 67
    assert compute_mastery(2, 3) == 67


def test_mastery_never_exceeds_100():
    assert compute_mastery(10, 10) <= 100


def test_mastery_never_below_0():
    assert compute_mastery(0, 10) >= 0


# ---------------------------------------------------------------------------
# compute_next_review — band boundaries
# ---------------------------------------------------------------------------

TODAY = "2026-07-17"


def test_next_review_needs_work_band():
    # mastery 0–33 → +1 day
    assert compute_next_review(0, TODAY) == "2026-07-18"
    assert compute_next_review(33, TODAY) == "2026-07-18"


def test_next_review_learning_band():
    # mastery 34–66 → +3 days
    assert compute_next_review(34, TODAY) == "2026-07-20"
    assert compute_next_review(66, TODAY) == "2026-07-20"


def test_next_review_confident_band():
    # mastery 67–84 → +7 days
    assert compute_next_review(67, TODAY) == "2026-07-24"
    assert compute_next_review(84, TODAY) == "2026-07-24"


def test_next_review_mastered_band():
    # mastery 85–100 → +14 days  (July 17 + 14 = July 31)
    assert compute_next_review(85, TODAY) == "2026-07-31"
    assert compute_next_review(100, TODAY) == "2026-07-31"


def test_next_review_exact_boundary_34():
    assert compute_next_review(34, TODAY) == "2026-07-20"


def test_next_review_exact_boundary_67():
    assert compute_next_review(67, TODAY) == "2026-07-24"


def test_next_review_exact_boundary_85():
    assert compute_next_review(85, TODAY) == "2026-07-31"


# ---------------------------------------------------------------------------
# TermRecord
# ---------------------------------------------------------------------------

def test_new_term_record_defaults():
    record = TermRecord(term="Basis Point", first_seen=TODAY, last_reviewed=TODAY)
    assert record.review_count == 0
    assert record.correct_count == 0
    assert record.incorrect_count == 0
    assert record.mastery_score == 0


def test_record_correct_answer():
    record = TermRecord(term="Basis Point", first_seen=TODAY, last_reviewed=TODAY)
    record.record_answer(correct=True, today=TODAY)
    assert record.review_count == 1
    assert record.correct_count == 1
    assert record.incorrect_count == 0
    assert record.mastery_score == 100


def test_record_incorrect_answer():
    record = TermRecord(term="Basis Point", first_seen=TODAY, last_reviewed=TODAY)
    record.record_answer(correct=False, today=TODAY)
    assert record.review_count == 1
    assert record.correct_count == 0
    assert record.incorrect_count == 1
    assert record.mastery_score == 0


def test_record_mixed_answers_mastery():
    record = TermRecord(term="Treasury Yield", first_seen=TODAY, last_reviewed=TODAY)
    record.record_answer(correct=True, today="2026-07-15")
    record.record_answer(correct=False, today="2026-07-16")
    record.record_answer(correct=True, today=TODAY)
    assert record.review_count == 3
    assert record.correct_count == 2
    assert record.incorrect_count == 1
    assert record.mastery_score == 67  # round(2/3 * 100)


def test_record_answer_updates_last_reviewed():
    record = TermRecord(term="Contango", first_seen="2026-07-15", last_reviewed="2026-07-15")
    record.record_answer(correct=True, today=TODAY)
    assert record.last_reviewed == TODAY


def test_record_answer_schedules_next_review_mastered():
    record = TermRecord(term="Contango", first_seen=TODAY, last_reviewed=TODAY)
    record.record_answer(correct=True, today=TODAY)
    # mastery = 100 → 14 days → 2026-07-31
    assert record.next_review_date == "2026-07-31"


def test_record_answer_schedules_next_review_needs_work():
    record = TermRecord(term="Contango", first_seen=TODAY, last_reviewed=TODAY)
    record.record_answer(correct=False, today=TODAY)
    # mastery = 0 → 1 day → 2026-07-18
    assert record.next_review_date == "2026-07-18"


def test_mastery_score_bounded_at_100():
    record = TermRecord(term="Test", first_seen=TODAY, last_reviewed=TODAY)
    for _ in range(10):
        record.record_answer(correct=True, today=TODAY)
    assert record.mastery_score == 100


def test_mastery_score_bounded_at_0():
    record = TermRecord(term="Test", first_seen=TODAY, last_reviewed=TODAY)
    for _ in range(10):
        record.record_answer(correct=False, today=TODAY)
    assert record.mastery_score == 0


# ---------------------------------------------------------------------------
# ProgressStore — term operations
# ---------------------------------------------------------------------------

def test_ensure_term_creates_new():
    store = ProgressStore()
    record = store.ensure_term("Basis Point", TODAY)
    assert record.term == "Basis Point"
    assert record.first_seen == TODAY
    assert "Basis Point" in store.terms


def test_ensure_term_does_not_overwrite_existing():
    store = ProgressStore()
    store.ensure_term("Basis Point", "2026-07-15")
    store.ensure_term("Basis Point", TODAY)
    assert store.terms["Basis Point"].first_seen == "2026-07-15"


def test_record_quiz_result_correct():
    store = ProgressStore()
    record = store.record_quiz_result("Basis Point", correct=True, today=TODAY)
    assert record.correct_count == 1
    assert record.mastery_score == 100


def test_record_quiz_result_incorrect():
    store = ProgressStore()
    record = store.record_quiz_result("Basis Point", correct=False, today=TODAY)
    assert record.incorrect_count == 1
    assert record.mastery_score == 0


def test_total_terms():
    store = ProgressStore()
    store.ensure_term("Basis Point", TODAY)
    store.ensure_term("Treasury Yield", TODAY)
    assert store.total_terms() == 2


def test_mastered_terms():
    store = ProgressStore()
    store.record_quiz_result("Basis Point", correct=True, today=TODAY)
    store.record_quiz_result("Treasury Yield", correct=False, today=TODAY)
    mastered = store.mastered_terms()
    assert len(mastered) == 1
    assert mastered[0].term == "Basis Point"


def test_due_for_review():
    store = ProgressStore()
    store.ensure_term("Contango", "2026-07-15")
    store.terms["Contango"].next_review_date = "2026-07-16"   # overdue
    store.ensure_term("Backwardation", "2026-07-15")
    store.terms["Backwardation"].next_review_date = "2026-07-20"  # future
    due = store.due_for_review(TODAY)
    assert len(due) == 1
    assert due[0].term == "Contango"


def test_due_for_review_includes_today():
    store = ProgressStore()
    store.ensure_term("Spot Price", TODAY)
    store.terms["Spot Price"].next_review_date = TODAY
    due = store.due_for_review(TODAY)
    assert len(due) == 1


def test_weakest_terms_ordering():
    store = ProgressStore()
    store.record_quiz_result("A", correct=True, today=TODAY)    # mastery 100
    store.record_quiz_result("B", correct=False, today=TODAY)   # mastery 0
    store.record_quiz_result("C", correct=True, today=TODAY)
    store.record_quiz_result("C", correct=False, today=TODAY)   # mastery 50
    weakest = store.weakest_terms(n=2)
    assert weakest[0].term == "B"
    assert weakest[0].mastery_score == 0
    assert weakest[1].mastery_score == 50


def test_weakest_terms_excludes_unreviewed():
    store = ProgressStore()
    store.ensure_term("Unreviewed Term", TODAY)  # review_count stays 0
    store.record_quiz_result("Reviewed", correct=False, today=TODAY)
    weakest = store.weakest_terms()
    terms = [r.term for r in weakest]
    assert "Unreviewed Term" not in terms
    assert "Reviewed" in terms


# ---------------------------------------------------------------------------
# ProgressStore — load / save
# ---------------------------------------------------------------------------

def test_save_and_load_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "progress.json"
        store = ProgressStore()
        store.record_quiz_result("Basis Point", correct=True, today=TODAY)
        store.save(path)

        loaded = ProgressStore.load(path)
        assert loaded.total_terms() == 1
        record = loaded.terms["Basis Point"]
        assert record.correct_count == 1
        assert record.mastery_score == 100
        assert record.first_seen == TODAY


def test_load_missing_file_returns_empty_store():
    path = Path("/nonexistent/path/progress.json")
    store = ProgressStore.load(path)
    assert store.total_terms() == 0


def test_load_corrupted_file_returns_empty_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "progress.json"
        path.write_text("not valid json {{ }", encoding="utf-8")
        store = ProgressStore.load(path)
        assert store.total_terms() == 0


def test_load_empty_terms_object():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "progress.json"
        path.write_text(
            json.dumps({"schema_version": "0.2", "terms": {}}),
            encoding="utf-8",
        )
        store = ProgressStore.load(path)
        assert store.total_terms() == 0


def test_save_creates_parent_directories():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "nested" / "dirs" / "progress.json"
        store = ProgressStore()
        store.ensure_term("Basis Point", TODAY)
        store.save(path)
        assert path.exists()


def test_schema_version_preserved_on_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "progress.json"
        store = ProgressStore()
        store.save(path)
        loaded = ProgressStore.load(path)
        assert loaded.schema_version == "0.2"


def test_multiple_terms_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "progress.json"
        store = ProgressStore()
        store.record_quiz_result("Contango", correct=True, today=TODAY)
        store.record_quiz_result("Backwardation", correct=False, today=TODAY)
        store.record_quiz_result("Spot Price", correct=True, today=TODAY)
        store.save(path)

        loaded = ProgressStore.load(path)
        assert loaded.total_terms() == 3
        assert loaded.terms["Contango"].mastery_score == 100
        assert loaded.terms["Backwardation"].mastery_score == 0
        assert loaded.terms["Spot Price"].correct_count == 1
