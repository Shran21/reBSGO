# github.com/Shran21
from __future__ import annotations

from rebsgo.gamedata.ship_parts.parts import ItemType, ShipItem


class ShopShip(ShipItem):
    def __init__(self, card_guid: int, server_id: int):
        super().__init__(card_guid, ItemType.Ship, server_id)

    def copy(self) -> ShipItem:
        return ShopShip(self.card_guid, self.server_id)
