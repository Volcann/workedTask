from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from ghtoolkit import ProjectConfig
from ghtoolkit.models import CommitItem
from src.extractors.daily_activity_extractor import DailyActivityExtractor


@pytest.fixture
def primary_project() -> ProjectConfig:
    return ProjectConfig(
        owner="folium-hr-management-tool",
        repo="hr-tool-backend",
        name="HR-Tool",
        category="Backend",
        author="Volcann",
        local_path="/mock/path/backend",
        enabled=True,
    )


@pytest.fixture
def secondary_project() -> ProjectConfig:
    return ProjectConfig(
        owner="folium-hr-management-tool",
        repo="hr-tool-frontend",
        name="HR-Tool",
        category="Frontend",
        author="Volcann",
        local_path="/mock/path/frontend",
        enabled=True,
    )


@pytest.fixture
def disabled_project() -> ProjectConfig:
    return ProjectConfig(
        owner="folium-hr-management-tool",
        repo="hr-tool-legacy",
        name="HR-Tool",
        category="Legacy",
        author="Volcann",
        local_path="/mock/path/legacy",
        enabled=False,
    )


def test_commit_extraction_aggregates_multiple_projects(
    primary_project: ProjectConfig,
    secondary_project: ProjectConfig,
) -> None:
    mock_github_client = MagicMock()
    mock_github_client.get_user_commits_for_date.side_effect = [
        [CommitItem({"sha": "backend_sha_1", "date": "2026-10-21T08:00:00Z"})],
        [CommitItem({"sha": "frontend_sha_1", "date": "2026-10-21T09:00:00Z"})],
    ]

    mock_repository_client = MagicMock()
    mock_repository_client._api.list.return_value = []
    mock_repository_client._runner.run_json.return_value = []

    with patch(
        "src.extractors.daily_activity_extractor.GitHubClient",
        return_value=mock_repository_client,
    ):
        extractor = DailyActivityExtractor(
            configured_projects=[primary_project, secondary_project],
            github_client=mock_github_client,
        )
        extraction_result = extractor.extract("2026-10-21")

    assert len(extraction_result["commit_data"]) == 2
    assert extraction_result["commit_data"][0] == {"backend_sha_1": "2026-10-21T08:00:00Z"}
    assert extraction_result["commit_data"][1] == {"frontend_sha_1": "2026-10-21T09:00:00Z"}


def test_commit_extraction_deduplicates_repeated_commit_hashes(
    primary_project: ProjectConfig,
) -> None:
    mock_github_client = MagicMock()
    mock_github_client.get_user_commits_for_date.return_value = [
        CommitItem({"sha": "duplicate_hash", "date": "2026-10-21T10:00:00Z"}),
        CommitItem({"sha": "duplicate_hash", "date": "2026-10-21T10:00:00Z"}),
    ]

    mock_repository_client = MagicMock()
    mock_repository_client._api.list.return_value = []
    mock_repository_client._runner.run_json.return_value = []

    with patch(
        "src.extractors.daily_activity_extractor.GitHubClient",
        return_value=mock_repository_client,
    ):
        extractor = DailyActivityExtractor(
            configured_projects=[primary_project],
            github_client=mock_github_client,
        )
        extraction_result = extractor.extract("2026-10-21")

    assert len(extraction_result["commit_data"]) == 1
    assert extraction_result["commit_data"][0] == {"duplicate_hash": "2026-10-21T10:00:00Z"}


def test_commit_extraction_ignores_disabled_projects(
    primary_project: ProjectConfig,
    disabled_project: ProjectConfig,
) -> None:
    mock_github_client = MagicMock()
    mock_github_client.get_user_commits_for_date.return_value = [
        CommitItem({"sha": "active_project_sha", "date": "2026-10-21T10:00:00Z"})
    ]

    mock_repository_client = MagicMock()
    mock_repository_client._api.list.return_value = []
    mock_repository_client._runner.run_json.return_value = []

    with patch(
        "src.extractors.daily_activity_extractor.GitHubClient",
        return_value=mock_repository_client,
    ):
        extractor = DailyActivityExtractor(
            configured_projects=[primary_project, disabled_project],
            github_client=mock_github_client,
        )
        extraction_result = extractor.extract("2026-10-21")

    assert len(extraction_result["commit_data"]) == 1
    assert extraction_result["commit_data"][0] == {"active_project_sha": "2026-10-21T10:00:00Z"}
    assert mock_github_client.get_user_commits_for_date.call_count == 1
