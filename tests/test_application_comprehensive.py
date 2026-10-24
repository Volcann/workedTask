from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from ghtoolkit import SnapshotSource
from report.data_classes import DailyReport, ManualTask, ReportSchedule
from utils.application import generate_report


@pytest.fixture
def minimal_schedule(schedule: ReportSchedule) -> ReportSchedule:
    return schedule


def test_generate_report_converts_projects_to_repositories_and_author(schedule: ReportSchedule):
    config = {
        "projects": [
            {"owner": "acme", "repo": "widget", "author": "alice"},
            {"owner": "acme", "repo": "gadget"},
            {"owner": "incomplete"},
        ],
        "timezone": "Asia/Karachi",
        "shift_start": "09:00",
        "shift_end": "18:00",
    }
    mock_service = MagicMock()
    mock_report = MagicMock(spec=DailyReport)
    mock_service.return_value.generate.return_value = mock_report

    with patch("utils.application.ReportService", mock_service):
        rep = generate_report(config, day="2026-10-24")

    assert rep is mock_report
    assert config["repositories"] == ["acme/widget", "acme/gadget"]
    assert config["author"] == "alice"
    mock_service.return_value.generate.assert_called_once()
    call_args = mock_service.return_value.generate.call_args
    assert call_args[0][0] == ["acme/widget", "acme/gadget"]
    assert call_args[0][1] == "alice"


def test_generate_report_preserves_existing_author_when_projects_present(schedule: ReportSchedule):
    config = {
        "projects": [{"owner": "acme", "repo": "widget", "author": "alice"}],
        "author": "bob",
        "timezone": "Asia/Karachi",
        "shift_start": "09:00",
        "shift_end": "18:00",
    }
    mock_service = MagicMock()
    mock_report = MagicMock(spec=DailyReport)
    mock_service.return_value.generate.return_value = mock_report

    with patch("utils.application.ReportService", mock_service):
        generate_report(config, day="2026-10-24")

    assert config["author"] == "bob"


def test_generate_report_empty_projects_does_not_set_author():
    config = {
        "projects": [],
        "timezone": "Asia/Karachi",
        "shift_start": "09:00",
        "shift_end": "18:00",
    }
    with pytest.raises(ValueError, match="repositories"):
        generate_report(config, day="2026-10-24")


@pytest.mark.parametrize(
    "bad_repos",
    [
        None,
        [],
        "acme/widget",
        123,
        ["acme/widget", 42],
        [None],
    ],
)
def test_generate_report_validates_repositories(bad_repos):
    config = {
        "repositories": bad_repos,
        "author": "alice",
        "shift_start": "09:00",
        "shift_end": "18:00",
    }
    with pytest.raises(ValueError, match="Set repositories to a nonempty list of owner/repo names."):
        generate_report(config)


@pytest.mark.parametrize(
    "bad_author",
    [
        None,
        "",
        "   ",
        123,
        [],
    ],
)
def test_generate_report_validates_author(bad_author):
    config = {
        "repositories": ["acme/widget"],
        "author": bad_author,
        "shift_start": "09:00",
        "shift_end": "18:00",
    }
    with pytest.raises(ValueError, match="Set the report author login."):
        generate_report(config)


@pytest.mark.parametrize(
    "bad_aliases",
    [
        "alice-alias",
        123,
        ["valid-alias", 456],
        [None],
    ],
)
def test_generate_report_validates_author_aliases(bad_aliases):
    config = {
        "repositories": ["acme/widget"],
        "author": "alice",
        "author_aliases": bad_aliases,
        "shift_start": "09:00",
        "shift_end": "18:00",
    }
    with pytest.raises(ValueError, match="author_aliases must be a list of strings."):
        generate_report(config)


def test_generate_report_creates_snapshot_source_when_specified(tmp_path):
    snapshot_path = tmp_path / "snap.json"
    snapshot_path.write_text("{}", encoding="utf-8")
    config = {
        "repositories": ["acme/widget"],
        "author": "alice",
        "shift_start": "09:00",
        "shift_end": "18:00",
        "snapshot": str(snapshot_path),
    }

    mock_service_cls = MagicMock()
    with patch("utils.application.ReportService", mock_service_cls):
        generate_report(config, day="2026-10-24")

    mock_service_cls.assert_called_once()
    source_arg = mock_service_cls.call_args[0][0]
    assert isinstance(source_arg, SnapshotSource)


