# github.com/Shran21

from __future__ import annotations

import math
import struct

_PACK = struct.Struct("<f").pack
_UNPACK = struct.Struct("<f").unpack

FLOAT_MAX_VALUE = struct.unpack("<f", b"\xff\xff\x7f\x7f")[0]


def f32(value: float) -> float:
    return _UNPACK(_PACK(value))[0]


def fdiv(a: float, b: float) -> float:
    if b != 0.0:
        return a / b
    if a == 0.0 or a != a:
        return math.nan
    if (math.copysign(1.0, a) * math.copysign(1.0, b)) < 0.0:
        return -math.inf
    return math.inf
