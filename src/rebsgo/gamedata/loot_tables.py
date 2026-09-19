# github.com/Shran21

from __future__ import annotations

from enum import Enum
from rebsgo.gamedata import json_helper as jh
from rebsgo.vocabulary.pilot import Faction


class LootByCard(Enum):
    Missile = 1
    MiningShip = 2
    Comet = 3
    Cargo = 30
    PvpKillGrey = 20
    PvpKillYellow = 21
    PvpKillWhite = 22
    PvpKillRed = 23

    @property
    def value_long(self) -> int:
        return self._value_

    @classmethod
    def from_code(cls, value: int) -> "LootByCard | None":
        return _BY_VALUE.get(value)

    @staticmethod
    def for_levels(from_level: int, to_level: int) -> "LootByCard":
        arany = LootByCard._get_modifier(from_level, to_level)
        for hatar, kartya in ((0.25, LootByCard.PvpKillGrey),
                              (0.8, LootByCard.PvpKillYellow)):
            if arany < hatar:
                return kartya
        return LootByCard.PvpKillRed if arany > 1.2 else LootByCard.PvpKillWhite

    @staticmethod
    def _get_modifier(from_level: int, to_level: int) -> float:
        from rebsgo.helpers.floats import f32

        if from_level == 0:
            return 1.5
        return f32(to_level / from_level)
_BY_VALUE = {s.value: s for s in LootByCard}


class LootSpec:
    def __init__(self, id: int, type, jutalom_darab: int, global_level_interval, experience: int,
                 chance: float, zsakmany_sorok):
        self._id = id
        self._type = type
        self.reward_count = jutalom_darab
        self._global_level_interval = global_level_interval
        self.experience = experience
        self.chance = chance
        self.loot_entry_infos = zsakmany_sorok

    @staticmethod
    def _fill_common(obj: dict, target: "LootSpec") -> None:
        target._id = jh.as_long(obj, "id")
        target._type = jh.as_enum_by_name(obj, "type", LootSpecKind)
        target.reward_count = jh.as_int(obj, "rewardCount")
        target._global_level_interval = jh.as_int_list(obj, "globalLevelIntervall")
        target.experience = jh.as_long(obj, "experience")
        target.chance = jh.as_float(obj, "chance")
        nyers = obj.get("lootEntryInfos")
        target.loot_entry_infos = None if nyers is None else [LootEntry.from_json(x) for x in nyers]

    @property
    def global_level_interval(self):
        return self._global_level_interval if self._global_level_interval is not None else [0, 255]

    def within_global_band(self, level: int) -> bool:
        if self._global_level_interval is None or len(self._global_level_interval) != 2:
            return True
        return self._global_level_interval[0] <= level <= self._global_level_interval[1]

    @property
    def id(self) -> int:
        return self._id

    @property
    def type(self):
        return self._type


class LootSpecKind(Enum):
    Damage = 0
    Radius = 1
    RadiusDamage = 2
    RadiusAll = 3


class LootEntry:
    def __init__(self, chance: float, level_interval, ship_item, szoras_szazalek: float, faction=Faction.Neutral):
        self._chance = chance
        self._level_interval = level_interval
        self._ship_item = ship_item
        self._variation_percentage = szoras_szazalek
        self._faction = faction

    @classmethod
    def from_json(cls, obj: dict) -> "LootEntry":
        from rebsgo.gamedata.decoding.ship_item_parser import ship_item_from_json

        raw_item = obj.get("shipItem")
        ship_item = None if raw_item is None else ship_item_from_json(raw_item)
        return cls(
            jh.as_float(obj, "chance"),
            jh.as_int_list(obj, "levelIntervall"),
            ship_item,
            jh.as_float(obj, "variationPercentage"),
            jh.as_enum_by_name(obj, "faction", Faction),
        )

    @property
    def chance(self) -> float:
        return self._chance

    @property
    def level_interval(self):
        return self._level_interval

    @property
    def ship_item(self):
        return self._ship_item

    @property
    def variation_percentage(self) -> float:
        return self._variation_percentage

    def faction(self) -> Faction:
        if self._faction is None:
            return Faction.Neutral
        return self._faction

    def is_in_level_interval(self, level: int) -> bool:
        return self._level_interval[0] <= level <= self._level_interval[1]

    def open_to_faction(self, faction: Faction) -> bool:
        current_faction = self.faction()
        if current_faction is Faction.Neutral:
            return True
        return current_faction == faction


class LootDamageSpec(LootSpec):
    def __init__(self, id: int, jutalom_darab: int, experience: int, chance: float, zsakmany_sorok):
        super().__init__(id, LootSpecKind.Damage, jutalom_darab, [0, 255], experience, chance, zsakmany_sorok)

    @classmethod
    def from_json(cls, obj: dict) -> "LootDamageSpec":
        t = cls.__new__(cls)
        LootSpec._fill_common(obj, t)
        return t

    @staticmethod
    def for_one(nyersanyag) -> "LootDamageSpec":
        return LootDamageSpec(
            -1, 1, 50, 1,
            [LootEntry(1, [0, 255], nyersanyag, 0)],
        )


class LootRadiusSpec(LootSpec):
    def __init__(self, id: int, jutalom_darab: int, experience: int, chance: float, zsakmany_sorok,
                 radius: float, type=LootSpecKind.Radius):
        super().__init__(id, type, jutalom_darab, [0, 255], experience, chance, zsakmany_sorok)
        self.radius = radius

    @classmethod
    def from_json(cls, obj: dict) -> "LootRadiusSpec":
        t = cls.__new__(cls)
        LootSpec._fill_common(obj, t)
        t.radius = jh.as_float(obj, "radius")
        return t

    def radius_of(self) -> float:
        return self.radius


class LootDamageRadiusSpec(LootRadiusSpec):
    def __init__(self, id: int, jutalom_darab: int, experience: int, chance: float, zsakmany_sorok,
                 radius: float, legkisebb_sebzes: float):
        super().__init__(id, jutalom_darab, experience, chance, zsakmany_sorok, radius,
                         type=LootSpecKind.RadiusDamage)
        self.min_damage = legkisebb_sebzes

    @classmethod
    def from_json(cls, obj: dict) -> "LootDamageRadiusSpec":
        t = cls.__new__(cls)
        LootSpec._fill_common(obj, t)
        t.radius = jh.as_float(obj, "radius")
        t.min_damage = jh.as_float(obj, "minDamage")
        return t

    @property
    def reaches_floor(self) -> bool:
        return self.min_damage != 0

    @property
    def bounded_by_radius(self) -> bool:
        return self.radius != 0
