from __future__ import annotations

import json

import utils
from report.data_classes import DailyReport, ReportChunk, ReportEntry
from utils import (
    build_prompt,
    format_office_status,
    generate_report,
    get_active_models,
    probe_gemini_models,
    render_pr_chunks,
)
from utils.application import generate_report as direct_generate_report
from utils.format import format_office_status as direct_format_office_status
from utils.formate import format_office_status as formate_office_status
from utils.models import (
    get_active_models as direct_get_active_models,
)
from utils.models import (
    probe_gemini_models as direct_probe_gemini_models,
)
from utils.prompt import build_prompt as direct_build_prompt
from utils.render import (
    render_pr_chunks as direct_render_pr_chunks,
)


def test_utils_package_exports():
    assert utils.render_pr_chunks is render_pr_chunks is direct_render_pr_chunks
    assert utils.generate_report is generate_report is direct_generate_report
    assert (
        utils.format_office_status
        is format_office_status
        is direct_format_office_status
        is formate_office_status
    )
    assert utils.build_prompt is build_prompt is direct_build_prompt
    assert utils.get_active_models is get_active_models is direct_get_active_models
    assert utils.probe_gemini_models is probe_gemini_models is direct_probe_gemini_models


def test_render_functions():
    entry = ReportEntry(
        id="e1",
        kind="pr_created",
        text="Created pull request",
        created_at="2026-10-25T10:00:00Z",
        extra_time=False,
        note=None,
    )
    chunk = ReportChunk(
        repository="org/repo",
        kind="pr",
        key="123",
        title="Sample PR",
        description="PR description",
        url="https://github.com/org/repo/pull/123",
        categories=("prs",),
        entries=(entry,),
        extra_time=False,
        note=None,
    )
    report = DailyReport(
        work_date="2026-10-25",
        timezone="Asia/Karachi",
        window={"start": "2026-10-25T05:00:00Z", "end": "2026-10-26T05:00:00Z"},
        shift={"start": "09:00", "end": "18:00"},
        author="alice",
        chunks=(chunk,),
        created_at_index={"org/repo:pr:123": chunk.key},
        summaries={},
        warnings=(),
    )

    pr_chunks = render_pr_chunks(report)
    pr_data = json.loads(pr_chunks.strip())
    assert pr_data["kind"] == "pr"
    assert pr_data["key"] == "123"
