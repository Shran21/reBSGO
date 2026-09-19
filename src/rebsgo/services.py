# github.com/Shran21

from __future__ import annotations

from typing import Callable, TypeVar

T = TypeVar("T")


class _ServiceRegistry:
    def __init__(self):
        self._instances: dict[type, object] = {}
        self._factories: dict[type, Callable[[], object]] = {}

    def register_instance(self, cls: type, instance: object) -> None:
        self._instances[cls] = instance

    def register_factory(self, cls: type, factory: Callable[[], object]) -> None:
        self._factories[cls] = factory

    def get(self, cls: type[T]) -> T:
        instance = self._instances.get(cls)
        if instance is not None:
            return instance  # type: ignore[return-value]
        if (factory := self._factories.get(cls)) is not None:
            instance = factory()
            self._instances[cls] = instance
            return instance  # type: ignore[return-value]
        raise KeyError(f"no service registered under {cls!r}")

    def clear(self) -> None:
        self._instances.clear()
        self._factories.clear()


Services = _ServiceRegistry()
