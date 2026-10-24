from __future__ import annotations

import os

import pytest


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    skip_live = pytest.mark.skip(reason="Live test requires GITHUB_TOKEN and projects.json")
    for item in items:
        if "live_extraction" in item.nodeid and not os.getenv("GITHUB_TOKEN"):
            item.add_marker(skip_live)
