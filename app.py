"""Gradio frontend for Supplier Risk Monitor."""

from __future__ import annotations

import functools
import subprocess
import sys

import gradio as gr
import pandas as pd
from dotenv import load_dotenv

load_dotenv(override=True)

# Windows Jupyter/Gradio kernels give MCP stdio a stderr handle with no fileno.
# Point stderr at DEVNULL so MCPServerStdio works the same as on Mac/Linux.
if sys.platform == "win32":
    import agents.mcp.server

    agents.mcp.server.stdio_client = functools.partial(
        agents.mcp.server.stdio_client, errlog=subprocess.DEVNULL
    )

from Evaluate_Agent import evaluate_vendor  # noqa: E402
from Research_Agent import research_vendor  # noqa: E402
from Research_Utils import save_research  # noqa: E402
from frontend_utils import (  # noqa: E402
    CUSTOM_CSS,
    DEFAULT_BATCH_SIZE,
    build_theme,
    build_ui,
    load_company_book,
    load_vendor_table,
)


async def run_monitor(batch_size: int, progress=gr.Progress()):
    batch_size = max(1, int(batch_size))
    book = load_company_book()
    vendors = book.get_vendors(batch_size)
    if not vendors:
        empty = pd.DataFrame(
            columns=["Vendor", "Risk level", "Flagged", "Reason", "Research file"]
        )
        yield "No vendors to process.", empty, load_vendor_table()
        return

    rows: list[dict] = []
    log_lines: list[str] = [f"Starting batch of {len(vendors)}…"]
    results_df = pd.DataFrame(
        columns=["Vendor", "Risk level", "Flagged", "Reason", "Research file"]
    )
    yield "\n".join(log_lines), results_df, load_vendor_table()

    for i, vendor in enumerate(vendors, start=1):
        progress((i - 1) / len(vendors), desc=f"Researching {vendor}")
        log_lines.append(f"\n### [{i}/{len(vendors)}] {vendor}")
        log_lines.append("Researching…")
        yield "\n".join(log_lines), results_df, load_vendor_table()

        try:
            summary = await research_vendor(vendor)
            out_path = save_research(vendor, summary)
            book.update_research_date(vendor)
            log_lines.append(f"Saved research → `{out_path}`")
            log_lines.append("Evaluating risk…")
            yield "\n".join(log_lines), results_df, load_vendor_table()

            decision = await evaluate_vendor(vendor, summary)
            book.update_risk_fields(vendor, decision)

            rows.append(
                {
                    "Vendor": vendor,
                    "Risk level": decision.Risk_level,
                    "Flagged": decision.is_risk,
                    "Reason": decision.Risk_Reason,
                    "Research file": str(out_path),
                }
            )
            results_df = pd.DataFrame(rows)
            flag = "⚠ flagged" if decision.is_risk else "clear"
            log_lines.append(
                f"**Done** — level {decision.Risk_level} ({flag}). {decision.Risk_Reason}"
            )
            log_lines.append("")
            log_lines.append("<details><summary>Research summary</summary>")
            log_lines.append("")
            log_lines.append(summary)
            log_lines.append("")
            log_lines.append("</details>")
        except Exception as exc:  # noqa: BLE001 — surface per-vendor failures in UI
            log_lines.append(f"**Error:** `{type(exc).__name__}: {exc}`")
            rows.append(
                {
                    "Vendor": vendor,
                    "Risk level": None,
                    "Flagged": None,
                    "Reason": f"Error: {exc}",
                    "Research file": "",
                }
            )
            results_df = pd.DataFrame(rows)

        progress(i / len(vendors), desc=f"Finished {vendor}")
        yield "\n".join(log_lines), results_df, load_vendor_table()

    log_lines.append("\n---\n**Batch complete.**")
    yield "\n".join(log_lines), results_df, load_vendor_table(False)


def create_app() -> gr.Blocks:
    return build_ui(
        run_monitor=run_monitor,
        default_batch_size=DEFAULT_BATCH_SIZE,
    )


if __name__ == "__main__":
    create_app().launch(theme=build_theme(), inbrowser=True, css=CUSTOM_CSS)
