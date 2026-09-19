# github.com/Shran21
from __future__ import annotations

from rebsgo.pilots.state.holdings.storages import BlackHole, Hold, Locker, ShipSlot, Shop

import logging

from rebsgo.pilots.state.holdings.walks.storage_walk import StorageWalk, vezet_ide

log = logging.getLogger(__name__)


class LockerWalk(StorageWalk):
    def __init__(self, user, transfer_request=None, dice=None):
        super().__init__(user, transfer_request, dice)
        self._from_locker = user.pilot_of().locker

    @vezet_ide(Hold)
    def _to_hold(self, hold) -> None:
        item_to_move = self._from_locker.by_id(self.transfer_request.item_id)
        if item_to_move is None:
            log.error('%s asked to move item %s out of the locker, which does not hold it',
                      self.user.user_log(), self.transfer_request.item_id)
            return
        self.shift_item(item_to_move, self._from_locker, hold)

    @vezet_ide(Locker)
    def _to_locker(self, locker) -> None:
        pass

    @vezet_ide(ShipSlot)
    def _into_slot(self, ship_slot) -> None:
        self.hold_into_slot(self._from_locker, ship_slot)

    @vezet_ide(Shop)
    def _to_shop(self, shop) -> None:
        self.sell_item(self._from_locker, self._from_locker,
                       self.transfer_request.item_id, self.transfer_request.count())

    @vezet_ide(BlackHole)
    def _to_black_hole(self, black_hole) -> None:
        item_to_remove = self._from_locker.by_id(self.transfer_request.item_id)
        if item_to_remove is None:
            log.warning('%s discarded item %s from the locker, which does not hold it',
                        self.user.user_log(), self.transfer_request.item_id)
            return
        self.take_item(item_to_remove, self._from_locker)
        black_hole.add_ship_item(item_to_remove)
