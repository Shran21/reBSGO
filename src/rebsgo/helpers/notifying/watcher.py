# github.com/Shran21

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")


class Watcher(ABC, Generic[T]):
    @abstractmethod
    def on_update(self, arg: T) -> None:
        ...
