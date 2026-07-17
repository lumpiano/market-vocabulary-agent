# Market Vocabulary Agent

A command-line AI application that transforms your daily Bloomberg Live notes into
a structured, beginner-friendly financial vocabulary lesson — delivered as both
Markdown and JSON, validated against a strict schema before anything is written
to disk.

---

## Overview

Market Vocabulary Agent reads the notes you take while watching Bloomberg Live,
sends them to the Gemini API, and returns a complete daily lesson: five market
vocabulary terms explained in plain English, an everyday analogy, a realistic
market example, a cause-and-effect chain, a multiple-choice quiz, and a
five-minute study plan.

Each lesson is tied to a daily theme (earnings on Mondays, rates and inflation
on Tuesdays, and so on). The agent prioritises terms connected to whatever you
personally heard that day, so the lesson reflects your actual viewing session
rather than a generic curriculum.

Every lesson is validated against a Pydantic schema before it is saved. If the
model returns a malformed or incomplete response, the agent prints a structured
error and exits without writing any files.

---

## Commercial Vision

Market Vocabulary Agent is the foundation of a personal finance-education
platform. The v0.1 pipeline — Bloomberg inbox, Gemini generation, schema
validation, dual-format output — is designed to grow into a full learning system
with a browser dashboard, quiz history, spaced-repetition vocabulary tracking,
weekly AI-generated summaries, and optional cloud automation.

The immediate goal is a tool that closes the gap between hearing financial
language on Bloomberg and understanding why markets move.

---

## Current Features

- **Bloomberg inbox integration** — paste or type today's notes into a plain-text
  file; the agent reads and incorporates them automatically
- **Gemini structured-output generation** — uses `response_schema=MarketLesson`
  and `response_mime_type="application/json"` to constrain model output directly
  to the required schema
- **Five vocabulary terms per lesson** — each term includes:
  - Plain-English definition
  - Everyday analogy
  - Realistic market example
  - Why-it-matters explanation
- **Cause-and-effect chain** — step-by-step sequence linking market events
- **Multiple-choice quiz** — one question with a validated answer
- **Five-minute study plan** — structured minute-by-minute reading guide
- **Dual output** — `lesson.md` (human-readable) and `lesson.json`
  (machine-readable), written to a dated folder under `data/outputs/`
- **Pydantic schema validation** — every lesson is validated before writing;
  malformed responses are rejected with a structured error
- **Dry-run mode** (`--dry-run`) — generates a fully structured sample lesson
  from local fallback data with no API call and no credits used
- **Optional Google Search grounding** (`--search`) — enables real-time web
  research during generation for fact-checked, source-cited lessons
- **Weekday themes** — each day of the week has a fixed topic so the vocabulary
  builds systematically across the week

---

## Project Structure

```
market_vocabulary_agent/
├── app/
│   ├── __init__.py          # Package marker; required for python -m app.main
│   ├── main.py              # Entry point — CLI, orchestration, all pipeline logic
│   └── models.py            # Pydantic schema: MarketLesson, VocabularyTerm, QuizQuestion
├── data/
│   ├── bloomberg_inbox/
│   │   └── today.txt        # Write your Bloomberg notes here before each run
│   └── outputs/             # Git-ignored; created at runtime
│       └── YYYY-MM-DD/
│           ├── lesson.json
│           └── lesson.md
├── .env                     # Git-ignored; holds your API key and settings
├── .gitignore
├── ARCHITECTURE.md          # Internal system documentation and pipeline diagrams
├── CHANGELOG.md             # Version history
├── CONTRIBUTING.md          # Contribution guidelines
├── LICENSE                  # Proprietary — All Rights Reserved
├── PROJECT_STRUCTURE.md     # Repository layout reference
├── README.md
├── ROADMAP.md               # Planned versions and features
└── requirements.txt
```

---

## Requirements

