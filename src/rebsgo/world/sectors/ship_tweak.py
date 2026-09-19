# github.com/Shran21
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from rebsgo.wire.bytes.outgoing import Outgoing
from rebsgo.gamedata.reading import ObjectStat, ObjectStats


class ShipTweak(Outgoing):
    def __init__(self, server_id: int, ship_ability, ship_system, start_time: float, kuldo_id: int,
                 item_buff_add=None, remote_buff_add=None, remote_buff_multiply=None):
        self._server_id = server_id
        if ship_ability is None:
            raise TypeError('a ship ability is required')
        self._ship_ability = ship_ability
        self._ship_system = ship_system
        if item_buff_add is None:
            item_buff_add = ship_ability.item_buff_add
        if remote_buff_multiply is None:
            remote_buff_multiply = ship_ability.remote_buff_multiply
        if remote_buff_add is None:
            remote_buff_add = ship_ability.remote_buff_add
        self._item_buff_add = ObjectStats(item_buff_add.copy())
        self._remote_buff_multiply = ObjectStats(remote_buff_multiply.copy())
        self._remote_buff_add = ObjectStats(remote_buff_add.copy())
        self._time_of_activation = start_time * 0.001
        self._source_player_id = kuldo_id

    @property
    def time_of_activation(self) -> float:
        return self._time_of_activation

    def time_of_activation_local_date_time(self) -> datetime:
        epoch_milli = int(self._time_of_activation * 1000)
        return datetime.fromtimestamp(epoch_milli / 1000, tz=timezone.utc).replace(tzinfo=None)

    @staticmethod
    def create(ship_ability, ship_system, start_time: float, kuldo_id: int) -> "ShipTweak":
        return ShipTweak(0, ship_ability, ship_system, start_time, kuldo_id)

    @staticmethod
    def create_with_remote_buffs(ship_ability, ship_system, start_time: float, kuldo_id: int,
                                 item_buff_add, remote_buff_add, remote_buff_multiply) -> "ShipTweak":
        return ShipTweak(0, ship_ability, ship_system, start_time, kuldo_id,
                         item_buff_add, remote_buff_add, remote_buff_multiply)

    def to_wire(self, bw) -> None:
        bw.write_uint32(self._server_id)
        bw.write_guid(self._ship_ability.ship_ability_card.card_guid_of())
        bw.write_single(self.item_buff_add.stat(ObjectStat.Duration))

    @property
    def ability_type(self):
        return self._ship_ability.ship_ability_card.ability_action_type

    @property
    def server_id(self) -> int:
        return self._server_id

    @server_id.setter
    def server_id(self, server_id: int) -> None:
        self._server_id = server_id

    def ship_ability(self):
        return self._ship_ability

    @property
    def ship_system(self):
        return self._ship_system

    @property
    def item_buff_add(self) -> ObjectStats:
        return self._item_buff_add

    @property
    def remote_buff_multiply(self) -> ObjectStats:
        return self._remote_buff_multiply

    @property
    def remote_buff_add(self) -> ObjectStats:
        return self._remote_buff_add

    @property
    def source_player_id(self) -> int:
        return self._source_player_id

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if type(other) is not type(self):
            return NotImplemented
        return self._server_id == other._server_id

    def __hash__(self) -> int:
        return hash(self._server_id)

    class BuffKind(Enum):
        Buff = 1
        SectorModifier = 2

        @staticmethod
        def from_code(value: int):
            return _BUFF_TYPE_BY_VALUE.get(value)

    def __repr__(self) -> str:
        return (f'<tweak #{self._server_id} from {self._ship_ability}'
                f' on {self._ship_system}, cast {self._time_of_activation};'
                f' adds {self._item_buff_add}, remote +{self._remote_buff_add}'
                f' x{self._remote_buff_multiply}>')


_BUFF_TYPE_BY_VALUE = {b.value: b for b in ShipTweak.BuffKind}
