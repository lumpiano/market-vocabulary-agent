from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import ValidationError

from app.knowledge_graph import KnowledgeGraph, RELATIONSHIP_TYPES, normalize_term
from app.models import MarketLesson
from app.progress import ProgressStore


THEMES = {
    "Monday": "Corporate earnings and company fundamentals",
    "Tuesday": "Interest rates, bonds, inflation, and the Federal Reserve",
    "Wednesday": "Commodities",
    "Thursday": "Technology, AI, semiconductors, software, and cloud computing",
    "Friday": "Global markets, currencies, trade, and economic indicators",
    "Saturday": "Mixed market vocabulary review and retrieval practice",
    "Sunday": "Weekly recap and weak-area review",
}


FALLBACK_TERMS = {
    "Monday": [
        "Earnings Per Share",
        "Revenue",
        "Operating Margin",
        "Forward Guidance",
        "Price-to-Earnings Ratio",
    ],
    "Tuesday": [
        "Basis Point",
        "Treasury Yield",
        "Yield Curve",
        "Consumer Price Index",
        "Federal Funds Rate",
    ],
    "Wednesday": [
        "Spot Price",
        "Futures Contract",
        "Contango",
        "Backwardation",
        "Inventory Report",
    ],
    "Thursday": [
        "Capital Expenditure",
        "Data Center",
        "Semiconductor Cycle",
        "Gross Margin",
        "Recurring Revenue",
    ],
    "Friday": [
        "Exchange Rate",
        "Purchasing Managers' Index",
        "Trade Balance",
        "Gross Domestic Product",
        "Emerging Market",
    ],
    "Saturday": [
        "Market Capitalization",
        "Volatility",
        "Liquidity",
        "Diversification",
        "Benchmark",
    ],
    "Sunday": [
        "Inflation",
        "Interest Rate",
        "Bond Yield",
        "Corporate Earnings",
        "Commodity Price",
    ],
}


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a beginner-friendly daily market vocabulary lesson."
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Create a local sample lesson without calling Gemini.",
    )

    parser.add_argument(
        "--search",
        action="store_true",
        help="Allow Gemini to use Google Search grounding for current research.",
    )

    parser.add_argument(
        "--record-quiz",
        metavar="TERM",
        help="Record a quiz result for a vocabulary term (use with --result).",
    )

    parser.add_argument(
        "--result",
        choices=["correct", "incorrect"],
        help="Outcome of the quiz attempt (required with --record-quiz).",
    )

    parser.add_argument(
        "--progress",
        action="store_true",
        help="Show the progress dashboard.",
    )

    parser.add_argument(
        "--graph-term",
        metavar="TERM",
        help="Show knowledge graph connections for a vocabulary term.",
    )

    parser.add_argument(
        "--graph-stats",
        action="store_true",
        help="Show knowledge graph statistics.",
    )

    parser.add_argument(
        "--rebuild-graph",
        action="store_true",
        help="Rebuild the knowledge graph from all saved lessons.",
    )

    return parser.parse_args()


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_settings(project_root: Path) -> dict[str, str]:
    env_path = project_root / ".env"
    load_dotenv(env_path)

    return {
        "api_key": os.getenv("GEMINI_API_KEY", "").strip(),
        "model": os.getenv("GEMINI_MODEL", "gemini-3.5-flash").strip(),
        "timezone": os.getenv("TIMEZONE", "America/New_York").strip(),
        "output_dir": os.getenv("OUTPUT_DIR", "data/outputs").strip(),
        "bloomberg_inbox": os.getenv(
            "BLOOMBERG_INBOX",
            "data/bloomberg_inbox/today.txt",
        ).strip(),
        "enable_google_search": os.getenv(
            "ENABLE_GOOGLE_SEARCH",
            "false",
        ).strip().lower(),
        "progress_dir": os.getenv("PROGRESS_DIR", "data/progress").strip(),
        "graph_dir": os.getenv("GRAPH_DIR", "data/knowledge_graph").strip(),
    }


def get_current_datetime(timezone_name: str) -> datetime:
    try:
        timezone = ZoneInfo(timezone_name)
    except Exception as exc:
        raise ValueError(
            f"Invalid timezone '{timezone_name}'. "
            "Use a value such as America/New_York."
        ) from exc

    return datetime.now(timezone)


