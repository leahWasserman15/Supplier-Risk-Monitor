# Supplier Risk Monitor

Procurement teams have hundreds of vendors and no idea which ones are about to fail, get sanctioned, or stop shipping.

A research agent gathers recent public news on the oldest-checked suppliers. A second agent scores supply risk from that summary only. Scores and flags write to a local SQLite vendor book.

**A single supplier failure costs more than this system costs for a decade.**

Everything feeds from public sources.

## Setup

Python 3.12. Copy `.env.example` to `.env` and add `OPENAI_API_KEY` plus either `EXA_API_KEY` or `TAVILY_API_KEY`. Set `SEARCH_TYPE` to `EXA` or `TAVILY` (defaults to Tavily if unset). Search runs through an MCP server via `npx`, so Node.js is required.

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

- **Run monitor** — preview the oldest-checked queue, then run research + risk evaluation
- **Vendor book** — browse suppliers; optionally show flagged risks only

The monitor picks vendors with the oldest last-checked date, gathers recent public news (default window 90 days), then scores supply risk from 0–5 (flagged at 3+). Transit, weather, and port events are out of scope; vendor finances, facilities, legal standing, and ability to deliver are in scope.

## Files

- `app.py` — Gradio frontend; runs a batch of research + eval
- `Research_Agent.py` — searches the web and writes a factual news summary
- `Evaluate_Agent.py` — classifies risk from that summary only (no extra search)
- `companies.py` — SQLite vendor book; seeds from Excel on first run
- `Research_Utils.py` — saves markdown under `Research/<vendor>/`
- `frontend_utils.py` — UI layout, theme, and vendor table
- `notebook.ipynb` — same pipeline, cell by cell
- `.env.example` — required API keys and `SEARCH_TYPE`
