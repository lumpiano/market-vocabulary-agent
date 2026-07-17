# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
