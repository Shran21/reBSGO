# github.com/Shran21

from __future__ import annotations

from rebsgo.geometry.primitives.frozen import frozen
from rebsgo.geometry.primitives.vector3 import Vector3
from rebsgo.geometry.primitives.quaternion import Quaternion


_INF = float("inf")


class CommonDirections:
    BACK = Vector3(0, 0, -1.0)
    DOWN = Vector3(0, -1.0, 0)
    FORWARD = frozen(Vector3.forward())

    LEFT = Vector3(-1.0, 0, 0)
    NEGATIVE_INFINITY = Vector3(-_INF, -_INF, -_INF)
    ONE = Vector3(1.0, 1.0, 1.0)
    POSITIVE_INFINITY = Vector3(_INF, _INF, _INF)
    RIGHT = frozen(Vector3(1, 0, 0))
    UP = frozen(Vector3(0, 1, 0))
    ZERO = frozen(Vector3(0, 0, 0))


class CommonTurns:
    IDENTITY = frozen(Quaternion(0.0, 0.0, 0.0, 1.0))
