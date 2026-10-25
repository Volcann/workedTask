from __future__ import annotations

import runpy
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from ghtoolkit import ProjectConfig
from src.extractors.daily_activity_extractor import DailyActivityExtractor


@pytest.fixture
def test_project() -> ProjectConfig:
    return ProjectConfig(
        owner="folium-hr-management-tool",
        repo="hr-tool-backend",
        name="HR-Tool",
        category="Backend",
        author="Volcann",
        local_path="/mock/backend",
        enabled=True,
    )


def test_resolve_existing_projects_path_variants(tmp_path: Path):
    extractor = DailyActivityExtractor(configured_projects=[])

    # Direct candidate
    direct_file = tmp_path / "projects_direct.json"
    direct_file.write_text("[]", encoding="utf-8")
    assert extractor._resolve_existing_projects_path(str(direct_file)) == direct_file

    # Non-existent anywhere
    assert extractor._resolve_existing_projects_path("completely_non_existent_path.json") is None
    assert extractor._load_projects_from_file("completely_non_existent_path.json") == []


def test_resolve_existing_projects_path_working_directory_and_source_root(tmp_path: Path):
    extractor = DailyActivityExtractor(configured_projects=[])

    # Simulate working directory candidate
    with patch("pathlib.Path.exists") as mock_exists:
        # 1st call for direct candidate (False), 2nd call for cwd candidate (True)
        mock_exists.side_effect = [False, True]
        resolved = extractor._resolve_existing_projects_path("projects.json")
        assert resolved == Path.cwd() / "projects.json"

    with patch("pathlib.Path.exists") as mock_exists:
        # 1st call (False), 2nd call (False), 3rd call for source root (True)
        mock_exists.side_effect = [False, False, True]
        resolved = extractor._resolve_existing_projects_path("projects.json")
        assert resolved is not None


def test_default_github_client_init():
    with patch("src.extractors.daily_activity_extractor.GitHubClient") as mock_client_cls:
        extractor = DailyActivityExtractor(configured_projects=[])
        assert extractor.github_client is not None
        mock_client_cls.assert_called_once_with(timezone="UTC")


def test_normalize_calendar_date_date_object():
    extractor = DailyActivityExtractor(configured_projects=[])
    d = date(2026, 10, 24)
    assert extractor._normalize_calendar_date(d) == d
    assert extractor._normalize_calendar_date("today") == datetime.now(UTC).date()
    assert extractor._normalize_calendar_date("yesterday") == datetime.now(UTC).date() - timedelta(days=1)
    assert extractor._normalize_calendar_date("2026-10-24T12:00:00Z") == date(2026, 10, 24)


def test_extract_project_commits_with_hash_attribute_and_missing_hash(test_project: ProjectConfig):
    mock_github_client = MagicMock()
    mock_github_client.get_user_commits_for_date.return_value = [
        SimpleNamespace(hash="hash_only_commit", date="2026-10-21T08:00:00Z"),
        SimpleNamespace(sha="", hash="", date="2026-10-21T08:30:00Z"),
    ]

    mock_repository_client = MagicMock()
    mock_repository_client._api.list.return_value = []
    mock_repository_client._runner.run_json.return_value = []

    with patch(
        "src.extractors.daily_activity_extractor.GitHubClient",
        return_value=mock_repository_client,
    ):
        extractor = DailyActivityExtractor(
            configured_projects=[test_project],
            github_client=mock_github_client,
        )
        extraction_result = extractor.extract("2026-10-21")

    assert extraction_result["commit_data"] == [{"hash_only_commit": "2026-10-21T08:00:00Z"}]


def test_extract_project_comments_edge_cases(test_project: ProjectConfig):
    mock_github_client = MagicMock()
    mock_github_client.get_user_commits_for_date.return_value = []

    mock_repository_client = MagicMock()
    # Return non-dict records and records with missing user/login/id
    mock_repository_client._api.list.side_effect = [
        [
            "not-a-dict",
            {"user": "not-a-dict"},
            {"user": {"login": ""}},
            {"id": None, "user": {"login": "Volcann"}, "created_at": "2026-10-21T12:00:00Z"},
            {"id": "duplicate_id", "user": {"login": "volcann"}, "created_at": "2026-10-21T12:00:00Z"},
            {"id": "duplicate_id", "user": {"login": "volcann"}, "created_at": "2026-10-21T12:00:00Z"},
        ],
        [],
    ]
    mock_repository_client._runner.run_json.return_value = []

    with patch(
        "src.extractors.daily_activity_extractor.GitHubClient",
        return_value=mock_repository_client,
    ):
        extractor = DailyActivityExtractor(
            configured_projects=[test_project],
            github_client=mock_github_client,
        )
        extraction_result = extractor.extract("2026-10-21")

    assert extraction_result["comment_data"] == [{"duplicate_id": "2026-10-21T12:00:00Z"}]


def test_extract_project_issues_edge_cases(test_project: ProjectConfig):
    mock_github_client = MagicMock()
    mock_github_client.get_user_commits_for_date.return_value = []

    mock_repository_client = MagicMock()
    mock_repository_client._api.list.return_value = []
    # Test runner returning non-list (e.g. dict or None)
    mock_repository_client._runner.run_json.return_value = {"error": "bad format"}

    with patch(
        "src.extractors.daily_activity_extractor.GitHubClient",
        return_value=mock_repository_client,
    ):
        extractor = DailyActivityExtractor(
            configured_projects=[test_project],
            github_client=mock_github_client,
        )
        assert extractor.extract("2026-10-21")["issues_data"] == []

    # Test runner returning non-dict records and invalid author / number
    mock_repository_client._runner.run_json.return_value = [
        "not-a-dict",
        {"author": "not-a-dict"},
        {"author": {"login": ""}},
        {"number": None, "author": {"login": "Volcann"}, "createdAt": "2026-10-21T12:00:00Z"},
        {"number": 999, "author": {"login": "volcann"}, "createdAt": "2026-10-21T12:00:00Z"},
        {"number": 999, "author": {"login": "volcann"}, "createdAt": "2026-10-21T12:00:00Z"},
    ]

    with patch(
        "src.extractors.daily_activity_extractor.GitHubClient",
        return_value=mock_repository_client,
    ):
        extractor = DailyActivityExtractor(
            configured_projects=[test_project],
            github_client=mock_github_client,
        )
        extraction_result = extractor.extract("2026-10-21")

    assert extraction_result["issues_data"] == [{"999": "2026-10-21T12:00:00Z"}]


def test_extractor_main_block_invocation():
    extractor_path = str(Path(__file__).parents[2] / "src" / "extractors" / "daily_activity_extractor.py")
    with (
        patch("sys.argv", ["daily_activity_extractor", "2026-10-21"]),
        patch("ghtoolkit.client.GitHubClient"),
        patch("ghtoolkit.GitHubClient"),
    ):
        with pytest.raises(SystemExit) as exc_info:
            runpy.run_path(extractor_path, run_name="__main__")
        assert exc_info.value.code == 0