def resolve_path(project_root: Path, configured_path: str) -> Path:
    path = Path(configured_path)

    if path.is_absolute():
        return path

    return project_root / path


def read_bloomberg_notes(inbox_path: Path) -> list[str]:
    if not inbox_path.exists():
        inbox_path.parent.mkdir(parents=True, exist_ok=True)
        inbox_path.write_text("", encoding="utf-8")
        return []

    text = inbox_path.read_text(encoding="utf-8")

    notes = []

    for line in text.splitlines():
        cleaned_line = line.strip()

        if not cleaned_line:
            continue

        cleaned_line = cleaned_line.lstrip("-* ").strip()

        if cleaned_line:
            notes.append(cleaned_line)

    return notes


def create_dry_run_lesson(
    lesson_date: str,
    weekday: str,
    theme: str,
    bloomberg_notes: list[str],
) -> MarketLesson:
    fallback = FALLBACK_TERMS[weekday]

    term_explanations = {
        "Basis Point": {
            "definition": (
                "A basis point is one one-hundredth of one percentage point."
            ),
            "analogy": (
                "Think of a dollar divided into 10,000 tiny pieces. "
                "One basis point is one of those pieces when measuring percentages."
            ),
            "example": (
                "If the Federal Reserve raises a rate from 5.00% to 5.25%, "
                "the increase is 25 basis points."
            ),
            "importance": (
                "Small rate changes can affect borrowing costs, bonds, stocks, "
                "mortgages, and business decisions."
            ),
        },
        "Treasury Yield": {
            "definition": (
                "A Treasury yield is the return investors expect from holding "
                "a United States government debt security."
            ),
            "analogy": (
                "It is similar to the interest you earn for lending money, "
                "except the borrower is the United States government."
            ),
            "example": (
                "A rising 10-year Treasury yield can make bonds more attractive "
                "compared with expensive growth stocks."
            ),
            "importance": (
                "Treasury yields influence mortgage rates, corporate borrowing "
                "costs, stock valuations, and the wider economy."
            ),
        },
        "Yield Curve": {
            "definition": (
                "The yield curve compares interest rates on government bonds "
                "with different maturity dates."
            ),
            "analogy": (
                "Imagine comparing the rental price for borrowing money for "
                "three months, two years, ten years, and thirty years."
            ),
            "example": (
                "An inverted yield curve occurs when some short-term Treasury "
                "yields are higher than long-term yields."
            ),
            "importance": (
                "Investors study its shape for clues about interest rates, "
                "economic growth, inflation, and recession risk."
            ),
        },
        "Consumer Price Index": {
            "definition": (
                "The Consumer Price Index, or CPI, measures average price changes "
                "for a basket of goods and services commonly purchased by consumers."
            ),
            "analogy": (
                "It is like checking the same household shopping cart each month "
                "to see whether the total price has risen or fallen."
            ),
            "example": (
                "A hotter-than-expected CPI report may cause investors to expect "
                "interest rates to stay higher for longer."
            ),
            "importance": (
                "CPI is a major inflation indicator that can affect Federal Reserve "
                "policy, bond yields, currencies, and stocks."
            ),
        },
        "Federal Funds Rate": {
            "definition": (
                "The federal funds rate is the overnight interest rate at which "
                "banks lend reserve balances to one another."
            ),
            "analogy": (
                "It is like a base rental price for very short-term money inside "
                "the banking system."
            ),
            "example": (
                "When the Federal Reserve raises its target range, many consumer "
                "and business borrowing rates may also increase."
            ),
            "importance": (
                "It is one of the Federal Reserve's main tools for influencing "
                "inflation, employment, borrowing, and economic activity."
            ),
        },
    }

    terms = []

    for term_name in fallback:
        explanation = term_explanations.get(
            term_name,
            {
                "definition": (
                    f"{term_name} is an important concept used to understand "
                    f"{theme.lower()}."
                ),
                "analogy": (
                    f"Think of {term_name} as one instrument on a market dashboard."
                ),
                "example": (
                    f"Investors may discuss {term_name} when evaluating changes "
                    f"in {theme.lower()}."
                ),
                "importance": (
                    f"Understanding {term_name} helps explain why financial "
                    "markets may rise, fall, or react differently."
                ),
            },
        )

        terms.append(
            {
                "term": term_name,
                "plain_english_definition": explanation["definition"],
                "everyday_analogy": explanation["analogy"],
                "market_example": explanation["example"],
                "why_it_matters": explanation["importance"],
            }
        )

    lesson_data = {
        "lesson_date": lesson_date,
        "weekday": weekday,
        "theme": theme,
        "bloomberg_notes_used": bloomberg_notes,
        "terms": terms,
        "cause_and_effect_chain": [
            "Inflation comes in higher than investors expected.",
            "Investors expect the Federal Reserve to keep interest rates higher.",
            "Treasury yields rise.",
            "Borrowing becomes more expensive.",
            "Some high-growth stock valuations may decline.",
        ],
        "quiz": {
            "question": (
                "Which term means one one-hundredth of one percentage point?"
                if weekday == "Tuesday"
                else (
                    f"Which of the following is a key vocabulary term "
                    f"for {weekday}'s market theme?"
                )
            ),
            "choices": [
                FALLBACK_TERMS[weekday][0],
                FALLBACK_TERMS[weekday][1],
                FALLBACK_TERMS[weekday][2],
                FALLBACK_TERMS[weekday][3],
            ],
            "answer": FALLBACK_TERMS[weekday][0],
            "explanation": (
                f"{FALLBACK_TERMS[weekday][0]} is the correct answer for "
                "this sample lesson."
            ),
        },
        "five_minute_study_plan": [
            "Minute 1: Read all five term names aloud.",
            "Minute 2: Read each plain-English definition.",
            "Minute 3: Review the everyday analogies.",
            "Minute 4: Follow the cause-and-effect chain from beginning to end.",
            "Minute 5: Answer the quiz without looking at the definitions.",
        ],
        "sources": [
            "Dry-run sample content generated locally without web research."
        ],
        "disclaimer": (
            "Educational information only. Not personalized financial, "
            "investment, legal, or tax advice."
        ),
    }

    return MarketLesson.model_validate(lesson_data)


