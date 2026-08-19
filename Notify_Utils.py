"""Helpers for building risk-change notification content."""

from __future__ import annotations

import pandas as pd

from Supplier_Database_Utils import CompanyBook
from Research_Utils import get_latest_research


def build_changes(flagged: pd.DataFrame) -> str:
    """Build notify payload with scored reason plus source research context."""
    if flagged.empty:
        return ""

    # Pull latest evaluated values so notify can anchor summaries to scored reasons.
    book = CompanyBook()
    latest = (
        book.df[["Company / Brand", "Risk_level", "Risk_Reason"]]
        .rename(columns={"Company / Brand": "vendor"})
        .copy()
    )

    changes = (
        flagged.sort_values("id", ascending=False)
        .drop_duplicates(subset="vendor", keep="first")
        .merge(latest, on="vendor", how="left")
    )
    sections: list[str] = []
    for _, row in changes.iterrows():
        vendor_name = row.get("vendor", "Unknown Vendor")
        old_value = str(row.get("old_value", "")).strip()
        new_value = str(row.get("new_value", "")).strip()
        status = "NEW RISK" if new_value == "1" else "CLEARED"
        file_label, summary_text = get_latest_research(vendor_name)
        sections.append(
            f"## {vendor_name}\n"
            f"Status: {status}\n"
            f"Transition: {old_value or 'null'} -> {new_value or 'null'}\n"
            f"Risk level: {row.get('Risk_level', 'unknown')}\n"
            f"Reason: {row.get('Risk_Reason', 'No reason recorded.')}\n"
            f"Source: {file_label}\n\n"
            f"Research summary:\n{summary_text}"
        )
    return "\n\n---\n\n".join(sections)
