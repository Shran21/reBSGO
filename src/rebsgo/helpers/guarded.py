# github.com/Shran21

from __future__ import annotations

import threading


class GuardedCount:
    def __init__(self, initial: int = 0):
        self._value = initial
        self._lock = threading.Lock()

    def get(self) -> int:
        with self._lock:
            return self._value

    def set(self, new_value: int) -> None:
        with self._lock:
            self._value = new_value

    def add(self, delta: int) -> int:
        with self._lock:
            self._value += delta
            return self._value


class GuardedFlag:
    def __init__(self, initial: bool = False):
        self._value = bool(initial)
        self._lock = threading.Lock()

    def get(self) -> bool:
        with self._lock:
            return self._value

    def set(self, new_value: bool) -> None:
        with self._lock:
            self._value = bool(new_value)

    def set_if(self, expect: bool, update: bool) -> bool:
        with self._lock:
            if self._value == expect:
                self._value = bool(update)
                return True
            return False


class GuardedCell:

    def __init__(self, initial=None):
        self._value = initial
        self._lock = threading.Lock()

    def get(self):
        with self._lock:
            return self._value

    def set(self, new_value) -> None:
        with self._lock:
            self._value = new_value

    def set_if(self, expect, update) -> bool:
        with self._lock:
            if self._value is expect:
                self._value = update
                return True
            return False
