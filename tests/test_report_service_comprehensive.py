from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from report.data_classes import (
    ManualTask,
    ReportSchedule,
)
from report.service.report_service import ReportService


def test_report_service_default_source_initialization():
    with (
        patch("report.service.report_service.GitHubHub") as mock_hub_cls,
        patch("report.service.report_service.github_token", return_value="test-token") as mock_token,
    ):
        service = ReportService()
        assert service.source is mock_hub_cls.return_value
        mock_token.assert_called_once_with()
        mock_hub_cls.assert_called_once_with(token="test-token")


def test_report_service_injected_source_skips_credential_lookup():
    source = SimpleNamespace()
    with patch("report.service.report_service.github_token") as mock_token:
        assert ReportService(source).source is source
    mock_token.assert_not_called()


@pytest.mark.parametrize("invalid_failure_mode", ["ignore", "fallback", "", None, 123])
def test_report_service_invalid_ai_failure_mode_raises(schedule: ReportSchedule, invalid_failure_mode):
    service = ReportService(source=SimpleNamespace())
    with pytest.raises(ValueError, match="ai_failure must be 'raise' or 'keep-raw'"):
        service.generate(
            ["acme/widget"],
            "alice",
            schedule,
            ai_failure=invalid_failure_mode,
        )


def test_report_service_branches_passed_to_source(schedule: ReportSchedule):
    mock_source = SimpleNamespace(collect_daily_activity=MagicMock(return_value=()))
    service = ReportService(source=mock_source)

    service.generate(
        ["acme/widget"],
        "alice",
        schedule,
        branches=["main", "feature/auth"],
    )

    mock_source.collect_daily_activity.assert_called_once()
    assert mock_source.collect_daily_activity.call_args.kwargs["branches"] == [
        "main",
        "feature/auth",
    ]


def test_report_service_manual_tasks_fallback_title_and_window_filter(schedule: ReportSchedule):
    mock_source = SimpleNamespace(collect_daily_activity=MagicMock(return_value=()))
    service = ReportService(source=mock_source)

    tasks = [
        ManualTask(
            id="t1",
            title="Manual Task Without Description",
            completed_at="2026-10-24T12:00:00+05:00",
            description="",
        ),
        ManualTask(
            id="t2",
            title="Out Of Window Task",
            completed_at="2026-10-23T01:00:00+05:00",
            description="Way before reporting window",
        ),
    ]

    report = service.generate(["acme/widget"], "alice", schedule, manual_tasks=tasks)

    manual_chunks = [c for c in report.chunks if c.kind == "extra_task"]
    assert len(manual_chunks) == 1
    assert manual_chunks[0].key == "t1"
    assert manual_chunks[0].title == "Manual Task Without Description"
    assert manual_chunks[0].entries[0].text == "Manual Task Without Description"
    assert "t2" not in [c.key for c in report.chunks]


def test_report_service_ai_summarizer_empty_and_whitespace_raises(activity, schedule: ReportSchedule):
    source = SimpleNamespace(collect_daily_activity=MagicMock(return_value=(activity,)))
    service = ReportService(source=source)

    for bad_summary in ["", "   ", "\n\t"]:
        bad_summarizer = SimpleNamespace(summarize=MagicMock(return_value=bad_summary))
        with pytest.raises(ValueError, match="Empty AI summary"):
            service.generate(["acme/widget"], "alice", schedule, summarizer=bad_summarizer)


def test_report_service_ai_failure_keep_raw_records_warnings(activity, schedule: ReportSchedule):
    source = SimpleNamespace(collect_daily_activity=MagicMock(return_value=(activity,)))
    service = ReportService(source=source)

    failing_summarizer = SimpleNamespace(
        summarize=MagicMock(side_effect=RuntimeError("AI API quota exceeded"))
    )
    report = service.generate(
        ["acme/widget"],
        "alice",
        schedule,
        summarizer=failing_summarizer,
        ai_failure="keep-raw",
    )

    assert len(report.warnings) > 0
    assert any("AI summary unavailable for" in w for w in report.warnings)
    assert any("original evidence retained" in w for w in report.warnings)
    assert report.summaries == {}
