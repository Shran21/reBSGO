# github.com/Shran21

from __future__ import annotations

import logging

from rebsgo.gamedata.cards.misc_cards import TallyCardKind
from rebsgo.gamedata.from_json.game_data_loader import GameDataLoader
from rebsgo import paths

log = logging.getLogger(__name__)

FAJL = "hull_tallies.json"


class HullTallyReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Progression")

    def fetch_hull_tallies(self) -> dict[int, TallyCardKind]:
        for utvonal in self.file_paths():
            if utvonal.name != FAJL:
                continue
            obj = self.read_json(utvonal)
            if obj is None:
                continue
            return self._parositas(obj.get("hullTallies", []))
        log.warning('%s absent - kills of individual hulls go uncounted', FAJL)
        return {}

    @staticmethod
    def _parositas(sorok) -> dict[int, TallyCardKind]:
        parok = {}
        for sor in sorok:
            szamlalo = getattr(TallyCardKind, str(sor.get("counter", "")), None)
            if szamlalo is None:
                log.warning('%s names a counter that does not exist: %s', FAJL, sor)
                continue
            parok[int(sor["shipObjectKey"])] = szamlalo
        return parok


_parok: dict[int, TallyCardKind] | None = None


def hull_tallies() -> dict[int, TallyCardKind]:
    global _parok
    if _parok is None:
        _parok = HullTallyReader().fetch_hull_tallies()
    return _parok