def test_generate_report_does_not_override_explicit_source_with_snapshot(tmp_path):
    snapshot_path = tmp_path / "snap.json"
    snapshot_path.write_text("{}", encoding="utf-8")
    config = {
        "repositories": ["acme/widget"],
        "author": "alice",
        "shift_start": "09:00",
        "shift_end": "18:00",
        "snapshot": str(snapshot_path),
    }

    custom_source = SimpleNamespace(collect_daily_activity=MagicMock(return_value=()))
    mock_service_cls = MagicMock()
    with patch("utils.application.ReportService", mock_service_cls):
        generate_report(config, day="2026-10-24", source=custom_source)

    mock_service_cls.assert_called_once_with(custom_source)


def test_generate_report_loads_manual_tasks_when_none_provided(tmp_path):
    tasks_file = tmp_path / "tasks.json"
    tasks_file.write_text("[]", encoding="utf-8")
    config = {
        "repositories": ["acme/widget"],
        "author": "alice",
        "shift_start": "09:00",
        "shift_end": "18:00",
        "manual_tasks": str(tasks_file),
    }

    with (
        patch("utils.application.ReportService") as mock_service_cls,
        patch("utils.application.load_manual_tasks") as mock_load_tasks,
    ):
        mock_load_tasks.return_value = (ManualTask("m1", "Manual task", "2026-10-24T12:00:00+05:00"),)
        generate_report(config, day="2026-10-24")
        mock_load_tasks.assert_called_once_with(str(tasks_file))
        assert mock_service_cls.return_value.generate.call_args.kwargs["manual_tasks"] == (
            mock_load_tasks.return_value
        )


def test_generate_report_uses_provided_manual_tasks_without_loading():
    config = {
        "repositories": ["acme/widget"],
        "author": "alice",
        "shift_start": "09:00",
        "shift_end": "18:00",
    }
    explicit_tasks = [ManualTask("m2", "Explicit task", "2026-10-24T12:00:00+05:00")]
    with (
        patch("utils.application.ReportService") as mock_service_cls,
        patch("utils.application.load_manual_tasks") as mock_load_tasks,
    ):
        generate_report(config, day="2026-10-24", manual_tasks=explicit_tasks)
        mock_load_tasks.assert_not_called()
        assert mock_service_cls.return_value.generate.call_args.kwargs["manual_tasks"] == explicit_tasks


def test_generate_report_ai_lifecycle_and_cleanup():
    config = {
        "repositories": ["acme/widget"],
        "author": "alice",
        "shift_start": "09:00",
        "shift_end": "18:00",
        "ai": True,
        "model": "gemini-2.5-flash",
    }

    mock_summarizer_instance = MagicMock()
    with (
        patch("utils.application.ReportService"),
        patch("ai.summarizer.GeminiSummarizer", return_value=mock_summarizer_instance) as mock_gemini_cls,
    ):
        generate_report(config, day="2026-10-24")
        mock_gemini_cls.assert_called_once_with("gemini-2.5-flash")
        mock_summarizer_instance.close.assert_called_once()


def test_generate_report_ai_closes_summarizer_on_service_exception():
    config = {
        "repositories": ["acme/widget"],
        "author": "alice",
        "shift_start": "09:00",
        "shift_end": "18:00",
        "ai": True,
    }

    mock_summarizer_instance = MagicMock()
    with (
        patch("utils.application.ReportService") as mock_service_cls,
        patch("ai.summarizer.GeminiSummarizer", return_value=mock_summarizer_instance),
        patch.dict(os.environ, {"GEMINI_MODEL": "gemini-3.5-flash-lite"}),
    ):
        mock_service_cls.return_value.generate.side_effect = RuntimeError("Generation failed")
        with pytest.raises(RuntimeError, match="Generation failed"):
            generate_report(config, day="2026-10-24")
        mock_summarizer_instance.close.assert_called_once()


def test_generate_report_passes_branches_workers_and_ai_failure():
    config = {
        "repositories": ["acme/widget"],
        "author": "alice",
        "shift_start": "09:00",
        "shift_end": "18:00",
        "branches": ["main", "dev"],
        "workers": 4,
        "ai_failure": "keep-raw",
    }
    with patch("utils.application.ReportService") as mock_service_cls:
        generate_report(config, day="2026-10-24")
        kwargs = mock_service_cls.return_value.generate.call_args.kwargs
        assert kwargs["branches"] == ["main", "dev"]
        assert kwargs["max_workers"] == 4
        assert kwargs["ai_failure"] == "keep-raw"
