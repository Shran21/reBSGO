# github.com/Shran21

from __future__ import annotations

import math
import struct

from rebsgo.helpers.thread_structs import F32, F32X3, F32X4

FLOAT_MAX_VALUE = struct.unpack("<f", b"\xff\xff\x7f\x7f")[0]


def f32(value: float) -> float:
    # a busy thread converts with its own Struct: a shared one is a lock without the GIL
    pack, unpack = F32.get()
    return unpack(pack(value))[0]


def f32x3(a: float, b: float, c: float) -> tuple:
    # (f32(a), f32(b), f32(c)) - bit for bit - with one conversion instead of three
    pack, unpack = F32X3.get()
    return unpack(pack(a, b, c))


def f32x4(a: float, b: float, c: float, d: float) -> tuple:
    pack, unpack = F32X4.get()
    return unpack(pack(a, b, c, d))


def fdiv(a: float, b: float) -> float:
    if b != 0.0:
        return a / b
    if a == 0.0 or a != a:
        return math.nan
    if (math.copysign(1.0, a) * math.copysign(1.0, b)) < 0.0:
        return -math.inf
    return math.inf
