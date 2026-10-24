from __future__ import annotations

import os
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ai.summarizer import Summarizer

from config import load_manual_tasks, schedule_from_config
from ghtoolkit import SnapshotSource
from report.data_classes import DailyReport, ManualTask
from report.service import ActivitySource, ReportService


def generate_report(
    config: dict[str, Any],
    day: str | None = None,
    *,
    source: ActivitySource | None = None,
    manual_tasks: Iterable[ManualTask] | None = None,
    summarizer: Summarizer | None = None,
) -> DailyReport:
    if "projects" in config and not config.get("repositories"):
        config["repositories"] = [
            f"{p['owner']}/{p['repo']}" for p in config["projects"] if "owner" in p and "repo" in p
        ]
        if not config.get("author") and config["projects"]:
            config["author"] = config["projects"][0].get("author", "")

    repositories = config.get("repositories")
    if (
        not isinstance(repositories, list)
        or not repositories
        or not all(isinstance(item, str) for item in repositories)
    ):
        raise ValueError("Set repositories to a nonempty list of owner/repo names.")
    author = config.get("author")
    if not isinstance(author, str) or not author.strip():
        raise ValueError("Set the report author login.")
    aliases = config.get("author_aliases", [])
    if not isinstance(aliases, list) or not all(isinstance(item, str) for item in aliases):
        raise ValueError("author_aliases must be a list of strings.")
    schedule = schedule_from_config(config, day)
    if source is None and config.get("snapshot"):
        source = SnapshotSource(config["snapshot"])
    if manual_tasks is None:
        manual_tasks = load_manual_tasks(config.get("manual_tasks"))
    owned_summarizer = None
    if summarizer is None and config.get("ai", False):
        from ai.summarizer import GeminiSummarizer

        owned_summarizer = GeminiSummarizer(config.get("model") or os.getenv("GEMINI_MODEL", ""))
        summarizer = owned_summarizer

    branches = config.get("branches")
    extra_service_kwargs = {"branches": branches} if branches is not None else {}
    try:
        return ReportService(source).generate(
            repositories,
            author,
            schedule,
            manual_tasks=manual_tasks,
            max_workers=config.get("workers", 1),
            author_aliases=aliases,
            summarizer=summarizer,
            ai_failure=config.get("ai_failure", "raise"),
            **extra_service_kwargs,
        )
    finally:
        if owned_summarizer is not None:
            owned_summarizer.close()
