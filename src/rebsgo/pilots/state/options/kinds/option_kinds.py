# github.com/Shran21

from __future__ import annotations

from rebsgo.wire.bytes.outgoing import Outgoing
from rebsgo.pilots.state.options.option_kind import OptionKind
from rebsgo.geometry.primitives.vector2 import Vector2


class OptionValue(Outgoing):
    def __init__(self, value, type):
        self.value = value
        self._type = type

    @property
    def type(self):
        return self._type


class OptionByte(OptionValue):
    def __init__(self, value: int):
        super().__init__(value, OptionKind.Byte)

    def to_wire(self, bw) -> None:
        bw.write_byte(self.value)


class OptionFlag(OptionValue):
    def __init__(self, value: bool):
        super().__init__(value, OptionKind.Boolean)

    def to_wire(self, bw) -> None:
        bw.write_boolean(self.value)


class OptionNumber(OptionValue):
    def __init__(self, value: int):
        super().__init__(value, OptionKind.Integer)

    def to_wire(self, bw) -> None:
        bw.write_int32(self.value)


class OptionDecimal(OptionValue):
    def __init__(self, value: float):
        super().__init__(value, OptionKind.Float)

    def to_wire(self, bw) -> None:
        bw.write_single(self.value)


class OptionPair(OptionValue):
    def __init__(self, pair: Vector2):
        super().__init__(pair, OptionKind.Float2)

    def to_wire(self, bw) -> None:
        bw.write_vector2(self.value)


class OptionHelpScreen(OptionValue):
    def __init__(self, value):
        super().__init__(value, OptionKind.HelpScreenKind)

    def to_wire(self, bw) -> None:
        bw.write_length(len(self.value))
        for help_screen_type in self.value:
            bw.write_uint16(help_screen_type.int_value)
