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


def test_comment_extraction_includes_issue_and_pull_request_comments(
    target_project: ProjectConfig,
) -> None:
    mock_github_client = MagicMock()
    mock_github_client.get_user_commits_for_date.return_value = []

    mock_repository_client = MagicMock()
    mock_repository_client._api.list.side_effect = [
        [
            {
                "id": 5001,
                "created_at": "2026-10-21T10:00:00Z",
                "user": {"login": "Volcann"},
            }
        ],
        [
            {
                "id": 5002,
                "created_at": "2026-10-21T11:00:00Z",
                "user": {"login": "Volcann"},
            }
        ],
    ]
    mock_repository_client._runner.run_json.return_value = []

    with patch(
        "src.extractors.daily_activity_extractor.GitHubClient",
        return_value=mock_repository_client,
    ):
        extractor = DailyActivityExtractor(
            configured_projects=[target_project],
            github_client=mock_github_client,
        )
        extraction_result = extractor.extract("2026-10-21")

    assert len(extraction_result["comment_data"]) == 2
    assert extraction_result["comment_data"][0] == {"5001": "2026-10-21T10:00:00Z"}
    assert extraction_result["comment_data"][1] == {"5002": "2026-10-21T11:00:00Z"}


def test_comment_extraction_filters_by_author_and_window(
    target_project: ProjectConfig,
) -> None:
    mock_github_client = MagicMock()
    mock_github_client.get_user_commits_for_date.return_value = []

    mock_repository_client = MagicMock()
    mock_repository_client._api.list.side_effect = [
        [
            {
                "id": 6001,
                "created_at": "2026-10-21T14:00:00Z",
                "user": {"login": "Volcann"},
            },
            {
                "id": 6002,
                "created_at": "2026-10-21T14:00:00Z",
                "user": {"login": "TeammateDev"},
            },
            {
                "id": 6003,
                "created_at": "2026-10-20T23:59:59Z",
                "user": {"login": "Volcann"},
            },
            {
                "id": 6004,
                "created_at": "2026-10-22T00:00:01Z",
                "user": {"login": "Volcann"},
            },
        ],
        [],
    ]
    mock_repository_client._runner.run_json.return_value = []

    with patch(
        "src.extractors.daily_activity_extractor.GitHubClient",
        return_value=mock_repository_client,
    ):
        extractor = DailyActivityExtractor(
            configured_projects=[target_project],
            github_client=mock_github_client,
        )
        extraction_result = extractor.extract("2026-10-21")

    assert len(extraction_result["comment_data"]) == 1
    assert extraction_result["comment_data"][0] == {"6001": "2026-10-21T14:00:00Z"}


def test_comment_extraction_handles_api_failure_gracefully(
    target_project: ProjectConfig,
) -> None:
    mock_github_client = MagicMock()
    mock_github_client.get_user_commits_for_date.return_value = []

    mock_repository_client = MagicMock()
    mock_repository_client._api.list.side_effect = RuntimeError("API unavailable")
    mock_repository_client._runner.run_json.return_value = []

    with patch(
        "src.extractors.daily_activity_extractor.GitHubClient",
        return_value=mock_repository_client,
    ):
        extractor = DailyActivityExtractor(
            configured_projects=[target_project],
            github_client=mock_github_client,
        )
        extraction_result = extractor.extract("2026-10-21")

    assert extraction_result["comment_data"] == []
