from __future__ import annotations

import json
import os
from datetime import date, time
from pathlib import Path
from typing import Any

from report.data_classes import ManualTask, ReportSchedule


def load_configuration(path: str | Path | None = None) -> dict[str, Any]:
    path = path or os.getenv("WORKED_TASK_CONFIG")
    if path is None:
        return {}
    result = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("Configuration must be a JSON object.")
    return result


def schedule_from_config(config: dict[str, Any], day: str | None = None) -> ReportSchedule:
    for required in ("shift_start", "shift_end"):
        if not config.get(required):
            raise ValueError(f"Set {required}; your actual shift hours cannot be inferred.")
    timezone = config.get("timezone", "UTC")
    start = time.fromisoformat(config.get("day_start", "00:00"))
    work_date = date.fromisoformat(day) if day else ReportSchedule.current_work_date(timezone, start)
    return ReportSchedule(
        work_date,
        timezone,
        time.fromisoformat(config["shift_start"]),
        time.fromisoformat(config["shift_end"]),
        start,
    )


def load_manual_tasks(path: str | Path | None) -> tuple[ManualTask, ...]:
    if path is None:
        return ()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Manual tasks must be a JSON array.")
    tasks = []
    for item in data:
        if not isinstance(item, dict) or not all(field in item for field in ("id", "title", "completed_at")):
            raise ValueError("Each manual task needs id, title and completed_at.")
        tasks.append(
            ManualTask(str(item["id"]), item["title"], item["completed_at"], item.get("description", ""))
        )
    return tuple(tasks)
