# github.com/Shran21

from __future__ import annotations

from rebsgo.geometry.maths.maths import Maths
from rebsgo.helpers.floats import f32
from rebsgo.gamedata.from_json.template_readers import world_timers


class DradisContacts:
    DEFAULT_TIME_SECONDS = world_timers().dradis_contact_seconds

    def __init__(self):
        self._current = None
        self._last = None

    def update_dradis(self, dradis_valtozas) -> bool:
        self._last = self._current
        self._current = dradis_valtozas
        return self.within_time()

    def within_time(self) -> bool:
        if self._current is None or self._last is None:
            return True
        diff = self._current.time() - self._last.time()
        time_seconds = f32(diff * 0.001)
        return Maths.within_bounds_of(time_seconds, self.DEFAULT_TIME_SECONDS - 5, self.DEFAULT_TIME_SECONDS + 5)

    @property
    def current(self):
        return self._current

    @property
    def last(self):
        return self._last
