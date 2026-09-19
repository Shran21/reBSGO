# github.com/Shran21

from __future__ import annotations

from enum import Enum


class SorszamosEnum(Enum):
    @classmethod
    def from_code(cls, value: int) -> "SorszamosEnum":
        return list(cls)[value]
