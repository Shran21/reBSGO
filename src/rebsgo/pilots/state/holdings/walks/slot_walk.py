# github.com/Shran21
from __future__ import annotations

from rebsgo.pilots.state.holdings.storages import Hold, Locker, ShipSlot, Shop

import logging

from rebsgo.pilots.state.holdings.walks.storage_walk import StorageWalk, vezet_ide
from rebsgo.journal import hivasi_lanc

log = logging.getLogger(__name__)


class SlotWalk(StorageWalk):
    def __init__(self, user, transfer_request=None):
        super().__init__(user, transfer_request, None)
        self._from_slot = None
        self._from_ship = None

    def _forras_kikeresese(self) -> None:
        from_ = self.transfer_request.source_container
        from_container_id = from_.container_id
        self._from_ship = self.user.pilot_of().hangar_of().by_server_id(from_container_id.ship_id)
        self._from_slot = self._from_ship.ship_slots.slot(from_container_id.slot_id)

    @vezet_ide(Shop)
    def _to_shop(self, shop) -> None:
        self._forras_kikeresese()
        item_id = self.transfer_request.item_id
        self.sell_item(self._from_slot, self.user.pilot_of().hold, item_id, 1)

    @vezet_ide(Hold)
    def _to_hold(self, hold) -> None:
        self._forras_kikeresese()
        removed_system = self._from_slot.take_item(self.transfer_request.item_id)
        self.add_ship_item(removed_system, hold)
        self.user.send(self.player_protocol.replies.ship_slots(self._from_ship))

    @vezet_ide(Locker)
    def _to_locker(self, locker) -> None:
        self._forras_kikeresese()
        self.unslot_the_item(self._from_slot, locker)

    @vezet_ide(ShipSlot)
    def _into_slot(self, ship_slot) -> None:
        self._forras_kikeresese()
        item_to_move = self._from_slot.by_id(self.transfer_request.item_id)

        from_item = self._from_slot.take_item(self._from_slot.ship_system.server_id)

        if ship_slot.ship_system.ship_system_card is not None:
            removed_item = ship_slot.take_item(item_to_move.server_id)
            ship_slot.add_ship_item(from_item)
            self._from_slot.add_ship_item(removed_item)
        else:
            try:
                ship_slot.add_ship_item(item_to_move)
            except ValueError as hibas_ertek:
                log.error('the slot refused an item for %s: %s', self.user.pilot_of().player_log,
                          hivasi_lanc(hibas_ertek))
                self.debug_protocol.tell_console(
                    f'slot refused the operation: {hibas_ertek} - worth reporting')

        hangar_ship = self.user.pilot_of().hangar_of().active_ship()
        from rebsgo.world.capitals.capital_roster import CAPITAL_SLOT
        if hangar_ship.server_id == CAPITAL_SLOT:
            self.player_protocol.load_capital_ammo_into_slot(ship_slot)
            self.player_protocol.load_capital_ammo_into_slot(self._from_slot)
        self.user.send(self.player_protocol.replies.ship_slots(hangar_ship))
        hangar_ship.ship_stats().fold_in_stats()
