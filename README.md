# Supplier Risk Monitor

Procurement teams have hundreds of vendors and no idea which ones are about to fail, get sanctioned, or stop shipping.

A research agent gathers recent public news on the oldest-checked suppliers. A second agent scores supply risk from that summary only. When a vendor's flagged status changes during a run, a notify agent writes a short alert and emails it. Scores and flags write to a local SQLite vendor book.

**A single supplier failure costs more than this system costs for a decade.**

Everything feeds from public sources.

## Setup

Python 3.12. Copy `.env.example` to `.env` and add:

- `OPENAI_API_KEY`
- Either `EXA_API_KEY` or `TAVILY_API_KEY`, plus `SEARCH_TYPE=EXA` or `SEARCH_TYPE=TAVILY` (defaults to Tavily if unset)
- Email settings for alerts: `EMAIL_ADDRESS`, `EMAIL_SMTP_SERVER`, `EMAIL_APP_PASSWORD` (optional `EMAIL_SMTP_PORT`, default `587`)

Search runs through an MCP server via `npx`, so Node.js is required.

For Gmail SMTP, enable 2-Step Verification and create an [App Password](https://myaccount.google.com/apppasswords). Use that password in `EMAIL_APP_PASSWORD`, not your normal Gmail password.

```bash
uv sync
uv run python app.py
```

Use the project environment (`uv run` or `.venv`), not a global Python. The OpenAI Agents SDK lives in `.venv`.

`real_pro_av_companies.xlsx` is the sample vendor book. On first run it is copied into `suppliers.db`, converting Excel `is_risk` 1/0 values to flags. After that, reads and writes go to the database, not the spreadsheet. Delete `suppliers.db` to rebuild from Excel.

Research files land in `Research/` and stay local. The database and research output are gitignored.

## Run the UI

```bash
uv run python app.py
```

Opens a Gradio app with two tabs:

- **Run monitor** — preview the oldest-checked queue, run research + risk evaluation, then send a notification if any vendor's flagged status changed during the run. A status panel shows the current step and overall progress.
- **Vendor book** — browse suppliers; optionally show flagged risks only

The monitor picks vendors with the oldest last-checked date, gathers recent public news (default window 90 days), then scores supply risk from 0–5 (flagged at 3+). Transit, weather, and port events are out of scope; vendor finances, facilities, legal standing, and ability to deliver are in scope.

## Notifications

After each batch, the app compares `is_risk` changes since the run started. If anything changed, `Notify_Agent` builds a structured alert:

- **Header** — e.g. `1 new risks, 2 cleared` (used as the email subject)
- **Body** — one line per vendor with level and a concise reason summary

If a vendor flipped more than once in the same run, only the latest change is reported. If nothing changed, no email is sent.

The same flow is available in `notebook.ipynb` via `notify_from_run_start(run_start)`.

## Files

- `app.py` — Gradio frontend; runs a batch of research + eval + notify
- `Research_Agent.py` — searches the web and writes a factual news summary
- `Evaluate_Agent.py` — classifies risk from that summary only (no extra search)
- `Notify_Agent.py` — formats risk-change alerts and sends email
- `Notify_Utils.py` — builds notify payload from audit log + latest research
- `Supplier_Database_Utils.py` — SQLite vendor book, change audit log; seeds from Excel on first run
- `Research_Utils.py` — saves markdown under `Research/<vendor>/`
- `Frontend_Utiles.py` — UI layout, theme, vendor table, and run status panel
- `notebook.ipynb` — same pipeline, cell by cell
- `.env.example` — required API keys, search provider, and email settings
