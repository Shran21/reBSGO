# github.com/Shran21

from __future__ import annotations

from dataclasses import dataclass

from rebsgo.geometry.primitives.vector3 import Vector3


@dataclass(slots=True, unsafe_hash=True)
class Face:
    f1: Vector3
    f2: Vector3
    f3: Vector3

    def __repr__(self) -> str:
        return f'<face {self.f1}-{self.f2}-{self.f3}>'