def build_agent_prompt(
    lesson_date: str,
    weekday: str,
    theme: str,
    bloomberg_notes: list[str],
    search_enabled: bool,
) -> str:
    if bloomberg_notes:
        notes_text = "\n".join(f"- {note}" for note in bloomberg_notes)
    else:
        notes_text = (
            "- No Bloomberg notes were entered today. "
            "Create a general lesson for the daily theme."
        )

    source_instruction = (
        "Google Search is enabled. Use reliable current sources when a current "
        "fact, company event, economic release, number, or date is mentioned. "
        "List concise source names or source descriptions in the sources field. "
        "Clearly separate verified facts from interpretation."
        if search_enabled
        else
        "Google Search is disabled. Do not claim to have checked live prices, "
        "current market data, current news, or today's economic releases. "
        "Use stable educational examples and put "
        "'No current web research used' in the sources field."
    )

    return f"""
You are the Market Vocabulary Agent.

Create one beginner-friendly financial-market lesson.

Lesson date: {lesson_date}
Weekday: {weekday}
Daily theme: {theme}

The learner is a beginner who watches Bloomberg Live and wants to understand
why markets move. The immediate purpose is education, not live trading.

Personal learning notes:
{notes_text}

Requirements:

1. Create exactly five distinct market vocabulary terms.
2. Prioritize terms connected to the personal notes when appropriate.
3. For each term, provide:
   - a plain-English definition
   - an everyday analogy
   - a realistic market example
   - why the term matters
4. Avoid unnecessary jargon.
5. Create one cause-and-effect chain with at least four clear steps.
6. Create one multiple-choice quiz.
7. The quiz answer must exactly match one of the listed choices.
8. Create a five-minute study plan.
9. Do not promise profits.
10. Do not give personalized trading instructions.
11. Do not connect to or mention access to a brokerage account.
12. Do not claim direct access to Bloomberg.
13. Do not copy or reproduce Bloomberg articles.
14. Use this exact disclaimer:
    Educational information only. Not personalized financial, investment,
    legal, or tax advice.

Source rule:
{source_instruction}

Return only content that follows the required structured lesson schema.
""".strip()


