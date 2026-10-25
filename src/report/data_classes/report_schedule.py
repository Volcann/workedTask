from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from ghtoolkit import DateWindow, parse_timestamp

EXTRA_TIME_NOTE = "(The task is done in extra time)"


def wall_time(day: date, clock: time, zone: ZoneInfo) -> datetime:
    naive = datetime.combine(day, clock.replace(tzinfo=None))
    result = naive.replace(tzinfo=zone, fold=0)
    if result.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != naive:
        raise ValueError(f"Local time {naive.isoformat()} does not exist in {zone.key}.")
    return result


@dataclass(frozen=True)
class ReportSchedule:
    work_date: date
    timezone: str
    shift_start: time
    shift_end: time
    day_start: time = time(0, 0)

    def __post_init__(self) -> None:
        ZoneInfo(self.timezone)
        if any(clock.tzinfo is not None for clock in (self.shift_start, self.shift_end, self.day_start)):
            raise ValueError("Shift/cutoff times must be local times without an offset.")
        if self.shift_start == self.shift_end:
            raise ValueError("Shift start and end must differ.")
        if not (self.window.start <= self.start_utc < self.end_utc <= self.window.end):
            raise ValueError(
                "The shift must fit inside the reporting day. Adjust day_start for overnight shifts."
            )

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def window(self) -> DateWindow:
        return DateWindow(
            wall_time(self.work_date, self.day_start, self.zone),
            wall_time(self.work_date + timedelta(days=1), self.day_start, self.zone),
        )

    @property
    def start_utc(self) -> datetime:
        return wall_time(self.work_date, self.shift_start, self.zone).astimezone(UTC)

    @property
    def end_utc(self) -> datetime:
        day = self.work_date + timedelta(days=self.shift_end < self.shift_start)
        return wall_time(day, self.shift_end, self.zone).astimezone(UTC)

    def is_extra_time(self, stamp: str | datetime) -> bool:
        event_time = parse_timestamp(stamp)
        return event_time < self.start_utc or event_time >= self.end_utc

    def local_timestamp(self, stamp: str | datetime) -> str:
        return parse_timestamp(stamp).astimezone(self.zone).isoformat()

    @staticmethod
    def current_work_date(timezone: str, day_start: time, now: datetime | None = None) -> date:
        local = (now or datetime.now(UTC)).astimezone(ZoneInfo(timezone))
        return local.date() - timedelta(days=local.time() < day_start)
