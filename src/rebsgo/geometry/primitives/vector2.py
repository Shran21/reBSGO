# github.com/Shran21

from __future__ import annotations

from rebsgo.geometry.maths.maths import Maths
from rebsgo.helpers.floats import f32


class Vector2:
    __slots__ = ("x", "y")


    def __init__(self, x, y):
        self.x = f32(x)
        self.y = f32(y)

    def copy(self) -> "Vector2":
        masolat = Vector2.__new__(Vector2)
        masolat.x = self.x
        masolat.y = self.y
        return masolat

    @staticmethod
    def zero() -> "Vector2":
        return Vector2(0.0, 0.0)


    def x_to(self, x: float) -> None:
        self.x = f32(x)

    def y_to(self, y: float) -> None:
        self.y = f32(y)


    @staticmethod
    def sub(a: "Vector2", b: "Vector2") -> "Vector2":
        return Vector2(a.x - b.x, a.y - b.y)


    @staticmethod
    def distance(a: "Vector2", b: "Vector2") -> float:
        return Vector2.sub(a, b).magnitude()

    def magnitude(self) -> float:
        return Maths.sqrt(self.x * self.x + self.y * self.y)


    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not isinstance(other, Vector2):
            return False
        return self.x == other.x and self.y == other.y

    def __hash__(self) -> int:
        return hash((self.x, self.y))

    def __repr__(self) -> str:
        return "<Vector2 " + f"x={self.x}, y={self.y}" + ">"
