# github.com/Shran21

from __future__ import annotations

from abc import ABC, abstractmethod


class MessageRoute(ABC):
    @abstractmethod
    def handle(self, br) -> None:
        ...
