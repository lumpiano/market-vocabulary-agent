"""Knowledge graph module for Market Vocabulary Agent.

Builds and maintains a graph of relationships between vocabulary terms
across lessons. Pure data module — no Gemini imports.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "0.1"
AI_CONFIDENCE_THRESHOLD = 0.70
SAME_LESSON_CONFIDENCE = 0.50
SAME_CATEGORY_CONFIDENCE = 0.60
CONFIDENCE_BOOST_PER_LESSON = 0.05

RELATIONSHIP_TYPES = frozenset({
    "related_to", "causes", "affects", "measured_by", "opposite_of",
    "part_of", "example_of", "used_in", "influenced_by",
})

_SYMMETRIC_TYPES = frozenset({"related_to", "opposite_of"})

KNOWN_ALIASES: dict[str, str] = {
    "cpi": "consumer price index",
    "gdp": "gross domestic product",
    "fed": "federal reserve",
    "fomc": "federal open market committee",
    "pe": "price-to-earnings ratio",
    "p/e": "price-to-earnings ratio",
    "pe ratio": "price-to-earnings ratio",
    "p/e ratio": "price-to-earnings ratio",
    "eps": "earnings per share",
    "pmi": "purchasing managers index",
    "purchasing managers' index": "purchasing managers index",
    "vix": "volatility index",
    "ecb": "european central bank",
    "bps": "basis points",
    "basis pts": "basis points",
    "ffr": "federal funds rate",
    "treasuries": "treasury yield",
    "t-bill": "treasury yield",
    "t-bills": "treasury yield",
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def normalize_term(term: str) -> str:
    """Normalize a vocabulary term for use as a lookup key.

    Steps:
    1. Lowercase and strip leading/trailing whitespace.
    2. Collapse multiple internal spaces to one.
    3. Remove punctuation except hyphens and apostrophes.
    4. Resolve KNOWN_ALIASES.
    """
    # Step 1: lowercase + strip
    result = term.lower().strip()
    # Step 2: collapse internal spaces
    result = re.sub(r"\s+", " ", result)
    # Step 3: remove punctuation except hyphens and apostrophes
    result = re.sub(r"[^\w\s\-']", "", result)
    # collapse again in case punctuation removal created extra spaces
    result = re.sub(r"\s+", " ", result).strip()
    # Step 4: resolve aliases
    result = KNOWN_ALIASES.get(result, result)
    return result


def is_confident_enough(
    confidence_score: float,
    threshold: float = AI_CONFIDENCE_THRESHOLD,
) -> bool:
    """Return True when confidence_score meets or exceeds threshold."""
    return confidence_score >= threshold


def _edge_key(source: str, target: str, relationship_type: str) -> str:
    """Compute a stable dict key for an edge.

    Symmetric relationship types use alphabetical ordering of the two
    endpoints so that (A, B) and (B, A) yield the same key.
    Directional types preserve source → target ordering.
    """
    if relationship_type in _SYMMETRIC_TYPES:
        a, b = sorted([source, target])
        return f"{a}|{relationship_type}|{b}"
    return f"{source}|{relationship_type}|{target}"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TermNode:
    """A vocabulary term in the knowledge graph."""

    term: str               # display form (original capitalisation)
    normalized_term: str    # lookup key
    definition: str
    category: str
    first_seen: str         # ISO date
    last_seen: str          # ISO date
    lesson_count: int = 0
    mastery_score: int = 0
    source_lesson_dates: list = field(default_factory=list)
    related_terms: list = field(default_factory=list)  # normalized keys


@dataclass
class RelationshipEdge:
    """A directed (or symmetric) relationship between two terms."""

    source_term: str        # normalized
    target_term: str        # normalized
    relationship_type: str
    explanation: str
    confidence_score: float  # 0.0–1.0
    first_created: str       # ISO date
    last_updated: str        # ISO date
    lesson_count: int = 1
    source_lesson_dates: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Knowledge Graph
# ---------------------------------------------------------------------------

@dataclass
class KnowledgeGraph:
    """In-memory knowledge graph with persistence."""

    schema_version: str = SCHEMA_VERSION
    nodes: dict = field(default_factory=dict)   # normalized_term → TermNode
    edges: dict = field(default_factory=dict)   # edge_key → RelationshipEdge

    # --- persistence -------------------------------------------------------

    @classmethod
    def load(cls, path: Path) -> "KnowledgeGraph":
        """Load graph from JSON. Returns empty graph on any error."""
        if not Path(path).exists():
            return cls()
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
            nodes = {}
            for k, v in raw.get("nodes", {}).items():
                nodes[k] = TermNode(**v)
            edges = {}
            for k, v in raw.get("edges", {}).items():
                edges[k] = RelationshipEdge(**v)
            return cls(
                schema_version=raw.get("schema_version", SCHEMA_VERSION),
                nodes=nodes,
                edges=edges,
            )
        except (json.JSONDecodeError, TypeError, KeyError, ValueError):
            return cls()

    def save(self, path: Path) -> None:
        """Persist graph to JSON, creating parent directories as needed."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "schema_version": self.schema_version,
            "nodes": {k: asdict(v) for k, v in self.nodes.items()},
            "edges": {k: asdict(v) for k, v in self.edges.items()},
        }
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # --- node operations ---------------------------------------------------

    def ensure_node(
        self,
        term: str,
        definition: str,
        category: str,
        lesson_date: str,
    ) -> TermNode:
        """Add a node if absent; update metadata on subsequent encounters."""
        key = normalize_term(term)
        if key not in self.nodes:
            self.nodes[key] = TermNode(
                term=term,
                normalized_term=key,
                definition=definition,
                category=category,
                first_seen=lesson_date,
                last_seen=lesson_date,
                lesson_count=1,
                source_lesson_dates=[lesson_date],
            )
        else:
            node = self.nodes[key]
            node.last_seen = lesson_date
            if lesson_date not in node.source_lesson_dates:
                node.source_lesson_dates.append(lesson_date)
                node.lesson_count += 1
            # Update definition if the new one is longer (more descriptive)
            if len(definition) > len(node.definition):
                node.definition = definition
        return self.nodes[key]

    def sync_mastery(self, progress_store: object) -> None:
        """Copy mastery scores from ProgressStore into nodes."""
        if not hasattr(progress_store, "terms"):
            return
        # Build a normalized-key → mastery mapping from the progress store
        for raw_term, record in progress_store.terms.items():
            nkey = normalize_term(raw_term)
            if nkey in self.nodes:
                self.nodes[nkey].mastery_score = record.mastery_score

    # --- edge operations ---------------------------------------------------

    def ensure_edge(
        self,
        source: str,
        target: str,
        relationship_type: str,
        explanation: str,
        confidence_score: float,
        lesson_date: str,
    ) -> RelationshipEdge:
        """Add an edge if absent; update on repeat encounter from new lesson."""
        src = normalize_term(source)
        tgt = normalize_term(target)
        key = _edge_key(src, tgt, relationship_type)

        if key not in self.edges:
            self.edges[key] = RelationshipEdge(
                source_term=src,
                target_term=tgt,
                relationship_type=relationship_type,
                explanation=explanation,
                confidence_score=confidence_score,
                first_created=lesson_date,
                last_updated=lesson_date,
                lesson_count=1,
                source_lesson_dates=[lesson_date],
            )
        else:
            edge = self.edges[key]
            if lesson_date not in edge.source_lesson_dates:
                edge.last_updated = lesson_date
                edge.source_lesson_dates.append(lesson_date)
                edge.lesson_count += 1
                # Boost confidence, capped at 1.0
                edge.confidence_score = min(
                    1.0,
                    edge.confidence_score + CONFIDENCE_BOOST_PER_LESSON,
                )
                # Update explanation if new one is longer
                if len(explanation) > len(edge.explanation):
                    edge.explanation = explanation
        return self.edges[key]

    # --- lesson-level update -----------------------------------------------

    def update_from_lesson(self, lesson: object, lesson_date: str) -> None:
        """Process one lesson: ensure nodes and same-lesson related_to edges."""
        terms = lesson.terms  # list of VocabularyTerm-like objects
        category = getattr(lesson, "theme", "General")

        # Ensure a node for every term in the lesson
        for vt in terms:
            self.ensure_node(
                term=vt.term,
                definition=vt.plain_english_definition,
                category=category,
                lesson_date=lesson_date,
            )

        # Create C(5,2) = 10 same-lesson "related_to" edges
        term_list = list(terms)
        for i in range(len(term_list)):
            for j in range(i + 1, len(term_list)):
                self.ensure_edge(
                    source=term_list[i].term,
                    target=term_list[j].term,
                    relationship_type="related_to",
                    explanation=(
                        f"Both '{term_list[i].term}' and '{term_list[j].term}' "
                        f"appeared in the same {category} lesson on {lesson_date}."
                    ),
                    confidence_score=SAME_LESSON_CONFIDENCE,
                    lesson_date=lesson_date,
                )

        # Update related_terms lists on each node
        for vt in terms:
            nkey = normalize_term(vt.term)
            if nkey not in self.nodes:
                continue
            connected = set()
            for edge in self.edges.values():
                if edge.source_term == nkey:
                    connected.add(edge.target_term)
                elif edge.target_term == nkey:
                    connected.add(edge.source_term)
            self.nodes[nkey].related_terms = sorted(connected)

    # --- query methods -----------------------------------------------------

    def connections_for_term(self, term: str) -> list[RelationshipEdge]:
        """Return all edges where the term appears as source OR target."""
        nkey = normalize_term(term)
        return [
            e for e in self.edges.values()
            if e.source_term == nkey or e.target_term == nkey
        ]

    def strongest_connections(
        self, term: str, n: int = 5
    ) -> list[RelationshipEdge]:
        """Return up to n connections sorted by confidence descending."""
        connections = self.connections_for_term(term)
        return sorted(
            connections, key=lambda e: e.confidence_score, reverse=True
        )[:n]

    def recommend_next_term(self, term: str) -> Optional[str]:
        """Return the normalized key of the connected term with lowest mastery.

        Tiebreak: highest confidence_score. Returns None if the term is
        isolated or has no connections to known nodes.
        """
        nkey = normalize_term(term)
        connections = self.connections_for_term(term)
        if not connections:
            return None

        candidates: list[tuple[int, float, str]] = []
        for edge in connections:
            other = edge.target_term if edge.source_term == nkey else edge.source_term
            if other in self.nodes:
                mastery = self.nodes[other].mastery_score
                candidates.append((mastery, edge.confidence_score, other))

        if not candidates:
            return None

        # Sort by mastery asc, then confidence desc (negate for descending)
        candidates.sort(key=lambda x: (x[0], -x[1]))
        return candidates[0][2]

    def stats(self) -> dict:
        """Return summary statistics about the knowledge graph."""
        # Compute degree for each node
        degree: dict[str, int] = {k: 0 for k in self.nodes}
        for edge in self.edges.values():
            if edge.source_term in degree:
                degree[edge.source_term] += 1
            if edge.target_term in degree:
                degree[edge.target_term] += 1

        # Most connected (degree > 0), top 5
        connected_sorted = sorted(
            [(d, k) for k, d in degree.items() if d > 0],
            reverse=True,
        )
        most_connected = [(k, d) for d, k in connected_sorted[:5]]

        # Isolated terms (degree == 0)
        isolated = [k for k, d in degree.items() if d == 0]

        # Strongest relationships (top 5 by confidence)
        strongest = sorted(
            self.edges.values(),
            key=lambda e: e.confidence_score,
            reverse=True,
        )[:5]

        # Category counts
        categories: dict[str, int] = {}
        for node in self.nodes.values():
            categories[node.category] = categories.get(node.category, 0) + 1

        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "most_connected_terms": most_connected,
            "isolated_terms": isolated,
            "strongest_relationships": strongest,
            "categories": categories,
        }

    # --- visualisation -----------------------------------------------------

    def to_dot(
        self,
        focus_term: Optional[str] = None,
        max_edges: int = 30,
    ) -> str:
        """Generate a Graphviz DOT string for the graph.

        focus_term is highlighted gold. Edges show rel_type and confidence%.
        At most max_edges edges are included (by confidence, descending).
        """
        focus_key = normalize_term(focus_term) if focus_term else None

        # Select top edges by confidence
        selected_edges = sorted(
            self.edges.values(),
            key=lambda e: e.confidence_score,
            reverse=True,
        )[:max_edges]

        # Collect referenced node keys
        referenced: set[str] = set()
        for edge in selected_edges:
            referenced.add(edge.source_term)
            referenced.add(edge.target_term)

        lines: list[str] = [
            "digraph knowledge_graph {",
            "    rankdir=LR;",
            '    node [shape=box, style=filled, fillcolor=lightblue];',
        ]

        # Node declarations
        for key in sorted(referenced):
            node = self.nodes.get(key)
            label = node.term if node else key
            if key == focus_key:
                lines.append(
                    f'    "{key}" [label="{label}", fillcolor=gold];'
                )
            else:
                lines.append(f'    "{key}" [label="{label}"];')

        # Edge declarations
        for edge in selected_edges:
            confidence_pct = round(edge.confidence_score * 100)
            label = f"{edge.relationship_type} ({confidence_pct}%)"
            lines.append(
                f'    "{edge.source_term}" -> "{edge.target_term}" '
                f'[label="{label}"];'
            )

        lines.append("}")
        return "\n".join(lines)
