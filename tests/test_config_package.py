from __future__ import annotations

import json
from datetime import date, time
from pathlib import Path

import config
import pytest
from config import load_configuration, load_manual_tasks, schedule_from_config
from config.config import (
    load_configuration as direct_load_configuration,
)
from config.config import (
    load_manual_tasks as direct_load_manual_tasks,
)
from config.config import (
    schedule_from_config as direct_schedule_from_config,
)
from report.data_classes import ManualTask, ReportSchedule


def test_config_exports_identity():
    assert config.load_configuration is load_configuration is direct_load_configuration
    assert config.load_manual_tasks is load_manual_tasks is direct_load_manual_tasks
    assert config.schedule_from_config is schedule_from_config is direct_schedule_from_config


def test_load_configuration(tmp_path: Path):
    assert load_configuration(None) == {}

    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"shift_start": "09:00", "shift_end": "18:00"}), encoding="utf-8")
    loaded = load_configuration(config_file)
    assert loaded == {"shift_start": "09:00", "shift_end": "18:00"}

    bad_config = tmp_path / "bad_config.json"
    bad_config.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
    with pytest.raises(ValueError, match="Configuration must be a JSON object."):
        load_configuration(bad_config)


def test_schedule_from_config():
    cfg = {
        "timezone": "Asia/Karachi",
        "shift_start": "09:00",
        "shift_end": "18:00",
        "day_start": "06:00",
    }
    sched = schedule_from_config(cfg, day="2026-10-24")
    assert isinstance(sched, ReportSchedule)
    assert sched.work_date == date(2026, 10, 24)
    assert sched.shift_start == time(9, 0)
    assert sched.shift_end == time(18, 0)

    with pytest.raises(ValueError, match="Set shift_start"):
        schedule_from_config({"shift_end": "18:00"})

    with pytest.raises(ValueError, match="Set shift_end"):
        schedule_from_config({"shift_start": "09:00"})


def test_load_manual_tasks(tmp_path: Path):
    assert load_manual_tasks(None) == ()

    tasks_file = tmp_path / "tasks.json"
    tasks_file.write_text(
        json.dumps(
            [
                {
                    "id": "1",
                    "title": "Manual Fix",
                    "completed_at": "2026-10-24T15:00:00+05:00",
                    "description": "Fixed bug",
                }
            ]
        ),
        encoding="utf-8",
    )
    tasks = load_manual_tasks(tasks_file)
    assert len(tasks) == 1
    assert isinstance(tasks[0], ManualTask)
    assert tasks[0].id == "1"
    assert tasks[0].title == "Manual Fix"
    assert tasks[0].description == "Fixed bug"

    bad_tasks = tmp_path / "bad_tasks.json"
    bad_tasks.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    with pytest.raises(ValueError, match="Manual tasks must be a JSON array."):
        load_manual_tasks(bad_tasks)

    invalid_task = tmp_path / "invalid_task.json"
    invalid_task.write_text(json.dumps([{"id": "1"}]), encoding="utf-8")
    with pytest.raises(ValueError, match="Each manual task needs id, title and completed_at."):
        load_manual_tasks(invalid_task)
