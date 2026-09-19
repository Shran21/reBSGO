# github.com/Shran21

from __future__ import annotations

import datetime as _dt
import time

_UTC = _dt.timezone.utc
_EPOCH = _dt.datetime(1970, 1, 1, tzinfo=_UTC)


def _to_epoch_milli(dt: _dt.datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_UTC)
    delta = dt - _EPOCH
    return delta.days * 86_400_000 + delta.seconds * 1000 + delta.microseconds // 1000


class Stamp:
    zone_offset = _UTC

    def __init__(self, value):
        if isinstance(value, _dt.datetime):
            self.epoch_millis = _to_epoch_milli(value)
        elif isinstance(value, float):
            self.epoch_millis = int(value) * 1000
        else:
            self.epoch_millis = int(value)

    @staticmethod
    def now() -> "Stamp":
        return Stamp(int(time.time() * 1000))

    def set(self, value) -> None:
        if isinstance(value, _dt.datetime):
            if value is None:
                raise TypeError('a moment in time is required')
            self.epoch_millis = _to_epoch_milli(value)
        else:
            self.epoch_millis = int(value)

    def take_seconds(self, seconds: float) -> None:
        self.epoch_millis = int(seconds * 1000)

    @property
    def in_seconds(self) -> float:
        return self.epoch_millis * 0.001

    @property
    def local_date(self) -> _dt.datetime:
        return _EPOCH + _dt.timedelta(milliseconds=self.epoch_millis)

    def minutes_before(self, minutes: int, date: _dt.datetime) -> bool:
        if date.tzinfo is None:
            date = date.replace(tzinfo=_UTC)
        return (self.local_date + _dt.timedelta(minutes=minutes)) < date

    def duration(self, end) -> _dt.timedelta:
        if isinstance(end, Stamp):
            end = end.local_date
        elif end.tzinfo is None:
            end = end.replace(tzinfo=_UTC)
        return abs(end - self.local_date)

    def span_ms(self, end: "Stamp") -> int:
        duration = self.duration(end)
        return abs(int(duration.total_seconds() * 1000))

    def __str__(self) -> str:
        return self.local_date.isoformat()
