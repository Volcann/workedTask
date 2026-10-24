from __future__ import annotations

from src.extractors.daily_activity_extractor import DailyActivityExtractor


def test_live_extraction_with_local_hr_tool_repositories() -> None:
    extractor = DailyActivityExtractor()
    extraction_result = extractor.extract("2026-10-21")

    assert extraction_result["date"] == "2026-10-21"
    assert isinstance(extraction_result["commit_data"], list)
    assert len(extraction_result["commit_data"]) > 0
    assert isinstance(extraction_result["comment_data"], list)
    assert isinstance(extraction_result["issues_data"], list)


def test_live_extraction_resolves_projects_json_from_root() -> None:
    extractor = DailyActivityExtractor(projects_file_path="projects.json")

    assert len(extractor.projects) >= 2
    project_repositories = [project.repo for project in extractor.projects]
    assert "hr-tool-backend" in project_repositories
    assert "hr-tool-frontend" in project_repositories
