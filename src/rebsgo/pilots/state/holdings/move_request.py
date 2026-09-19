# github.com/Shran21
from __future__ import annotations

from rebsgo.pilots.state.holdings.storages import container_of, StorageKind


class MoveRequest:
    def __init__(self, br, player):
        self._br = br
        self._player = player
        self._from = None
        self._to = None
        self._item_id = 0
        self._count = 0
        self._equip = False

    def read_move_item(self) -> None:
        self._from = container_of(self._br, self._player)
        if self._from.container_id.container_type == StorageKind.BlackHole:
            raise ValueError('moving an item out of the black hole')
        self._item_id = self._br.read_uint16()
        self._count = self._br.read_uint32()
        self._to = container_of(self._br, self._player)
        self._equip = self._br.read_boolean()

    @property
    def read_container(self):
        return container_of(self._br, self._player)

    def read_move_all(self) -> None:
        self._from = container_of(self._br, self._player)
        self._to = container_of(self._br, self._player)

    def read_augment_use(self) -> None:
        self._from = container_of(self._br, self._player)
        self._item_id = self._br.read_uint16()

    def read_repair(self) -> None:
        self._from = container_of(self._br, self._player)

    def read_bulk_augment(self) -> int:
        self._from = container_of(self._br, self._player)
        self._item_id = self._br.read_uint16()
        return self._br.read_uint32()

    @property
    def source_container(self):
        return self._from

    @property
    def to(self):
        return self._to

    @property
    def item_id(self) -> int:
        return self._item_id

    def count(self) -> int:
        return self._count

    @property
    def is_equip(self) -> bool:
        return self._equip

    def __repr__(self) -> str:
        return (f'<MoveRequest from={self._from}, to={self._to}, item={self._item_id}, '
                f'count={self._count}, equip={self._equip}>')
