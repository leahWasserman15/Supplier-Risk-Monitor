"""Helpers for persisting vendor research output."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


def safe_vendor_dirname(vendor: str) -> str:
    """Sanitize a vendor name for use as a directory name."""
    return vendor.replace("/", "-").replace("\\", "-").strip() or "unknown"


def save_research(vendor: str, summary: str, base_dir: str | Path = "Research") -> Path:
    """Write a research summary markdown file under Research/<vendor>/."""
    vendor_dir = Path(base_dir) / safe_vendor_dirname(vendor)
    vendor_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_path = vendor_dir / f"research_{stamp}.md"
    out_path.write_text(summary, encoding="utf-8")
    print(f"Saved to {out_path}")
    return out_path
