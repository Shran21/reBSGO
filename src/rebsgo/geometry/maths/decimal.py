# github.com/Shran21

from __future__ import annotations

from rebsgo.helpers.floats import f32


class Decimal:
    def __init__(self, base: float = 0.0):
        self._value = f32(base)

    @property
    def value(self) -> float:
        return self._value

    def grow_by(self, hozzaadas: float) -> float:
        self._value = f32(self._value + hozzaadas)
        return self._value

    def shrink_by(self, levonando: float) -> float:
        self._value = f32(self._value - levonando)
        return self._value

    def set_value(self, value: float) -> None:
        self._value = f32(value)

    def __str__(self) -> str:
        return str(self._value)

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if type(other) is not type(self):
            return NotImplemented
        return self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value) if self._value != 0.0 else 0
