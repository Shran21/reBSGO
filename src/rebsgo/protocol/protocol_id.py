# github.com/Shran21

from __future__ import annotations

from enum import Enum


class ProtocolID(Enum):
    Login = 0
    Universe = 1
    Game = 2
    Sync = 3
    Pilot = 4
    Debug = 5
    Catalogue = 6
    Ranking = 7
    Story = 8
    Scene = 9
    Room = 10
    Community = 11
    Shop = 12
    Setting = 13
    Ship = 14
    Dialog = 15
    Market = 16
    Notification = 17
    Subscribe = 18
    Feedback = 19
    Tournament = 20
    Arena = 21
    Battlespace = 22
    Wof = 23
    Zone = 24

    @property
    def value_byte(self) -> int:
        return self._value_

    @staticmethod
    def _to_signed_byte(value: int) -> int:
        b = value & 0xFF
        return b - 256 if b >= 128 else b

    @classmethod
    def from_code(cls, value: int) -> "ProtocolID | None":
        return _BY_VALUE.get(cls._to_signed_byte(value))


_BY_VALUE = {member.value: member for member in ProtocolID}
