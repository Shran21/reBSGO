# github.com/Shran21

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING
from typing import Generic, Iterable, TypeVar
from rebsgo.helpers.dice import Dice
from rebsgo.helpers.locks import ReentrantLock


if TYPE_CHECKING:
    from rebsgo.vocabulary.pilot import Faction

_FIVE_MINUTES_NS = 5 * 60 * 1_000_000_000


class DecayingCount:
    def __init__(self, faction: "Faction"):
        self._faction = faction
        self._timestamps: dict[int, int] = {}
        self._lock = threading.Lock()

    def mark_time(self) -> None:
        with self._lock:
            kulcs = time.time_ns()
            self._timestamps[kulcs] = self._timestamps.get(kulcs, 0) + 1

    def mark_moment(self, num: int) -> None:
        with self._lock:
            kulcs = time.time_ns()
            self._timestamps[kulcs] = self._timestamps.get(kulcs, 0) + num

    def trim_history(self) -> None:
        with self._lock:
            five_minutes_ago = time.time_ns() - _FIVE_MINUTES_NS
            for kulcs in [k for k in self._timestamps if k < five_minutes_ago]:
                del self._timestamps[kulcs]

    def count(self) -> int:
        self.trim_history()
        with self._lock:
            return len(self._timestamps)

    @property
    def faction(self) -> "Faction":
        return self._faction

Item = TypeVar("Item")


class WeightedPick(Generic[Item]):
    def __init__(self, random: Dice | None = None):
        self.rnd = random if random is not None else Dice()
        self._probability_map: dict[Item, int] = {}
        self._max_probability = 0
        self._lock = ReentrantLock()

    def add(self, item: Item, probability: int) -> None:
        if item is None:
            raise TypeError('an item is required')
        with self._lock:
            if probability < 1:
                return
            self._probability_map[item] = probability + self._max_probability
            self._max_probability += probability

    def add_float(self, item: Item, probability: float) -> None:
        self.add(item, int(probability) * 100)

    def add_all(self, items: Iterable[Item], probability: int) -> None:
        for tetel in items:
            self.add(tetel, probability)

    def random_item(self) -> Item:
        with self._lock:
            if not self._probability_map:
                raise ValueError('nothing eligible to choose from')
            rnd_result = self.rnd.between_whole(0, self._max_probability)

            jeloltek = [v for v in self._probability_map.values() if v >= rnd_result]
            if not jeloltek:
                raise ValueError('a state this code rules out')
            valasz = min(jeloltek)

            for tetel, ertek in self._probability_map.items():
                if ertek == valasz:
                    return tetel

            raise RuntimeError('a state this code rules out')
