# github.com/Shran21
from __future__ import annotations

from rebsgo.pilots.state.holdings.storages import BlackHole, Hold, Locker, ShipSlot, Shop

import logging

from rebsgo.pilots.state.holdings.walks.storage_walk import NincsIlyenTetel, StorageWalk, vezet_ide
from rebsgo.gamedata.ship_parts.parts import ItemType

log = logging.getLogger(__name__)


class HoldWalk(StorageWalk):
    def __init__(self, user, transfer_request=None, dice=None):
        super().__init__(user, transfer_request, dice)
        self._from_hold = self.user.pilot_of().hold

    @vezet_ide(Hold)
    def _to_hold(self, hold) -> None:
        self.debug_protocol.tell_console('hold-to-hold item move')

    @vezet_ide(Locker)
    def _to_locker(self, locker) -> None:
        is_equip = self.transfer_request.is_equip
        if is_equip:
            self.debug_protocol.tell_console(
                f'hold-to-locker move: the gear check fell over for pilot {self.user.pilot_of().user_id_of()}')
            return

        item_to_move = self._from_hold.by_id(self.transfer_request.item_id)
        if item_to_move is None:
            raise NincsIlyenTetel(self.transfer_request.item_id)

        if item_to_move.item_type == ItemType.Countable:
            self.shift_stack(item_to_move, self._from_hold, locker)
        else:
            self.shift_item(item_to_move, self._from_hold, locker)

    @vezet_ide(ShipSlot)
    def _into_slot(self, ship_slot) -> None:
        self.hold_into_slot(self._from_hold, ship_slot)

    @vezet_ide(Shop)
    def _to_shop(self, shop) -> None:
        self.sell_item(self._from_hold, self._from_hold,
                       self.transfer_request.item_id, self.transfer_request.count())

    @vezet_ide(BlackHole)
    def _to_black_hole(self, black_hole) -> None:
        item_to_remove = self._from_hold.by_id(self.transfer_request.item_id)
        if item_to_remove is None:
            log.warning('void-discard of an item the hold never contained')
            return
        log.info('{} threw item {} away for good'.format(
            self.user.user_log(), item_to_remove.card_guid_of()))
        self.take_item(item_to_remove, self._from_hold)
        black_hole.add_ship_item(item_to_remove)
