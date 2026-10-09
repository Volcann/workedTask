"""Utility functions for date parsing, text formatting, and ticket extraction."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Sequence


def parse_target_date(raw_date: str | date | datetime | None = None) -> date:
    """Parse various date formats into a standard datetime.date object.

    Supported formats:
    - None or 'today': current date
    - 'yesterday': previous day
    - '11-SEP-2026', '16-Sep-2026', '22-sep-2026'
    - '2026-09-11' (ISO)
    - '2026/09/11'
    - '11-09-2026', '11/09/2026'
    - 'Sep 11 2026', 'September 11, 2026'

    Raises:
        ValueError: If raw_date cannot be recognized as a valid date.
    """
    if raw_date is None:
        return date.today()

    if isinstance(raw_date, datetime):
        return raw_date.date()

    if isinstance(raw_date, date):
        return raw_date

    clean_str = raw_date.strip().lower()

    if clean_str in ("today", "now"):
        return date.today()
    if clean_str == "yesterday":
        return date.today() - timedelta(days=1)

    patterns = [
        "%d-%b-%Y",  # 11-SEP-2026 / 11-Sep-2026
        "%d-%B-%Y",  # 11-September-2026
        "%Y-%m-%d",  # 2026-09-11
        "%Y/%m/%d",  # 2026/09/11
        "%d-%m-%Y",  # 11-09-2026
        "%d/%m/%Y",  # 11/09/2026
        "%m/%d/%Y",  # 09/11/2026
        "%b %d %Y",  # Sep 11 2026
        "%B %d %Y",  # September 11 2026
        "%b %d, %Y",  # Sep 11, 2026
        "%B %d, %Y",  # September 11, 2026
    ]

    for fmt in patterns:
        try:
            return datetime.strptime(clean_str, fmt).date()
        except ValueError:
            pass

    # Try normalizing hyphenated uppercase like 11-SEP-2026
    for fmt in ("%d-%b-%Y", "%d-%B-%Y"):
        try:
            return datetime.strptime(raw_date.strip(), fmt).date()
        except ValueError:
            pass

    raise ValueError(
        f"Unable to parse date '{raw_date}'. Supported formats include: "
        f"'11-SEP-2026', 'YYYY-MM-DD', 'DD-MM-YYYY', 'today', 'yesterday'."
    )


def format_status_date(dt: date) -> str:
    """Format a date object into the canonical report date format: '11-SEP-2026'."""
    return dt.strftime("%d-%b-%Y").upper()


def format_iso_date(dt: date) -> str:
    """Format date into standard ISO string: 'YYYY-MM-DD'."""
    return dt.strftime("%Y-%m-%d")


def extract_ticket_prefix(text: str) -> str | None:
    """Extract ticket prefix like HMT-258 or HTM-228 or MB-228 from a text string."""
    match = re.search(r"\b([A-Z]{2,10}-\d+)\b", text)
    if match:
        return match.group(1)
    return None


def clean_commit_message(msg: str) -> str:
    """Clean and return the primary headline of a commit message."""
    if not msg:
        return ""
    lines = [line.strip() for line in msg.strip().splitlines() if line.strip()]
    if not lines:
        return ""
    headline = lines[0]
    return headline


def is_merge_commit(msg: str) -> bool:
    """Check if the commit is an automated merge commit."""
    lower = msg.lower()
    return (
        lower.startswith("merge pull request")
        or lower.startswith("merge branch")
        or "merge remote-tracking branch" in lower
    )


def clean_markdown_bullets(text: str) -> list[str]:
    """Extract bullet points from a markdown text block."""
    bullets: list[str] = []
    if not text:
        return bullets

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # Remove markdown checkbox markers like [ ] or [x]
        line = re.sub(r"^[-*]\s*\[[ xX]\]\s*", "- ", line)
        # Bullet patterns
        if line.startswith(("- ", "* ", "• ", "-> ")):
            cleaned = re.sub(r"^(?:->|[-*•])\s*", "", line).strip()
            if cleaned:
                bullets.append(cleaned)
    return bullets


def format_arrow_lines(lines: Sequence[str]) -> list[str]:
    """Prefix non-empty lines with '-> '."""
    formatted = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("-> "):
            formatted.append(stripped)
        elif stripped.startswith("->"):
            formatted.append("-> " + stripped[2:].strip())
        else:
            formatted.append(f"-> {stripped}")
    return formatted


def clean_reports_directory(
    reports_dir: str | Path = "reports",
    keep: str | None = None,
    remove_all: bool = False,
    dry_run: bool = False,
) -> tuple[list[Path], list[Path]]:
    """Remove report files that are no longer in use.

    Args:
        reports_dir: Directory containing report .txt files.
        keep: Specific date or 'latest' to keep. If None and remove_all is False,
              defaults to keeping the most recently modified report file.
        remove_all: If True, remove all .txt reports regardless of keep setting.
        dry_run: If True, do not actually delete files.

    Returns:
        tuple of (deleted_files, kept_files)
    """
    dir_path = Path(reports_dir)
    if not dir_path.exists():
        return [], []

    all_txt = [p for p in dir_path.glob("*.txt") if p.is_file()]
    if not all_txt:
        return [], []

    if remove_all:
        to_delete = sorted(all_txt)
        to_keep: list[Path] = []
    else:
        to_keep = []
        if keep:
            keep_clean = keep.strip()
            if keep_clean.lower() in ("latest", "current", "active", "recent"):
                latest_file = max(all_txt, key=lambda p: p.stat().st_mtime)
                to_keep = [latest_file]
            else:
                try:
                    parsed_dt = parse_target_date(keep_clean)
                    safe_date_str = format_status_date(parsed_dt).replace("-", "_")
                    expected_name = f"status_report_{safe_date_str}.txt"
                    to_keep = [
                        p for p in all_txt if p.name == expected_name or safe_date_str in p.name
                    ]
                except ValueError:
                    to_keep = [p for p in all_txt if keep_clean in p.name]

                if not to_keep:
                    to_keep = [p for p in all_txt if keep_clean.lower() in p.name.lower()]
        else:
            # Default: keep the most recently modified report (active report in use)
            latest_file = max(all_txt, key=lambda p: p.stat().st_mtime)
            to_keep = [latest_file]

        to_delete = sorted([p for p in all_txt if p not in to_keep])

    if not dry_run:
        for p in to_delete:
            p.unlink(missing_ok=True)

    return to_delete, to_keep
