from __future__ import annotations

import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from ghtoolkit import ConfigurationError
from status_reporter_auth import github_token


def test_github_token_reads_existing_gh_login(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    with patch(
        "status_reporter_auth.subprocess.run",
        return_value=SimpleNamespace(returncode=0, stdout="secret-token\n"),
    ) as mock_run:
        assert github_token() == "secret-token"
    mock_run.assert_called_once_with(
        ["gh", "auth", "token"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def test_github_token_preserves_environment_credentials(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "environment-token")
    with patch("status_reporter_auth.subprocess.run") as mock_run:
        assert github_token() == "environment-token"
    mock_run.assert_not_called()


@pytest.mark.parametrize(
    "outcome",
    [SimpleNamespace(returncode=1, stdout="secret-token"), SimpleNamespace(returncode=0, stdout="")],
)
def test_github_token_reports_missing_login_without_leaking_output(monkeypatch, outcome):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    with (
        patch("status_reporter_auth.subprocess.run", return_value=outcome),
        pytest.raises(ConfigurationError, match="gh auth login") as exc,
    ):
        github_token()
    assert "secret-token" not in str(exc.value)
