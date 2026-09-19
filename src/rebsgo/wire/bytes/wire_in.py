# github.com/Shran21

from __future__ import annotations

import struct

from rebsgo.wire.bytes.byte_cursor import ByteCursor
from rebsgo.geometry.primitives.euler3 import Euler3
from rebsgo.geometry.primitives.vector2 import Vector2
from rebsgo.geometry.primitives.vector3 import Vector3


class WireIn(ByteCursor):
    def __init__(self, puffer):
        super().__init__(puffer)

    @property
    def size(self) -> int:
        return self.count

    @staticmethod
    def buffer_size(data) -> int:
        szam = data[0] & 0xFF
        num2 = data[1] & 0xFF
        return (szam << 8) | num2

    @property
    def can_read(self) -> bool:
        return self.available > 0

    def read_single(self) -> float:
        return struct.unpack("<f", self.read_nbytes(4))[0]

    def read_double(self) -> float:
        return struct.unpack("<d", self.read_nbytes(8))[0]

    def read_byte(self) -> int:
        eredmeny = self.read()
        if eredmeny >= 128:
            return eredmeny - 256
        return eredmeny

    def read_uint32_array(self) -> list[int]:
        to_read = self.read_length()
        return [self.read_uint32() for _ in range(to_read)]

    def read_boolean(self) -> bool:
        return self.read_byte() != 0

    def read_int16(self) -> int:
        b = self.read_nbytes(2)
        ertek = (b[0] & 0xFF) + ((b[1] & 0xFF) << 8)
        if ertek >= 0x8000:
            ertek -= 0x10000
        return ertek

    def read_uint16(self) -> int:
        b = self.read_nbytes(2)
        return (b[0] & 0xFF) + ((b[1] & 0xFF) << 8)

    def read_length(self) -> int:
        return self.read_uint16()

    def read_int32(self) -> int:
        b = self.read_nbytes(4)
        ertek = (b[0] & 0xFF) + ((b[1] & 0xFF) << 8) + ((b[2] & 0xFF) << 16) + ((b[3] & 0xFF) << 24)
        if ertek >= 0x80000000:
            ertek -= 0x100000000
        return ertek

    def read_uint32(self) -> int:
        b = self.read_nbytes(4)
        return (b[0] & 0xFF) + ((b[1] & 0xFF) << 8) + ((b[2] & 0xFF) << 16) + ((b[3] & 0xFF) << 24)

    def read_guid(self) -> int:
        return self.read_uint32()

    def read_int64(self) -> int:
        return struct.unpack("<q", self.read_nbytes(8))[0]

    def read_uint64(self) -> str:
        return str(self.read_int64() & 0xFFFFFFFFFFFFFFFF)

    def read_string(self) -> str:
        num_to_read = self.read_length()
        if num_to_read > 0:
            return self.read_nbytes(num_to_read).decode("utf-8")
        return ""

    def read_desc(self, cls):
        eredmeny = cls()
        eredmeny.read(self)
        return eredmeny

    def read_euler3(self) -> Euler3:
        return Euler3(self.read_single(), self.read_single(), self.read_single())

    def read_vector3(self) -> Vector3:
        return Vector3(self.read_single(), self.read_single(), self.read_single())

    def read_vector2(self) -> Vector2:
        return Vector2(self.read_single(), self.read_single())
