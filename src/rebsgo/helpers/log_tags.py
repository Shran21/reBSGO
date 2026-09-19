# github.com/Shran21

from __future__ import annotations

import threading


class _TagStore(threading.local):
    def __init__(self):
        self.data: dict[str, str] = {}


_store = _TagStore()


def tag(key: str, value: str) -> None:
    _store.data[key] = value


def get(key: str) -> str | None:
    return _store.data.get(key)


def remove(key: str) -> None:
    _store.data.pop(key, None)


def clear() -> None:
    _store.data.clear()


def copy_of_context_map() -> dict[str, str]:
    return dict(_store.data)