def generate_gemini_lesson(
    settings: dict[str, str],
    lesson_date: str,
    weekday: str,
    theme: str,
    bloomberg_notes: list[str],
    search_enabled: bool,
) -> MarketLesson:
    if not settings["api_key"]:
        raise ValueError(
            "No Gemini API key was found. Add GEMINI_API_KEY to the .env file, "
            "or run with --dry-run."
        )

    client = genai.Client(api_key=settings["api_key"])

    prompt = build_agent_prompt(
        lesson_date=lesson_date,
        weekday=weekday,
        theme=theme,
        bloomberg_notes=bloomberg_notes,
        search_enabled=search_enabled,
    )

    tools = None

    if search_enabled:
        tools = [
            types.Tool(
                google_search=types.GoogleSearch()
            )
        ]

    config = types.GenerateContentConfig(
        temperature=0.3,
        response_mime_type="application/json",
        response_schema=MarketLesson,
        tools=tools,
    )

    response = client.models.generate_content(
        model=settings["model"],
        contents=prompt,
        config=config,
    )

    if getattr(response, "parsed", None) is not None:
        parsed = response.parsed

        if isinstance(parsed, MarketLesson):
            return parsed

        return MarketLesson.model_validate(parsed)

    if not response.text:
        raise ValueError("Gemini returned an empty response.")

    return MarketLesson.model_validate_json(response.text)


def lesson_to_markdown(lesson: MarketLesson) -> str:
    lines = [
        f"# Market Vocabulary Lesson - {lesson.lesson_date}",
        "",
        f"**Day:** {lesson.weekday}",
        "",
        f"**Theme:** {lesson.theme}",
        "",
        "## Bloomberg Learning Notes",
        "",
    ]

    if lesson.bloomberg_notes_used:
        for note in lesson.bloomberg_notes_used:
            lines.append(f"- {note}")
    else:
        lines.append("- No personal Bloomberg notes were entered today.")

    lines.extend(
        [
            "",
            "## Today's Five Terms",
            "",
        ]
    )

    for number, vocabulary_term in enumerate(lesson.terms, start=1):
        lines.extend(
            [
                f"### {number}. {vocabulary_term.term}",
                "",
                f"**Plain-English definition:** "
                f"{vocabulary_term.plain_english_definition}",
                "",
                f"**Everyday analogy:** {vocabulary_term.everyday_analogy}",
                "",
                f"**Market example:** {vocabulary_term.market_example}",
                "",
                f"**Why it matters:** {vocabulary_term.why_it_matters}",
                "",
            ]
        )

    lines.extend(
        [
            "## Market Cause-and-Effect Chain",
            "",
        ]
    )

    for number, step in enumerate(lesson.cause_and_effect_chain, start=1):
        lines.append(f"{number}. {step}")

    lines.extend(
        [
            "",
            "## Multiple-Choice Quiz",
            "",
            lesson.quiz.question,
            "",
        ]
    )

    choice_labels = ["A", "B", "C", "D", "E", "F"]

    for index, choice in enumerate(lesson.quiz.choices):
        label = (
            choice_labels[index]
            if index < len(choice_labels)
            else str(index + 1)
        )
        lines.append(f"- {label}. {choice}")

    lines.extend(
        [
            "",
            f"**Correct answer:** {lesson.quiz.answer}",
            "",
            f"**Explanation:** {lesson.quiz.explanation}",
            "",
            "## Five-Minute Study Plan",
            "",
        ]
    )

    for step in lesson.five_minute_study_plan:
        lines.append(f"- {step}")

    lines.extend(
        [
            "",
            "## Sources",
            "",
        ]
    )

    if lesson.sources:
        for source in lesson.sources:
            lines.append(f"- {source}")
    else:
        lines.append("- No current web research used.")

    lines.extend(
        [
            "",
            "## Educational Disclaimer",
            "",
            lesson.disclaimer,
            "",
        ]
    )

    return "\n".join(lines)


