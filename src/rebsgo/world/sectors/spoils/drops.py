# github.com/Shran21

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from rebsgo.gamedata.loot_tables import LootDamageSpec, LootEntry
from rebsgo.vocabulary.pilot import ResourceKind
from rebsgo.world.sectors.running.coming_and_going import DepartureWatcher


class Loot(ABC):
    @abstractmethod
    def loot_items(self):
        ...

    @abstractmethod
    def exp(self) -> int:
        ...

    @abstractmethod
    def carries_loot(self) -> bool:
        ...

    @abstractmethod
    def loot_template_lst(self):
        ...


class LootOwnership(DepartureWatcher):
    def __init__(self, zsakmany_terkep=None):
        if zsakmany_terkep is None:
            zsakmany_terkep = {}
        self._loot_map = zsakmany_terkep

    def carries_loot(self, space_object) -> bool:
        zsakmany = self._loot_map.get(space_object.id_in_space())
        if zsakmany is None:
            return False
        return zsakmany.carries_loot()

    def stash_loot(self, space_object, loot) -> None:
        self._loot_map[space_object.id_in_space()] = loot

    def get(self, space_object):
        return self._loot_map.get(space_object.id_in_space())

    def take_out(self, space_object):
        return self._loot_map.pop(space_object.id_in_space(), None)

    def remove(self, object_id: int) -> bool:
        ertek = self._loot_map.pop(object_id, None)
        return ertek is not None

    def on_update(self, arg) -> None:
        self.remove(arg.departed_object.id_in_space())


class SpoilsSource(Enum):
    PVE = 0
    PVP = 1
    ASTEROID = 2
    PLANETOID_MINING = 3


class AsteroidSpoils(Loot):
    def __init__(self, nyersanyag):
        self._ressource = nyersanyag

    def loot_items(self):
        return [LootEntry(1, [0, 255], self._ressource, 0)]

    def exp(self) -> int:
        return 50

    def carries_loot(self) -> bool:
        return self._ressource is not None and self._ressource.card_guid_of() != ResourceKind.None_.guid

    def loot_template_lst(self):
        return [LootDamageSpec.for_one(self._ressource)]

    @property
    def ressource(self):
        return self._ressource


class NpcSpoils(Loot):
    def __init__(self, zsakmany_sablonok):
        self._loot_templates = zsakmany_sablonok

    def loot_items(self):
        return [info for lt in self._loot_templates for info in lt.loot_entry_infos]

    def exp(self) -> int:
        return sum(lt.experience for lt in self._loot_templates)

    def carries_loot(self) -> bool:
        return len(self._loot_templates) != 0

    def loot_template_lst(self):
        return self._loot_templates


class PvpSpoils(Loot):
    def __init__(self, zsakmany_sablon):
        self._loot_template = zsakmany_sablon

    def loot_items(self):
        return self._loot_template.loot_entry_infos

    def exp(self) -> int:
        return self._loot_template.experience

    def carries_loot(self) -> bool:
        return len(self._loot_template.loot_entry_infos) != 0

    def loot_template_lst(self):
        return [self._loot_template]
