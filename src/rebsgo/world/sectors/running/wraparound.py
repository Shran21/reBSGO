# github.com/Shran21
from __future__ import annotations

from rebsgo.vocabulary.pilot import Faction, FactionGroup


class Wraparound:
    def __init__(self, min_: int, max_: int):
        self._min = min_
        self._max = max_
        self._next_free_id = min_

    def next_id_for(self, faction, faction_group) -> int:
        safe_faction = Faction.Neutral if faction is None else faction
        safe_group = FactionGroup.Group0 if faction_group is None else faction_group
        return self.next_in_ring() | safe_faction.mask | safe_group.mask

    def next_in_ring(self) -> int:
        free_id = self._next_free_id
        self._next_free_id += 1
        if self._next_free_id >= self._max:
            self._next_free_id = self._min
        return free_id
