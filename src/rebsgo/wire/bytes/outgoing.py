# github.com/Shran21

from __future__ import annotations


# Not an ABC: isinstance() against an ABC goes through its cache, which takes a
# lock without the GIL - and every object in a sector is an Outgoing, checked
# (isinstance(x, PlayerShip) and the like) from every thread.
class Outgoing:
    def to_wire(self, bw) -> None:
        raise NotImplementedError(f"{type(self).__name__} does not say how it goes on the wire")
