# github.com/Shran21

from __future__ import annotations

from abc import ABC, abstractmethod


class Outgoing(ABC):
    @abstractmethod
    def to_wire(self, bw) -> None:
        ...
