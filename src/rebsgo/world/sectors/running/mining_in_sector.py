# github.com/Shran21
from __future__ import annotations

import logging
from datetime import timedelta

from rebsgo.wire.bytes.stamp import Stamp
from rebsgo.vocabulary.world import ObjectKind
from rebsgo.gamedata.cards.misc_cards import TallyCardKind
from rebsgo.helpers.locks import ReentrantLock

log = logging.getLogger(__name__)


BOOKING_KEEPS = timedelta(minutes=10)


class MiningInSector:
    def __init__(self, objektumok, share_book, arrival_gate, object_forge, szektor_kartyak):
        self._space_objects = objektumok
        self._share_book = share_book
        self._arrival_gate = arrival_gate
        self._object_forge = object_forge
        self._sector_cards = szektor_kartyak
        self._user_id_to_mining_requests = {}
        self._max_time_between_mining_request_and_current_time = BOOKING_KEEPS
        self._lock = ReentrantLock()

    def book_mining(self, user_id: int, object_id: int, price) -> None:
        with self._lock:
            self._user_id_to_mining_requests.setdefault(user_id, []).append(
                MiningInSector.MiningQueue.for_object_at_price(object_id, price))

    def cancel_mining(self, user_id: int, object_id: int):
        with self._lock:
            mining_keys = self._user_id_to_mining_requests.get(user_id)
            key_was_present = next((k for k in mining_keys if k.object_id == object_id), None)
            if key_was_present is None:
                return None
            mining_requests = key_was_present

            is_ts_fine = self._is_timestamp_fine(Stamp.now(), mining_requests)
            if is_ts_fine:
                mining_keys.remove(mining_requests)
                return mining_requests.price
            else:
                return None

    def _is_timestamp_fine(self, now, banyaszkeres) -> bool:
        duration = now.duration(banyaszkeres.mining_request_time_stamp)
        return duration < self._max_time_between_mining_request_and_current_time

    def drop_stale(self) -> None:
        with self._lock:
            now = Stamp.now()
            for long_list_entry_value in self._user_id_to_mining_requests.values():
                long_list_entry_value[:] = [mr for mr in long_list_entry_value
                                            if not self._is_timestamp_fine(now, mr)]

    def mining_ship_ordered(self, user, object_id: int, price) -> None:
        from rebsgo.pilots.state.holdings.walks.storage_walk import StorageWalk

        planetoid = self._space_objects.get(object_id)
        if planetoid is None:
            return
        if planetoid.space_entity_type != ObjectKind.Planetoid:
            log.error("MiningShip call on non planetoid object!!! %s", user.user_log())
        elif planetoid.owns_miner():
            log.info("MiningShip call, MiningShip already present! %s %s",
                     planetoid.id_in_space(), user.user_log())
        elif self._share_book.loot_ownership.get(planetoid) is None:
            log.error("MiningShip call, MiningShip has no loot! %s", user.user_log())
        elif not StorageWalk.enough_held(price, user.pilot_of().hold, 1):
            log.error("Price not enough to buy %s", user.user_log())
        else:
            self._send_the_miner(user, planetoid, price)

    def _send_the_miner(self, user, planetoid, price) -> None:
        from rebsgo.pilots.state.holdings.walks.hold_walk import HoldWalk

        hold_walker = HoldWalk(user, None)
        hold_walker.take_payment(price, user.pilot_of().hold, 1)

        new_mining_ship = self._object_forge.hatch_miner(user, planetoid)
        player = user.pilot_of()
        szektor_guid = self._sector_cards.sector_card.card_guid_of()
        player.tally_desk.bump_counter(TallyCardKind.mining_ships_called, szektor_guid)
        player.tally_desk.bump_counter(TallyCardKind.planetoids_claimed, szektor_guid)
        self._arrival_gate.admit_object(new_mining_ship)

    class MiningQueue:
        def __init__(self, object_id: int, price, banyaszkeres_ms):
            self.object_id = object_id
            self._price = price
            self._mining_request_time_stamp = banyaszkeres_ms

        @property
        def price(self):
            return self._price

        @property
        def mining_request_time_stamp(self):
            return self._mining_request_time_stamp

        @staticmethod
        def for_object_at_price(object_id: int, price) -> "MiningInSector.MiningQueue":
            return MiningInSector.MiningQueue(object_id, price, Stamp.now())
