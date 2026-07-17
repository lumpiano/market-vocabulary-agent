# Architecture

This document describes how the Market Vocabulary Agent works internally — from
reading the user's Bloomberg notes to writing the final lesson files. It is
intended for contributors who want to understand, extend, or debug the system.

---

## Overview

Market Vocabulary Agent is a single-pass, command-line pipeline. On each run it
reads one plain-text inbox file, constructs a structured prompt, sends it to the
Gemini API with a JSON schema constraint, validates the response against a Pydantic
model, and writes the lesson to disk in both Markdown and JSON formats.

There is no server, no database, and no persistent state between runs beyond
the local JSON files. On each run the pipeline writes two lesson files to
`data/outputs/YYYY-MM-DD/`, updates the progress store in
`data/progress/progress.json`, and updates the knowledge graph in
`data/knowledge_graph/knowledge_graph.json`.

---

## High-Level Architecture

```
Bloomberg Live
      │
      │  (user watches and takes notes)
      ▼
today.txt
(data/bloomberg_inbox/today.txt)
      │
      │  read_bloomberg_notes()
      │  strips bullets, blank lines
      ▼
Input Loader
      │
      │  combined with weekday theme
      │  from THEMES dict
      ▼
Prompt Builder
(build_agent_prompt)
      │
      │  HTTPS request
      │  response_mime_type="application/json"
      │  response_schema=MarketLesson
      ▼
Gemini API
(google-genai SDK)
      │
      │  structured JSON response
      ▼
Raw JSON Response
      │
      │  MarketLesson.model_validate()
      │  or model_validate_json()
      ▼
Pydantic Validation
      │
      ├─── Validation Error ──▶ stderr + exit code 1
      │                         (no files written)
      ▼
Validated MarketLesson
      │
      ├──▶ json.dumps(lesson.model_dump())
      │         │
      │         ▼
      │     lesson.json
      │
      └──▶ lesson_to_markdown(lesson)
                │
                ▼
            lesson.md

                │
                ▼
      KnowledgeGraph.update_from_lesson()
      (same-lesson edges, confidence 0.50)
                │
                │  [live run only]
                ▼
      build_ai_connections()
      (Gemini call → typed semantic edges, confidence ≥ 0.70)
                │
                ▼
      knowledge_graph.json
```

---

## Component Breakdown

### Input — `read_bloomberg_notes()`

**File:** `app/main.py`

Reads `data/bloomberg_inbox/today.txt` line by line. Each line is stripped of
leading whitespace and common bullet prefixes (`-`, `*`). Blank lines are
discarded. The result is a `list[str]` of clean note strings.

If the file does not exist, the function creates it as an empty file and returns
an empty list. The agent continues and generates a general lesson for the day's
theme with a note inside the prompt that no personal notes were provided.

```
today.txt line:  "- NVIDIA issued stronger forward guidance."
          output: "NVIDIA issued stronger forward guidance."
```

---

### Settings — `load_settings()`

**File:** `app/main.py`

Calls `python-dotenv` to load `.env` from the project root, then reads six
environment variables with sensible defaults. Returns a plain `dict[str, str]`
that is threaded through the rest of the pipeline.

| Key | Source | Default |
|---|---|---|
| `api_key` | `GEMINI_API_KEY` | `""` |
| `model` | `GEMINI_MODEL` | `gemini-3.5-flash` |
| `timezone` | `TIMEZONE` | `America/New_York` |
| `output_dir` | `OUTPUT_DIR` | `data/outputs` |
| `bloomberg_inbox` | `BLOOMBERG_INBOX` | `data/bloomberg_inbox/today.txt` |
| `enable_google_search` | `ENABLE_GOOGLE_SEARCH` | `false` |
| `graph_dir` | `GRAPH_DIR` | `data/knowledge_graph` |

---

### Prompt Construction — `build_agent_prompt()`

**File:** `app/main.py`

Assembles the instruction string sent to Gemini. It embeds:

