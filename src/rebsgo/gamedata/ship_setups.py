# github.com/Shran21

from __future__ import annotations

from rebsgo.gamedata import json_helper as jh
from typing import Optional


_ship_config_template_map: dict[int, object] = {}


def take_all(hajo_beallitasok) -> None:
    for t in hajo_beallitasok:
        _ship_config_template_map[t.id] = t


def free_ids() -> set:
    ids: set[int] = set()
    i = 0
    while len(ids) < 100:
        if i not in _ship_config_template_map:
            ids.add(i)
        i += 1
    return ids


def config_for_id(id: int) -> Optional[object]:
    return _ship_config_template_map.get(id)


def configs_for_ship_guid(guid: int) -> list:
    return [c for c in _ship_config_template_map.values() if c.ship_guid == guid]


def first_best_config_for_guid(guid: int) -> Optional[object]:
    for c in _ship_config_template_map.values():
        if c.ship_guid == guid:
            return c
    return None


def first_best_config_for_guid_and_level(guid: int, level: int) -> Optional[object]:
    for c in _ship_config_template_map.values():
        if c.ship_guid == guid and c.level == level:
            return c
    return None


class SlotSetup:
    def __init__(self, slot_id: int, targy_guid: int, consumable_guid: int):
        self.slot_id = slot_id
        self.item_guid = targy_guid
        self.consumable_guid = consumable_guid

    @classmethod
    def from_json(cls, obj: dict) -> "SlotSetup":
        return cls(jh.as_int(obj, "slotID"), jh.as_long(obj, "itemGUID"), jh.as_long(obj, "consumableGUID"))


class ShipSetupSpec:
    def __init__(self, id: int, level: int, ship_guid: int, rekesz_beallitasok):
        self._id = id
        self.level = level
        self.ship_guid = ship_guid
        self.slot_configs = rekesz_beallitasok

    @classmethod
    def from_json(cls, obj: dict) -> "ShipSetupSpec":
        nyers = obj.get("slotConfigs")
        slot_configs = None if nyers is None else [SlotSetup.from_json(s) for s in nyers]
        return cls(jh.as_int(obj, "id"), jh.as_short(obj, "level"), jh.as_long(obj, "shipGUID"), slot_configs)

    @property
    def id(self) -> int:
        return self._id