def save_lesson(
    lesson: MarketLesson,
    project_root: Path,
    configured_output_dir: str,
) -> tuple[Path, Path]:
    if not lesson.lesson_date.strip():
        raise ValueError("lesson_date is empty; cannot determine output directory.")

    output_root = resolve_path(project_root, configured_output_dir)
    lesson_directory = output_root / lesson.lesson_date

    if lesson_directory == output_root:
        raise ValueError(
            f"lesson_date '{lesson.lesson_date}' resolves to the output root; "
            "refusing to write files there."
        )

    lesson_directory.mkdir(parents=True, exist_ok=True)

    json_path = lesson_directory / "lesson.json"
    markdown_path = lesson_directory / "lesson.md"

    json_path.write_text(
        json.dumps(
            lesson.model_dump(mode="json"),
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    markdown_path.write_text(
        lesson_to_markdown(lesson),
        encoding="utf-8",
    )

    return markdown_path, json_path


def get_progress_path(project_root: Path, configured_progress_dir: str) -> Path:
    return resolve_path(project_root, configured_progress_dir) / "progress.json"


def get_graph_path(project_root: Path, configured_graph_dir: str) -> Path:
    return resolve_path(project_root, configured_graph_dir) / "knowledge_graph.json"


def cmd_graph_term(term: str, graph_path: Path) -> int:
    """Show knowledge graph connections for a single vocabulary term."""
    graph = KnowledgeGraph.load(graph_path)
    nkey = normalize_term(term)

    if nkey not in graph.nodes:
        print(f"Term '{term}' not found in knowledge graph.", file=sys.stderr)
        return 1

    node = graph.nodes[nkey]
    definition_display = (
        node.definition[:100] + "..."
        if len(node.definition) > 100
        else node.definition
    )

    print(f"=== Knowledge Graph: {node.term} ===")
    print(f"Category    : {node.category}")
    print(f"Definition  : {definition_display}")
    print(f"Mastery     : {node.mastery_score}%")
    print(f"Lessons seen: {node.lesson_count}")
    print(f"First seen  : {node.first_seen}")
    print(f"Last seen   : {node.last_seen}")

    connections = graph.strongest_connections(term, n=10)
    if connections:
        print()
        print("Connections:")
        for edge in connections:
            other = (
                edge.target_term
                if edge.source_term == nkey
                else edge.source_term
            )
            confidence_pct = round(edge.confidence_score * 100)
            print(
                f"  {other:<35} {edge.relationship_type:<15} "
                f"{confidence_pct}% confidence"
            )
    else:
        print()
        print("No connections found for this term.")

    recommendation = graph.recommend_next_term(term)
    if recommendation:
        rec_node = graph.nodes.get(recommendation)
        rec_display = rec_node.term if rec_node else recommendation
        print()
        print(f"Study next  : {rec_display} (lowest mastery among connections)")

    return 0


def cmd_graph_stats(graph_path: Path) -> int:
    """Print summary statistics about the knowledge graph."""
    graph = KnowledgeGraph.load(graph_path)
    s = graph.stats()

    print("=== Knowledge Graph Statistics ===")
    print(f"Total terms      : {s['total_nodes']}")
    print(f"Total connections: {s['total_edges']}")

    if s["most_connected_terms"]:
        print()
        print("Most connected terms:")
        for term_key, degree in s["most_connected_terms"]:
            node = graph.nodes.get(term_key)
            display = node.term if node else term_key
            print(f"  {display:<35} {degree} connections")

    if s["isolated_terms"]:
        print()
        print("Isolated terms (no connections):")
        for term_key in s["isolated_terms"]:
            node = graph.nodes.get(term_key)
            display = node.term if node else term_key
            print(f"  {display}")

    if s["strongest_relationships"]:
        print()
        print("Strongest relationships:")
        for edge in s["strongest_relationships"]:
            confidence_pct = round(edge.confidence_score * 100)
            print(
                f"  {edge.source_term} --[{edge.relationship_type}]--> "
                f"{edge.target_term}  ({confidence_pct}%)"
            )

    if s["categories"]:
        print()
        print("Categories:")
        for category, count in sorted(s["categories"].items()):
            print(f"  {category:<30} {count} term(s)")

    return 0


def cmd_rebuild_graph(
    graph_path: Path,
    project_root: Path,
    settings: dict,
) -> int:
    """Rebuild the knowledge graph from all saved lesson.json files."""
    graph = KnowledgeGraph()
    output_root = resolve_path(project_root, settings["output_dir"])

    lesson_files = sorted(output_root.glob("*/lesson.json"))

    if not lesson_files:
        print("No saved lessons found. Run a lesson first.")
        return 0

    loaded = 0
    failed = 0

    for lesson_file in lesson_files:
        try:
            raw = json.loads(lesson_file.read_text(encoding="utf-8"))
            lesson = MarketLesson.model_validate(raw)
            # lesson_date comes from the directory name (YYYY-MM-DD)
            lesson_date = lesson_file.parent.name
            graph.update_from_lesson(lesson, lesson_date)
            loaded += 1
        except Exception:
            failed += 1

    graph.save(graph_path)

    print(f"Rebuilt knowledge graph from {loaded} lesson(s).")
    if failed:
        print(f"Skipped {failed} lesson(s) due to errors.")
    print(f"Nodes: {len(graph.nodes)}  Edges: {len(graph.edges)}")
    print(f"Saved: {graph_path}")

    return 0


def build_ai_connections(
    lesson: "MarketLesson",
    settings: dict,
    lesson_date: str,
) -> list[dict]:
    """Ask Gemini to identify semantic relationships between lesson terms.

    Returns an empty list if no API key is configured or on any error.
    """
    if not settings.get("api_key"):
        return []

    try:
        from google import genai  # local import to avoid hard dependency
        from google.genai import types as gtypes

        term_names = [vt.term for vt in lesson.terms]
        terms_str = "\n".join(f"- {t}" for t in term_names)
        rel_types_str = ", ".join(sorted(RELATIONSHIP_TYPES))

        prompt = f"""
You are a financial education assistant.

Given these five market vocabulary terms from a lesson:
{terms_str}

Identify meaningful semantic relationships between pairs of these terms.

For each relationship return a JSON object with these exact keys:
  "source": <term name exactly as listed above>,
  "target": <term name exactly as listed above>,
  "relationship_type": <one of: {rel_types_str}>,
  "explanation": <one sentence explaining the relationship>,
  "confidence_score": <float between 0.0 and 1.0>

Return a JSON array of relationship objects. Only include pairs where you are
at least 70% confident (confidence_score >= 0.70). Return at most 10 objects.
Do not include the same pair twice. Source and target must be different terms.
Return only the JSON array with no surrounding text or markdown.
""".strip()

        client = genai.Client(api_key=settings["api_key"])
        response = client.models.generate_content(
            model=settings["model"],
            contents=prompt,
            config=gtypes.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
            ),
        )

        text = response.text or ""
        raw_list = json.loads(text)

        if not isinstance(raw_list, list):
            return []

        valid_term_names_normalized = {
            normalize_term(vt.term): vt.term for vt in lesson.terms
        }

        results: list[dict] = []
        for item in raw_list:
            if not isinstance(item, dict):
                continue
            src = item.get("source", "")
            tgt = item.get("target", "")
            rel = item.get("relationship_type", "")
            explanation = item.get("explanation", "")
            confidence = item.get("confidence_score", 0.0)

            # Validate: both terms must be from the lesson
            src_norm = normalize_term(src)
            tgt_norm = normalize_term(tgt)
            if src_norm not in valid_term_names_normalized:
                continue
            if tgt_norm not in valid_term_names_normalized:
                continue
            if src_norm == tgt_norm:
                continue

            # Validate relationship type
            if rel not in RELATIONSHIP_TYPES:
                continue

            # Validate confidence
            try:
                confidence = float(confidence)
            except (TypeError, ValueError):
                continue
            if confidence < 0.70:
                continue

            # Validate explanation
            if not explanation or not str(explanation).strip():
                continue

            results.append({
                "source": src_norm,
                "target": tgt_norm,
                "relationship_type": rel,
                "explanation": str(explanation).strip(),
                "confidence_score": confidence,
            })

        return results

    except Exception:
        return []


def cmd_record_quiz(
    term: str,
    correct: bool,
    progress_path: Path,
    today: str,
) -> int:
    store = ProgressStore.load(progress_path)
    record = store.record_quiz_result(term=term, correct=correct, today=today)
    store.save(progress_path)

    result_label = "correct" if correct else "incorrect"
    days_until = (date.fromisoformat(record.next_review_date) - date.fromisoformat(today)).days
    print(f"Recorded: {term} — {result_label}")
    print(f"  Mastery score : {record.mastery_score}")
    print(f"  Next review   : {record.next_review_date} ({days_until} days)")
    print(f"  Total reviews : {record.review_count}")
    return 0


def cmd_show_progress(
    progress_path: Path,
    today: str,
) -> int:
    store = ProgressStore.load(progress_path)
    total = store.total_terms()
    mastered = store.mastered_terms()
    due = store.due_for_review(today)
    weakest = store.weakest_terms(n=5)

    print("=== Progress Dashboard ===")
    print(f"Total terms learned : {total}")
    print(f"Mastered  (>=85%)   : {len(mastered)}")
    print(f"Due for review today: {len(due)}")

    if weakest:
        print()
        print("Weakest terms:")
        for i, r in enumerate(weakest, 1):
            print(
                f"  {i}. {r.term:<30} "
                f"mastery {r.mastery_score:>3}%  "
                f"({r.review_count} reviews, {r.correct_count} correct)"
            )
    else:
        print()
        print(
            "No terms reviewed yet. "
            "Run a lesson and record results with --record-quiz."
        )

    return 0


def main() -> int:
    args = parse_arguments()
    project_root = get_project_root()
    settings = load_settings(project_root)

    progress_path = get_progress_path(project_root, settings["progress_dir"])
    graph_path = get_graph_path(project_root, settings["graph_dir"])

    if args.graph_term:
        return cmd_graph_term(term=args.graph_term, graph_path=graph_path)

    if args.graph_stats:
        return cmd_graph_stats(graph_path=graph_path)

    if args.rebuild_graph:
        return cmd_rebuild_graph(
            graph_path=graph_path,
            project_root=project_root,
            settings=settings,
        )

    if args.progress:
        today = get_current_datetime(settings["timezone"]).date().isoformat()
        return cmd_show_progress(progress_path=progress_path, today=today)

    if args.record_quiz:
        if not args.result:
            print(
                "Error: --result {correct,incorrect} is required "
                "when using --record-quiz.",
                file=sys.stderr,
            )
            return 1
        today = get_current_datetime(settings["timezone"]).date().isoformat()
        return cmd_record_quiz(
            term=args.record_quiz,
            correct=(args.result == "correct"),
            progress_path=progress_path,
            today=today,
        )

    try:
        current_datetime = get_current_datetime(settings["timezone"])
        lesson_date = current_datetime.date().isoformat()
        weekday = current_datetime.strftime("%A")
        theme = THEMES[weekday]

        inbox_path = resolve_path(
            project_root,
            settings["bloomberg_inbox"],
        )

        bloomberg_notes = read_bloomberg_notes(inbox_path)

        env_search_enabled = (
            settings["enable_google_search"] == "true"
        )

        search_enabled = args.search or env_search_enabled

        if args.dry_run and search_enabled:
            print(
                "Notice: Google Search is ignored during dry-run mode."
            )
            search_enabled = False

        if args.dry_run:
            lesson = create_dry_run_lesson(
                lesson_date=lesson_date,
                weekday=weekday,
                theme=theme,
                bloomberg_notes=bloomberg_notes,
            )
        else:
            lesson = generate_gemini_lesson(
                settings=settings,
                lesson_date=lesson_date,
                weekday=weekday,
                theme=theme,
                bloomberg_notes=bloomberg_notes,
                search_enabled=search_enabled,
            )

        markdown_path, json_path = save_lesson(
            lesson=lesson,
            project_root=project_root,
            configured_output_dir=settings["output_dir"],
        )

        # Register each term in the progress store (first_seen only; no review count).
        store = ProgressStore.load(progress_path)
        for vocabulary_term in lesson.terms:
            store.ensure_term(vocabulary_term.term, lesson_date)
        store.save(progress_path)

        # --- knowledge graph update ----------------------------------------
        graph = KnowledgeGraph.load(graph_path)
        graph.update_from_lesson(lesson, lesson_date)
        graph.sync_mastery(store)
        if not args.dry_run:
            for edge_data in build_ai_connections(lesson, settings, lesson_date):
                graph.ensure_edge(
                    source=edge_data["source"],
                    target=edge_data["target"],
                    relationship_type=edge_data["relationship_type"],
                    explanation=edge_data["explanation"],
                    confidence_score=edge_data["confidence_score"],
                    lesson_date=lesson_date,
                )
        graph.save(graph_path)

        print("Vocabulary lesson created successfully.")
        print(f"Open: {markdown_path}")
        print(f"JSON: {json_path}")

        if args.dry_run:
            print("Mode: Dry run - no Gemini API credits were used.")
        elif search_enabled:
            print("Mode: Gemini with Google Search enabled.")
        else:
            print("Mode: Gemini without Google Search.")

        return 0

    except ValidationError as exc:
        print(
            "Lesson validation failed. The generated lesson did not match "
            "the required structure.",
            file=sys.stderr,
        )
        print(exc, file=sys.stderr)
        return 1

    except FileNotFoundError as exc:
        print(f"File error: {exc}", file=sys.stderr)
        return 1

    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    except Exception as exc:
        print(
            f"Unexpected error: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())