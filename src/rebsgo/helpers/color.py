# github.com/Shran21

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Color:
    r: float
    g: float
    b: float
    a: float
