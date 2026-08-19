"""Helpers for persisting vendor research output."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


def safe_vendor_dirname(vendor: str) -> str:
    """Sanitize a vendor name for use as a directory name."""
    return vendor.replace("/", "-").replace("\\", "-").strip() or "unknown"


def get_latest_research(vendor: str, base_dir: str | Path = "Research") -> tuple[str, str]:
    """Return (filename, text) of the most recent research file for a vendor.

    Returns ("N/A", "No research file found.") if none exists.
    """
    vendor_dir = Path(base_dir) / safe_vendor_dirname(vendor)
    md_files = sorted(vendor_dir.glob("research_*.md")) if vendor_dir.exists() else []
    if not md_files:
        return "N/A", "No research file found."
    latest = md_files[-1]
    return latest.name, latest.read_text(encoding="utf-8")


def save_research(vendor: str, summary: str, base_dir: str | Path = "Research") -> Path:
    """Write a research summary markdown file under Research/<vendor>/."""
    vendor_dir = Path(base_dir) / safe_vendor_dirname(vendor)
    vendor_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_path = vendor_dir / f"research_{stamp}.md"
    out_path.write_text(summary, encoding="utf-8")
    print(f"Saved to {out_path}")
    return out_path
