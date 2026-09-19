# github.com/Shran21

from __future__ import annotations

import logging

from rebsgo.gamedata.from_json.game_data_loader import GameDataLoader
from rebsgo.pilots.state.options.input_actions import Action
from rebsgo.pilots.state.options.key_binding import KeyBinding
from rebsgo.vocabulary.client import KeyCode, KeyHeld
from rebsgo import paths

log = logging.getLogger(__name__)

FAJL = "key_bindings.json"


class KeyBindingReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Controls")

    def fetch_default_bindings(self) -> list[KeyBinding]:
        for utvonal in self.file_paths():
            if utvonal.name != FAJL:
                continue
            obj = self.read_json(utvonal)
            if obj is None:
                continue
            return [b for b in (self._kiosztas(sor) for sor in obj.get("keyBindings", []))
                    if b is not None]
        log.warning('%s absent - new pilots start with no keys bound at all', FAJL)
        return []

    @staticmethod
    def _kiosztas(sor) -> KeyBinding | None:
        cselekves = getattr(Action, str(sor.get("action", "")), None)
        billentyu = getattr(KeyCode, str(sor.get("key", "")), None)
        if cselekves is None or billentyu is None:
            log.warning('%s names an action or key that does not exist: %s', FAJL, sor)
            return None
        tartva = sor.get("hold")
        return KeyBinding(cselekves, billentyu,
                          None if tartva is None else getattr(KeyHeld, str(tartva), None))


_kiosztasok: list[KeyBinding] | None = None


def default_key_bindings() -> list[KeyBinding]:
    global _kiosztasok
    if _kiosztasok is None:
        _kiosztasok = KeyBindingReader().fetch_default_bindings()
    return list(_kiosztasok)
