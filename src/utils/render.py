from __future__ import annotations

import json

from report.data_classes import DailyReport


def render_pr_chunks(report: DailyReport) -> str:
    return "".join(
        json.dumps(chunk.to_dict(), ensure_ascii=False) + "\n"
        for chunk in report.chunks
        if chunk.kind == "pr"
    )
