# Roadmap

This document outlines the planned development trajectory for the Market
Vocabulary Agent. Each version builds on the previous one, moving from a working
local CLI tool toward a fully automated, analytics-driven learning platform.

Phases are listed in order of priority. Items within a phase may be delivered
incrementally and are not strictly ordered.

---

## Version 0.1 — Foundation ✅ Completed

**Released:** 2026-07-16

The first stable end-to-end release. Establishes the core pipeline from Bloomberg
notes to validated lesson files and puts the project under version control with
full documentation.

| Feature | Status |
|---|---|
| Live Gemini API integration with structured-output generation | ✅ Done |
| Dry-run mode for offline testing without API credits | ✅ Done |
| Pydantic schema validation (`MarketLesson`, `VocabularyTerm`, `QuizQuestion`) | ✅ Done |
| JSON lesson output (`lesson.json`) | ✅ Done |
| Markdown lesson output (`lesson.md`) | ✅ Done |
| Date-stamped output folders (`data/outputs/YYYY-MM-DD/`) | ✅ Done |
| Git repository with `.gitignore`, secrets excluded | ✅ Done |
| README, LICENSE, ARCHITECTURE, PROJECT_STRUCTURE, CHANGELOG, ROADMAP | ✅ Done |

---

## Version 0.2 — Robustness and Flexibility

**Target:** Near-term

This phase hardens the pipeline for everyday use. The goal is to make the agent
more reliable under real conditions — network failures, varied input formats, and
growing personal note collections — without changing the user-facing behaviour
significantly.

### Multiple Bloomberg Note Files

Support a dated inbox pattern (`YYYY-MM-DD.txt`) alongside `today.txt`, allowing
the user to maintain a running archive of Bloomberg sessions. The agent selects
the file matching the current date, falling back to `today.txt` if no dated file
exists.

```
data/bloomberg_inbox/
├── today.txt          ← current fallback
├── 2026-07-14.txt
├── 2026-07-15.txt
└── 2026-07-16.txt
```

### Improved Prompt Templates

Extract the prompt string from `main.py` into a dedicated template file under
`prompts/`. Separating prompt text from application logic makes it easier to
iterate on wording, test variations, and review changes in version control without
touching Python source.

```
prompts/
├── lesson_prompt.txt
└── weekly_summary_prompt.txt   ← future
```

### Retry Logic for API Failures

Wrap the Gemini API call in an exponential-backoff retry loop with a configurable
maximum attempt count. Transient 503 errors (as seen during v0.1 testing) are
retried automatically rather than exiting immediately, with a clear log message on
each attempt.

```
Attempt 1 of 3 — model unavailable, retrying in 5s...
Attempt 2 of 3 — model unavailable, retrying in 10s...
Attempt 3 of 3 — success.
```

### Configuration File

Introduce a `config.toml` or `config.yaml` as an optional layer above `.env`.
Structured config allows more expressive settings — retry counts, fallback model
names, prompt temperature, output format preferences — without crowding the
environment file.

### Improved Logging

Replace bare `print()` calls with Python's `logging` module. Log levels (`DEBUG`,
`INFO`, `WARNING`, `ERROR`) are configurable via an environment variable or config
file. A `--verbose` flag exposes debug-level output at the CLI without changing
the default quiet behaviour.

| Level | Example |
|---|---|
| `INFO` | `Lesson saved to data/outputs/2026-07-16/lesson.md` |
| `WARNING` | `No Bloomberg notes found. Generating general lesson.` |
| `ERROR` | `Gemini API returned 503. Attempt 1 of 3.` |
| `DEBUG` | Full prompt text, raw API response, validation trace |

---

## Version 0.3 — Dashboard and Progress Tracking

**Target:** Medium-term

This phase introduces a local web dashboard built with Streamlit, turning the
agent from a CLI tool into an interactive learning environment. The learner can
browse past lessons, replay quizzes, and track progress without touching the
terminal.

### Streamlit Dashboard

A local Streamlit app (`app/dashboard.py`) that reads the `data/outputs/`
directory and presents lessons in a browser. Launched with a single command.

```bash
streamlit run app/dashboard.py
```

Key views:

