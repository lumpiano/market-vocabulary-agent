# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.4.0] - 2026-07-17

### Added

- **Knowledge graph module** (`app/knowledge_graph.py`) — pure data layer (no
  Gemini imports) that maintains a graph of vocabulary terms (nodes) and their
  semantic relationships (edges); persisted to `data/knowledge_graph/knowledge_graph.json`
- **`TermNode` dataclass** — stores `term`, `normalized_term`, `definition`,
  `category`, `first_seen`, `last_seen`, `lesson_count`, `mastery_score`, and
  related-term list; deduplicates by normalized key on repeat lessons
- **`RelationshipEdge` dataclass** — stores `source_term`, `target_term`,
  `relationship_type`, `explanation`, `confidence_score`, `first_created`,
  `last_updated`, `lesson_count`; boosts confidence +0.05 per repeat occurrence
  (capped at 1.0)
- **Two-layer connection system** — deterministic same-lesson edges
  (`related_to` at 0.50 confidence) added for every pair of co-occurring terms;
  AI-assisted semantic edges (9 typed relationships, minimum confidence 0.70)
  added on live runs via a secondary Gemini call
- **Nine relationship types** — `related_to`, `causes`, `affects`,
  `measured_by`, `opposite_of`, `part_of`, `example_of`, `used_in`,
  `influenced_by`
- **`normalize_term()`** — lowercase, collapse whitespace, strip punctuation,
  resolve known financial aliases (CPI → consumer price index, GDP, Fed, FOMC,
  P/E, EPS, VIX, and 18 more)
- **Symmetric edge deduplication** — `related_to` and `opposite_of` use a
  sorted alphabetical key so (A→B) and (B→A) resolve to the same edge
- **`--graph-term TERM`** CLI command — prints node details, top-10 connections
  with confidence percentages and lesson counts, and a study recommendation
- **`--graph-stats`** CLI command — prints totals (nodes, edges), most-connected
  terms, isolated terms, strongest relationships, and category breakdown
- **`--rebuild-graph`** CLI command — reconstructs the graph from scratch by
  replaying all `data/outputs/*/lesson.json` files chronologically
- **Knowledge Graph page** added to the Streamlit dashboard — three metrics
  (terms, connections, categories), term explorer with definition, mastery, and
  connection list, Graphviz DOT chart (focus term highlighted gold), and a
  "study next" recommendation
- **`build_ai_connections()`** in `main.py` — secondary Gemini call after lesson
  generation; validates that both terms are from the lesson, relationship type is
  recognised, confidence ≥ 0.70, and explanation is non-empty; returns `[]` on
  any error so a failed AI-connections call never aborts the lesson
- **`examples/sample_knowledge_graph.json`** — sanitised example with 8 nodes
  from two lesson dates, 20 edges (17 same-lesson + 3 AI semantic), and mastery
  scores ranging 0–100
- **30-test pytest suite** (`tests/test_knowledge_graph.py`) — covers
  `normalize_term` (7), `is_confident_enough` (2), edge key deduplication (2),
  `ensure_node` (3), `ensure_edge` (4), `update_from_lesson` (3),
  `connections_for_term` (2), `strongest_connections` (1),
  `recommend_next_term` (2), `stats` (2), persistence roundtrip / missing /
  corrupted (3); total test suite grows to 95 tests
- **`data/knowledge_graph/`** added to `.gitignore` — graph data is personal
  runtime state and is not committed to version control
- **`GRAPH_DIR`** environment variable — configures where the knowledge graph
  file is stored (default `data/knowledge_graph`)

---

## [0.3.0] - 2026-07-17

### Added

- **Notes module** (`app/notes.py`) — `load_notes`, `save_notes`, `parse_notes`,
  and `validate_notes` for reading and writing `data/bloomberg_inbox/today.txt`;
  `parse_notes` strips bullet prefixes (`-`, `*`) and blank lines;
  `validate_notes` enforces a 10 000-character total limit and a 500-character
  per-line limit
- **Streamlit dashboard** (`app/dashboard.py`) — browser-based interface
  launched with `streamlit run app/dashboard.py`; replaces the terminal workflow
  for daily learners
- **Market Notes page** — text area for entering Bloomberg observations, live
  parse preview before saving, save/clear buttons, dry-run and live lesson
  generation buttons, in-page lesson output preview
- **Bloomberg external-source notice** — displayed on every Market Notes page
  visit; clarifies that Bloomberg Live is an independent external resource,
  unaffiliated with this application, and that all generated content is original
  output from the Gemini API
- **Progress page** — three headline metrics (terms seen, mastered ≥ 85%, due
  for review today), weakest-terms list with `st.progress` mastery bars, and an
  in-browser quiz recording form
- **25-test pytest suite** (`tests/test_notes.py`) — covers `load_notes` (3),
  `save_notes` (4), `parse_notes` (10), and `validate_notes` (8)
- **`streamlit>=1.28`** added to `requirements.txt`

---

## [0.2.0] - 2026-07-17

### Added

- **Progress tracking module** (`app/progress.py`) — new `TermRecord` and
  `ProgressStore` dataclasses that persist per-term quiz history to a local JSON
  file under `data/progress/`
- **`--record-quiz TERM --result correct|incorrect`** — CLI command that records
  one quiz attempt for a named term and displays the updated mastery score and
  next scheduled review date
