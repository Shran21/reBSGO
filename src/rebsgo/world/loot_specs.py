# github.com/Shran21
from __future__ import annotations

from types import MappingProxyType


class LootSpecs:
    def __init__(self, zsakmany_tabla: dict):
        self._loot_template_map = MappingProxyType(zsakmany_tabla)

    def get(self, id: int):
        return self._loot_template_map.get(id)

    def unsafe(self, id: int):
        return self._loot_template_map.get(id)
