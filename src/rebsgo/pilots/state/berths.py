# github.com/Shran21
from __future__ import annotations

from rebsgo.pilots.state.berthed_ship import HangarShip
from rebsgo.pilots.state.pilot_bits import HangarChange
from rebsgo.pilots.state.watching import InfoBroadcast
from rebsgo.protocol.watching.watching import InfoKind
from rebsgo.helpers.locks import ReadWriteLock, Zarhato


class Hangar(InfoBroadcast, Zarhato):
    def __init__(self, player_id: int, ships=None):
        super().__init__(InfoKind.Ships, player_id, HangarChange("", []))
        self._ships: dict = {} if ships is None else ships
        self._active_ship_index = -1
        self._read_write_lock = ReadWriteLock()

    def __str__(self) -> str:
        return "<Hangar " + f"ships={self._ships}, active_ship_index={self._active_ship_index}" + ">"

    def active_ship(self) -> HangarShip:
        with self._olvasva:
            if self._active_ship_index == -1:
                if len(self._ships) == 0:
                    raise RuntimeError('the hangar holds no ships for this player yet')
                raise RuntimeError('no ship is marked active')
            return self._ships.get(self._active_ship_index)

    def all_hangar_ships(self) -> list:
        with self._olvasva:
            return list(self._ships.values())

    def berth(self, uj_hangar_hajo: HangarShip) -> None:
        with self._irva:
            if len(self._ships) == 0:
                self._active_ship_index = uj_hangar_hajo.server_id
            self._ships[uj_hangar_hajo.server_id] = uj_hangar_hajo
            self._hangar_ships_update()

    def by_server_id(self, server_id: int) -> HangarShip:
        with self._olvasva:
            return self._ships.get(server_id)

    def choose_active_ship(self, index: int) -> None:
        with self._irva:
            if index in self._ships:
                self._active_ship_index = index
                self._hangar_ships_update()

    def flying_something(self) -> bool:
        with self._olvasva:
            if self._active_ship_index == -1:
                if len(self._ships) == 0:
                    return False
                return False
            return True

    def remove_hangar_ship(self, server_id: int):
        with self._irva:
            removed = self._ships.pop(server_id, None)
            if removed is not None:
                if self._active_ship_index == server_id:
                    self._active_ship_index = next(iter(self._ships)) if self._ships else -1
                if self._ships:
                    self._hangar_ships_update()
            return removed

    def sorted_guids(self) -> list:
        with self._olvasva:
            ids = [self.active_ship().card_guid_of()]
            for ertek in self._ships.values():
                if self.active_ship().card_guid_of() == ertek.card_guid_of():
                    continue
                ids.append(ertek.card_guid_of())
            return ids

    def wipe_hangar(self) -> None:
        with self._irva:
            self._ships.clear()

    def _hangar_ships_update(self) -> None:
        self.set(HangarChange(self.active_ship().name, self.sorted_guids()))
