# github.com/Shran21
from __future__ import annotations

import logging

from rebsgo.pilots.state.holdings.storages import StorageKind, Hold, Locker, ShipSlot
from rebsgo.pilots.state.holdings.walks.storage_walk import StorageWalk, vezet_ide
from rebsgo.vocabulary.world import PlaceKind
from rebsgo.gamedata.ship_parts.parts import CountableItem, ItemType
from rebsgo.journal import hivasi_lanc

log = logging.getLogger(__name__)


class ShopWalk(StorageWalk):
    def __init__(self, user, transfer_request=None, dice=None):
        super().__init__(user, transfer_request, dice)
        self._from_shop = self.user.pilot_of().shop

    @vezet_ide(Hold)
    def _to_hold(self, hold) -> None:
        self._buy_from_this_to_container(hold)

    @vezet_ide(Locker)
    def _to_locker(self, locker) -> None:
        self._buy_from_this_to_container(locker)

    @vezet_ide(ShipSlot)
    def _into_slot(self, ship_slot) -> None:
        player = self.user.pilot_of()
        if player.location.game_location != PlaceKind.Room:
            log.error(f'pilot {player.user_id_of()} moved gear between slots away from a station')
            return

        item_to_buy = self._from_shop.by_id(self.transfer_request.item_id)
        if item_to_buy is None or item_to_buy.item_type != ItemType.System:
            self.debug_protocol.tell_console(
                'purchase target absent' if item_to_buy is None
                else 'purchase target is not the entry-level system')
            return

        try:
            buy_price = self.purchase_price(item_to_buy, player.hold, 1)
            if buy_price is None:
                self.debug_protocol.tell_console('purchase attempted where purchasing is off ')
                return
            buy_count = self.transfer_request.count()
            self.take_payment(buy_price, player.hold, buy_count)
            copy_item = item_to_buy.copy()
            self.relocate_into_slot(
                copy_item, player.hold, ship_slot, StorageKind.Shop)
        except ValueError as hibas_ertek:
            log.warning(str(hibas_ertek))

    def _buy_from_this_to_container(self, hova_tarolo) -> None:
        try:
            item_to_buy = self._from_shop.by_id(self.transfer_request.item_id)
            buy_count = self.transfer_request.count()
            buy_container = self.user.pilot_of().hold
            buy_price = self.purchase_price(item_to_buy, buy_container, buy_count)

            if buy_price is None:
                log.warning("purchase refused: card %s, %s asked",
                            item_to_buy.card_guid_of(), buy_count)
                return

            log.info("purchase went through: %s x%s for %s", item_to_buy, buy_count, buy_price)

            self.take_payment(buy_price, buy_container, buy_count)
            item_to_buy = item_to_buy.copy()
            if isinstance(item_to_buy, CountableItem):
                item_to_buy.update_count(buy_count)

            self.add_ship_item(item_to_buy, hova_tarolo)
        except ValueError as hibas_ertek:
            log.error(hivasi_lanc(hibas_ertek))
