# github.com/Shran21

from __future__ import annotations

import logging
import threading

from rebsgo.runtime.seat import Seat
from rebsgo.vocabulary.pilot import Faction
from rebsgo.helpers.guarded import GuardedCount
from rebsgo.helpers.locks import ReadWriteLock, Zarhato

log = logging.getLogger(__name__)


class PilotRoster(Zarhato):
    def __init__(self, nev_ellenor, pilota_tabla: dict | None = None,
                 karakter_nelkuliek: dict | None = None):
        self._user_map: dict = {} if pilota_tabla is None else pilota_tabla
        self._users_without_character: dict = {} if karakter_nelkuliek is None else karakter_nelkuliek
        self._name_validation = nev_ellenor
        self._colonial_count = GuardedCount()
        self._cylon_count = GuardedCount()
        self._colonial_sum_level = GuardedCount()
        self._cylon_sum_level = GuardedCount()
        self._read_write_lock = ReadWriteLock()
        self._choose_name_lock = threading.Lock()

    @property
    def colonial_count(self) -> GuardedCount:
        return self._colonial_count

    @property
    def cylon_count(self) -> GuardedCount:
        return self._cylon_count

    @property
    def colonial_sum_level(self) -> GuardedCount:
        return self._colonial_sum_level

    @property
    def cylon_sum_level(self) -> GuardedCount:
        return self._cylon_sum_level

    def name_available(self, vizsgalt_nev: str, user_id: int) -> bool:
        with self._olvasva:
            if self._get_internal(vizsgalt_nev, kiveve=user_id) is not None:
                return False
            return self._name_validation.name_is_free(vizsgalt_nev, user_id)

    def _get_internal(self, nev: str, kiveve: int | None = None):
        # Someone online under this name, the asker aside: an account made
        # before its character arrives with its own name already on it.
        keresett = nev.casefold()
        for user in self._user_map.values():
            player = user.pilot_of()
            if player is None or player.user_id_of() == kiveve:
                continue
            if player.name.casefold() == keresett:
                return user
        return None

    def reserved_name_for(self, name: str, player_id: int) -> bool:
        with self._choose_name_lock:
            return self._name_validation.remove_reservation(name, player_id)

    def holds_user(self, id: int) -> bool:
        with self._olvasva:
            return id in self._user_map

    def _get_without_char_internal(self, id: int):
        return self._users_without_character.get(id)

    def by_id(self, user_id: int):
        with self._olvasva:
            return self._user_map.get(user_id)

    def mind(self):
        with self._olvasva:
            return list(self._user_map.values())

    def by_name(self, name: str):
        if name is None:
            return None
        with self._olvasva:
            for user in self._user_map.values():
                player = user.pilot_of()
                if player is not None and player.name == name:
                    return user
        return None

    def anyhow(self, azonosito_vagy_nev):
        return (self.by_name(azonosito_vagy_nev)
                if isinstance(azonosito_vagy_nev, str)
                else self.by_id(azonosito_vagy_nev))
        return None

    def size(self) -> int:
        with self._olvasva:
            return len(self._user_map)

    def update(self) -> None:
        colonial = self.user_stream(lambda user: user.pilot_of().faction == Faction.Colonial)
        cylon = self.user_stream(lambda user: user.pilot_of().faction == Faction.Cylon)
        current_sum_colonial_level = sum(user.pilot_of().skill_book.get() for user in colonial)
        self._colonial_sum_level.set(current_sum_colonial_level)
        current_sum_cylon_level = sum(user.pilot_of().skill_book.get() for user in cylon)
        self._cylon_sum_level.set(current_sum_cylon_level)
        self._colonial_count.set(self.faction_headcount(Faction.Colonial))
        self._cylon_count.set(self.faction_headcount(Faction.Cylon))

    def faction_headcount(self, faction: Faction) -> int:
        with self._olvasva:
            return sum(1 for user in self._user_map.values()
                       if user.is_connected() and user.pilot_of().faction == faction)

    def pilot_born(self, player) -> Seat:
        user_id = player.user_id_of()
        with self._irva:
            if (without_char := self._get_without_char_internal(user_id)) is not None:
                associated = self._users_without_character.pop(user_id, None)
                user = Seat.of_playerless(associated, player)
                try:
                    self._add_internal(user)
                except TypeError:
                    log.exception("add_internal failed")
                log.info("Char createdfinished %s %s", len(self._user_map), len(self._users_without_character))
                return user
            raise ValueError(f'UserID could not find pre_char {user_id}')

    def remove(self, user: Seat) -> None:
        with self._irva:
            self._user_map.pop(user.pilot_of().user_id_of(), None)

    def _add_internal(self, new_user: Seat) -> None:
        if new_user is None or new_user.pilot_of() is None:
            raise TypeError('a seat with a pilot behind it is required')
        self._user_map[new_user.pilot_of().user_id_of()] = new_user

    def reserve_bare(self, id: int, user) -> None:
        with self._irva:
            self._users_without_character[id] = user

    def release_bare(self, id: int):
        with self._irva:
            return self._users_without_character.pop(id, None)

    def user_stream(self, predicate):
        return [user for user in self._user_map.values() if predicate(user)]

    def user_set(self, predicate) -> set:
        with self._olvasva:
            return {user for user in self._user_map.values() if predicate(user)}

    def user_list(self, predicate=None) -> list:
        if predicate is None:
            return list(self.values())
        with self._olvasva:
            return [user for user in self._user_map.values() if predicate(user)]

    def values(self):
        return self._user_map.values()
