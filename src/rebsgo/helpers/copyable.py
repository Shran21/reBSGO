# github.com/Shran21

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")


class Copyable(ABC, Generic[T]):
    @abstractmethod
    def copy(self) -> T:
        ...
