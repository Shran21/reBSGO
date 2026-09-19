# github.com/Shran21
from __future__ import annotations

from enum import Enum


class ClanJoinError(Enum):
    Guild_doesnt_exist = 0
    Guild_already_joined = 1
    Guild_wrong_faction = 2

    @property
    def byte(self) -> int:
        return self._value_ + 1
