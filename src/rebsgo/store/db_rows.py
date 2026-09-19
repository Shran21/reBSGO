# github.com/Shran21

from __future__ import annotations

from dataclasses import dataclass


class HangarRow:
    def __init__(self, aktiv_hely: int, hajo_sorok):
        self._active_index = aktiv_hely
        self._ship_info_fetch_results = hajo_sorok

    @property
    def active_index(self) -> int:
        return self._active_index

    @property
    def ship_info_fetch_results(self):
        return self._ship_info_fetch_results

    def __repr__(self) -> str:
        return (f'<hangar, flying slot {self._active_index},'
                f' ships {self._ship_info_fetch_results}>')


@dataclass(slots=True, eq=False)
class PlaceRow:
    sector_id: int
    game_location: object
    previous_location: object

    def __repr__(self) -> str:
        return (f'<in sector {self.sector_id}, {self.game_location}'
                f' (was {self.previous_location})>')


class ShipRow:
    def __init__(self, guid: int, server_id: int, durability: float, name: str, rekesz_sorok):
        self._guid = guid
        self._server_id = server_id
        self._durability = durability
        self._name = name
        self._slot_info_wrappers = rekesz_sorok

    @property
    def guid(self) -> int:
        return self._guid

    @property
    def server_id(self) -> int:
        return self._server_id

    @property
    def durability(self) -> float:
        return self._durability

    def name(self) -> str:
        return self._name

    @property
    def slot_info_wrappers(self):
        return self._slot_info_wrappers

    def __repr__(self) -> str:
        return (f'<ship {self._name} #{self._server_id}, card {self._guid},'
                f' wear {self._durability}, fitted {self._slot_info_wrappers}>')


class SlotRow:
    def __init__(self, server_id: int, guid: int, durability: float, current_consumable_guid: int = 0):
        self._server_id = server_id
        self._guid = guid
        self._durability = durability
        self._current_consumable_guid = current_consumable_guid

    @property
    def server_id(self) -> int:
        return self._server_id

    @property
    def guid(self) -> int:
        return self._guid

    @property
    def durability(self) -> float:
        return self._durability

    @property
    def current_consumable_guid(self) -> int:
        return self._current_consumable_guid

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if type(other) is not type(self):
            return NotImplemented
        return (self._server_id == other._server_id and self._guid == other._guid
                and self._durability == other._durability
                and self._current_consumable_guid == other._current_consumable_guid)

    def __hash__(self) -> int:
        return hash((self._server_id, self._guid, self._durability, self._current_consumable_guid))

    def __repr__(self) -> str:
        return (f'<slot #{self._server_id} holds card {self._guid},'
                f' wear {self._durability}, ammo {self._current_consumable_guid}>')
