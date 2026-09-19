# github.com/Shran21

from __future__ import annotations


class ContactPair:
    def __init__(self, first, second):
        self._first = first
        self._second = second

    def first(self):
        return self._first

    def second(self):
        return self._second

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not isinstance(other, ContactPair):
            return False
        return self._first == other._first and self._second == other._second

    def __hash__(self) -> int:
        return hash((self._first, self._second))

    def __repr__(self) -> str:
        return f'<{self._first} touching {self._second}>'
