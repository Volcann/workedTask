"""Status report formatting engine producing user-specified report formats."""

from __future__ import annotations

from status_reporter.models.models import (
    BranchActivity,
    DailyReport,
    ProjectActivity,
    PullRequestInfo,
    ReviewInfo,
)
from status_reporter.shared.utils import format_arrow_lines


class StatusReportFormatter:
    """Format collected activities into canonical engineering status reports."""

    def format_report(self, report: DailyReport) -> str:
        """Render a complete DailyReport into the exact formatted status string."""
        lines: list[str] = [f"STATUS ({report.date_display})"]

        # Group activities by project name (e.g. "HR-Tool")
        projects_grouped: dict[str, list[ProjectActivity]] = {}
        for act in report.projects:
            projects_grouped.setdefault(act.project_name, []).append(act)

        for proj_idx, (proj_name, acts) in enumerate(projects_grouped.items()):
            if proj_idx > 0 and lines and lines[-1] != "":
                lines.append("")
            lines.append(proj_name)

            # Check for reviewed PRs across all sub-activities of this project
            all_reviews: list[ReviewInfo] = []
            for act in acts:
                all_reviews.extend(act.reviewed_prs)

            if all_reviews:
                lines.append("Reviewed PRs:")
                for r in all_reviews:
                    if r.pr_number:
                        lines.append(f"-> {r.pr_title} -> PR#{r.pr_number}")
                    else:
                        lines.append(f"-> {r.pr_title}")
                    bullets = r.review_bullets or r.comments
                    if bullets:
                        for c in bullets:
                            cleaned_c = c.strip()
                            if cleaned_c:
                                formatted_c = format_arrow_lines([cleaned_c])
                                lines.extend(formatted_c)
                lines.append("")

            # Check if there are distinct categories like Backend vs Frontend
            has_frontend = any(act.category.lower() == "frontend" for act in acts)
            has_backend = any(act.category.lower() == "backend" for act in acts)
            should_show_category_headers = has_frontend and has_backend

            for act in acts:
                if should_show_category_headers:
                    if lines and lines[-1] != "" and not lines[-1].endswith("Reviewed PRs:"):
                        lines.append("")
                    lines.append(f"{act.category} PR:")

                # Render foreign contributions and own PRs
                combined_prs: list[PullRequestInfo] = [*act.foreign_contributions, *act.own_prs]

                for pr in combined_prs:
                    pr_lines = self._format_pr_entry(pr)
                    lines.extend(pr_lines)
                    lines.append("")

                # Render standalone branch commits if present
                for branch in act.branch_commits:
                    branch_lines = self._format_branch_entry(branch)
                    lines.extend(branch_lines)
                    lines.append("")

                # Render standalone project notes
                for note in act.notes:
                    formatted_note = format_arrow_lines([note])
                    lines.extend(formatted_note)
                    lines.append("")

            # Clean up trailing blank lines inside project
            while lines and lines[-1] == "":
                lines.pop()

        report_text = "\n".join(lines).strip() + "\n"
        report.rendered_text = report_text
        return report_text

    def _format_pr_entry(self, pr: PullRequestInfo) -> list[str]:
        """Format an individual Pull Request entry."""
        entry_lines: list[str] = [pr.title]

        bullets = pr.bullets
        if not bullets:
            bullets = [f"PR#{pr.number} -> {pr.title}"]

        for b in bullets:
            if b == "":
                entry_lines.append("")
                continue

            stripped = b.strip()
            if not stripped:
                continue

            formatted = format_arrow_lines([stripped])
            entry_lines.extend(formatted)

        return entry_lines

    def _format_branch_entry(self, branch: BranchActivity) -> list[str]:
        """Format direct commits inside a branch."""
        lines: list[str] = [f"Inside branch {branch.branch_name}:"]
        commit_bullets = [
            f"-> {c.headline}" if not c.headline.startswith("->") else c.headline
            for c in branch.commits
        ]
        lines.extend(commit_bullets)
        return lines


def format_status_report(report: DailyReport) -> str:
    """Convenience helper to format a DailyReport."""
    formatter = StatusReportFormatter()
    return formatter.format_report(report)
