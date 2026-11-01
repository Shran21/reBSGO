# github.com/Shran21
from __future__ import annotations

import contextvars
import struct

# Without the GIL a struct.Struct takes a lock on every pack and unpack - so do
# the ones struct.pack() and struct.unpack() keep in their cache. Threads that
# share one queue up on it, and on a busy machine the thread holding it can be
# put aside by the system for many milliseconds, holding up all the others.
# So a thread that does a lot of it - a sector thread, a sector's helper - takes
# converters of its own with own_converters(); the rest share one set, as before.
# (A new thread starts with a copy of its starter's context, so a thread wanting
# its own must ask for them itself.)


class Converters:
    __slots__ = ("f32", "f32x2", "f32x3", "f32x4", "f64", "u16", "u32", "u64", "i64", "_others")

    def __init__(self):
        self.f32 = struct.Struct("<f")
        self.f32x2 = struct.Struct("<ff")
        self.f32x3 = struct.Struct("<fff")
        self.f32x4 = struct.Struct("<ffff")
        self.f64 = struct.Struct("<d")
        self.u16 = struct.Struct("<H")
        self.u32 = struct.Struct("<I")
        self.u64 = struct.Struct("<Q")
        self.i64 = struct.Struct("<q")
        self._others = {}

    def struct_for(self, fmt: str) -> struct.Struct:
        found = self._others.get(fmt)
        if found is None:
            found = self._others[fmt] = struct.Struct(fmt)
        return found


_SHARED = Converters()
CONVERTERS = contextvars.ContextVar("rebsgo_converters", default=_SHARED)
# the float32 roundings are the hottest of them all: their (pack, unpack) pairs on
# their own, bound already
F32 = contextvars.ContextVar("rebsgo_f32", default=(_SHARED.f32.pack, _SHARED.f32.unpack))
F32X3 = contextvars.ContextVar("rebsgo_f32x3", default=(_SHARED.f32x3.pack, _SHARED.f32x3.unpack))
F32X4 = contextvars.ContextVar("rebsgo_f32x4", default=(_SHARED.f32x4.pack, _SHARED.f32x4.unpack))


def own_converters() -> None:
    mine = Converters()
    CONVERTERS.set(mine)
    F32.set((mine.f32.pack, mine.f32.unpack))
    F32X3.set((mine.f32x3.pack, mine.f32x3.unpack))
    F32X4.set((mine.f32x4.pack, mine.f32x4.unpack))


def struct_for(fmt: str) -> struct.Struct:
    return CONVERTERS.get().struct_for(fmt)
