# github.com/Shran21

from __future__ import annotations

from abc import ABC, abstractmethod
import time


class SectorStep(ABC):
    def run_timed(self) -> int:
        kezdet = int(time.time() * 1000)
        self.run()
        return int(time.time() * 1000) - kezdet

    @abstractmethod
    def run(self) -> None:
        ...


class StagedEvent:
    pass


class ScriptedEventStage:
    def __init__(self):
        self.start = 0
        self.end = 0


class SectorCatalogue:
    def __init__(self, sector_card, regulation_card, map_card):
        self._sector_card = sector_card
        self._regulation_card = regulation_card
        self._galaxy_map_card = map_card

    @property
    def sector_card(self):
        return self._sector_card

    def regulation_card(self):
        return self._regulation_card

    @property
    def map_card(self):
        return self._galaxy_map_card

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not isinstance(other, SectorCatalogue):
            return False
        return (self._sector_card == other._sector_card
                and self._regulation_card == other._regulation_card
                and self._galaxy_map_card == other._galaxy_map_card)

    def __hash__(self) -> int:
        return hash((self._sector_card, self._regulation_card, self._galaxy_map_card))

    def __repr__(self) -> str:
        return (f'<sector papers: {self._sector_card}, rules {self._regulation_card}, '
                f'map entry {self._galaxy_map_card}>')
