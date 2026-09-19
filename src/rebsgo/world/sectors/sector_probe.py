# github.com/Shran21

from __future__ import annotations

import time
from enum import Enum

from rebsgo.helpers import json_text


class SectorProbeEvent(Enum):
    JoinQueue = 0
    MovementUpdater = 1
    ContactSweep = 2
    CastQueue = 3
    ClockworkStep = 4
    Reaper = 5


def _now_millis() -> int:
    return int(time.time() * 1000)


class SectorProbe:
    SectorProbeEvent = SectorProbeEvent

    def __init__(self, events=None, inditasi_tabla=None):
        self._events = {} if events is None else events
        self._start_timer_map = {} if inditasi_tabla is None else inditasi_tabla
        self._result_str = ""

    def _add_event(self, name: str, kello_ido: int) -> None:
        self._events[name] = kello_ido

    def start_timer(self, name) -> None:
        if isinstance(name, SectorProbeEvent):
            self.start_timer(name.name)
            return
        self._start_timer_map[name] = _now_millis()

    def stop_clock(self, name) -> None:
        if isinstance(name, SectorProbeEvent):
            self.stop_clock(name.name)
            return
        old = self._start_timer_map.pop(name, None)
        if old is None:
            return

        delta_time_stamp = _now_millis() - old

        self._add_event(name, delta_time_stamp)

    def event_older_than(self, milliseconds: int) -> bool:
        sum_value = 0
        events_array = []

        for event_name, time_value in self._events.items():
            event_object = {"Event": event_name, "time": time_value}
            events_array.append(event_object)
            sum_value += time_value

        eredmeny = {"Events": events_array, "Sum": sum_value}

        self._result_str = json_text.szoveggé(eredmeny)
        return sum_value >= milliseconds

    @property
    def result_str(self) -> str:
        return self._result_str

    def reset_trace(self) -> None:
        self._events.clear()
        self._start_timer_map.clear()

    def __repr__(self) -> str:
        return (f'<SectorProbe , events={self._events}, start_timer_map={self._start_timer_map}>')

    def is_timer_started(self, name: str) -> bool:
        return name in self._start_timer_map

    def event_pending(self, name: str) -> bool:
        return name in self._events
