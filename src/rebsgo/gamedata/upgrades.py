# github.com/Shran21

from __future__ import annotations

from abc import ABC
from rebsgo.gamedata import json_helper as jh
from rebsgo.gamedata.loot_tables import LootEntry
from rebsgo.gamedata.reading import AugmentActionKind
from rebsgo.helpers.floats import f32
from rebsgo.vocabulary.pilot import BoostSource
from typing import Optional


class AugmentSpec(ABC):
    def __init__(self, augment_action_type, associated_item_guid: int):
        self.augment_action_type = augment_action_type
        self.associated_item_guid = associated_item_guid


_augment_templates: dict[int, object] = {}


def remember_augment_templates(mapping: dict) -> None:
    _augment_templates.update(mapping)


def augment_template_for(for_item_guid: int) -> Optional[object]:
    return _augment_templates.get(for_item_guid)


class BoostKindRow:
    def __init__(self, type, value: float):
        self._type = type
        self._value = value

    @classmethod
    def from_json(cls, obj: dict) -> "BoostKindRow":
        from rebsgo.vocabulary.pilot import BoostKind

        return cls(jh.as_enum_by_name(obj, "type", BoostKind), jh.as_float(obj, "value"))

    def type(self):
        return self._type

    def value(self) -> float:
        return self._value


class AugmentBoostSpec(AugmentSpec):
    def __init__(self, associated_item_guid: int, factor_source, boost_sorok, aktiv_orak: int):
        super().__init__(AugmentActionKind.None_, associated_item_guid)
        self.factor_source = factor_source
        self._factor_type_records = boost_sorok
        self.active_time_in_hours = aktiv_orak

    @classmethod
    def from_json(cls, obj: dict) -> "AugmentBoostSpec":
        nyers = obj.get("factorTypeRecords")
        feljegyzesek = [] if nyers is None else [BoostKindRow.from_json(x) for x in nyers]
        forras = jh.as_enum_by_name(obj, "factorSource", BoostSource)
        if forras is None:
            raise ValueError("augment %s names no known factorSource (%r)" % (
                obj.get("associatedItemGUID"), obj.get("factorSource")))
        return cls(
            jh.as_long(obj, "associatedItemGUID"),
            forras,
            feljegyzesek,
            jh.as_int(obj, "activeTimeInHours"),
        )

    @property
    def factor_type_records(self) -> list:
        return list(self._get_accumulated_into_one_type_record())

    def _get_accumulated_into_one_type_record(self):
        sums: dict = {}
        for feljegyzes in self._factor_type_records:
            sums[feljegyzes.type()] = sums.get(feljegyzes.type(), 0.0) + feljegyzes.value()
        return [BoostKindRow(t, f32(s)) for t, s in sums.items()]


class AugmentLootSpec(AugmentSpec):
    def __init__(self, associated_item_guid: int, experience: int, zsakmany_sorok):
        super().__init__(AugmentActionKind.LootItem, associated_item_guid)
        self.experience = experience
        self.loot_entry_infos = zsakmany_sorok

    @classmethod
    def from_json(cls, obj: dict) -> "AugmentLootSpec":
        nyers = obj.get("lootEntryInfos")
        loot_entry_infos = None if nyers is None else [LootEntry.from_json(x) for x in nyers]
        return cls(jh.as_long(obj, "associatedItemGUID"), jh.as_long(obj, "experience"), loot_entry_infos)


class AugmentExperienceSpec(AugmentSpec):
    def __init__(self, associated_item_guid: int, experience: int):
        super().__init__(AugmentActionKind.None_, associated_item_guid)
        self.experience = experience

    @classmethod
    def from_json(cls, obj: dict) -> "AugmentExperienceSpec":
        return cls(jh.as_long(obj, "associatedItemGUID"), jh.as_long(obj, "experience"))


class AugmentTeleportSpec(AugmentSpec):
    def __init__(self, associated_item_guid: int):
        super().__init__(AugmentActionKind.Teleport, associated_item_guid)

    @classmethod
    def from_json(cls, obj: dict) -> "AugmentTeleportSpec":
        return cls(jh.as_long(obj, "associatedItemGUID"))
