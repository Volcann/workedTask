from __future__ import annotations

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytest
from report.data_classes import ReportSchedule, wall_time


def test_wall_time_valid():
    dt = wall_time(date(2026, 10, 24), time(14, 30), ZoneInfo("Asia/Karachi"))
    assert dt.year == 2026
    assert dt.month == 10
    assert dt.day == 24
    assert dt.hour == 14
    assert dt.minute == 30
    assert dt.tzinfo.key == "Asia/Karachi"


def test_wall_time_nonexistent_dst_raises():
    with pytest.raises(ValueError, match="does not exist"):
        wall_time(date(2026, 3, 8), time(2, 30), ZoneInfo("America/New_York"))


def test_schedule_invalid_timezone_raises():
    with pytest.raises(ZoneInfoNotFoundError):
        ReportSchedule(date(2026, 10, 24), "Invalid/Timezone_Name", time(9, 0), time(18, 0))


@pytest.mark.parametrize(
    "bad_start, bad_end, bad_day",
    [
        (time(9, 0, tzinfo=UTC), time(18, 0), time(0, 0)),
        (time(9, 0), time(18, 0, tzinfo=UTC), time(0, 0)),
        (time(9, 0), time(18, 0), time(0, 0, tzinfo=UTC)),
    ],
)
def test_schedule_tzinfo_in_clocks_raises(bad_start, bad_end, bad_day):
    with pytest.raises(ValueError, match="Shift/cutoff times must be local times without an offset."):
        ReportSchedule(date(2026, 10, 24), "Asia/Karachi", bad_start, bad_end, day_start=bad_day)


def test_schedule_equal_start_and_end_raises():
    with pytest.raises(ValueError, match="Shift start and end must differ."):
        ReportSchedule(date(2026, 10, 24), "Asia/Karachi", time(9, 0), time(9, 0))


def test_schedule_shift_must_fit_inside_window_raises():
    # Shift from 22:00 to 06:00 with default day_start 00:00 doesn't fit
    with pytest.raises(ValueError, match="The shift must fit inside the reporting day"):
        ReportSchedule(date(2026, 10, 24), "Asia/Karachi", time(22, 0), time(6, 0), day_start=time(0, 0))


def test_schedule_properties_and_local_timestamp():
    sched = ReportSchedule(date(2026, 10, 24), "Asia/Karachi", time(9, 0), time(18, 0), day_start=time(6, 0))
    assert sched.zone.key == "Asia/Karachi"
    assert sched.window.start.isoformat() == "2026-10-24T06:00:00+05:00"
    assert sched.window.end.isoformat() == "2026-10-25T06:00:00+05:00"

    utc_iso = "2026-10-24T04:00:00Z"
    local_iso = sched.local_timestamp(utc_iso)
    assert local_iso == "2026-10-24T09:00:00+05:00"

    dt_obj = datetime(2026, 10, 24, 4, 0, tzinfo=UTC)
    assert sched.local_timestamp(dt_obj) == "2026-10-24T09:00:00+05:00"


def test_current_work_date_default_now():
    now_utc = datetime.now(UTC)
    computed = ReportSchedule.current_work_date("UTC", time(0, 0))
    assert isinstance(computed, date)
    assert computed in {now_utc.date(), now_utc.date()}
