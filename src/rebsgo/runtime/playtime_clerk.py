# github.com/Shran21

from __future__ import annotations

import logging

from rebsgo.gamedata.cards.misc_cards import TallyCardKind

log = logging.getLogger(__name__)


class PlaytimeClerk:
    def __init__(self, pilot_roster, masodperc: float):
        self._pilot_roster = pilot_roster
        self._masodperc = float(masodperc)

    @property
    def interval_seconds(self) -> float:
        return self._masodperc

    def run(self) -> None:
        for user in self._pilot_roster.mind():
            try:
                pilota = user.pilot_of()
                if pilota is None:
                    continue
                pilota.tally_desk.bump_counter(TallyCardKind.time_played, 0, self._masodperc)
            except Exception:
                log.exception("playtime would not be booked for one pilot")
