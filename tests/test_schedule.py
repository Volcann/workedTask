from datetime import date, datetime, time, timedelta

import pytest
from config import schedule_from_config
from ghtoolkit import DateWindow, parse_timestamp
from report.data_classes import EXTRA_TIME_NOTE, ManualTask, ReportSchedule


def test_exact_required_extra_time_note():
    assert EXTRA_TIME_NOTE == "(The task is done in extra time)"


@pytest.mark.parametrize(
    "timestamp, expected",
    [
        ("2026-10-24T08:00:00+05:00", True),
        ("2026-10-24T09:00:00+05:00", False),
        ("2026-10-24T17:59:59+05:00", False),
        ("2026-10-24T18:00:00+05:00", True),
        ("2026-10-24T18:00:01+05:00", True),
        ("2026-10-25T02:00:00+05:00", True),
        ("2026-10-24T13:00:01Z", True),
    ],
)
def test_shift_boundaries_are_half_open_and_timezone_aware(schedule, timestamp, expected):
    assert schedule.is_extra_time(timestamp) is expected


def test_workday_cutoff_includes_next_day_two_am(schedule):
    assert schedule.window.contains("2026-10-25T02:00:00+05:00")
    assert schedule.window.contains("2026-10-24T06:00:00+05:00")
    assert not schedule.window.contains("2026-10-25T06:00:00+05:00")
    calendar = ReportSchedule(date(2026, 10, 24), "Asia/Karachi", time(9), time(18))
    assert not calendar.window.contains("2026-10-25T02:00:00+05:00")


def test_overnight_shift_does_not_mislabel_after_midnight_work():
    schedule = ReportSchedule(date(2026, 10, 24), "Asia/Karachi", time(22), time(6), time(12))
    assert not schedule.is_extra_time("2026-10-25T02:00:00+05:00")
    assert schedule.is_extra_time("2026-10-25T06:00:00+05:00")
    assert schedule.is_extra_time("2026-10-25T06:01:00+05:00")


@pytest.mark.parametrize("day,hours", [(date(2026, 3, 8), 23), (date(2026, 11, 1), 25)])
def test_dst_calendar_days_are_not_assumed_to_be_24_hours(day, hours):
    schedule = ReportSchedule(day, "America/New_York", time(9), time(18))
    assert schedule.window.end - schedule.window.start == timedelta(hours=hours)


def test_nonexistent_dst_shift_is_rejected():
    with pytest.raises(ValueError, match="does not exist"):
        ReportSchedule(date(2026, 3, 8), "America/New_York", time(2, 30), time(18))


def test_ambiguous_dst_times_use_the_first_occurrence():
    schedule = ReportSchedule(date(2026, 11, 1), "America/New_York", time(1, 30), time(18))
    assert schedule.start_utc.isoformat() == "2026-11-01T05:30:00+00:00"


def test_shift_must_fit_in_report_window():
    with pytest.raises(ValueError, match="fit inside"):
        ReportSchedule(date(2026, 10, 24), "Asia/Karachi", time(22), time(6))
    with pytest.raises(ValueError, match="must differ"):
        ReportSchedule(date(2026, 10, 24), "UTC", time(9), time(9))


def test_shift_hours_are_not_invented():
    with pytest.raises(ValueError, match="cannot be inferred"):
        schedule_from_config({})


def test_current_work_date_uses_cutoff():
    assert ReportSchedule.current_work_date(
        "Asia/Karachi", time(6), parse_timestamp("2026-10-25T02:00:00+05:00")
    ) == date(2026, 10, 24)
    assert ReportSchedule.current_work_date(
        "Asia/Karachi", time(6), parse_timestamp("2026-10-25T06:00:00+05:00")
    ) == date(2026, 10, 25)


@pytest.mark.parametrize("value", ["2026-10-24T12:00:00", datetime(2026, 10, 24, 12)])
def test_naive_manual_timestamps_are_rejected(value):
    with pytest.raises(ValueError, match="timezone offset"):
        ManualTask("x", "Task", value)


def test_invalid_date_window():
    stamp = parse_timestamp("2026-10-24T00:00:00Z")
    with pytest.raises(ValueError):
        DateWindow(stamp, stamp)
