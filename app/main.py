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