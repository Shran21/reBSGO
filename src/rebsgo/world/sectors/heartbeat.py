# github.com/Shran21

from __future__ import annotations

import time

from rebsgo.wire.bytes.outgoing import Outgoing
from rebsgo.helpers.copyable import Copyable


UTEM_MASODPERCENKENT = 10


def utemre(masodperc: float) -> int:
    return int(masodperc * UTEM_MASODPERCENKENT)


class Tick(Outgoing, Copyable):
    TICK_RATE = 10
    TIME_DELAY_MS = 100

    def __init__(self, kezdo_ido: int):
        self._value = 0
        self._origin_time = kezdo_ido
        self._current_time = 0
        self._previous_time = 0

    def __lt__(self, other: "Tick") -> bool:
        return self._value < other._value

    def __hash__(self) -> int:
        return self._value

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if type(other) is not type(self):
            return NotImplemented
        return self._value == other._value

    def __str__(self) -> str:
        return f"<tick {self._value}>"

    @property
    def current_time_double(self) -> float:
        return self._current_time * 0.001

    @property
    def ms_passed_since_start(self) -> int:
        return self._current_time - self._origin_time

    @property
    def origin_time(self) -> int:
        return self._origin_time

    @property
    def seconds_since_start(self) -> float:
        return self.ms_passed_since_start / 1000.0

    @property
    def value(self) -> int:
        return self._value

    def actual_delta_time(self) -> float:
        from rebsgo.helpers.floats import f32
        return f32((self._current_time - self._previous_time) * 0.001)

    @staticmethod
    def at(value: int) -> "Tick":
        return Tick._of(value, 0, 0, 0)

    def copy(self) -> "Tick":
        return Tick._of(self._value, self._origin_time, self._current_time, self._previous_time)

    def delta_time(self) -> float:
        from rebsgo.helpers.floats import f32
        return f32(Tick.TICK_RATE / Tick.TIME_DELAY_MS)

    def lags_by(self, other: "Tick", seconds: float) -> bool:
        delta = self.tick_diff(other)
        if delta >= 0:
            return False
        return -delta >= utemre(seconds)

    def sleep_until_next_tick(self) -> None:
        self._previous_time = self._current_time
        self._current_time = int(time.time() * 1000)
        diff = self._current_time - self._origin_time
        current_tick = diff // Tick.TIME_DELAY_MS
        while self._value == current_tick:
            time_left = Tick.TIME_DELAY_MS - (diff % Tick.TIME_DELAY_MS)
            self._doze(time_left)
            self._current_time = int(time.time() * 1000)
            diff = self._current_time - self._origin_time
            current_tick = diff // Tick.TIME_DELAY_MS
        self._value += 1

    def sync_to_wall_clock(self) -> None:
        self._previous_time = self._current_time
        self._current_time = int(time.time() * 1000)
        diff = self._current_time - self._origin_time
        current_tick = diff // Tick.TIME_DELAY_MS
        if current_tick > self._value:
            self._value = current_tick

    def tick_diff(self, other: "Tick") -> int:
        return self._value - other._value

    def time_stamp(self) -> int:
        return self._value * Tick.TIME_DELAY_MS + self._origin_time

    def to_wire(self, bw) -> None:
        bw.write_int32(self._value)

    def _doze(self, varakozas_ms: int) -> None:
        time.sleep(varakozas_ms / 1000.0)

    @classmethod
    def _of(cls, value: int, kezdo_ido: int, current_time: int, elozo_ido: int) -> "Tick":
        t = cls.__new__(cls)
        t._value = value
        t._origin_time = kezdo_ido
        t._current_time = current_time
        t._previous_time = elozo_ido
        return t
