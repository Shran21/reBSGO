# github.com/Shran21
from __future__ import annotations


class TallySheet:
    def __init__(self, player_id: int, counters=None):
        self._player_id = player_id
        self._counters = {} if counters is None else counters

    @property
    def player_id(self) -> int:
        return self._player_id

    def counters(self) -> dict:
        return self._counters

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not isinstance(other, TallySheet):
            return False
        return self._player_id == other._player_id and self._counters == other._counters

    def __hash__(self) -> int:
        return hash(self._player_id)

    def __repr__(self) -> str:
        return f'<tallies for pilot {self._player_id}: {self._counters}>'
