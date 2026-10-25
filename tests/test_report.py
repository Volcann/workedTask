import json
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from ai import GeminiSummarizer, build_prompt
from report.data_classes import EXTRA_TIME_NOTE, ManualTask, chunk_id
from report.service import ReportService
from utils.format import format_office_status
from utils.render import render_pr_chunks


def source_for(activity):
    return SimpleNamespace(collect_daily_activity=Mock(return_value=(activity,)))


def test_worked_task_calls_hub_and_never_fetches_itself(activity, schedule):
    source = source_for(activity)
    report = ReportService(source).generate(
        ["acme/widget"], "alice", schedule, author_aliases=["alias@example.test"], max_workers=2
    )
    source.collect_daily_activity.assert_called_once_with(
        ["acme/widget"], "alice", schedule.window, max_workers=2, author_aliases=["alias@example.test"]
    )
    assert report.counts == {"prs": 3, "reviewed_prs": 2, "branch_commits": 3, "issues": 2, "extra_tasks": 0}


def test_labels_follow_each_event_not_entity_creation_date(activity, schedule):
    report = ReportService(source_for(activity)).generate(["acme/widget"], "alice", schedule)
    incident = next(chunk for chunk in report.chunks if chunk.kind == "issue" and chunk.key == "39")
    assert incident.note == EXTRA_TIME_NOTE
    assert incident.entries[0].created_at == "2026-10-25T02:00:00+05:00"
    login = next(chunk for chunk in report.chunks if chunk.kind == "pr" and chunk.key == "36")
    assert not login.extra_time
    assert all(entry.note is None for entry in login.entries)
    mixed = next(chunk for chunk in report.chunks if chunk.kind == "pr" and chunk.key == "37")
    assert mixed.extra_time
    assert any(entry.note is None for entry in mixed.entries)
    assert any(entry.note == EXTRA_TIME_NOTE for entry in mixed.entries)
    assert report.counts["reviewed_prs"] == 2
    assert EXTRA_TIME_NOTE in format_office_status(report)


def test_manual_tasks_are_fifth_log_filtered_by_completion_time(activity, schedule):
    tasks = [
        ManualTask("normal", "Planning", "2026-10-24T17:00:00+05:00"),
        ManualTask("late", "Support", "2026-10-25T02:00:00+05:00"),
        ManualTask("outside", "Tomorrow", "2026-10-25T06:00:00+05:00"),
    ]
    report = ReportService(source_for(activity)).generate(
        ["acme/widget"], "alice", schedule, manual_tasks=tasks
    )
    manual = {chunk.key: chunk for chunk in report.chunks if chunk.kind == "extra_task"}
    assert set(manual) == {"normal", "late"}
    assert manual["normal"].note is None
    assert manual["late"].note == EXTRA_TIME_NOTE
    assert report.counts["extra_tasks"] == 2
    assert "non-github:extra_task:late" in report.created_at_index


def test_duplicate_manual_ids_fail(activity, schedule):
    task = ManualTask("x", "Task", "2026-10-24T12:00:00+05:00")
    with pytest.raises(ValueError, match="Duplicate"):
        ReportService(source_for(activity)).generate(
            ["acme/widget"], "alice", schedule, manual_tasks=[task, task]
        )


def test_ai_gets_one_pr_at_a_time_and_cannot_remove_overtime_notes(activity, schedule):
    summarizer = SimpleNamespace(summarize=Mock(return_value="Work summary without any overtime note."))
    report = ReportService(source_for(activity)).generate(
        ["acme/widget"], "alice", schedule, summarizer=summarizer
    )
    assert summarizer.summarize.call_count == 4
    submitted = [call.args[0] for call in summarizer.summarize.call_args_list]
    assert all(chunk.kind == "pr" for chunk in submitted)
    assert {chunk.key for chunk in submitted} == {"36", "37", "38", "41"}
    assert len(report.summaries) == 4
    output = format_office_status(report)
    assert "Work summary without any overtime note." in output
    assert EXTRA_TIME_NOTE in output
    assert all(json.loads(line)["kind"] == "pr" for line in render_pr_chunks(report).splitlines())


