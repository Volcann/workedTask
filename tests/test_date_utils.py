"""Tests for date parsing, ticket extraction, and text manipulation utilities."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from shared.utils import (
    clean_commit_message,
    clean_markdown_bullets,
    extract_ticket_prefix,
    format_arrow_lines,
    format_iso_date,
    format_status_date,
    is_merge_commit,
    parse_target_date,
)


class TestDateUtils:
    def test_parse_uppercase_hyphen_date(self) -> None:
        res = parse_target_date("11-SEP-2026")
        assert res == date(2026, 9, 11)

    def test_parse_mixedcase_hyphen_date(self) -> None:
        res = parse_target_date("16-Sep-2026")
        assert res == date(2026, 9, 16)

    def test_parse_iso_date(self) -> None:
        res = parse_target_date("2026-09-22")
        assert res == date(2026, 9, 22)

    def test_parse_today_and_yesterday(self) -> None:
        today = date.today()
        assert parse_target_date("today") == today
        assert parse_target_date("yesterday") == today - timedelta(days=1)
        assert parse_target_date(None) == today

    def test_parse_date_object_passthrough(self) -> None:
        d = date(2026, 5, 20)
        assert parse_target_date(d) == d

    def test_parse_invalid_date_raises(self) -> None:
        with pytest.raises(ValueError, match="Unable to parse date"):
            parse_target_date("invalid-date-string-xyz")

    def test_format_status_date(self) -> None:
        d = date(2026, 9, 11)
        assert format_status_date(d) == "11-SEP-2026"

    def test_format_iso_date(self) -> None:
        d = date(2026, 9, 11)
        assert format_iso_date(d) == "2026-09-11"


class TestTextUtils:
    def test_extract_ticket_prefix(self) -> None:
        assert extract_ticket_prefix("HMT-258 | Add search") == "HMT-258"
        assert extract_ticket_prefix("HTM-228: feat - adopt AXI") == "HTM-228"
        assert extract_ticket_prefix("MB-228: Payroll run") == "MB-228"
        assert extract_ticket_prefix("No ticket prefix here") is None

    def test_clean_commit_message(self) -> None:
        raw = "   feat: add user device mapping   \n\nDetailed body description\nSecond line"
        assert clean_commit_message(raw) == "feat: add user device mapping"
        assert clean_commit_message("") == ""

    def test_is_merge_commit(self) -> None:
        assert is_merge_commit("Merge pull request #340 from dev/fix") is True
        assert is_merge_commit("Merge branch 'main' into feature") is True
        assert is_merge_commit("feat: regular non-merge commit") is False

    def test_clean_markdown_bullets(self) -> None:
        text = """
        - [x] First completed task
        * Second task item
        -> Third bullet format
        Random paragraph that is not a bullet
        • Fourth bullet item
        """
        bullets = clean_markdown_bullets(text)
        assert bullets == [
            "First completed task",
            "Second task item",
            "Third bullet format",
            "Fourth bullet item",
        ]

    def test_format_arrow_lines(self) -> None:
        items = ["Task one", "-> Task two", "->Task three", "   "]
        res = format_arrow_lines(items)
        assert res == ["-> Task one", "-> Task two", "-> Task three"]
