from __future__ import annotations

import pytest
from report import (
    EXTRA_TIME_NOTE,
    ActivitySource,
    DailyReport,
    ManualTask,
    ReportChunk,
    ReportEntry,
    ReportSchedule,
    ReportService,
    chunk_id,
    wall_time,
)
from report.data_classes import (
    EXTRA_TIME_NOTE as EXTRA_TIME_NOTEDC,
)
from report.data_classes import (
    DailyReport as DailyReportDC,
)
from report.data_classes import (
    ManualTask as ManualTaskDC,
)
from report.data_classes import (
    ReportChunk as ReportChunkDC,
)
from report.data_classes import (
    ReportEntry as ReportEntryDC,
)
from report.data_classes import (
    ReportSchedule as ReportScheduleDC,
)
from report.data_classes import (
    chunk_id as chunk_idDC,
)
from report.data_classes import (
    wall_time as wall_timeDC,
)
from report.data_classes.daily_report import DailyReport as DirectDailyReport
from report.data_classes.manual_task import ManualTask as DirectManualTask
from report.data_classes.report_chunk import ReportChunk as DirectReportChunk
from report.data_classes.report_chunk import chunk_id as direct_chunk_id
from report.data_classes.report_entry import ReportEntry as DirectReportEntry
from report.data_classes.report_schedule import EXTRA_TIME_NOTE as DirectEXTRA_TIME_NOTE
from report.data_classes.report_schedule import ReportSchedule as DirectReportSchedule
from report.data_classes.report_schedule import wall_time as direct_wall_time
from report.service import (
    ActivitySource as ActivitySourceService,
)
from report.service import (
    ReportService as ReportServiceService,
)
from report.service.report_service import (
    ActivitySource as DirectActivitySource,
)
from report.service.report_service import (
    ReportService as DirectReportService,
)


def test_classes_identity():
    assert DailyReport is DirectDailyReport is DailyReportDC
    assert ManualTask is DirectManualTask is ManualTaskDC
    assert ReportChunk is DirectReportChunk is ReportChunkDC
    assert ReportEntry is DirectReportEntry is ReportEntryDC
    assert chunk_id is direct_chunk_id is chunk_idDC
    assert ReportSchedule is DirectReportSchedule is ReportScheduleDC
    assert wall_time is direct_wall_time is wall_timeDC
    assert EXTRA_TIME_NOTE == DirectEXTRA_TIME_NOTE == EXTRA_TIME_NOTEDC
    assert ReportService is DirectReportService is ReportServiceService
    assert ActivitySource is DirectActivitySource is ActivitySourceService


def test_manual_task_instantiation_and_validation():
    task = ManualTask(
        id="task-1",
        title="Fix authentication bug",
        completed_at="2026-10-25T14:30:00+05:00",
        description="Resolved JWT token expiration issue",
    )
    assert task.id == "task-1"
    assert task.title == "Fix authentication bug"
    assert task.description == "Resolved JWT token expiration issue"
    assert task.completed_at.isoformat() == "2026-10-25T09:30:00+00:00"

    with pytest.raises(ValueError, match="nonempty"):
        ManualTask(id="", title="Valid Title", completed_at="2026-10-25T14:30:00+05:00")

    with pytest.raises(ValueError, match="nonempty"):
        ManualTask(id="task-2", title="   ", completed_at="2026-10-25T14:30:00+05:00")


def test_report_entry_instantiation():
    entry = ReportEntry(
        id="entry-1",
        kind="commit",
        text="Commit message",
        created_at="2026-10-25T12:00:00+05:00",
        extra_time=True,
        note="(The task is done in extra time)",
        sha="abc1234",
        url="https://github.com/org/repo/commit/abc1234",
        branches=("main",),
        review_state="APPROVED",
    )
    assert entry.id == "entry-1"
    assert entry.kind == "commit"
    assert entry.extra_time is True
    assert entry.note == "(The task is done in extra time)"
    assert entry.sha == "abc1234"
    assert entry.branches == ("main",)
    assert entry.review_state == "APPROVED"


def test_report_chunk_instantiation_and_to_dict():
    entry = ReportEntry(
        id="e1",
        kind="pr_created",
        text="Created PR",
        created_at="2026-10-25T10:00:00+05:00",
        extra_time=False,
        note=None,
    )
    chunk = ReportChunk(
        repository="owner/repo",
        kind="pr",
        key="101",
        title="Add feature",
        description="Feature description",
        url="https://github.com/owner/repo/pull/101",
        categories=("prs",),
        entries=(entry,),
        extra_time=False,
        note=None,
    )
    assert chunk_id(chunk) == "owner/repo:pr:101"
    d = chunk.to_dict()
    assert d["repository"] == "owner/repo"
    assert d["kind"] == "pr"
    assert d["key"] == "101"
    assert len(d["entries"]) == 1


def test_daily_report_instantiation_and_counts():
    entry = ReportEntry(
        id="e1",
        kind="pr_created",
        text="Created PR",
        created_at="2026-10-25T10:00:00+05:00",
        extra_time=False,
        note=None,
    )
    chunk_pr = ReportChunk(
        repository="owner/repo",
        kind="pr",
        key="101",
        title="Add feature",
        description="",
        url="https://github.com/owner/repo/pull/101",
        categories=("prs",),
        entries=(entry,),
        extra_time=False,
        note=None,
    )
    chunk_issue = ReportChunk(
        repository="owner/repo",
        kind="issue",
        key="202",
        title="Fix bug",
        description="",
        url="https://github.com/owner/repo/issues/202",
        categories=("issues",),
        entries=(entry,),
        extra_time=False,
        note=None,
    )
    report = DailyReport(
        work_date="2026-10-25",
        timezone="Asia/Karachi",
        window={"start": "2026-10-25T06:00:00+05:00", "end": "2026-10-26T06:00:00+05:00"},
        shift={"start": "11:00", "end": "20:00"},
        author="alice",
        chunks=(chunk_pr, chunk_issue),
        created_at_index={"owner/repo:pr:101": "2026-10-25T10:00:00+05:00"},
        summaries={},
        warnings=(),
    )
    assert report.counts == {
        "prs": 1,
        "reviewed_prs": 0,
        "branch_commits": 0,
        "issues": 1,
        "extra_tasks": 0,
    }
    d = report.to_dict()
    assert d["work_date"] == "2026-10-25"
    assert len(d["chunks"]) == 2
