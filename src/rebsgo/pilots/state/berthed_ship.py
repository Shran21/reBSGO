# github.com/Shran21
from __future__ import annotations

from rebsgo.services import Services
from rebsgo.pilots.state.holdings.storages import SlotName, ShipSlot, ShipSlots
from rebsgo.world.objects.attachments import ShipTraits
from rebsgo.world.objects.numbers.kinds import PilotFeed
from rebsgo.vocabulary.world import WellKnownCard
from rebsgo.geometry.maths.maths import Maths
from rebsgo.gamedata.cards.card_view import CardView
from rebsgo.gamedata.library import Catalogue
from rebsgo.helpers.locks import ReentrantLock


class HangarShip:
    def __init__(self, user_id: int, server_id: int, guid: int, name: str):
        catalogue: Catalogue = Services.get(Catalogue)
        if server_id < 0:
            raise ValueError('server id below zero is invalid')
        if guid < 0:
            raise ValueError('id below zero is invalid')
        if name is None:
            raise TypeError('hangar ships need a name')

        self._lock = ReentrantLock()
        self._server_id = server_id
        self._name = name
        self._ship_aspects = ShipTraits()

        shop_item_card = catalogue.card_of(guid, CardView.Price)
        ship_card = catalogue.card_of(guid, CardView.Ship)
        world_card = catalogue.card_of(guid, CardView.World)
        owner_card = catalogue.card_of(guid, CardView.Owner)

        if shop_item_card is None:
            raise ValueError('shop item card absent')
        if ship_card is None:
            raise ValueError('hull card absent')
        if world_card is None:
            raise ValueError('world card absent')
        if owner_card is None:
            raise ValueError('owner card absent')

        self._shop_item_card = shop_item_card
        self._ship_card = ship_card
        self._world_card = world_card
        self._owner_card = owner_card

        self._ship_slots = ShipSlots()
        self._stickers: list = []
        self._durability = 0.0

        self._build_from_cards()
        self._ship_stats = PilotFeed(user_id, self._ship_card.stats_of)
        self._ship_stats.ship_slots = self._ship_slots

    def __str__(self) -> str:
        return ("<HangarShip " + f"server_id={self._server_id}, shop_item_card={self._shop_item_card},"
                f" ship_card={self._ship_card}, ship_aspects={self._ship_aspects}, durability={self._durability},"
                f" name='{self._name}', slots={self._ship_slots}, stickers={self._stickers},"
                f" ship_stats={self._ship_stats}" + ">")

    @property
    def durability(self) -> float:
        with self._lock:
            if self._durability < 0:
                return self._ship_card.durability
            return self._durability

    @durability.setter
    def durability(self, durability: float) -> None:
        self._durability = Maths.clamp_safe(durability, 0, self._ship_card.durability)

    @property
    def name(self) -> str:
        with self._lock:
            return self._name

    @name.setter
    def name(self, name: str) -> None:
        with self._lock:
            self._name = name

    @property
    def owner_card(self):
        return self._owner_card

    @property
    def server_id(self) -> int:
        return self._server_id

    @property
    def ship_aspects(self) -> ShipTraits:
        return self._ship_aspects

    @property
    def ship_slots(self) -> ShipSlots:
        with self._lock:
            return self._ship_slots

    @property
    def shop_item_card(self):
        return self._shop_item_card

    @property
    def stickers(self) -> list:
        return self._stickers

    def card_guid_of(self) -> int:
        return self._ship_card.card_guid_of()

    def peel_sticker(self, sticker) -> None:
        with self._lock:
            if sticker in self._stickers:
                self._stickers.remove(sticker)

    def quality(self) -> float:
        with self._lock:
            if self._ship_card.durability == 0:
                raise RuntimeError('hull card durability reads zero')
            card_durability_cleaned = 1.0 if self._ship_card.durability <= 0 else self._ship_card.durability
            return self.durability / card_durability_cleaned

    def repair_costs(self, use_cubits: bool) -> float:
        catalogue: Catalogue = Services.get(Catalogue)
        world_card = catalogue.card_or_none(WellKnownCard.GlobalCard, CardView.Global)
        repair_multiplier = world_card.repair_card(use_cubits)
        return Maths.ceil(self._durability_gap() * repair_multiplier)

    def restore_durability(self) -> None:
        self._durability = self._ship_card.durability

    def ship_card_of(self):
        return self._ship_card

    def ship_stats(self):
        with self._lock:
            return self._ship_stats

    def take_slots(self, slots: ShipSlots) -> None:
        with self._lock:
            for rekesz in slots.values():
                self._ship_slots.take_slot(rekesz)
            self._ship_stats.fold_in_stats()

    def take_sticker(self, sticker_binding) -> None:
        with self._lock:
            self._stickers.append(sticker_binding)

    def wear_down(self, levonas: float) -> None:
        with self._lock:
            if self._durability == 0:
                return
            self.durability = self._durability - levonas

    def world_card(self):
        return self._world_card

    def _build_from_cards(self) -> None:
        self._durability = self._ship_card.durability
        for ship_slot_card in self._ship_card.ship_slot_cards:
            slot_id = ship_slot_card.slot_id
            slot_level = ship_slot_card.level
            ship_slot = ShipSlot(SlotName(self._server_id, slot_id), ship_slot_card)
            if self._ship_card.level >= slot_level:
                self._ship_slots.take_slot(ship_slot)

    def _durability_gap(self) -> float:
        with self._lock:
            return self._ship_card.durability * (1.0 - self.quality())
