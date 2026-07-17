# Contributing to Market Vocabulary Agent

Thank you for your interest in contributing. This project is designed to help
beginners understand financial vocabulary through AI — and contributions of all
sizes are welcome, from fixing a typo to adding a new feature.

This guide walks you through everything you need to get started.

---

## Welcome

Market Vocabulary Agent is an educational project. Its purpose is to make
financial language accessible to people who watch Bloomberg Live but find the
terminology confusing. Every contribution — a clearer definition, a better
analogy, a more helpful error message, or a new feature — makes that goal more
achievable.

Contributions are accepted by invitation or prior arrangement with the author.
If you have found a bug or have a suggestion, please open an issue before
submitting a pull request.

---

## Development Environment

### Python Version

This project requires **Python 3.11 or later**. The project was developed and
tested on Python 3.11.9.

Check your Python version with:

```bash
python --version
```

If you need to install Python, download it from
[python.org/downloads](https://www.python.org/downloads/). Make sure to check
**Add Python to PATH** during installation on Windows.

---

### Setting Up a Virtual Environment

A virtual environment keeps the project's dependencies isolated from the rest of
your system. Always create one before installing anything.

```bash
# Step 1 — navigate to the project folder
cd market_vocabulary_agent

# Step 2 — create the virtual environment
python -m venv .venv

# Step 3 — activate it

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

You will see `(.venv)` at the start of your terminal prompt when the environment
is active. You need to activate it every time you open a new terminal window.

To deactivate it when you are done:

```bash
deactivate
```

---

### Installing Requirements

With the virtual environment active, install all dependencies:

```bash
pip install -r requirements.txt
```

This installs the exact versions of every library the project uses. Do not skip
this step.

---

### Setting Up Your `.env` File

Copy the following block into a new file named `.env` in the project root and
fill in your Gemini API key. This file is git-ignored and will never be committed.

```
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.5-flash
TIMEZONE=America/New_York
OUTPUT_DIR=data/outputs
BLOOMBERG_INBOX=data/bloomberg_inbox/today.txt
ENABLE_GOOGLE_SEARCH=false
```

Get a free Gemini API key at [aistudio.google.com](https://aistudio.google.com).

---

## Running the Project

### Dry Run (No API Key Required)

The dry-run mode generates a complete sample lesson from local data with no
network call. It is the safest way to test your changes.

```bash
python -m app.main --dry-run
```

Expected output:

```
Vocabulary lesson created successfully.
Open: data/outputs/2026-07-16/lesson.md
JSON: data/outputs/2026-07-16/lesson.json
Mode: Dry run - no Gemini API credits were used.
```

Always run the dry run first after making a change to confirm nothing is broken.

---

### Live Run (Requires API Key)

Once your `.env` file is configured, run the full pipeline:

```bash
python -m app.main
```

This calls the Gemini API, generates a real lesson from your Bloomberg notes, and
writes `lesson.md` and `lesson.json` to a date-stamped folder under
`data/outputs/`.

---

## Coding Standards

Consistent code style makes the project easier for everyone to read and review.
Please follow these guidelines before submitting a pull request.

### PEP 8

All Python code should follow [PEP 8](https://peps.python.org/pep-0008/), the
official Python style guide. The key rules:

- Indent with **4 spaces** (not tabs)
- Maximum line length of **88 characters**
- Two blank lines between top-level functions and classes
- One blank line between methods inside a class
- Imports at the top of the file, grouped: standard library, then third-party,
  then local

You can check your code automatically with a linter. From the project root:

```bash
pip install flake8
flake8 app/
```

---

### Type Hints

All function signatures should include type hints for parameters and return
values. Type hints make the code self-documenting and catch mistakes early.

```python
# Good
def read_bloomberg_notes(inbox_path: Path) -> list[str]:
    ...

# Not preferred
def read_bloomberg_notes(inbox_path):
    ...
```

---

### Docstrings

Public functions do not currently use docstrings — the code uses descriptive
function names and type hints instead. If you add a function whose purpose is not
immediately obvious from its name and signature alone, add a single concise line:

```python
def resolve_path(project_root: Path, configured_path: str) -> Path:
    """Return an absolute path, resolving relative paths from the project root."""
    ...
```

Do not write multi-paragraph docstrings for simple helper functions.

---

### Meaningful Variable Names

Choose names that make the code read like a sentence. Avoid single-letter
variables outside of short loops, and avoid abbreviations unless they are
universally understood (like `url` or `id`).

```python
# Good
for vocabulary_term in lesson.terms:
    ...

# Not preferred
for vt in lesson.terms:
    ...
```

---

## Pull Requests

1. **Clone the repository** locally (after receiving access from the author).

2. **Create a branch** for your change. Use a short, descriptive name:

   ```bash
   git checkout -b add-retry-logic
   git checkout -b fix-quiz-validator
   git checkout -b update-readme-installation
   ```

3. **Make your changes.** Keep each pull request focused on one thing. A PR that
   fixes a bug and adds a feature at the same time is harder to review.

4. **Test your change** by running the dry run and confirming the output is
   correct:

   ```bash
   python -m app.main --dry-run
   ```

5. **Commit your changes** (see the commit message guide below).

6. **Push your branch** and open a pull request against the `main` branch.

7. **Describe your change** in the pull request description. Explain what you
   changed, why, and how you tested it. A reviewer should not have to guess.

Pull requests are reviewed as time allows. Be patient and responsive to feedback
— reviewers may ask clarifying questions or suggest improvements.

---

## Commit Messages

Clear commit messages make the project history easy to understand. Follow this
format:

```
Short summary in the imperative mood (under 72 characters)

Optional longer explanation if the change is non-obvious. Explain WHY
the change was made, not just what it does — the code already shows what
changed. Wrap at 72 characters.
```

**Good examples:**

```
Add retry logic for transient Gemini 503 errors

Replace bare print() calls with logging module

Fix quiz answer validator for non-Tuesday weekdays

Add CONTRIBUTING.md for new contributors
```

**Not preferred:**

```
fixed stuff
updated main.py
WIP
changes
```

Use the **imperative mood** — write "Add feature" not "Added feature" or "Adds
feature". Think of it as completing the sentence: *"If applied, this commit
will... add retry logic for transient Gemini 503 errors."*

---

## Reporting Issues

If you find a bug, have a question, or want to suggest a feature, open an issue
on GitHub.

When reporting a bug, please include:

- **What you did** — the exact command you ran
- **What you expected** — the behaviour you were looking for
- **What happened** — the full error message or unexpected output
- **Your environment** — Python version, operating system, and which Gemini model
  is configured in your `.env`

The more detail you provide, the faster the issue can be diagnosed and fixed.

---

## A Note for Future Contributors

This project exists because financial markets move the world, but the language
used to describe them is often inaccessible to beginners. Most people who watch
Bloomberg or read financial news have to look up the same terms over and over
because there is nowhere that explains them simply, in context, based on what
was actually discussed that day.

Market Vocabulary Agent tries to fix that — one lesson at a time.

If you are a beginner yourself, you are exactly the right person to provide
feedback. You know what is confusing, what analogies click, and what explanations
fall flat. That perspective is more valuable than years of financial experience.

Suggestions that improve clarity, accessibility, and educational value are
welcome. If an explanation in the prompt, the README, or this document could be
clearer — please open an issue describing the change you have in mind.
