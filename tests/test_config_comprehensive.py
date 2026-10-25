from __future__ import annotations

import json
import os
from datetime import date, time
from pathlib import Path
from unittest.mock import patch

import pytest
from config.config import (
    load_configuration,
    load_manual_tasks,
    schedule_from_config,
)
from report.data_classes import ReportSchedule


def test_load_configuration_from_env_var(tmp_path: Path):
    cfg_file = tmp_path / "env_config.json"
    cfg_file.write_text(json.dumps({"shift_start": "10:00", "shift_end": "19:00"}), encoding="utf-8")

    with patch.dict(os.environ, {"WORKED_TASK_CONFIG": str(cfg_file)}):
        loaded = load_configuration(None)
        assert loaded == {"shift_start": "10:00", "shift_end": "19:00"}


@pytest.mark.parametrize("invalid_json", ["[1, 2, 3]", '"string"', "123", "true"])
def test_load_configuration_invalid_type_raises(tmp_path: Path, invalid_json: str):
    cfg_file = tmp_path / "invalid.json"
    cfg_file.write_text(invalid_json, encoding="utf-8")

    with pytest.raises(ValueError, match="Configuration must be a JSON object"):
        load_configuration(cfg_file)


def test_schedule_from_config_defaults_and_current_work_date():
    cfg = {
        "shift_start": "09:00",
        "shift_end": "18:00",
    }
    # When day is None, it computes current_work_date
    sched = schedule_from_config(cfg, day=None)
    assert isinstance(sched, ReportSchedule)
    assert sched.timezone == "UTC"
    assert sched.day_start == time(0, 0)
    assert sched.shift_start == time(9, 0)
    assert sched.shift_end == time(18, 0)
    assert isinstance(sched.work_date, date)


@pytest.mark.parametrize(
    "missing_field, err_msg",
    [
        ({"shift_end": "18:00"}, "Set shift_start"),
        ({"shift_start": "09:00"}, "Set shift_end"),
        ({}, "Set shift_start"),
    ],
)
def test_schedule_from_config_missing_hours_raises(missing_field, err_msg):
    with pytest.raises(ValueError, match=err_msg):
        schedule_from_config(missing_field)


@pytest.mark.parametrize("invalid_tasks_json", ['{"not": "a list"}', '"a string"', "123"])
def test_load_manual_tasks_invalid_root_type_raises(tmp_path: Path, invalid_tasks_json: str):
    f = tmp_path / "tasks.json"
    f.write_text(invalid_tasks_json, encoding="utf-8")
    with pytest.raises(ValueError, match="Manual tasks must be a JSON array"):
        load_manual_tasks(f)


@pytest.mark.parametrize(
    "bad_item",
    [
        "not-a-dict",
        {"id": "1", "title": "Missing completed_at"},
        {"id": "1", "completed_at": "2026-10-24T12:00:00+05:00"},
        {"title": "Missing id", "completed_at": "2026-10-24T12:00:00+05:00"},
    ],
)
def test_load_manual_tasks_invalid_item_raises(tmp_path: Path, bad_item):
    f = tmp_path / "bad_item.json"
    f.write_text(json.dumps([bad_item]), encoding="utf-8")
    with pytest.raises(ValueError, match="Each manual task needs id, title and completed_at"):
        load_manual_tasks(f)


def test_load_manual_tasks_success_with_and_without_description(tmp_path: Path):
    tasks_data = [
        {
            "id": "task-with-desc",
            "title": "Task 1",
            "completed_at": "2026-10-24T14:00:00+05:00",
            "description": "Custom detailed description",
        },
        {
            "id": "task-no-desc",
            "title": "Task 2",
            "completed_at": "2026-10-24T15:00:00+05:00",
        },
    ]
    f = tmp_path / "valid.json"
    f.write_text(json.dumps(tasks_data), encoding="utf-8")
    tasks = load_manual_tasks(f)

    assert len(tasks) == 2
    assert tasks[0].id == "task-with-desc"
    assert tasks[0].description == "Custom detailed description"
    assert tasks[1].id == "task-no-desc"
    assert tasks[1].description == ""
