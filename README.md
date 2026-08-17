# Supplier Risk Monitor

Procurement teams have hundreds of vendors and no idea which ones are about to fail, get sanctioned, or blow up a shipment.

Agents watch each supplier for lawsuits, liens, enforcement actions, layoffs, port and weather disruption, and news. They maintain a live risk score and alert when something changes.

**A single supplier failure costs more than this system costs for a decade.**

Everything feeds from public sources.

## Setup

Copy `.env.example` to `.env` and add `OPENAI_API_KEY` plus either `EXA_API_KEY` or `TAVILY_API_KEY`. Set `SEARCH_TYPE` to `EXA` or `TAVILY`.

`real_pro_av_companies.xlsx` is the sample vendor book. Research files land in `Research/` and stay local.

## Run the UI

```bash
python app.py
```

Opens a Gradio app to preview the oldest-checked vendor queue, run research + risk evaluation, and browse the company book.

The monitor picks vendors with the oldest last-checked date, gathers recent public news, then scores supply risk from 0–5 (flag at 3+). Scores write back to the workbook.

## Files

- `app.py` — Gradio frontend; runs a batch of research + eval
- `Research_Agent.py` — searches the web and writes a factual news summary
- `Evaluate_Agent.py` — classifies risk from that summary only (no extra search)
- `companies.py` — reads/writes `real_pro_av_companies.xlsx`
- `Research_Utils.py` — saves markdown under `Research/<vendor>/`
- `frontend_utils.py` — UI layout, theme, and vendor table
- `notebook.ipynb` — same pipeline, cell by cell
- `.env.example` — required API keys and `SEARCH_TYPE`
