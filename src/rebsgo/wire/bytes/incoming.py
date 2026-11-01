# github.com/Shran21

from __future__ import annotations


# Not an ABC, for the same reason as Outgoing.
class Incoming:
    def read(self, br) -> None:
        raise NotImplementedError(f"{type(self).__name__} does not say how it comes off the wire")
