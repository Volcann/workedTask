from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from src.extractors.daily_activity_extractor import DailyActivityExtractor, main


def test_cli_execution_with_explicit_date_argument(
    capsys: pytest.CaptureFixture[str],
) -> None:
    expected_payload = {
        "date": "2026-10-21",
        "commit_data": [{"sample_hash": "2026-10-21T01:00:00Z"}],
        "comment_data": [],
        "issues_data": [],
    }

    with (
        patch.object(
            DailyActivityExtractor,
            "extract",
            return_value=expected_payload,
        ),
        patch("sys.argv", ["daily_activity_extractor", "2026-10-21"]),
    ):
        exit_code = main()

    captured_output = capsys.readouterr().out
    deserialized_data = json.loads(captured_output)

    assert exit_code == 0
    assert deserialized_data["date"] == "2026-10-21"
    assert deserialized_data["commit_data"] == [{"sample_hash": "2026-10-21T01:00:00Z"}]


def test_cli_execution_with_today_keyword(
    capsys: pytest.CaptureFixture[str],
) -> None:
    today_date_string = datetime.now(UTC).date().strftime("%Y-%m-%d")
    expected_payload = {
        "date": today_date_string,
        "commit_data": [],
        "comment_data": [],
        "issues_data": [],
    }

    with (
        patch.object(
            DailyActivityExtractor,
            "extract",
            return_value=expected_payload,
        ),
        patch("sys.argv", ["daily_activity_extractor", "today"]),
    ):
        exit_code = main()

    captured_output = capsys.readouterr().out
    deserialized_data = json.loads(captured_output)

    assert exit_code == 0
    assert deserialized_data["date"] == today_date_string


def test_cli_execution_with_yesterday_keyword(
    capsys: pytest.CaptureFixture[str],
) -> None:
    yesterday_date_string = (datetime.now(UTC).date() - timedelta(days=1)).strftime("%Y-%m-%d")
    expected_payload = {
        "date": yesterday_date_string,
        "commit_data": [],
        "comment_data": [],
        "issues_data": [],
    }

    with (
        patch.object(
            DailyActivityExtractor,
            "extract",
            return_value=expected_payload,
        ),
        patch("sys.argv", ["daily_activity_extractor", "yesterday"]),
    ):
        exit_code = main()

    captured_output = capsys.readouterr().out
    deserialized_data = json.loads(captured_output)

    assert exit_code == 0
    assert deserialized_data["date"] == yesterday_date_string


def test_cli_execution_default_fallback_to_today(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with (
        patch.object(
            DailyActivityExtractor,
            "extract",
            return_value={
                "date": "2026-10-24",
                "commit_data": [],
                "comment_data": [],
                "issues_data": [],
            },
        ) as mock_extract_method,
        patch("sys.argv", ["daily_activity_extractor"]),
    ):
        exit_code = main()

    assert exit_code == 0
    mock_extract_method.assert_called_once_with("today")
