# github.com/Shran21

from __future__ import annotations

from dataclasses import dataclass

from rebsgo.gamedata import json_helper as jh
from rebsgo.vocabulary.pilot import Faction
from types import MappingProxyType


@dataclass(slots=True, eq=False)
class AssignmentSectorInfo:
    static_sector_id: int
    use_random_sector: bool
    sector_ids_blacklist: object
    sector_ids_whitelist: object

    @classmethod
    def from_json(cls, obj: dict) -> "AssignmentSectorInfo":
        raw_b = obj.get("sectorIdsBlacklist")
        raw_w = obj.get("sectorIdsWhitelist")
        return cls(
            jh.as_long(obj, "staticSectorId"),
            jh.as_flag(obj, "useRandomSector"),
            None if raw_b is None else set(int(x) for x in raw_b),
            None if raw_w is None else set(int(x) for x in raw_w),
        )

    @property
    def is_global(self) -> bool:
        return self.static_sector_id == 0 and not self.use_random_sector

    def barred(self, id: int) -> bool:
        return id in self.sector_ids_blacklist

    def admitted(self, id: int) -> bool:
        if len(self.sector_ids_whitelist) == 0:
            return True
        return id in self.sector_ids_whitelist


_mission_template_list: dict[int, object] = {}
_colonial_mission_templates: dict[int, object] = {}
_cylon_mission_templates: dict[int, object] = {}


def seed_missions(kuldetes_sablonok: dict) -> None:
    if _mission_template_list:
        raise RuntimeError("AssignmentSpecs can only be initialized one time!")
    _mission_template_list.update(kuldetes_sablonok)
    _add_for_mission_template(kuldetes_sablonok, _colonial_mission_templates, Faction.Colonial)
    _add_for_mission_template(kuldetes_sablonok, _cylon_mission_templates, Faction.Cylon)


def _add_for_mission_template(forras: dict, celtabla: dict, faction: Faction) -> None:
    inverted = Faction.negated(faction)
    for mission_template in forras.values():
        if inverted is not mission_template.faction():
            celtabla[mission_template.id()] = mission_template


def mission_templates(faction: Faction):
    celpont = _colonial_mission_templates if faction is Faction.Colonial else _cylon_mission_templates
    return MappingProxyType(celpont)


class AssignmentTallyEntry:
    def __init__(self, guid: int, need_count: int):
        self._guid = guid
        self._need_count = need_count

    @classmethod
    def from_json(cls, obj: dict) -> "AssignmentTallyEntry":
        return cls(jh.as_long(obj, "guid"), jh.as_long(obj, "needCount"))

    @property
    def guid(self) -> int:
        return self._guid

    @property
    def need_count(self) -> int:
        return self._need_count


class AssignmentSpec:
    def __init__(self, id: int, assignment_guid: int, faction, mission_layout, kuldetes_szamlalok):
        self._id = id
        self._mission_guid = assignment_guid
        self._faction = faction
        self._mission_sector_desc = mission_layout
        self._mission_count_entries = kuldetes_szamlalok

    @classmethod
    def from_json(cls, obj: dict) -> "AssignmentSpec":
        raw_sector = obj.get("missionSectorDesc")
        sector_desc = None if raw_sector is None else AssignmentSectorInfo.from_json(raw_sector)
        raw_entries = obj.get("missionCountEntries")
        bejegyzesek = None if raw_entries is None else [AssignmentTallyEntry.from_json(x) for x in raw_entries]
        return cls(
            jh.as_int(obj, "id"),
            jh.as_long(obj, "missionGuid"),
            jh.as_enum_by_name(obj, "faction", Faction),
            sector_desc,
            bejegyzesek,
        )

    def id(self) -> int:
        return self._id

    @property
    def mission_guid(self) -> int:
        return self._mission_guid

    def faction(self) -> Faction:
        return self._faction

    @property
    def mission_layout(self):
        return self._mission_sector_desc

    @property
    def mission_count_entries(self):
        return self._mission_count_entries
