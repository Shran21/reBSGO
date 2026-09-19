# github.com/Shran21
from __future__ import annotations

from rebsgo.gamedata.ship_parts.parts import CountableItem, ItemType


def ship_item_from_json(obj: dict):
    elso = obj.get("itemType")
    second = obj.get("type")
    nyers = second if elso is None else elso
    item_type = ItemType[nyers] if isinstance(nyers, str) else ItemType.from_code(int(nyers))

    card_guid = int(obj.get("cardGuid"))

    if item_type is ItemType.Countable:
        return CountableItem.from_guid(card_guid, int(obj.get("count")))
    if item_type is ItemType.System:
        from rebsgo.gamedata.ship_parts.parts import ShipSystem
        return ShipSystem.from_guid(card_guid)
    raise RuntimeError('nothing implements this')
