"""Gradio UI styling, layout, and vendor-table helpers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import gradio as gr
import pandas as pd

from companies import CompanyBook

WORKBOOK_PATH = Path(__file__).resolve().with_name("real_pro_av_companies.xlsx")
DEFAULT_BATCH_SIZE = 100

DISPLAY_COLS = [
    "Company / Brand",
    "Category",
    "HQ Country",
    "Last Checked Date",
    "Risk_level",
    "is_risk",
    "Risk_Reason",
    "Last Risk Eval",
]

CUSTOM_CSS = """
:root {
  --srm-ink: #0f1c24;
  --srm-steel: #1a3a4a;
  --srm-accent: #c45c26;
  --srm-paper: #e8eef1;
  --srm-line: #c5d0d6;
}
.gradio-container {
  max-width: 100% !important;
  width: 100% !important;
  padding: 0 1.5rem 1.5rem !important;
  font-family: "IBM Plex Sans", "Segoe UI", sans-serif !important;
}
.srm-hero {
  background:
    linear-gradient(135deg, rgba(15, 28, 36, 0.92), rgba(26, 58, 74, 0.88)),
    repeating-linear-gradient(
      -12deg,
      transparent,
      transparent 10px,
      rgba(255, 255, 255, 0.02) 10px,
      rgba(255, 255, 255, 0.02) 11px
    );
  color: #f4f7f8;
  padding: 1.75rem 2rem 1.5rem;
  margin: 0 -1.5rem 1.25rem;
  border-bottom: 3px solid var(--srm-accent);
}
.srm-hero h1 {
  font-family: "IBM Plex Serif", Georgia, serif !important;
  font-size: 2rem !important;
  font-weight: 600 !important;
  margin: 0 0 0.35rem !important;
  letter-spacing: -0.02em;
  color: #f4f7f8 !important;
}
.srm-hero p {
  margin: 0;
  max-width: 42rem;
  color: #c9d6dc !important;
  font-size: 0.98rem;
  line-height: 1.45;
}
"""

HERO_HTML = """
<div class="srm-hero">
  <h1>Supplier Risk Monitor</h1>
  <p>
    Research the oldest-checked suppliers, classify supply risk from
    public news, and keep the vendor book current.
  </p>
</div>
"""


def load_company_book() -> CompanyBook:
    """Load the supplier data from the project's Excel workbook."""
    return CompanyBook(path=WORKBOOK_PATH)


def load_vendor_table(flagged_only: bool = False) -> pd.DataFrame:
    book = load_company_book()
    df = book.df.copy()
    for col in DISPLAY_COLS:
        if col not in df.columns:
            df[col] = None
    view = df[DISPLAY_COLS].copy()
    if flagged_only:
        view = view[view["is_risk"] == True]  # noqa: E712
    return view.sort_values(
        by=["is_risk", "Risk_level", "Last Checked Date"],
        ascending=[False, False, True],
        na_position="last",
    )


def preview_batch(batch_size: int) -> str:
    book = load_company_book()
    vendors = book.get_vendors(int(batch_size))
    if not vendors:
        return "_No vendors in the book._"
    lines = [f"**Next {len(vendors)} vendor(s) by oldest Last Checked Date:**", ""]
    lines.extend(f"- {name}" for name in vendors)
    return "\n".join(lines)


def build_theme() -> gr.themes.Base:
    return gr.themes.Base(
        primary_hue=gr.themes.Color(
            c50="#f4f7f8",
            c100="#e0e8ec",
            c200="#c5d0d6",
            c300="#9aafba",
            c400="#6d8a99",
            c500="#1a3a4a",
            c600="#16303d",
            c700="#122632",
            c800="#0f1c24",
            c900="#0a1318",
            c950="#050a0d",
        ),
        secondary_hue="slate",
        neutral_hue="slate",
        font=gr.themes.GoogleFont("IBM Plex Sans"),
        font_mono=gr.themes.GoogleFont("IBM Plex Mono"),
    ).set(
        button_primary_background_fill="#c45c26",
        button_primary_background_fill_hover="#a84c1f",
        button_primary_text_color="#ffffff",
        block_title_text_weight="600",
    )


def build_ui(
    *,
    run_monitor: Callable[..., Awaitable[Any]],
    default_batch_size: int = DEFAULT_BATCH_SIZE,
) -> gr.Blocks:
    supplier_count = len(load_company_book().df)

    with gr.Blocks(title="Supplier Risk Monitor", fill_width=True) as demo:
        gr.HTML(HERO_HTML)

        with gr.Tabs():
            with gr.Tab("Run monitor"):
                with gr.Row():
                    batch_size = gr.Number(
                        label="Vendors to process",
                        value=default_batch_size,
                        minimum=1,
                        maximum=supplier_count,
                        precision=0,
                        scale=1,
                    )
                    preview_btn = gr.Button(
                        "Preview queue", variant="secondary", scale=1
                    )
                    run_btn = gr.Button(
                        "Run research + risk eval", variant="primary", scale=1
                    )
                    gr.Column(scale=3)

                queue_md = gr.Markdown(value=preview_batch(default_batch_size))
                run_log = gr.Markdown(label="Run log", value="_Idle._")
                run_results = gr.Dataframe(
                    label="This run",
                    headers=[
                        "Vendor",
                        "Risk level",
                        "Flagged",
                        "Reason",
                        "Research file",
                    ],
                    interactive=False,
                    wrap=True,
                )

            with gr.Tab("Vendor book"):
                with gr.Row():
                    flagged_only = gr.Checkbox(
                        label="Show flagged risks only", value=False, scale=1
                    )
                    refresh_btn = gr.Button("Refresh", variant="secondary", scale=1)
                    gr.Column(scale=4)

                vendor_table = gr.Dataframe(
                    value=load_vendor_table(),
                    label="Company book",
                    interactive=False,
                    wrap=True,
                )

        preview_btn.click(fn=preview_batch, inputs=[batch_size], outputs=[queue_md])
        batch_size.change(fn=preview_batch, inputs=[batch_size], outputs=[queue_md])
        run_btn.click(
            fn=run_monitor,
            inputs=[batch_size],
            outputs=[run_log, run_results, vendor_table],
        )
        refresh_btn.click(
            fn=load_vendor_table, inputs=[flagged_only], outputs=[vendor_table]
        )
        flagged_only.change(
            fn=load_vendor_table, inputs=[flagged_only], outputs=[vendor_table]
        )

    return demo
