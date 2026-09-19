# github.com/Shran21
from __future__ import annotations

from dataclasses import dataclass

import logging

from rebsgo.gamedata.from_json.game_data_loader import GameDataLoader
from rebsgo import paths

log = logging.getLogger(__name__)


@dataclass(slots=True, eq=False)
class EventShopTemplate:
    include_all_paints: bool
    rotate_daily: bool
    rotation_count: int
    system_items: object
    countable_items: object
    card_guid: int = 0

    @staticmethod
    def empty() -> "EventShopTemplate":
        return EventShopTemplate(False, False, 0, [], [], 0)


class ShopBlacklists:
    def __init__(self, hull_guids, system_guids, consumable_guids):
        self._ship_guids = set(hull_guids)
        self._system_guids = set(system_guids)
        self._consumable_guids = set(consumable_guids)

    @property
    def ship_guids(self) -> set:
        return self._ship_guids

    @property
    def system_guids(self) -> set:
        return self._system_guids

    @property
    def consumable_guids(self) -> set:
        return self._consumable_guids

    @staticmethod
    def empty() -> "ShopBlacklists":
        return ShopBlacklists([], [], [])


class EventShopTemplateReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Shop")

    def fetch_shop_blacklists(self) -> ShopBlacklists:
        for utvonal in self.file_paths():
            if utvonal.name != "shop_blacklists.json":
                continue
            obj = self.read_json(utvonal)
            if obj is None:
                continue
            return ShopBlacklists(
                [int(g) for g in obj.get("shipGuids", [])],
                [int(g) for g in obj.get("systemGuids", [])],
                [int(g) for g in obj.get("consumableGuids", [])])
        log.warning("No shop_blacklists.json found; shop blacklists are empty")
        return ShopBlacklists.empty()

    def fetch_event_shop_template(self) -> EventShopTemplate:
        for utvonal in self.file_paths():
            if utvonal.name != "event_shop.json":
                continue
            obj = self.read_json(utvonal)
            if obj is None:
                continue
            countables = [(int(e["cardGuid"]), int(e.get("count", 1)))
                          for e in obj.get("countableItems", [])]
            return EventShopTemplate(
                bool(obj.get("includeAllPaints", False)),
                bool(obj.get("rotateDaily", False)),
                int(obj.get("rotationCount", 0)),
                [int(g) for g in obj.get("systemItems", [])],
                countables,
                int(obj.get("cardGuid", 0)))
        log.warning("No event_shop.json template found; event shop will be empty")
        return EventShopTemplate.empty()
