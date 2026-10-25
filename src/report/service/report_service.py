from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, Protocol

from ghtoolkit import DateWindow, GitHubHub, RepositoryActivity
from status_reporter_auth import github_token

from report.data_classes import (
    EXTRA_TIME_NOTE,
    DailyReport,
    ManualTask,
    ReportChunk,
    ReportEntry,
    ReportSchedule,
    chunk_id,
)

if TYPE_CHECKING:
    from ai import Summarizer


class ActivitySource(Protocol):
    def collect_daily_activity(
        self, repositories: Iterable[str], author: str, window: DateWindow, **kwargs: Any
    ) -> tuple[RepositoryActivity, ...]: ...


class ReportService:
    def __init__(self, source: ActivitySource | None = None):
        self.source = source if source is not None else GitHubHub(token=github_token())

    def generate(
        self,
        repositories: Iterable[str],
        author: str,
        schedule: ReportSchedule,
        *,
        manual_tasks: Iterable[ManualTask] = (),
        max_workers: int = 1,
        author_aliases: Iterable[str] = (),
        branches: Any = None,
        summarizer: Summarizer | None = None,
        ai_failure: str = "raise",
    ) -> DailyReport:
        if ai_failure not in {"raise", "keep-raw"}:
            raise ValueError("ai_failure must be 'raise' or 'keep-raw'.")
        extra_kwargs = {"branches": branches} if branches is not None else {}
        activity = self.source.collect_daily_activity(
            repositories,
            author,
            schedule.window,
            max_workers=max_workers,
            author_aliases=author_aliases,
            **extra_kwargs,
        )
        chunks = []
        index: dict[str, str] = {}
        for repository in activity:
            index.update(repository.created_at_index)
            for group in repository.groups:
                entries = []
                for event in group.events:
                    extra = schedule.is_extra_time(event.created_at)
                    entries.append(
                        ReportEntry(
                            event.id,
                            event.kind,
                            event.text,
                            schedule.local_timestamp(event.created_at),
                            extra,
                            EXTRA_TIME_NOTE if extra else None,
                            event.sha,
                            event.url,
                            event.branches,
                            event.review_state,
                            event.actor_login,
                        )
                    )
                any_extra = any(entry.extra_time for entry in entries)
                entity = group.subject
                chunks.append(
                    ReportChunk(
                        entity.repository,
                        entity.kind,
                        entity.key,
                        entity.title,
                        entity.description,
                        entity.url,
                        group.categories,
                        tuple(entries),
                        any_extra,
                        EXTRA_TIME_NOTE if any_extra else None,
                        entity.merged_at,
                        entity.merged_by,
                        entity.merge_commit_sha,
                        entity.merge_status_verified,
                    )
                )
        seen_manual: set[str] = set()
        for task in sorted(manual_tasks, key=lambda item: (item.completed_at, item.id)):
            if task.id in seen_manual:
                raise ValueError(f"Duplicate manual task id: {task.id}")
            seen_manual.add(task.id)
            if not schedule.window.contains(task.completed_at):
                continue
            extra = schedule.is_extra_time(task.completed_at)
            note = EXTRA_TIME_NOTE if extra else None
            identifier = f"non-github:extra_task:{task.id}"
            index[identifier] = task.completed_at.isoformat()
            entry = ReportEntry(
                identifier,
                "extra_task",
                task.description or task.title,
                schedule.local_timestamp(task.completed_at),
                extra,
                note,
            )
            chunks.append(
                ReportChunk(
                    None,
                    "extra_task",
                    task.id,
                    task.title,
                    task.description,
                    "",
                    ("extra_tasks",),
                    (entry,),
                    extra,
                    note,
                )
            )

        summaries = {}
        warnings = []
        if summarizer is not None:
            for chunk in chunks:
                if chunk.kind != "pr":
                    continue
                try:
                    summary = summarizer.summarize(chunk)
                    if not isinstance(summary, str) or not summary.strip():
                        raise ValueError("Empty AI summary.")
                    summaries[chunk_id(chunk)] = summary.strip()
                except Exception:
                    if ai_failure == "raise":
                        raise
                    warnings.append(
                        f"AI summary unavailable for {chunk_id(chunk)}; original evidence retained."
                    )
        return DailyReport(
            schedule.work_date.isoformat(),
            schedule.timezone,
            {
                "start": schedule.local_timestamp(schedule.window.start),
                "end": schedule.local_timestamp(schedule.window.end),
            },
            {
                "start": schedule.local_timestamp(schedule.start_utc),
                "end": schedule.local_timestamp(schedule.end_utc),
            },
            author,
            tuple(chunks),
            dict(sorted(index.items(), key=lambda item: (item[1], item[0]))),
            summaries,
            tuple(warnings),
        )
