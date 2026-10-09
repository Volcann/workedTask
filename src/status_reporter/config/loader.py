"""Configuration management for projects.json and environment settings."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv
from ghtoolkit.models import ProjectConfig

# Automatically load .env from current directory or parent directories
load_dotenv()
load_dotenv("/home/folium/Documents/volcanai/.env")

DEFAULT_PROJECTS_FILE = Path("projects.json")
DEFAULT_AUTHOR = os.getenv("GITHUB_USER", "Volcann")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN", "")


def get_default_projects() -> list[ProjectConfig]:
    """Default fallback project list if no projects.json exists."""
    return [
        ProjectConfig(
            name="HR-Tool",
            category="Backend",
            owner="MoneyTalks-vantaggio",
            repo="backend",
            author=DEFAULT_AUTHOR,
        ),
        ProjectConfig(
            name="HR-Tool",
            category="Frontend",
            owner="MoneyTalks-vantaggio",
            repo="frontend",
            author=DEFAULT_AUTHOR,
        ),
    ]


def resolve_config_path(custom_path: str | Path | None = None) -> Path:
    """Resolve the path to projects.json."""
    if custom_path:
        return Path(custom_path)
    if DEFAULT_PROJECTS_FILE.exists():
        return DEFAULT_PROJECTS_FILE
    # Fallback to volcanai projects.json if local is absent
    volcanai_projects = Path("/home/folium/Documents/volcanai/cron_job/projects.json")
    if volcanai_projects.exists():
        return volcanai_projects
    return DEFAULT_PROJECTS_FILE


def load_projects(config_path: str | Path | None = None) -> list[ProjectConfig]:
    """Load project configurations from JSON file."""
    path = resolve_config_path(config_path)
    if not path.exists():
        return get_default_projects()

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError(f"Expected a JSON list in '{path}', got {type(data).__name__}")
        return [ProjectConfig.from_dict(item) for item in data if isinstance(item, dict)]
    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: Could not read {path} ({e}), using default projects.")
        return get_default_projects()


def save_projects(
    projects: Sequence[ProjectConfig],
    config_path: str | Path | None = None,
) -> Path:
    """Save project configurations to JSON file."""
    path = Path(config_path) if config_path else DEFAULT_PROJECTS_FILE
    serialized = [p.to_dict() for p in projects]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(serialized, f, indent=2)
    return path


def add_project(
    name: str,
    owner: str,
    repo: str,
    category: str = "Backend",
    author: str | None = None,
    local_path: str = "",
    config_path: str | Path | None = None,
) -> ProjectConfig:
    """Add a new project to projects.json or update existing."""
    projects = load_projects(config_path)
    author_val = author or DEFAULT_AUTHOR

    # Auto-discover local repo path if not explicitly provided
    resolved_local_path = local_path
    if not resolved_local_path:
        candidates = [
            Path(f"/home/folium/Documents/HR-Tool/{repo}"),
            Path(f"/home/folium/Documents/{name}/{repo}"),
            Path(f"../{name}/{repo}"),
            Path(f"../{repo}"),
        ]
        for c in candidates:
            if c.exists() and (c / ".git").exists():
                resolved_local_path = str(c.resolve())
                break

    new_project = ProjectConfig(
        name=name,
        category=category,
        owner=owner,
        repo=repo,
        author=author_val,
        local_path=resolved_local_path,
    )

    # Check if duplicate exists
    updated = False
    for i, p in enumerate(projects):
        if p.owner.lower() == owner.lower() and p.repo.lower() == repo.lower():
            projects[i] = new_project
            updated = True
            break

    if not updated:
        projects.append(new_project)

    save_projects(projects, config_path)
    return new_project


def remove_project(
    owner: str,
    repo: str,
    config_path: str | Path | None = None,
) -> bool:
    """Remove a project from projects.json by owner and repo."""
    projects = load_projects(config_path)
    initial_len = len(projects)
    filtered = [
        p
        for p in projects
        if not (p.owner.lower() == owner.lower() and p.repo.lower() == repo.lower())
    ]
    if len(filtered) < initial_len:
        save_projects(filtered, config_path)
        return True
    return False


def filter_projects(
    projects: Sequence[ProjectConfig],
    project_name: str | None = None,
    category: str | None = None,
    repo: str | None = None,
) -> list[ProjectConfig]:
    """Filter projects by project name, category, or repo."""
    result: list[ProjectConfig] = []
    for p in projects:
        if not p.enabled:
            continue
        if project_name and p.name.lower() != project_name.lower():
            continue
        if category and p.category.lower() != category.lower():
            continue
        if repo and p.repo.lower() != repo.lower():
            continue
        result.append(p)
    return result