- **Today's lesson** — full lesson rendered with term cards and the quiz
- **Calendar view** — one tile per day; green for lessons completed, grey for
  gaps
- **Term of the day** — random review card drawn from the full vocabulary history

### Historical Lesson Browser

Navigate all past lessons by date or by theme. Each lesson is displayed in the
same format as the current day's output. Clicking a term opens a detail card with
its definition, analogy, example, and why-it-matters explanation.

### Vocabulary Search

Full-text search across every term ever generated. Results show the term name,
the lesson date it appeared in, and the theme. Useful for finding a definition
heard on Bloomberg without remembering which day it was covered.

### Progress Tracking

A `data/progress.json` file records quiz results, review counts, and last-seen
dates for every term. The dashboard surfaces this as a simple progress view — how
many terms learned, how many quizzes attempted, current streak.

```json
{
  "Basis Point": {
    "first_seen": "2026-07-14",
    "quiz_attempts": 3,
    "quiz_correct": 2,
    "last_reviewed": "2026-07-16"
  }
}
```

### Quiz History

Replay any past quiz from the lesson archive. Correct and incorrect answers are
stored in `progress.json` so the system can identify weak areas. The dashboard
shows a per-term accuracy table sorted by lowest score.

---

## Version 1.0 — Automation and Intelligence

**Target:** Long-term

Version 1.0 transforms the agent into a fully automated, self-improving learning
system. The learner receives daily lessons without manual intervention, receives
weekly performance summaries, and can query an AI tutor about any term or concept.

### Daily Automation

A scheduled task runs the agent each morning at a configured time — cron on
Linux/macOS, Task Scheduler on Windows — without any manual command. An optional
email or desktop notification delivers the lesson link when it is ready.

```
07:00 ── cron / Task Scheduler
              │
              ▼
        python -m app.main
              │
              ├──▶ lesson.md / lesson.json
              └──▶ email / desktop notification
```

### Weekly Summaries

A `--weekly` mode generates a consolidated Sunday recap lesson. It reads the
seven most recent lesson files, compiles the full list of terms covered, and asks
Gemini to produce a review lesson that prioritises terms with low quiz accuracy
scores from `progress.json`.

### Learning Analytics

Charts and metrics derived from `progress.json`, accessible from the dashboard:

- Quiz accuracy over time (line chart)
- Terms learned per week (bar chart)
- Strongest and weakest themes (radar chart)
- Daily streak tracker
- Estimated vocabulary retention curve

Optionally exported as a weekly Markdown report alongside the lesson files.

### Vocabulary Mastery Tracking

Each term is assigned a mastery level (`new`, `learning`, `reviewing`, `mastered`)
using a spaced-repetition model. The prompt builder reads the mastery index and
avoids reintroducing mastered terms unless in a review context. Terms at the
`learning` stage are surfaced more frequently until they reach `mastered`.

```
new  ──▶  learning  ──▶  reviewing  ──▶  mastered
             ▲                │
             └── incorrect quiz answer resets level
```

### AI Tutor

A conversational follow-up session that launches after a lesson is generated. The
tutor has the day's `lesson.json` loaded as context and can answer clarifying
questions, generate additional examples, or explain terms in a different way. The
session history is kept in memory for the duration of the conversation.

```bash
python -m app.main --tutor

Tutor: Today's lesson is ready. What would you like to explore?
You:   Can you give me another example of yield curve inversion?
Tutor: Sure. Imagine ...
```

### Cloud Deployment

Optional deployment to a cloud provider (e.g. a small VM or serverless function)
so the agent runs on a schedule without requiring the user's local machine to be
on. The dashboard becomes accessible from any device via a private URL. Secrets
are managed through the provider's secret store rather than a local `.env` file.

---

## Summary

| Version | Theme | Status |
|---|---|---|
| 0.1 | Foundation — core pipeline, validation, documentation | ✅ Released |
| 0.2 | Robustness — retries, logging, flexible config, prompt templates | 🔲 Planned |
| 0.3 | Dashboard — Streamlit UI, quiz history, progress tracking | 🔲 Planned |
| 1.0 | Automation — daily scheduling, AI tutor, cloud deployment | 🔲 Planned |