- Today's date and weekday
- The day's fixed theme (drawn from the `THEMES` dict)
- The user's cleaned Bloomberg notes
- Numbered content requirements (five terms, quiz, cause-and-effect chain, study plan)
- A source rule that changes depending on whether Google Search grounding is enabled
- The required disclaimer text

The prompt explicitly forbids profit promises, personalized trading instructions,
and Bloomberg article reproduction — guardrails that apply regardless of the
model's own safety filters.

```python
THEMES = {
    "Monday":    "Corporate earnings and company fundamentals",
    "Tuesday":   "Interest rates, bonds, inflation, and the Federal Reserve",
    "Wednesday": "Commodities",
    "Thursday":  "Technology, AI, semiconductors, software, and cloud computing",
    "Friday":    "Global markets, currencies, trade, and economic indicators",
    "Saturday":  "Mixed market vocabulary review and retrieval practice",
    "Sunday":    "Weekly recap and weak-area review",
}
```

---

### Gemini Generation — `generate_gemini_lesson()`

**File:** `app/main.py`

Initialises a `google.genai.Client` with the API key and calls
`client.models.generate_content()` with three key config options:

| Option | Value | Effect |
|---|---|---|
| `temperature` | `0.3` | Low randomness; consistent, structured output |
| `response_mime_type` | `application/json` | Forces JSON-mode output |
| `response_schema` | `MarketLesson` | Constrains the JSON structure to the schema |

When `--search` is active, a `types.Tool(google_search=GoogleSearch())` object is
added to the config, enabling Gemini to perform real-time web lookups before
answering. In that mode the source rule in the prompt instructs the model to cite
sources; without it, the model is told to use only stable educational examples.

