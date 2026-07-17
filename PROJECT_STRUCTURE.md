# Project Structure

This document describes the layout of the Market Vocabulary Agent repository and
the purpose of every major folder and file. It is intended as a quick orientation
for contributors joining the project.

---

## Repository Tree

```
market_vocabulary_agent/
├── app/
│   ├── __init__.py
│   ├── dashboard.py
│   ├── main.py
│   ├── models.py
│   ├── notes.py
│   └── progress.py
├── data/
│   ├── bloomberg_inbox/
│   │   └── today.txt
│   ├── outputs/               ← git-ignored; created at runtime
│   │   └── YYYY-MM-DD/
│   │       ├── lesson.json
│   │       └── lesson.md
│   └── progress/              ← git-ignored; created at runtime
│       └── progress.json
├── examples/
│   ├── sample_lesson.json
│   ├── sample_lesson.md
│   └── sample_progress.json
├── tests/
│   ├── __init__.py
│   ├── test_notes.py
│   └── test_progress.py
├── .env                       ← git-ignored; holds secrets
├── .gitignore
├── LICENSE
├── PROJECT_STRUCTURE.md
├── README.md
└── requirements.txt
```

---

## Folder and File Reference

### `app/`

The Python package that contains all application logic. Every file the interpreter
runs lives here.

| File | Purpose |
|---|---|
| `__init__.py` | Marks `app` as a Python package. Empty; required for `python -m app.main` to resolve correctly. |
| `dashboard.py` | Streamlit dashboard. Two pages: **Market Notes** (enter and save Bloomberg observations, preview parsed notes, launch dry-run or live lesson generation) and **Progress** (mastery metrics, weakest terms, quiz recording). |
| `main.py` | Entry point and orchestration layer. Parses CLI arguments, loads settings from `.env`, reads the Bloomberg inbox, calls either the dry-run path or the Gemini API, validates the result, writes the output files, and delegates to `progress.py` for quiz and progress commands. |
| `models.py` | Pydantic schema definitions. Declares `VocabularyTerm`, `QuizQuestion`, and `MarketLesson`. All generated content is validated against these models before anything is written to disk. |
| `notes.py` | Manual notes module. Provides `load_notes`, `save_notes`, `parse_notes`, and `validate_notes` for reading and writing `data/bloomberg_inbox/today.txt` and parsing bullet-prefixed note lines. |
| `progress.py` | Progress tracking module. Defines `TermRecord` and `ProgressStore` dataclasses, the mastery formula (`compute_mastery`), and the spaced-repetition scheduler (`compute_next_review`). Persists data to `data/progress/progress.json`. |

---

### `data/`

Runtime data directory. Split into an inbox (human-written input) and an outputs
folder (machine-generated output).

#### `data/bloomberg_inbox/`

Drop zone for the learner's daily notes. The agent reads `today.txt` on every run
and uses its contents to personalize the lesson.

| File | Purpose |
|---|---|
| `today.txt` | Plain-text file. Write one note per line before running the agent. Bullet prefixes (`-`, `*`) are stripped automatically. Clear or replace the file each morning. If the file is empty or missing, the agent generates a general lesson for the day's theme. |

#### `data/outputs/`

Generated lesson files. **This folder is git-ignored** and created automatically on
the first run. Do not commit its contents.

Each successful run writes a date-stamped subfolder:

```
data/outputs/
└── 2026-07-16/
    ├── lesson.json   # Structured lesson data; validated against MarketLesson schema
    └── lesson.md     # Human-readable Markdown version of the same lesson
```

Running the agent again on the same date overwrites the existing files for that date.

#### `data/progress/`

Quiz and mastery data. **This folder is git-ignored** and created automatically
when a lesson is generated or a quiz result is recorded. Do not commit its
contents — progress data is personal and specific to each learner's session.

```
data/progress/
└── progress.json   # TermRecord entries keyed by term name; schema_version 0.2
```

---

### `examples/`

Sanitised example files committed to the repository for documentation and
reference. These are static snapshots — they are not read by the agent at runtime.

| File | Purpose |
|---|---|
| `sample_lesson.json` | Example `MarketLesson` JSON output matching the Pydantic schema |
| `sample_lesson.md` | Same lesson rendered as Markdown |
| `sample_progress.json` | Example `ProgressStore` JSON with eight terms at varying mastery levels (0–100) |

---

### `tests/`

Automated test suite. Run with `python -m pytest tests/ -v`.

| File | Purpose |
|---|---|
| `__init__.py` | Marks `tests` as a Python package. Empty. |
| `test_notes.py` | 25 pytest tests covering `load_notes` (missing/existing/empty files), `save_notes` (creates, overwrites, creates parent dirs), `parse_notes` (bullet prefixes, blank lines, order), and `validate_notes` (empty, whitespace, length limits, per-line limits). |
| `test_progress.py` | 40 pytest tests covering `compute_mastery`, `compute_next_review`, `TermRecord` state transitions, and `ProgressStore` operations (term management, load/save, missing and corrupted files). |

---

### `.env`

Local environment file holding secrets and runtime configuration. **Never committed.**
Copy the template from the README, fill in your `GEMINI_API_KEY`, and save this file
to the project root before running the agent.

```
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.5-flash
TIMEZONE=America/New_York
OUTPUT_DIR=data/outputs
BLOOMBERG_INBOX=data/bloomberg_inbox/today.txt
ENABLE_GOOGLE_SEARCH=false
```

---

### `.gitignore`

Tells Git which files and folders to ignore. The following are excluded:

| Pattern | Reason |
|---|---|
| `.env` | Contains the API key — must never be committed |
| `.venv/` | Virtual environment; reproducible from `requirements.txt` |
| `data/outputs/` | Generated files; not part of source control |
| `data/progress/` | Personal quiz and mastery data; not part of source control |
| `__pycache__/` | Python bytecode cache; auto-generated |
| `*.pyc` | Compiled Python files; auto-generated |
| `.vscode/` | VS Code editor settings; developer-specific |
| `.idea/` | JetBrains IDE settings; developer-specific |

---

### `LICENSE`

Proprietary license, copyright © 2026 Guadalupe Contreras. All Rights Reserved.
This repository is shared for evaluation and portfolio purposes only. No copying,
modification, distribution, or commercial use without prior written permission.

---

### `README.md`

Primary project documentation. Covers the project overview, features, installation
steps, environment variable reference, usage instructions, example output, schema
validation details, version status, and the future roadmap. Start here.

---

### `requirements.txt`

Pinned Python dependencies. Install with:

```bash
pip install -r requirements.txt
```

After adding a new package, update this file with:

```bash
pip freeze > requirements.txt
```

---

## Data Flow

The diagram below shows how information moves through the agent on a live run.

```
today.txt
    │
    ▼
read_bloomberg_notes()
    │
    ▼
build_agent_prompt()  ──────────────────────────────────────┐
    │                                                        │
    ▼                                                   THEMES dict
generate_gemini_lesson()                           (weekday → theme)
    │
    ▼
MarketLesson.model_validate()   ← validation against Pydantic schema
    │
    ├──▶ lesson.json   (data/outputs/YYYY-MM-DD/)
    └──▶ lesson.md     (data/outputs/YYYY-MM-DD/)
```

On a `--dry-run`, the `generate_gemini_lesson()` step is replaced by
`create_dry_run_lesson()`, which builds a lesson from local fallback terms with
no API call. Validation and file writing are identical in both paths.
