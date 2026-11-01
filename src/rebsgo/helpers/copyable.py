# github.com/Shran21

from __future__ import annotations

from typing import Generic, TypeVar

T = TypeVar("T")


# Not an ABC: isinstance() against an ABC goes through its cache, which takes a
# lock without the GIL - and Vector3 and its kin are checked everywhere, from
# every thread.
class Copyable(Generic[T]):
    def copy(self) -> T:
        raise NotImplementedError(f"{type(self).__name__} does not say how it copies")