The function checks `response.parsed` first (the SDK's pre-parsed object), then
falls back to `response.text` for manual `model_validate_json()`. An empty
response raises a `ValueError` immediately.

---

### Schema Validation — `MarketLesson.model_validate()`

**File:** `app/models.py`

All generated content passes through three Pydantic models before anything is
written to disk.

#### `VocabularyTerm`

```
term                    str  min_length=1
plain_english_definition str  min_length=1
everyday_analogy        str  min_length=1
market_example          str  min_length=1
why_it_matters          str  min_length=1
```

#### `QuizQuestion`

```
question   str        min_length=1
choices    list[str]  min_length=2
answer     str        min_length=1
explanation str       min_length=1
```

Cross-field validator: `answer` must be an exact string match of one item in
`choices`. If not, a `ValueError` is raised before the model is constructed.

#### `MarketLesson`

```
lesson_date            str               min_length=1
weekday                str               min_length=1
theme                  str               min_length=1
bloomberg_notes_used   list[str]
terms                  list[VocabularyTerm]
cause_and_effect_chain list[str]         min_length=2
quiz                   QuizQuestion
five_minute_study_plan list[str]         min_length=1
sources                list[str]
disclaimer             str               min_length=1
```

Cross-field validator: `terms` must contain **exactly five** entries with no
duplicate names (case-insensitive, stripped). A `ValidationError` caught in
`main()` prints the full error to stderr and exits with code `1`. No output
files are created or modified on failure.

---

### Knowledge Graph — `app/knowledge_graph.py`

A pure data module with no Gemini imports. It maintains two collections:

- **Nodes** (`dict[str, TermNode]`) — keyed by `normalize_term(term)`; one entry
  per unique vocabulary term across all lessons
- **Edges** (`dict[str, RelationshipEdge]`) — keyed by a deterministic edge key;
  one entry per unique (source, relationship_type, target) triple

**Node lifecycle (`ensure_node`):** On first encounter a `TermNode` is created.
On repeat lessons: `last_seen` and `lesson_count` are updated; `definition` is
replaced only if the new one is longer.

**Edge lifecycle (`ensure_edge`):** On first encounter a `RelationshipEdge` is
created. On repeat: `confidence_score` is boosted by +0.05 (capped at 1.0),
`lesson_count` is incremented, and `explanation` is replaced only if the new one
is longer.

**Symmetric deduplication:** `related_to` and `opposite_of` use a sorted edge
key so `(A→B)` and `(B→A)` map to the same entry. Directed types preserve order.

**`normalize_term(term)`:** Lowercase → collapse whitespace → strip punctuation
(except `-` and `'`) → resolve `KNOWN_ALIASES` (e.g. `"cpi"` →
`"consumer price index"`). Called on every term before any map lookup or edge
key construction.

**`update_from_lesson(lesson, lesson_date)`:** Adds five nodes and C(5,2) = 10
`related_to` edges (one for every pair of co-occurring terms in the lesson).

**`build_ai_connections()` (in `main.py`):** Secondary Gemini call after lesson
generation on live runs. Returns a list of edge dicts. Each entry is validated:
both terms must be from the lesson, `relationship_type` must be in
`RELATIONSHIP_TYPES`, `confidence_score` must be ≥ 0.70, and `explanation` must
be non-empty. Returns `[]` on any error — a failed AI-connections call never
aborts the lesson.

**`recommend_next_term(term)`:** Among all terms connected to the given term,
returns the normalized key of the one with the lowest `mastery_score`. Ties are
broken by highest edge confidence. Returns `None` if the term is isolated.

---

### Markdown Generation — `lesson_to_markdown()`

**File:** `app/main.py`

Converts a validated `MarketLesson` object into a structured Markdown string.
Builds a `list[str]` of lines, then joins with `"\n"`. Sections in order:

1. H1 title with lesson date
2. Day and theme metadata
3. Bloomberg notes used
4. Five vocabulary terms (H3, four labelled fields each)
5. Cause-and-effect chain (numbered list)
6. Multiple-choice quiz (lettered choices A–F, correct answer, explanation)
7. Five-minute study plan (bulleted list)
8. Sources
9. Educational disclaimer

The function is pure — it takes a `MarketLesson` and returns a `str` with no
side effects.

---

### File Output — `save_lesson()`

**File:** `app/main.py`

Resolves the output directory, creates `data/outputs/YYYY-MM-DD/` if it does
not exist, and writes both files atomically via `Path.write_text()`.

```
data/outputs/
└── 2026-07-16/
    ├── lesson.json   ← json.dumps(lesson.model_dump(mode="json"), indent=2)
    └── lesson.md     ← lesson_to_markdown(lesson)
```

A guard at the top of the function raises `ValueError` if `lesson_date` is
blank or if it resolves to the output root — preventing the files from being
written directly into `data/outputs/` rather than a date subfolder.

Running the agent again on the same date overwrites both files for that date.

---

### Logging

There is no logging framework. The agent prints four lines to stdout on success:

```
Vocabulary lesson created successfully.
Open: <markdown path>
JSON: <json path>
Mode: <dry-run | Gemini with/without Google Search>
```

Errors go to stderr via `print(..., file=sys.stderr)`. The exit code is `0` on
success and `1` on any handled error (`ValidationError`, `ValueError`,
`FileNotFoundError`, or unexpected exceptions).

---

### Dry-Run Mode — `create_dry_run_lesson()`

**File:** `app/main.py`

Invoked when `--dry-run` is passed. Builds a `MarketLesson` entirely from local
data — no network call, no API key required.

Term content is drawn from a `FALLBACK_TERMS` dict keyed by weekday. Detailed
pre-written explanations exist for the five Tuesday terms (Basis Point, Treasury
Yield, Yield Curve, Consumer Price Index, Federal Funds Rate). All other weekdays
receive generic placeholder text that follows the schema structure.

The dry-run path feeds into the same `MarketLesson.model_validate()` call and
the same `save_lesson()` function as the live path. This means a passing dry run
confirms that the schema, file-writing logic, and Markdown renderer are all
working correctly before any API credits are used.

---

### Live Mode — `generate_gemini_lesson()`

**File:** `app/main.py`

Invoked when `--dry-run` is absent. Requires `GEMINI_API_KEY` to be set.
Raises `ValueError` immediately if the key is missing, before any network
request is made.

The Gemini response is parsed and validated. If validation passes, `save_lesson()`
is called identically to the dry-run path.

---

## Execution Flow

```
python -m app.main [--dry-run] [--search] [--graph-term|--graph-stats|--rebuild-graph]
        │
        ├── parse_arguments()
        ├── get_project_root()
        ├── load_settings()
        │
        ├── [--graph-term / --graph-stats / --rebuild-graph]  ← early return
        │
        ├── get_current_datetime()   → lesson_date, weekday, theme
        ├── read_bloomberg_notes()   → bloomberg_notes
        │
        ├── [--dry-run]
        │       └── create_dry_run_lesson()
        │                 └── MarketLesson.model_validate()
        │
        └── [live]
                └── generate_gemini_lesson()
                          ├── build_agent_prompt()
                          ├── client.models.generate_content()
                          └── MarketLesson.model_validate()
                                    │
                                    ▼
                              save_lesson()
                                    ├── lesson.json
                                    └── lesson.md
                                    │
                                    ▼
                              ProgressStore.record + save
                                    │
                                    ▼
                              KnowledgeGraph.update_from_lesson()
                              (same-lesson edges)
                                    │
                                    │  [live only]
                                    ▼
                              build_ai_connections()
                              (semantic edges via Gemini)
                                    │
                                    ▼
                              KnowledgeGraph.save()
```

---

## Future Architecture

The sections below describe planned additions for future versions.

---

### Robustness (v0.5)

Retry logic, structured logging, dated inbox files, and a config file layer.

---

---

### AI Tutor

A conversational follow-up mode where the learner can ask clarifying questions
about any term in the day's lesson. The tutor has access to the lesson JSON as
context and maintains a short session history.

```
lesson.json  ──▶  tutor prompt context
                        │
                        ▼
                  Gemini (conversational)
                        │
                        ▼
                  Q&A terminal session
```

---

### Daily Automation

A scheduled task (cron on Linux/macOS, Task Scheduler on Windows) that runs the
agent at a fixed time each morning and optionally sends the lesson by email or
pushes it to a local dashboard.

```
cron / Task Scheduler
        │
        ▼
python -m app.main
        │
        ├──▶ lesson.md / lesson.json
        └──▶ email / notification (optional)
```

---

### Weekly Summary and Reports

A separate `--weekly` mode that reads the seven most recent lesson files,
identifies the terms covered, and asks Gemini to generate a consolidated review
lesson with a longer quiz targeting terms the learner found difficult during the
week.

---

### Learning Analytics

Charts and statistics derived from `progress.json`: quiz accuracy over time,
terms per theme, retention curves, and streak tracking. Rendered either in the
dashboard or exported as a Markdown report.

```
progress.json  ──▶  analytics engine  ──▶  weekly_report.md
                                       └──▶  dashboard charts
```

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| Single-pass CLI, no server | Keeps the system simple and fully local for v0.1 |
| Pydantic for validation | Catches malformed API responses before files are written; schema is also used as the Gemini `response_schema` constraint |
| `response_schema=MarketLesson` | Instructs Gemini to return JSON that matches the schema directly, reducing post-processing |
| `temperature=0.3` | Low enough for consistent structure; high enough for varied vocabulary selection |
| Dual output (JSON + Markdown) | JSON enables future programmatic use; Markdown is immediately human-readable |
| Date-stamped output folders | Preserves one lesson per day without overwriting history; maps cleanly to a future calendar UI |
| Dry-run path shares save logic | Ensures the file-writing and rendering code is always tested, not just the API path |
| `knowledge_graph.py` has zero Gemini imports | Keeps the data layer testable without mocking the API; all Gemini calls stay in `main.py` |
| Two-layer connections (deterministic + AI) | Same-lesson edges are always produced and never fail; AI edges add richer semantics but are optional |
| `build_ai_connections()` returns `[]` on error | A failed secondary Gemini call never aborts the lesson; the graph degrades gracefully |
| Symmetric edge keys for `related_to` / `opposite_of` | Prevents duplicate A→B and B→A entries for commutative relationships |
| `normalize_term()` + alias resolution | Keeps the graph clean across abbreviation variants without requiring the model to be consistent |
