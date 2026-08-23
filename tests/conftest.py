"""Pytest configuration and shared fixtures."""

from __future__ import annotations

from datetime import date

import pytest

from status_reporter.models import ProjectConfig


@pytest.fixture
def sample_date() -> date:
    return date(2026, 9, 11)


@pytest.fixture
def sample_projects() -> list[ProjectConfig]:
    return [
        ProjectConfig(
            name="HR-Tool",
            category="Backend",
            owner="MoneyTalks-vantaggio",
            repo="backend",
            author="Volcann",
        ),
        ProjectConfig(
            name="HR-Tool",
            category="Frontend",
            owner="MoneyTalks-vantaggio",
            repo="frontend",
            author="Volcann",
        ),
    ]