def test_ai_is_not_called_without_a_provider(activity, schedule):
    report = ReportService(source_for(activity)).generate(["acme/widget"], "alice", schedule)
    assert report.summaries == {}


def test_review_ai_summary_is_stored_separately_from_work_summary(activity, schedule):
    ai = SimpleNamespace(
        summarize=Mock(return_value="Implementation summary."),
        summarize_review=Mock(return_value="Flagged an approval routing gap."),
    )
    report = ReportService(source_for(activity)).generate(["acme/widget"], "alice", schedule, summarizer=ai)

    assert ai.summarize_review.called
    assert any(key.startswith("review:acme/widget:pr:") for key in report.summaries)


def test_review_ai_no_finding_is_recorded_without_impact_claim(activity, schedule):
    ai = SimpleNamespace(
        summarize=Mock(return_value="Implementation summary."),
        summarize_review=Mock(return_value="NO_FINDING"),
    )
    report = ReportService(source_for(activity)).generate(["acme/widget"], "alice", schedule, summarizer=ai)

    assert "NO_FINDING" in report.summaries.values()
    assert "Review impact:" not in format_office_status(report)


def test_ai_failure_raises_unless_explicit_raw_fallback(activity, schedule):
    ai = SimpleNamespace(summarize=Mock(side_effect=RuntimeError("provider failed")))
    service = ReportService(source_for(activity))
    with pytest.raises(RuntimeError):
        service.generate(["acme/widget"], "alice", schedule, summarizer=ai)
    report = service.generate(["acme/widget"], "alice", schedule, summarizer=ai, ai_failure="keep-raw")
    assert len(report.warnings) == 4
    assert len(report.chunks) == 9
    assert EXTRA_TIME_NOTE in format_office_status(report)


def test_empty_ai_response_is_not_accepted(activity, schedule):
    ai = SimpleNamespace(summarize=Mock(return_value="  "))
    with pytest.raises(ValueError, match="Empty"):
        ReportService(source_for(activity)).generate(["acme/widget"], "alice", schedule, summarizer=ai)


def test_gemini_adapter_uses_structured_single_pr_prompt(activity, schedule):
    report = ReportService(source_for(activity)).generate(["acme/widget"], "alice", schedule)
    chunk = next(chunk for chunk in report.chunks if chunk.kind == "pr")
    fake_client = SimpleNamespace(
        models=SimpleNamespace(generate_content=Mock(return_value=SimpleNamespace(text="Summary")))
    )
    ai = GeminiSummarizer("configured-model", client=fake_client)
    assert ai.summarize(chunk) == "Summary"
    args = fake_client.models.generate_content.call_args.kwargs
    assert args["model"] == "configured-model"
    assert "untrusted data" in args["contents"]
    assert "BEGIN_PR_DATA_JSON" in args["contents"]
    other = next(chunk for chunk in report.chunks if chunk.kind == "issue")
    with pytest.raises(ValueError, match="PR-wise"):
        build_prompt(other)


def test_summary_keys_include_repository(activity, schedule):
    chunks = ReportService(source_for(activity)).generate(["acme/widget"], "alice", schedule).chunks
    one = next(chunk for chunk in chunks if chunk.kind == "pr")
    assert chunk_id(one) != chunk_id(replace(one, repository="other/repo"))


def test_empty_report_is_explicit(schedule):
    source = SimpleNamespace(collect_daily_activity=Mock(return_value=()))
    report = ReportService(source).generate(["acme/widget"], "alice", schedule)
    assert format_office_status(report).startswith("STATUS (")
    assert not any(report.counts.values())


def test_gateway_failures_are_not_swallowed(schedule):
    from ghtoolkit import GitHubRequestError

    source = SimpleNamespace(collect_daily_activity=Mock(side_effect=GitHubRequestError("pulls.list", 403)))
    with pytest.raises(GitHubRequestError):
        ReportService(source).generate(["acme/widget"], "alice", schedule)
