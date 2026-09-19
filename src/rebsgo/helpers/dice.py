# github.com/Shran21

from __future__ import annotations

from typing import Sequence, TypeVar

from rebsgo.helpers.floats import f32
from rebsgo.helpers.seeded_random import SeededRandom

T = TypeVar("T")


class Dice(SeededRandom):
    def __init__(self, seed: int | None = None):
        super().__init__(seed)

    def between_whole(self, min_v: int, max_v: int) -> int:
        if min_v == max_v:
            return min_v
        if min_v > max_v:
            return self.between_whole(max_v, min_v)
        return self.whole(max_v + 1 - min_v) + min_v

    def between_wide(self, min_v: int, max_v: int) -> int:
        if min_v == max_v:
            return min_v
        if min_v > max_v:
            return self.between_wide(max_v, min_v)
        return self.wide_below(max_v + 1 - min_v) + min_v

    def signed(self, value: float) -> float:
        return value if self.coin else -value

    def gauss(self, mean: float | None = None, std_dev: float | None = None) -> float:
        if mean is None and std_dev is None:
            return super().gauss()
        return mean + std_dev * super().gauss()

    def between(self, min_v: float, max_v: float) -> float:
        if min_v == max_v:
            return min_v
        if min_v > max_v:
            return self.between(max_v, min_v)
        return f32(self.frac() * (max_v - min_v) + min_v)

    def between_fine(self, min_v: float, max_v: float) -> float:
        if min_v == max_v:
            return min_v
        if min_v > max_v:
            return self.between_fine(max_v, min_v)
        return self.fine() * (max_v - min_v) + min_v

    def spread(self, value: float) -> float:
        return self.between(-value, value)

    def point_between(self, a: Sequence[float], b: Sequence[float]) -> list[float]:
        if a is None or b is None:
            raise TypeError("a or b is None")
        if len(a) != 3 or len(b) != 3:
            raise ValueError('operand sizes disagree')
        return [self.between(a[i], b[i]) for i in range(3)]

    def passes(self, chance: float) -> bool:
        if chance >= 1.0:
            return True
        return self.frac() < chance

    def pick(self, lst: Sequence[T]) -> T:
        if lst is None:
            raise TypeError('a list is required')
        if len(lst) == 0:
            raise ValueError('an empty list will not do')
        return lst[self.whole(len(lst))]

    def wobble(self, mostani_darab: int, percentage: float) -> int:
        if percentage == 0:
            return mostani_darab
        count_percent = f32(mostani_darab * percentage)
        min_count = f32(mostani_darab - count_percent)
        max_count = f32(mostani_darab + count_percent)
        return int(f32(max(1.0, self.between(min_count, max_count))))
