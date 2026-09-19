# github.com/Shran21

from __future__ import annotations

from abc import ABC, abstractmethod


class Incoming(ABC):
    @abstractmethod
    def read(self, br) -> None:
        ...
