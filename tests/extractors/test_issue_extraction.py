from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from ghtoolkit import ProjectConfig
from src.extractors.daily_activity_extractor import DailyActivityExtractor


@pytest.fixture
def target_project() -> ProjectConfig:
    return ProjectConfig(
        owner="folium-hr-management-tool",
        repo="hr-tool-backend",
        name="HR-Tool",
        category="Backend",
        author="Volcann",
        local_path="/mock/path/backend",
        enabled=True,
    )


def test_issue_extraction_formats_number_and_timestamp(
    target_project: ProjectConfig,
) -> None:
    mock_github_client = MagicMock()
    mock_github_client.get_user_commits_for_date.return_value = []

    mock_repository_client = MagicMock()
    mock_repository_client._api.list.return_value = []
    mock_repository_client._runner.run_json.return_value = [
        {
            "number": 455,
            "createdAt": "2026-10-17T16:07:57Z",
            "author": {"login": "Volcann"},
        }
    ]

    with patch(
        "src.extractors.daily_activity_extractor.GitHubClient",
        return_value=mock_repository_client,
    ):
        extractor = DailyActivityExtractor(
            configured_projects=[target_project],
            github_client=mock_github_client,
        )
        extraction_result = extractor.extract("2026-10-17")

    assert len(extraction_result["issues_data"]) == 1
    assert extraction_result["issues_data"][0] == {"455": "2026-10-17T16:07:57Z"}


def test_issue_extraction_filters_by_author_and_window(
    target_project: ProjectConfig,
) -> None:
    mock_github_client = MagicMock()
    mock_github_client.get_user_commits_for_date.return_value = []

    mock_repository_client = MagicMock()
    mock_repository_client._api.list.return_value = []
    mock_repository_client._runner.run_json.return_value = [
        {
            "number": 101,
            "createdAt": "2026-10-17T10:00:00Z",
            "author": {"login": "Volcann"},
        },
        {
            "number": 102,
            "createdAt": "2026-10-17T10:00:00Z",
            "author": {"login": "OtherDev"},
        },
        {
            "number": 103,
            "createdAt": "2026-10-18T10:00:00Z",
            "author": {"login": "Volcann"},
        },
    ]

    with patch(
        "src.extractors.daily_activity_extractor.GitHubClient",
        return_value=mock_repository_client,
    ):
        extractor = DailyActivityExtractor(
            configured_projects=[target_project],
            github_client=mock_github_client,
        )
        extraction_result = extractor.extract("2026-10-17")

    assert len(extraction_result["issues_data"]) == 1
    assert extraction_result["issues_data"][0] == {"101": "2026-10-17T10:00:00Z"}


def test_issue_extraction_handles_runner_failure_gracefully(
    target_project: ProjectConfig,
) -> None:
    mock_github_client = MagicMock()
    mock_github_client.get_user_commits_for_date.return_value = []

    mock_repository_client = MagicMock()
    mock_repository_client._api.list.return_value = []
    mock_repository_client._runner.run_json.side_effect = RuntimeError("Runner error")

    with patch(
        "src.extractors.daily_activity_extractor.GitHubClient",
        return_value=mock_repository_client,
    ):
        extractor = DailyActivityExtractor(
            configured_projects=[target_project],
            github_client=mock_github_client,
        )
        extraction_result = extractor.extract("2026-10-17")

    assert extraction_result["issues_data"] == []
