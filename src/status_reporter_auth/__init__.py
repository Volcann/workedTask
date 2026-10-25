"""Resolve credentials for live status reports without exposing token output."""

from __future__ import annotations

import os
import subprocess

from ghtoolkit import ConfigurationError


def github_token() -> str:
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if token:
        return token

    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise ConfigurationError(
            "Set GITHUB_TOKEN or GH_TOKEN, or run `gh auth login` to enable live reports."
        ) from None

    token = result.stdout.strip()
    if result.returncode != 0 or not token:
        raise ConfigurationError(
            "Set GITHUB_TOKEN or GH_TOKEN, or run `gh auth login` to enable live reports."
        )
    return token
