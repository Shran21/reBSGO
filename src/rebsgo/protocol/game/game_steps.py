# github.com/Shran21

from __future__ import annotations


class RespawnChoices:
    def __init__(self, szektor_ids, hordozo_ids):
        self._sector_ids = szektor_ids
        self._carrier_ids = hordozo_ids

    @property
    def sector_ids(self):
        return self._sector_ids

    @property
    def carrier_ids(self):
        return self._carrier_ids

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not isinstance(other, RespawnChoices):
            return False
        return self._sector_ids == other._sector_ids and self._carrier_ids == other._carrier_ids

    def __repr__(self) -> str:
        return f'<respawn at sectors {self._sector_ids} or carriers {self._carrier_ids}>'


class MiningStep:
    def __init__(self, object_id: int, sector_id: int):
        self._object_id = object_id
        self._sector_id = sector_id

    @property
    def object_id(self) -> int:
        return self._object_id

    @property
    def sector_id(self) -> int:
        return self._sector_id

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not isinstance(other, MiningStep):
            return False
        return self._object_id == other._object_id and self._sector_id == other._sector_id

    def __hash__(self) -> int:
        return hash((self._object_id, self._sector_id))

    def __repr__(self) -> str:
        return f'<mining {self._object_id} in sector {self._sector_id}>'


class ShipInSector:
    NO_SECTOR = None

    def __init__(self, sector, player_ship):
        self._sector = sector
        self._player_ship = player_ship

    def sector(self):
        return self._sector

    @property
    def player_ship(self):
        return self._player_ship

    def has_a_sector(self) -> bool:
        return self._sector is not None

    @property
    def has_player_ship(self) -> bool:
        return self._player_ship is not None

    def pair_complete(self) -> bool:
        return self.has_a_sector() and self.has_player_ship

ShipInSector.NO_SECTOR = ShipInSector(None, None)
