# github.com/Shran21

from __future__ import annotations

from abc import ABC, abstractmethod
from rebsgo.helpers.locks import ReadWriteLock
from types import MappingProxyType
from typing import Callable, Generic, Mapping, Optional, TypeVar


K = TypeVar("K")
V = TypeVar("V")


class Ownable(ABC):
    @property
    @abstractmethod
    def server_id(self) -> int:
        ...

    @server_id.setter
    @abstractmethod
    def server_id(self, server_id: int) -> None:
        ...


T = TypeVar("T", bound=Ownable)
_MAX_USHORT_PLUS_ONE = 0x7FFF * 2 + 1 + 1


class TwoWayMap(ABC, Generic[T]):
    def __init__(self, items: dict[int, T]):
        if items is None:
            raise TypeError('an item table is required')
        self._items = items
        rw = ReadWriteLock()
        self._olvasva = rw.read_lock
        self._irva = rw.write_lock

    def _get_free_server_id(self) -> int:
        for i in range(_MAX_USHORT_PLUS_ONE):
            if i not in self._items:
                return i
        raise RuntimeError('id space exhausted; cannot add')

    def add_item(self, new_item: T) -> None:
        with self._irva:
            free_id = self._get_free_server_id()
            new_item.server_id = free_id
            self._items[free_id] = new_item

    def remove_item(self, server_id: int) -> Optional[T]:
        with self._irva:
            return self._items.pop(server_id, None)

    def size(self) -> int:
        with self._olvasva:
            return len(self._items)

    def by_id(self, server_id: int) -> Optional[T]:
        with self._olvasva:
            return self._items.get(server_id)

    def find(self, predicate: Callable[[T], bool]) -> Optional[T]:
        with self._olvasva:
            for tetel in self._items.values():
                if predicate(tetel):
                    return tetel
            return None

    def find_all(self, predicate: Callable[[T], bool]) -> list[T]:
        with self._olvasva:
            return [tetel for tetel in self._items.values() if predicate(tetel)]

    def contains(self, server_id: int) -> bool:
        with self._olvasva:
            return server_id in self._items

    def items(self) -> Mapping[int, T]:
        return MappingProxyType(self._items)
