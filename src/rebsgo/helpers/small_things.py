# github.com/Shran21

from __future__ import annotations


class SmallIdPool:
    _LAST_ID = 65535

    def __init__(self, initial: int = 0):
        self._ushort_id = initial

    def free_id(self) -> int:
        new_value = self._ushort_id
        self._ushort_id += 1
        if new_value >= self._LAST_ID:
            new_value = 0
        return new_value


class OrderedSet:
    def __init__(self, iterable=None):
        self._items = []
        if iterable is not None:
            for x in iterable:
                self.add(x)

    def _bisect(self, item):
        lo, hi = 0, len(self._items)
        while lo < hi:
            mid = (lo + hi) >> 1
            kozepso = self._items[mid]
            if kozepso < item:
                lo = mid + 1
            elif item < kozepso:
                hi = mid
            else:
                return mid, True
        return lo, False

    def add(self, item) -> bool:
        idx, talalt = self._bisect(item)
        if talalt:
            return False
        self._items.insert(idx, item)
        return True

    def remove(self, item) -> bool:
        idx, talalt = self._bisect(item)
        if talalt:
            del self._items[idx]
            return True
        return False

    def __contains__(self, item) -> bool:
        return self._bisect(item)[1]

    def __iter__(self):
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def first(self):
        if not self._items:
            raise KeyError("the set is empty")
        return self._items[0]
