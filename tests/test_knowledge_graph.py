"""Tests for app/knowledge_graph.py — 30 test functions."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.knowledge_graph import (
    AI_CONFIDENCE_THRESHOLD,
    SAME_LESSON_CONFIDENCE,
    KnowledgeGraph,
    RelationshipEdge,
    TermNode,
    _edge_key,
    is_confident_enough,
    normalize_term,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_lesson(terms, theme="Rates", weekday="Tuesday"):
    """Build a minimal lesson-like object without importing app.main."""
    return SimpleNamespace(
        terms=[
            SimpleNamespace(term=t[0], plain_english_definition=t[1])
            for t in terms
        ],
        theme=theme,
        weekday=weekday,
    )


_FIVE_TERMS = [
    ("Basis Point", "One one-hundredth of a percentage point."),
    ("Treasury Yield", "Return on US government bonds."),
    ("Yield Curve", "Chart comparing yields across maturities."),
    ("Consumer Price Index", "Measure of consumer price changes."),
    ("Federal Funds Rate", "Overnight inter-bank lending rate."),
]


def _five_term_lesson():
    return _make_lesson(_FIVE_TERMS)


# ---------------------------------------------------------------------------
# normalize_term tests
# ---------------------------------------------------------------------------

def test_normalize_term_lowercase():
    assert normalize_term("Treasury Yield") == "treasury yield"


def test_normalize_term_strips_whitespace():
    assert normalize_term("  basis point  ") == "basis point"


def test_normalize_term_collapses_spaces():
    assert normalize_term("yield   curve") == "yield curve"


def test_normalize_term_strips_special_chars():
    # Exclamation mark should be removed; result is lower-cased
    assert normalize_term("Yield Curve!") == "yield curve"


def test_normalize_known_alias_cpi():
    assert normalize_term("CPI") == "consumer price index"


def test_normalize_known_alias_gdp():
    assert normalize_term("GDP") == "gross domestic product"


def test_normalize_returns_original_for_unknown():
    assert normalize_term("Semiconductor Cycle") == "semiconductor cycle"


# ---------------------------------------------------------------------------
# is_confident_enough tests
# ---------------------------------------------------------------------------

def test_is_confident_enough_accepts_at_threshold():
    assert is_confident_enough(0.70) is True


def test_is_confident_enough_rejects_below_threshold():
    assert is_confident_enough(0.69) is False


# ---------------------------------------------------------------------------
# _edge_key tests
# ---------------------------------------------------------------------------

def test_edge_key_symmetric_for_related_to():
    key_ab = _edge_key("alpha", "beta", "related_to")
    key_ba = _edge_key("beta", "alpha", "related_to")
    assert key_ab == key_ba


def test_edge_key_directed_for_causes():
    key_ab = _edge_key("alpha", "beta", "causes")
    key_ba = _edge_key("beta", "alpha", "causes")
    assert key_ab != key_ba


# ---------------------------------------------------------------------------
# ensure_node tests
# ---------------------------------------------------------------------------

def test_ensure_node_creates_new():
    g = KnowledgeGraph()
    g.ensure_node("Basis Point", "One hundredth of a pct point.", "Rates", "2026-07-15")
    assert "basis point" in g.nodes
    node = g.nodes["basis point"]
    assert node.term == "Basis Point"
    assert node.first_seen == "2026-07-15"
    assert node.lesson_count == 1


def test_ensure_node_prevents_duplicate():
    g = KnowledgeGraph()
    g.ensure_node("Basis Point", "Def A", "Rates", "2026-07-15")
    g.ensure_node("Basis Point", "Def A again", "Rates", "2026-07-15")
    # Only one node should exist
    assert len(g.nodes) == 1
    # first_seen unchanged
    assert g.nodes["basis point"].first_seen == "2026-07-15"


def test_ensure_node_updates_last_seen_and_lesson_count():
    g = KnowledgeGraph()
    g.ensure_node("Basis Point", "Def A", "Rates", "2026-07-15")
    g.ensure_node("Basis Point", "Def A", "Rates", "2026-07-17")
    node = g.nodes["basis point"]
    assert node.last_seen == "2026-07-17"
    assert node.lesson_count == 2


# ---------------------------------------------------------------------------
# ensure_edge tests
# ---------------------------------------------------------------------------

def test_ensure_edge_creates_new():
    g = KnowledgeGraph()
    g.ensure_edge(
        "Basis Point", "Treasury Yield", "related_to",
        "Both appear together.", 0.50, "2026-07-15"
    )
    assert len(g.edges) == 1


def test_ensure_edge_prevents_duplicate_key():
    g = KnowledgeGraph()
    g.ensure_edge(
        "Basis Point", "Treasury Yield", "related_to",
        "Co-occurring.", 0.50, "2026-07-15"
    )
    # Same edge, same date → still only one entry
    g.ensure_edge(
        "Treasury Yield", "Basis Point", "related_to",
        "Co-occurring (reversed).", 0.50, "2026-07-15"
    )
    assert len(g.edges) == 1


def test_ensure_edge_boosts_confidence_on_repeat():
    g = KnowledgeGraph()
    g.ensure_edge(
        "Basis Point", "Treasury Yield", "related_to",
        "Co-occurring.", 0.50, "2026-07-15"
    )
    g.ensure_edge(
        "Basis Point", "Treasury Yield", "related_to",
        "Co-occurring.", 0.50, "2026-07-17"
    )
    edge = list(g.edges.values())[0]
    assert edge.confidence_score > 0.50


def test_ensure_edge_increments_lesson_count_on_repeat():
    g = KnowledgeGraph()
    g.ensure_edge(
        "Basis Point", "Treasury Yield", "related_to",
        "Co-occurring.", 0.50, "2026-07-15"
    )
    g.ensure_edge(
        "Basis Point", "Treasury Yield", "related_to",
        "Co-occurring.", 0.50, "2026-07-17"
    )
    edge = list(g.edges.values())[0]
    assert edge.lesson_count == 2


# ---------------------------------------------------------------------------
# update_from_lesson tests
# ---------------------------------------------------------------------------

def test_update_from_lesson_creates_nodes():
    g = KnowledgeGraph()
    lesson = _five_term_lesson()
    g.update_from_lesson(lesson, "2026-07-15")
    assert len(g.nodes) == 5


def test_update_from_lesson_creates_edges():
    g = KnowledgeGraph()
    lesson = _five_term_lesson()
    g.update_from_lesson(lesson, "2026-07-15")
    # C(5,2) = 10
    assert len(g.edges) == 10


def test_update_from_lesson_populates_related_terms():
    g = KnowledgeGraph()
    lesson = _five_term_lesson()
    g.update_from_lesson(lesson, "2026-07-15")
    # Each node should list 4 related terms (connected to all other 4)
    for node in g.nodes.values():
        assert len(node.related_terms) == 4


# ---------------------------------------------------------------------------
# connections_for_term tests
# ---------------------------------------------------------------------------

def test_connections_for_term_returns_both_directions():
    g = KnowledgeGraph()
    # Use a directed edge type
    g.ensure_node("Federal Funds Rate", "Overnight rate.", "Rates", "2026-07-15")
    g.ensure_node("Treasury Yield", "Bond return.", "Rates", "2026-07-15")
    g.ensure_edge(
        "Federal Funds Rate", "Treasury Yield", "affects",
        "FFR changes affect yields.", 0.80, "2026-07-15"
    )
    # Connections from the SOURCE perspective
    src_conns = g.connections_for_term("Federal Funds Rate")
    assert len(src_conns) == 1
    # Connections from the TARGET perspective
    tgt_conns = g.connections_for_term("Treasury Yield")
    assert len(tgt_conns) == 1


# ---------------------------------------------------------------------------
# strongest_connections tests
# ---------------------------------------------------------------------------

def test_strongest_connections_ordered_by_confidence():
    g = KnowledgeGraph()
    g.ensure_node("A", "def A", "Cat", "2026-07-15")
    g.ensure_node("B", "def B", "Cat", "2026-07-15")
    g.ensure_node("C", "def C", "Cat", "2026-07-15")
    g.ensure_edge("A", "B", "related_to", "Low confidence.", 0.50, "2026-07-15")
    g.ensure_edge("A", "C", "affects", "High confidence.", 0.90, "2026-07-15")
    results = g.strongest_connections("A", n=5)
    assert results[0].confidence_score >= results[-1].confidence_score


# ---------------------------------------------------------------------------
# recommend_next_term tests
# ---------------------------------------------------------------------------

def test_recommend_next_term_prefers_low_mastery():
    g = KnowledgeGraph()
    g.ensure_node("A", "def A", "Cat", "2026-07-15")
    g.ensure_node("B", "def B", "Cat", "2026-07-15")
    g.ensure_node("C", "def C", "Cat", "2026-07-15")
    # B has mastery 80, C has mastery 20
    g.nodes["b"].mastery_score = 80
    g.nodes["c"].mastery_score = 20
    g.ensure_edge("A", "B", "related_to", "desc", 0.70, "2026-07-15")
    g.ensure_edge("A", "C", "related_to", "desc", 0.70, "2026-07-15")
    recommendation = g.recommend_next_term("A")
    assert recommendation == "c"


def test_recommend_next_term_returns_none_for_isolated():
    g = KnowledgeGraph()
    g.ensure_node("Isolated Term", "lone node.", "Cat", "2026-07-15")
    result = g.recommend_next_term("Isolated Term")
    assert result is None


# ---------------------------------------------------------------------------
# stats tests
# ---------------------------------------------------------------------------

def test_graph_stats_totals():
    g = KnowledgeGraph()
    lesson = _five_term_lesson()
    g.update_from_lesson(lesson, "2026-07-15")
    s = g.stats()
    assert s["total_nodes"] == 5
    assert s["total_edges"] == 10


def test_graph_stats_isolated_terms():
    g = KnowledgeGraph()
    # Add one term without any edges
    g.ensure_node("Lone Wolf", "isolated.", "Cat", "2026-07-15")
    s = g.stats()
    assert "lone wolf" in s["isolated_terms"]


# ---------------------------------------------------------------------------
# save / load tests
# ---------------------------------------------------------------------------

def test_save_and_load_roundtrip():
    g = KnowledgeGraph()
    lesson = _five_term_lesson()
    g.update_from_lesson(lesson, "2026-07-15")

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "graph.json"
        g.save(path)
        g2 = KnowledgeGraph.load(path)

    assert len(g2.nodes) == len(g.nodes)
    assert len(g2.edges) == len(g.edges)
    # Spot-check one node
    assert "basis point" in g2.nodes
    assert g2.nodes["basis point"].term == "Basis Point"


def test_load_missing_file_returns_empty():
    g = KnowledgeGraph.load(Path("/nonexistent/path/graph.json"))
    assert len(g.nodes) == 0
    assert len(g.edges) == 0


def test_load_corrupted_file_returns_empty():
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        f.write("{ this is not valid json }")
        tmp_path = Path(f.name)

    g = KnowledgeGraph.load(tmp_path)
    tmp_path.unlink(missing_ok=True)
    assert len(g.nodes) == 0
    assert len(g.edges) == 0
