"""Tests for dynamic project configuration operations in projects.json."""

from __future__ import annotations

import json
from pathlib import Path

from ghtoolkit.models import ProjectConfig

from status_reporter.config.loader import (
    add_project,
    filter_projects,
    load_projects,
    remove_project,
    save_projects,
)


def test_load_projects_from_file(tmp_path: Path) -> None:
    config_file = tmp_path / "projects.json"
    data = [
        {
            "name": "HR-Tool",
            "category": "Backend",
            "owner": "MoneyTalks-vantaggio",
            "repo": "backend",
            "author": "Volcann",
        },
        {
            "name": "HR-Tool",
            "category": "Frontend",
            "owner": "MoneyTalks-vantaggio",
            "repo": "frontend",
            "author": "Volcann",
        },
    ]
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    projects = load_projects(config_file)
    assert len(projects) == 2
    assert projects[0].name == "HR-Tool"
    assert projects[0].category == "Backend"
    assert projects[0].full_name == "MoneyTalks-vantaggio/backend"
    assert projects[1].category == "Frontend"


def test_load_projects_missing_file_fallback(tmp_path: Path) -> None:
    non_existent = tmp_path / "does_not_exist.json"
    projects = load_projects(non_existent)
    assert len(projects) > 0
    assert projects[0].name == "HR-Tool"


def test_add_and_update_project(tmp_path: Path) -> None:
    config_file = tmp_path / "projects.json"
    save_projects([], config_file)

    # 1. Add project
    p1 = add_project(
        name="Circle2Learn",
        owner="Circle2Learn",
        repo="backend",
        category="Backend",
        author="Volcann",
        config_path=config_file,
    )
    assert p1.name == "Circle2Learn"
    loaded = load_projects(config_file)
    assert len(loaded) == 1
    assert loaded[0].owner == "Circle2Learn"

    # 2. Update existing project (same owner and repo)
    p2 = add_project(
        name="Circle2Learn-V2",
        owner="Circle2Learn",
        repo="backend",
        category="Backend",
        author="OtherUser",
        config_path=config_file,
    )
    assert p2.name == "Circle2Learn-V2"
    loaded2 = load_projects(config_file)
    assert len(loaded2) == 1
    assert loaded2[0].name == "Circle2Learn-V2"
    assert loaded2[0].author == "OtherUser"


def test_remove_project(tmp_path: Path) -> None:
    config_file = tmp_path / "projects.json"
    save_projects(
        [
            ProjectConfig(name="P1", owner="Org", repo="repo-a"),
            ProjectConfig(name="P2", owner="Org", repo="repo-b"),
        ],
        config_file,
    )

    # Remove repo-a
    success = remove_project(owner="Org", repo="repo-a", config_path=config_file)
    assert success is True

    remaining = load_projects(config_file)
    assert len(remaining) == 1
    assert remaining[0].repo == "repo-b"

    # Removing non-existent repo returns False
    fail = remove_project(owner="Org", repo="unknown-repo", config_path=config_file)
    assert fail is False


def test_filter_projects() -> None:
    projects = [
        ProjectConfig(name="HR-Tool", category="Backend", owner="O1", repo="backend"),
        ProjectConfig(name="HR-Tool", category="Frontend", owner="O1", repo="frontend"),
        ProjectConfig(name="Crypto", category="Backend", owner="O2", repo="crypto-be"),
    ]

    by_name = filter_projects(projects, project_name="HR-Tool")
    assert len(by_name) == 2

    by_cat = filter_projects(projects, category="Frontend")
    assert len(by_cat) == 1
    assert by_cat[0].repo == "frontend"

    by_repo = filter_projects(projects, repo="crypto-be")
    assert len(by_repo) == 1
    assert by_repo[0].name == "Crypto"
