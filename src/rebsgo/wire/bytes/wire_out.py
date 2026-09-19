# github.com/Shran21

from __future__ import annotations

import datetime as _dt
import struct

from rebsgo.wire.bytes.growing_buffer import (
    GrowingBuffer,
)
from rebsgo.helpers.floats import f32


def _to_epoch_second_utc(dt: _dt.datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dt.timezone.utc)
    return int(dt.timestamp())


class WireOut(GrowingBuffer):
    def __init__(self):
        super().__init__()
        self.write_uint16(0)

    @classmethod
    def from_frozen_bytes(cls, data: bytes | bytearray | memoryview) -> "WireOut":
        rakomany = bytes(data)
        if len(rakomany) < 2:
            raise ValueError("frozen protocol packet must include a two-byte length prefix")
        iro = cls.__new__(cls)
        GrowingBuffer.__init__(iro, len(rakomany))
        iro.buffer = bytearray(rakomany)
        iro.count = len(rakomany)
        iro.length_written = True
        iro._frozen_bytes = rakomany
        return iro

    def write_byte(self, b: int) -> "WireOut":
        self.write_one(b & 0xFF)
        return self

    def write_single(self, f: float) -> "WireOut":
        self.write(struct.pack("<f", f))
        return self

    def write_double(self, d: float) -> None:
        self.write(struct.pack("<d", d))

    def write_int16(self, s: int) -> "WireOut":
        self.write(struct.pack("<H", s & 0xFFFF))
        return self

    def write_uint16(self, i: int) -> "WireOut":
        if i < 0 or i > 65_535:
            raise ValueError(f'number negative or oversized: {i}')
        return self.write_int16(i)

    def write_length(self, i: int) -> None:
        self.write_uint16(i)

    def write_msg_type(self, i: int) -> "WireOut":
        return self.write_uint16(i)

    def write_int32(self, i: int) -> "WireOut":
        self.write(struct.pack("<I", i & 0xFFFFFFFF))
        return self

    def write_guid(self, l: int) -> "WireOut":
        return self.write_uint32(l)

    def write_uint32(self, l: int) -> "WireOut":
        self.write_int32(l)
        return self

    def write_uint16_collection(self, nums) -> None:
        self.write_length(len(nums))
        for szam in nums:
            self.write_uint16(szam)

    def write_uint32_collection(self, ids) -> "WireOut":
        self.write_length(len(ids))
        for a_long in ids:
            self.write_uint32(a_long)
        return self

    def write_int32_collection(self, egeszek) -> None:
        self.write_length(len(egeszek))
        for integer in egeszek:
            self.write_int32(integer)

    def write_uint32_array(self, hosszak) -> None:
        self.write_length(len(hosszak))
        for l in hosszak:
            self.write_uint32(l)

    def write_int64(self, l: int) -> "WireOut":
        self.write(struct.pack("<Q", l & 0xFFFFFFFFFFFFFFFF))
        return self

    def write_uint64(self, l: int) -> None:
        self.write_int64(l)

    def write_boolean(self, b: bool) -> "WireOut":
        return self.write_byte(1 if b else 0)

    def write_string(self, s) -> "WireOut":
        if s is None:
            self.write_uint16(0)
            return self
        data = s.encode("utf-8")
        self.write_uint16(len(data))
        if len(data) > 0:
            self.write(data)
        return self

    def write_string_array(self, str_arr) -> None:
        if str_arr is None:
            raise TypeError('a string array is required')
        self.write_uint16(len(str_arr))
        for s in str_arr:
            self.write_string(s)

    def write_desc(self, desc) -> "WireOut":
        if desc is None:
            return self
        desc.to_wire(self)
        return self

    def write_desc_array(self, valasz_konyv) -> None:
        if valasz_konyv is None:
            self.write_length(0)
            return
        self.write_length(len(valasz_konyv))
        for protocol_write in valasz_konyv:
            self.write_desc(protocol_write)

    def write_desc_collection(self, valasz_konyv) -> "WireOut":
        if valasz_konyv is None:
            self.write_uint16(0)
            return self
        self.write_length(len(valasz_konyv))
        for t in valasz_konyv:
            self.write_desc(t)
        return self

    def write_color(self, color) -> None:
        r = int(f32(255.0 * color.r)) & 0xFF
        g = int(f32(255.0 * color.g)) & 0xFF
        b = int(f32(255.0 * color.b)) & 0xFF
        a = int(f32(255.0 * color.a)) & 0xFF
        self.write(bytes([r, g, b, a]))

    def write_vector3(self, position) -> None:
        self.write(struct.pack("<fff", position.x, position.y, position.z))

    def write_vector2(self, vector2) -> None:
        self.write(struct.pack("<ff", vector2.x, vector2.y))

    def write_euler3(self, euler3) -> None:
        self.write(struct.pack("<fff", euler3.pitch, euler3.yaw, euler3.roll))

    def write_quaternion(self, rotation) -> None:
        self.write(struct.pack("<ffff", rotation.x, rotation.y, rotation.z, rotation.w))

    def write_date_time(self, received: _dt.datetime) -> None:
        self.write_uint32(_to_epoch_second_utc(received))

    def write_moment(self, value) -> None:
        if isinstance(value, _dt.datetime):
            self.write_uint64(_to_epoch_second_utc(value))
        else:
            dt = _dt.datetime.fromtimestamp(value / 1000.0, tz=_dt.timezone.utc)
            self.write_uint64(_to_epoch_second_utc(dt))