- Python 3.11 or later
- A Google Gemini API key ([aistudio.google.com](https://aistudio.google.com))

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/lumpiano/market-vocabulary-agent.git
cd market_vocabulary_agent

# 2. Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

Dependencies (`requirements.txt`):

| Package | Version | Purpose |
|---|---|---|
| `google-genai` | `>=2.0.0` | Gemini API client |
| `pydantic` | `>=2.8` | Schema definition and validation |
| `python-dotenv` | `>=1.0` | `.env` file loading |

---

## Environment Variables

Create a `.env` file in the project root with the following content:

```env
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.5-flash
TIMEZONE=America/New_York
OUTPUT_DIR=data/outputs
BLOOMBERG_INBOX=data/bloomberg_inbox/today.txt
ENABLE_GOOGLE_SEARCH=false
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | Yes | — | Your Google Gemini API key |
| `GEMINI_MODEL` | No | `gemini-3.5-flash` | Gemini model name |
| `TIMEZONE` | No | `America/New_York` | Timezone used to determine the lesson date and weekday |
| `OUTPUT_DIR` | No | `data/outputs` | Root directory for saved lessons |
| `BLOOMBERG_INBOX` | No | `data/bloomberg_inbox/today.txt` | Path to your daily Bloomberg notes file |
| `ENABLE_GOOGLE_SEARCH` | No | `false` | Set to `true` to enable Google Search grounding by default |

The `.env` file is git-ignored and will never be committed to version control.

---

## Adding Bloomberg Notes

Before each run, open `data/bloomberg_inbox/today.txt` and write one note per
line describing what you heard on Bloomberg Live. Bullet prefixes (`-`, `*`) are
stripped automatically.

```
- Treasury yields rose sharply this morning.
- The Fed signaled rates may stay higher for longer.
- I do not understand what an inverted yield curve means.
- NVIDIA issued stronger-than-expected forward guidance.
- Oil inventories were lower than expected.
```

If the file is empty or missing, the agent generates a general lesson for the
day's theme without personalisation and creates the file automatically on the
next run.

---

## Usage

### Dry Run — No API Key Required

Generates a complete sample lesson from local fallback data. No network call,
no Gemini credits used. Use this to verify your setup or test changes before
going live.

```bash
python -m app.main --dry-run
```

Expected output:

```
Vocabulary lesson created successfully.
Open: data/outputs/2026-07-17/lesson.md
JSON: data/outputs/2026-07-17/lesson.json
Mode: Dry run - no Gemini API credits were used.
```

---

### Live Generation — Calls the Gemini API

Requires `GEMINI_API_KEY` to be set in `.env`. Reads your Bloomberg notes,
builds a structured prompt, calls Gemini, validates the response, and writes
the lesson files.

```bash
python -m app.main
```

Expected output:

```
Vocabulary lesson created successfully.
Open: data/outputs/2026-07-17/lesson.md
JSON: data/outputs/2026-07-17/lesson.json
Mode: Gemini without Google Search.
```

---

### Live Generation with Google Search Grounding

Enables Gemini to perform real-time web lookups to verify current facts, prices,
and events before answering. Requires a Gemini plan that supports Google Search
grounding.

```bash
python -m app.main --search
```

You can also set `ENABLE_GOOGLE_SEARCH=true` in `.env` to enable grounding on
every run without passing the flag manually.

When grounding is active, the agent instructs Gemini to cite sources and clearly
separate verified facts from interpretation. When grounding is disabled, Gemini
is instructed to use only stable educational examples and to note that no
live web research was performed.

The `--search` flag is silently ignored in `--dry-run` mode.

---

## Output Files

Each successful run writes two files to a date-stamped subfolder:

```
data/outputs/
└── 2026-07-17/
    ├── lesson.md    # Human-readable Markdown lesson
    └── lesson.json  # Machine-readable JSON matching the MarketLesson schema
```

Running the agent again on the same date overwrites both files for that date.
The `data/outputs/` directory is git-ignored and is never committed to version
control.

---

## Daily Themes

Each weekday has a fixed theme. Vocabulary terms are selected to match both
the theme and your Bloomberg notes for that day.

| Day | Theme |
|---|---|
| Monday | Corporate earnings and company fundamentals |
| Tuesday | Interest rates, bonds, inflation, and the Federal Reserve |
| Wednesday | Commodities |
| Thursday | Technology, AI, semiconductors, software, and cloud computing |
| Friday | Global markets, currencies, trade, and economic indicators |
| Saturday | Mixed market vocabulary review and retrieval practice |
| Sunday | Weekly recap and weak-area review |

---

## Data Model

All generated content is validated against three Pydantic models before
anything is written to disk.

### `VocabularyTerm`

| Field | Type | Constraint |
|---|---|---|
| `term` | `str` | Non-empty |
| `plain_english_definition` | `str` | Non-empty |
| `everyday_analogy` | `str` | Non-empty |
| `market_example` | `str` | Non-empty |
| `why_it_matters` | `str` | Non-empty |

### `QuizQuestion`

| Field | Type | Constraint |
|---|---|---|
| `question` | `str` | Non-empty |
| `choices` | `list[str]` | At least 2 items |
| `answer` | `str` | Must exactly match one item in `choices` |
| `explanation` | `str` | Non-empty |

### `MarketLesson`

| Field | Type | Constraint |
|---|---|---|
| `lesson_date` | `str` | Non-empty |
| `weekday` | `str` | Non-empty |
| `theme` | `str` | Non-empty |
| `bloomberg_notes_used` | `list[str]` | — |
| `terms` | `list[VocabularyTerm]` | Exactly 5; no duplicate term names |
| `cause_and_effect_chain` | `list[str]` | At least 2 steps |
| `quiz` | `QuizQuestion` | See above |
| `five_minute_study_plan` | `list[str]` | At least 1 step |
| `sources` | `list[str]` | — |
| `disclaimer` | `str` | Non-empty |

If validation fails, the agent prints a structured `ValidationError` to stderr
and exits with code `1`. No output files are created or modified on failure.

---

## Safety and Scope Limitations

The agent enforces the following guardrails in every prompt sent to Gemini,
regardless of the model's own safety filters:

- **No profit promises** — the agent does not predict market outcomes
- **No personalised trading instructions** — lessons are educational only
- **No brokerage account references** — the agent does not connect to or mention
  any trading platform
- **No Bloomberg article reproduction** — the agent does not copy or quote
  Bloomberg content
- **No claims of direct Bloomberg access** — the agent processes the user's
  own notes, not a live data feed
- **Fixed disclaimer** — every lesson includes the exact text:
  *"Educational information only. Not personalized financial, investment,
  legal, or tax advice."*

When Google Search grounding is disabled, Gemini is instructed to use only
stable educational examples and to explicitly state that no live market data
was consulted.

---

## Current Status

**Version 0.1** — initial working release.

The core pipeline is complete and validated end-to-end:

| Component | Status |
|---|---|
| Bloomberg inbox reading | Complete |
| Weekday-themed prompt construction | Complete |
| Gemini structured-output generation | Complete |
| Pydantic schema validation | Complete |
| Markdown lesson output | Complete |
| JSON lesson output | Complete |
| Date-stamped output folders | Complete |
| Dry-run mode | Complete |
| Google Search grounding (optional) | Complete |

---

## Roadmap

### Version 0.2 — Robustness and Flexibility

- Dated inbox files (`YYYY-MM-DD.txt`) alongside `today.txt`
- Prompt templates extracted to a `prompts/` directory
- Exponential-backoff retry logic for transient API failures
- Structured config file (`config.toml`) for advanced settings
- Python `logging` module replacing bare `print()` calls

### Version 0.3 — Dashboard and Progress Tracking

- Local Streamlit dashboard for reading and navigating lessons
- Historical lesson browser by date and theme
- Full-text vocabulary search across all past lessons
- Quiz history and per-term accuracy tracking in `data/progress.json`
- Daily learning streak and progress summary

### Version 1.0 — Automation and Intelligence

- Daily automation via cron (Linux/macOS) or Task Scheduler (Windows)
- Weekly summary mode (`--weekly`) generating a consolidated review lesson
- Learning analytics: quiz accuracy, retention curves, themed progress charts
- Vocabulary mastery levels with spaced-repetition scheduling
- AI tutor mode (`--tutor`) for conversational follow-up on lesson content
- Optional cloud deployment for device-agnostic access

---

## License

Copyright © 2026 Guadalupe Contreras. All Rights Reserved.

This repository is shared for evaluation and portfolio purposes only.
No part of this software may be copied, modified, distributed, sublicensed,
resold, or used for commercial purposes without prior written permission.

For licensing inquiries: guadalupe8contreras@gmail.com
