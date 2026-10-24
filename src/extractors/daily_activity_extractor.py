from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from ghtoolkit import GitHubClient, ProjectConfig
from ghtoolkit.core.dates import DateWindow


class DailyActivityExtractor:
    def __init__(
        self,
        projects_file_path: str | Path = "projects.json",
        configured_projects: list[ProjectConfig] | None = None,
        github_client: GitHubClient | None = None,
        timezone_identifier: str = "UTC",
    ) -> None:
        self.timezone_identifier = timezone_identifier
        self.github_client = github_client or GitHubClient(timezone=timezone_identifier)
        self.projects = (
            configured_projects
            if configured_projects is not None
            else self._load_projects_from_file(projects_file_path)
        )

    def extract(self, target_date_input: str | date = "today") -> dict[str, Any]:
        calendar_date = self._normalize_calendar_date(target_date_input)
        calendar_date_string = calendar_date.strftime("%Y-%m-%d")
        date_window = DateWindow.for_date(calendar_date_string, self.timezone_identifier)

        extracted_commits: list[dict[str, str]] = []
        extracted_comments: list[dict[str, str]] = []
        extracted_issues: list[dict[str, str]] = []

        recorded_commit_hashes: set[str] = set()
        recorded_comment_ids: set[str] = set()
        recorded_issue_numbers: set[str] = set()

        for project in self.projects:
            if not getattr(project, "enabled", True):
                continue

            self._extract_project_commits(
                project=project,
                calendar_date_string=calendar_date_string,
                extracted_commits=extracted_commits,
                recorded_commit_hashes=recorded_commit_hashes,
            )
            self._extract_project_comments(
                project=project,
                date_window=date_window,
                extracted_comments=extracted_comments,
                recorded_comment_ids=recorded_comment_ids,
            )
            self._extract_project_issues(
                project=project,
                date_window=date_window,
                extracted_issues=extracted_issues,
                recorded_issue_numbers=recorded_issue_numbers,
            )

        return {
            "date": calendar_date_string,
            "commit_data": extracted_commits,
            "comment_data": extracted_comments,
            "issues_data": extracted_issues,
        }

    def _load_projects_from_file(self, projects_file_path: str | Path) -> list[ProjectConfig]:
        resolved_path = self._resolve_existing_projects_path(projects_file_path)
        if not resolved_path:
            return []
        return GitHubClient.load_projects(resolved_path)

    def _resolve_existing_projects_path(self, projects_file_path: str | Path) -> Path | None:
        direct_candidate = Path(projects_file_path)
        if direct_candidate.exists():
            return direct_candidate

        working_directory_candidate = Path.cwd() / projects_file_path
        if working_directory_candidate.exists():
            return working_directory_candidate

        source_root_candidate = Path(__file__).resolve().parent.parent.parent / projects_file_path
        if source_root_candidate.exists():
            return source_root_candidate

        return None

    def _normalize_calendar_date(self, target_date_input: str | date) -> date:
        if isinstance(target_date_input, date):
            return target_date_input

        lowercased_input = target_date_input.strip().lower()
        if lowercased_input == "today":
            return datetime.now(UTC).date()
        if lowercased_input == "yesterday":
            return datetime.now(UTC).date() - timedelta(days=1)

        return date.fromisoformat(target_date_input[:10])

    def _extract_project_commits(
        self,
        project: ProjectConfig,
        calendar_date_string: str,
        extracted_commits: list[dict[str, str]],
        recorded_commit_hashes: set[str],
    ) -> None:
        retrieved_commits = self.github_client.get_user_commits_for_date(
            project.owner,
            project.repo,
            project.author,
            calendar_date_string,
            local_path=project.local_path,
        )

        for commit_item in retrieved_commits:
            commit_hash = getattr(commit_item, "sha", None) or getattr(commit_item, "hash", "")
            commit_timestamp = getattr(commit_item, "date", "")
            if commit_hash and commit_hash not in recorded_commit_hashes:
                recorded_commit_hashes.add(commit_hash)
                extracted_commits.append({str(commit_hash): str(commit_timestamp)})

    def _extract_project_comments(
        self,
        project: ProjectConfig,
        date_window: DateWindow,
        extracted_comments: list[dict[str, str]],
        recorded_comment_ids: set[str],
    ) -> None:
        repository_slug = f"{project.owner}/{project.repo}"
        repository_client = GitHubClient(
            repo=repository_slug,
            timezone=self.timezone_identifier,
            runner=self.github_client._runner,
        )
        since_timestamp = date_window.start.isoformat().replace("+00:00", "Z")

        try:
            issue_comments = repository_client._api.list(
                "issues/comments", {"since": since_timestamp}
            )
        except Exception:
            issue_comments = []

        try:
            review_comments = repository_client._api.list(
                "pulls/comments", {"since": since_timestamp}
            )
        except Exception:
            review_comments = []

        all_candidate_comments = [*issue_comments, *review_comments]

        for comment_record in all_candidate_comments:
            if not isinstance(comment_record, dict):
                continue

            comment_author_login = (
                (comment_record.get("user") or {}).get("login")
                if isinstance(comment_record.get("user"), dict)
                else ""
            )
            if (
                not comment_author_login
                or comment_author_login.casefold() != project.author.casefold()
            ):
                continue

            creation_timestamp = str(comment_record.get("created_at") or "")
            if not date_window.contains(creation_timestamp):
                continue

            comment_identifier = str(comment_record.get("id"))
            if comment_identifier and comment_identifier not in recorded_comment_ids:
                recorded_comment_ids.add(comment_identifier)
                extracted_comments.append({comment_identifier: creation_timestamp})

    def _extract_project_issues(
        self,
        project: ProjectConfig,
        date_window: DateWindow,
        extracted_issues: list[dict[str, str]],
        recorded_issue_numbers: set[str],
    ) -> None:
        repository_slug = f"{project.owner}/{project.repo}"
        repository_client = GitHubClient(
            repo=repository_slug,
            timezone=self.timezone_identifier,
            runner=self.github_client._runner,
        )

        try:
            listed_issues = repository_client._runner.run_json(
                "issue",
                "list",
                "--repo",
                repository_client.repo,
                "--state",
                "all",
                "--search",
                date_window.search("created"),
                "--json",
                "number,createdAt,author",
            )
        except Exception:
            listed_issues = []

        if not isinstance(listed_issues, list):
            return

        for issue_record in listed_issues:
            if not isinstance(issue_record, dict):
                continue

            issue_author_login = (
                (issue_record.get("author") or {}).get("login")
                if isinstance(issue_record.get("author"), dict)
                else ""
            )
            if not issue_author_login or issue_author_login.casefold() != project.author.casefold():
                continue

            creation_timestamp = str(issue_record.get("createdAt") or "")
            if not date_window.contains(creation_timestamp):
                continue

            issue_number = str(issue_record.get("number"))
            if issue_number and issue_number not in recorded_issue_numbers:
                recorded_issue_numbers.add(issue_number)
                extracted_issues.append({issue_number: creation_timestamp})


def main() -> int:
    target_date_argument = sys.argv[1] if len(sys.argv) > 1 else "today"
    extractor = DailyActivityExtractor()
    extracted_daily_activity = extractor.extract(target_date_argument)
    print(json.dumps(extracted_daily_activity, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
