# github.com/Shran21

from __future__ import annotations

import math
import random
import struct

from rebsgo.helpers.floats import f32

_FELSO32 = 1 << 31
_FELSO64 = 1 << 63
_TORT_LEPES = 1.0 / (1 << 24)


def _egy_lepes_lejjebb(hatar: float) -> float:
    bits = struct.unpack("<I", struct.pack("<f", hatar))[0]
    return struct.unpack("<f", struct.pack("<I", bits - 1))[0]


class SeededRandom:
    def __init__(self, seed: int | None = None):
        self._forras = random.Random(seed)

    def reseed(self, seed: int) -> None:
        self._forras.seed(seed)

    def whole(self, bound: int | None = None) -> int:
        if bound is None:
            ertek = self._forras.getrandbits(32)
            return ertek - (1 << 32) if ertek >= _FELSO32 else ertek
        if bound <= 0:
            raise ValueError("bound must be positive")
        return self._forras.randrange(bound)

    def wide(self) -> int:
        ertek = self._forras.getrandbits(64)
        return ertek - (1 << 64) if ertek >= _FELSO64 else ertek

    def wide_below(self, bound: int) -> int:
        if bound <= 0:
            raise ValueError("bound must be positive")
        return self._forras.randrange(bound)

    @property
    def coin(self) -> bool:
        return self._forras.getrandbits(1) == 1

    def frac(self, origin: float | None = None, bound: float | None = None) -> float:
        if origin is None and bound is None:
            return f32(self._forras.getrandbits(24) * _TORT_LEPES)

        if bound is None:
            bound = float(origin)
            if not (0.0 < bound < math.inf):
                raise ValueError("bound must be finite and positive")
            r = self.frac()
            r = f32(r * bound)
            if r >= bound:
                r = _egy_lepes_lejjebb(bound)
            return r

        origin = float(origin)
        bound = float(bound)
        if not (-math.inf < origin < bound < math.inf):
            raise ValueError("bound must be greater than origin and the range finite")
        r = self.frac()
        if origin < bound:
            r = f32(f32(r * f32(bound - origin)) + origin)
            if r >= bound:
                r = _egy_lepes_lejjebb(bound)
        return r

    def fine(self) -> float:
        return self._forras.random()

    def gauss(self) -> float:
        return self._forras.gauss(0.0, 1.0)
