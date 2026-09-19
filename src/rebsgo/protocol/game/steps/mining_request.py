# github.com/Shran21
from __future__ import annotations

import logging

from rebsgo.protocol.message_route import MessageRoute

log = logging.getLogger(__name__)


class MiningRequest(MessageRoute):
    def __init__(self, user, sector_book):
        self._user = user
        self._sector_book = sector_book

    def handle(self, br) -> None:
        planetoid_id = br.read_uint32()
        sector = self._resolve_sector()
        if sector is None:
            log.warning('%s asked to mine while in no sector at all', self._user.user_log())
            return

        ar = sector.mining_sector_operations.cancel_mining(
            self._user.pilot_of().user_id_of(), planetoid_id)
        if ar is None:
            log.warning('%s asked to mine %s without a scan to price it by',
                        self._user.user_log(), planetoid_id)
            return

        log.info('mining %s ordered for %s', planetoid_id, ar)
        sector.mining_sector_operations.mining_ship_ordered(self._user, planetoid_id, ar)

    def _resolve_sector(self):
        if self._user is None:
            return None
        player = self._user.pilot_of()
        return self._sector_book.sector_by_id(player.sector_id)