- **`--progress`** — CLI command that prints a four-item dashboard: total terms
  seen, terms mastered (mastery ≥ 85), terms due for review today, and the five
  weakest terms with their mastery scores
- **Mastery formula** — `round(correct / total × 100)` clamped to `[0, 100]`;
  returns `0` when no reviews have been recorded
- **Spaced-repetition scheduling** — four bands drive the next-review interval:
  `0–33 → +1 day`, `34–66 → +3 days`, `67–84 → +7 days`, `85–100 → +14 days`
- **Auto-registration** — every lesson generation run silently registers its five
  vocabulary terms in the progress store so they appear in `--progress` output
  without requiring a manual quiz result first
- **`examples/sample_progress.json`** — sanitised example progress file with
  eight terms at varying mastery levels (0–100), illustrating the `schema_version
  0.2` JSON format
- **Test suite** (`tests/test_progress.py`) — 40 pytest tests covering mastery
  formula bounds, next-review band boundaries, `TermRecord` state transitions,
  `ProgressStore` term operations, and load/save roundtrips including missing and
  corrupted files
- **`data/progress/`** added to `.gitignore` — progress data is personal runtime
  state and is not committed to version control

---

## [0.1.0] - 2026-07-16

### Added

- **Market Vocabulary Agent** — initial working release of the end-to-end lesson
  generation pipeline; reads Bloomberg inbox notes, builds a structured prompt,
  and produces a complete daily vocabulary lesson
- **Gemini API integration** — structured-output generation using the
  `google-genai` SDK with `response_schema=MarketLesson` and
  `response_mime_type="application/json"` to constrain model output to the
  required schema
- **Dry-run mode** (`--dry-run`) — generates a fully structured sample lesson
  from local fallback terms with no API call; validates and writes output through
  the same pipeline as a live run
- **Live generation mode** — calls the Gemini API with the user's Bloomberg notes
  and the day's theme; supports optional Google Search grounding via `--search`
- **Pydantic schema validation** — `MarketLesson`, `VocabularyTerm`, and
  `QuizQuestion` models enforce structure, field lengths, term count (exactly
  five), no duplicate terms, and quiz answer integrity before any file is written
- **Markdown lesson output** — `lesson_to_markdown()` renders the validated
  lesson as a human-readable `lesson.md` file
- **JSON lesson output** — `lesson.model_dump(mode="json")` serializes the
  validated lesson as a machine-readable `lesson.json` file
- **Date-based output folders** — each run writes to
  `data/outputs/YYYY-MM-DD/`, preserving one lesson per day without overwriting
  history
- **Git repository initialization** — project placed under version control with
  an initial commit containing all source files
- **README.md** — full project documentation covering overview, features, folder
  structure, installation, environment variables, dry-run and live usage,
  example output, schema validation details, version status, and roadmap
- **Proprietary License** — copyright © 2026 Guadalupe Contreras, All Rights Reserved; shared for evaluation and portfolio purposes only
- **PROJECT_STRUCTURE.md** — repository layout reference with annotated ASCII
  tree and per-file and per-folder descriptions for new contributors
- **ARCHITECTURE.md** — internal system documentation covering component
  breakdown, ASCII pipeline diagrams, execution flow, key design decisions, and
  planned future architecture

### Fixed

- **Empty output file bug** — lessons were previously written to
  `data/outputs/lesson.md` and `data/outputs/lesson.json` (the output root)
  instead of a date-stamped subfolder when `lesson_date` resolved to an empty
  path segment; the correct date-subdirectory path is now always used
- **Stale 0-byte artifacts** — removed two empty files (`data/outputs/lesson.md`
  and `data/outputs/lesson.json`) left behind by an earlier failed run
- **`lesson_date` guard** — added an explicit check in `save_lesson()` that
  raises `ValueError` if `lesson_date` is blank or if it resolves back to the
  output root, preventing the file-path collapse from recurring silently
- **Model configuration** — updated `GEMINI_MODEL` in `.env` from
  `gemini-3.5-flash` to `gemini-2.5-flash` after the configured model returned
  persistent 503 errors; availability was verified by listing models via the API
  before switching

### Security

- **`.gitignore` created** — ensures sensitive and generated files are never
  committed to version control
- **`.env` excluded** — API key and runtime secrets are kept out of the
  repository
- **`.venv/` excluded** — virtual environment directory is not tracked; the
  dependency list is captured in `requirements.txt` instead
- **`data/outputs/` excluded** — generated lesson files are runtime artifacts
  and do not belong in source control
- **Editor metadata excluded** — `.vscode/` and `.idea/` directories are
  ignored to keep developer-specific IDE settings out of the repository;
  `__pycache__/` and `*.pyc` bytecode files are also excluded

---

## Notes

v0.1.0 represents the first stable, end-to-end release of the Market Vocabulary
Agent. The core pipeline is complete and validated: Bloomberg inbox reading,
weekday-themed prompt construction, Gemini structured-output generation, Pydantic
schema validation, and dual Markdown and JSON file output. Both the dry-run and
live generation paths have been tested and confirmed to produce fully populated,
schema-valid lessons. The repository is under version control with secrets
excluded and professional documentation in place.

Future versions will extend the system with a browser dashboard, vocabulary
history, quiz-driven progress tracking, weekly summaries, and learning analytics.
See `ARCHITECTURE.md` for the full roadmap.

---

[0.1.0]: https://github.com/lumpiano/market-vocabulary-agent/releases/tag/v0.1.0
