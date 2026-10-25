from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

from config import load_configuration
from ghtoolkit import GitHubError
from utils.application import generate_report
from utils.format import format_office_status
from utils.render import render_pr_chunks


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = stream.name
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Daily work report using the centralized ghToolkit hub.")
    result.add_argument(
        "date", nargs="?", help="Work date YYYY-MM-DD; defaults to current configured reporting day"
    )
    result.add_argument("--config", type=Path, help="JSON configuration file; or set WORKED_TASK_CONFIG")
    result.add_argument(
        "--repo", action="append", dest="repositories", help="owner/repo; repeat for multiple repositories"
    )
    result.add_argument("--author")
    result.add_argument("--alias", action="append", dest="author_aliases")
    result.add_argument("--timezone")
    result.add_argument("--shift-start", help="Local HH:MM; required unless configured in JSON")
    result.add_argument("--shift-end", help="Local HH:MM; required unless configured in JSON")
    result.add_argument(
        "--day-start", help="Reporting-day cutoff HH:MM (default 00:00); use 06:00 to include next-day 02:00"
    )
    result.add_argument(
        "--workers", type=int, help="Parallel repositories (1-8); stages within each repo remain sequential"
    )
    result.add_argument("--manual-tasks", help="JSON file of non-GitHub tasks")
    result.add_argument("--snapshot", help="Replay a ghToolkit activity snapshot without network access")
    result.add_argument(
        "--ai",
        action="store_true",
        default=None,
        help="Send each PR chunk to Gemini; may disclose private repository content",
    )
    result.add_argument("--model", help="Gemini model identifier; or set GEMINI_MODEL")
    result.add_argument("--ai-failure", choices=("raise", "keep-raw"))
    result.add_argument(
        "--format", choices=("office",), default="office", help="Report format (only 'office' is supported)"
    )
    result.add_argument("--output", type=Path)
    result.add_argument(
        "--chunks-output", type=Path, help="Write one cleaned PR per JSONL line for AI handoff"
    )
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        config = load_configuration(args.config)
        for key in (
            "repositories",
            "author",
            "author_aliases",
            "timezone",
            "shift_start",
            "shift_end",
            "day_start",
            "workers",
            "manual_tasks",
            "snapshot",
            "ai",
            "model",
            "ai_failure",
        ):
            value = getattr(args, key)
            if value is not None:
                config[key] = value
        report = generate_report(config, args.date)
        output = format_office_status(report)
        if args.chunks_output:
            write_atomic(args.chunks_output, render_pr_chunks(report))
        if args.output:
            write_atomic(args.output, output)
        else:
            print(output, end="")
        return 0
    except (GitHubError, ValueError, TypeError, KeyError, OSError, RuntimeError) as exc:
        print(f"Report failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
