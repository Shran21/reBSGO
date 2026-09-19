# github.com/Shran21

from __future__ import annotations

import heapq
from rebsgo.world.objects.ships import PlayerShip
from rebsgo.helpers.locks import ReentrantLock


class Booking:
    def __init__(self, mostani_ora, keses_mp: float, entry):
        self._time_stamp = mostani_ora.time_stamp() + int(keses_mp * 1000.0)
        self._entry = entry

    @property
    def entry(self):
        return self._entry

    def time_stamp(self) -> int:
        return self._time_stamp

    def __lt__(self, other: "Booking") -> bool:
        return self._time_stamp < other._time_stamp


class JumpBooking:
    def __init__(self, mostani_ora, seconds, entry, cel_szektor, player_ids,
                 arrival_transform=None):
        self._time_stamp = mostani_ora.time_stamp() + int(seconds) * 1000
        self._entry = entry
        self._target_sector = cel_szektor
        self._player_ids = player_ids
        self._arrival_transform = arrival_transform

    @property
    def entry(self):
        return self._entry

    def time_stamp(self) -> int:
        return self._time_stamp

    @property
    def target_sector(self) -> int:
        return self._target_sector

    @property
    def player_ids(self):
        return self._player_ids

    @property
    def arrival_transform(self):
        return self._arrival_transform

    def __lt__(self, other: "JumpBooking") -> bool:
        return self._time_stamp < other._time_stamp

    def __repr__(self) -> str:
        return f'<{self._entry} expires at {self._time_stamp}>' 


class JumpBook:
    def __init__(self, pilotak, tick):
        self._users = pilotak
        self._tick = tick
        self._objects = {}
        self._jumping_objects = []
        self._lock = ReentrantLock()

    def _enqueue_jump(self, space_object, cel_szektor: int, toltesi_ido: float, player_ids,
                      arrival_transform=None) -> None:
        if space_object is None:
            raise TypeError('there is no jump without an object to jump')
        if isinstance(space_object, PlayerShip):
            space_object.visibility_of().settle_ghost_jump()
        with self._lock:
            if self._objects.pop(space_object.id_in_space(), None) is not None:
                self._jumping_objects = [tetel for tetel in self._jumping_objects
                                         if tetel.entry.pilot_id() != space_object.pilot_id()]
                heapq.heapify(self._jumping_objects)

            heapq.heappush(self._jumping_objects,
                           JumpBooking(self._tick, toltesi_ido, space_object, cel_szektor, player_ids,
                                       arrival_transform))
            self._objects[space_object.id_in_space()] = space_object

    def book_jump_out(self, user_id: int, target_sector_id: int, toltesi_ido: float, player_ids,
                      arrival_transform=None) -> None:
        player_ship = self._users.ship_of_pilot(user_id)
        if player_ship is None:
            return

        self._enqueue_jump(player_ship, target_sector_id, toltesi_ido, player_ids, arrival_transform)

    def remove_jump(self, user_id: int) -> None:
        with self._lock:
            users_matching = {obj.id_in_space() for obj in self._objects.values()
                              if obj.pilot_id() == user_id}

            self._jumping_objects = [tetel for tetel in self._jumping_objects
                                     if tetel.entry.id_in_space() not in users_matching]
            heapq.heapify(self._jumping_objects)
            for obj_id in users_matching:
                self._objects.pop(obj_id, None)

    def holds_object(self, arg) -> bool:
        if not isinstance(arg, int):
            return self.holds_object(arg.id_in_space())
        with self._lock:
            return arg in self._objects

    def has_expiring(self, current) -> bool:
        with self._lock:
            if not self._jumping_objects:
                return False

            jump_schedule_item = self._jumping_objects[0]
            delta = jump_schedule_item.time_stamp() - current.time_stamp()
            return delta <= 0

    def item(self) -> JumpBooking:
        with self._lock:
            if not self._jumping_objects:
                raise RuntimeError('queue is empty; nothing to take')
            ertek = heapq.heappop(self._jumping_objects)
            entry = ertek.entry
            self._objects.pop(entry.id_in_space(), None)
            return ertek
