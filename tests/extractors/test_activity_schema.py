from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from ghtoolkit import ProjectConfig
from ghtoolkit.models import CommitItem

from src.extractors.daily_activity_extractor import DailyActivityExtractor


@pytest.fixture
def mock_project() -> ProjectConfig:
    return ProjectConfig(
        owner="folium-hr-management-tool",
        repo="hr-tool-backend",
        name="HR-Tool",
        category="Backend",
        author="Volcann",
        local_path="/mock/path/hr-tool-backend",
        enabled=True,
    )


def test_extract_returns_exact_expected_top_level_keys(mock_project: ProjectConfig) -> None:
    mock_github_client = MagicMock()
    mock_github_client.get_user_commits_for_date.return_value = [
        CommitItem({"sha": "commit_hash_1", "date": "2026-10-21T10:00:00Z"})
    ]

    mock_repository_client = MagicMock()
    mock_repository_client._api.list.side_effect = [
        [
            {
                "id": 1001,
                "created_at": "2026-10-21T11:00:00Z",
                "user": {"login": "Volcann"},
            }
        ],
        [],
    ]
    mock_repository_client._runner.run_json.return_value = [
        {
            "number": 201,
            "createdAt": "2026-10-21T12:00:00Z",
            "author": {"login": "Volcann"},
        }
    ]

    with patch(
        "src.extractors.daily_activity_extractor.GitHubClient",
        return_value=mock_repository_client,
    ):
        extractor = DailyActivityExtractor(
            configured_projects=[mock_project],
            github_client=mock_github_client,
        )
        extraction_result = extractor.extract("2026-10-21")

    assert set(extraction_result.keys()) == {
        "date",
        "commit_data",
        "comment_data",
        "issues_data",
    }
    assert extraction_result["date"] == "2026-10-21"
    assert extraction_result["commit_data"] == [{"commit_hash_1": "2026-10-21T10:00:00Z"}]
    assert extraction_result["comment_data"] == [{"1001": "2026-10-21T11:00:00Z"}]
    assert extraction_result["issues_data"] == [{"201": "2026-10-21T12:00:00Z"}]


def test_extract_returns_empty_lists_on_inactive_date(mock_project: ProjectConfig) -> None:
    mock_github_client = MagicMock()
    mock_github_client.get_user_commits_for_date.return_value = []

    mock_repository_client = MagicMock()
    mock_repository_client._api.list.return_value = []
    mock_repository_client._runner.run_json.return_value = []

    with patch(
        "src.extractors.daily_activity_extractor.GitHubClient",
        return_value=mock_repository_client,
    ):
        extractor = DailyActivityExtractor(
            configured_projects=[mock_project],
            github_client=mock_github_client,
        )
        extraction_result = extractor.extract("2026-01-01")

    assert extraction_result == {
        "date": "2026-01-01",
        "commit_data": [],
        "comment_data": [],
        "issues_data": [],
    }


def test_extract_handles_custom_timezone_identifier(mock_project: ProjectConfig) -> None:
    mock_github_client = MagicMock()
    mock_github_client.get_user_commits_for_date.return_value = []

    mock_repository_client = MagicMock()
    mock_repository_client._api.list.return_value = []
    mock_repository_client._runner.run_json.return_value = []

    with patch(
        "src.extractors.daily_activity_extractor.GitHubClient",
        return_value=mock_repository_client,
    ):
        extractor = DailyActivityExtractor(
            configured_projects=[mock_project],
            github_client=mock_github_client,
            timezone_identifier="Asia/Karachi",
        )
        extraction_result = extractor.extract("2026-10-21")

    assert extraction_result["date"] == "2026-10-21"
    assert extractor.timezone_identifier == "Asia/Karachi"
