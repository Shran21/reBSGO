# github.com/Shran21
from __future__ import annotations

import datetime
from decimal import ROUND_HALF_UP, Decimal

from rebsgo.wire.bytes.outgoing import Outgoing
from rebsgo.helpers.gathering import Ownable
from rebsgo.helpers.floats import f32

_TWO_PLACES = Decimal("0.01")


def _to_epoch_second_utc(dt: datetime.datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return int(dt.timestamp())


class Boost(Outgoing, Ownable):
    def __init__(self, server_id: int, factor_type, factor_source, value: float, end_time):
        v32 = f32(value)
        bd = Decimal(v32).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
        self._server_id = server_id
        self._factor_type = factor_type
        self._factor_source = factor_source
        self._value = f32(float(bd))
        self._end_time = end_time

    def copy(self) -> "Boost":
        return Boost(0, self._factor_type, self._factor_source, self._value, self._end_time)

    @staticmethod
    def lasting(factor_type, factor_source, value, now, seconds: float) -> "Boost":
        return Boost(0, factor_type, factor_source, value,
                     now + datetime.timedelta(seconds=seconds))

    @staticmethod
    def ending_at(factor_type, factor_source, value, end_time) -> "Boost":
        return Boost(0, factor_type, factor_source, value, end_time)

    @staticmethod
    def starting_at(factor_type, factor_source, value, start_time, hossz_ora) -> "Boost":
        return Boost(0, factor_type, factor_source, value, start_time + datetime.timedelta(hours=hossz_ora))

    @staticmethod
    def of_template(augment_factor_template, custom_duration_hours: int = -1):
        factors = []
        for factor_type_record in augment_factor_template.factor_type_records:
            tartam = (augment_factor_template.active_time_in_hours
                      if custom_duration_hours == -1 else custom_duration_hours)
            szorzo = Boost.starting_at(
                factor_type_record.type(), augment_factor_template.factor_source, factor_type_record.value(),
                datetime.datetime.now(datetime.timezone.utc), tartam)
            factors.append(szorzo)
        return factors

    def to_wire(self, bw) -> None:
        bw.write_uint16(self._server_id)
        bw.write_byte(self._factor_type.int_value)
        bw.write_byte(self._factor_source.int_value)
        bw.write_single(self._value)
        bw.write_uint32(_to_epoch_second_utc(self._end_time))

    @property
    def factor_type(self):
        return self._factor_type

    @property
    def factor_source(self):
        return self._factor_source

    @property
    def value(self) -> float:
        return self._value

    @property
    def server_id(self) -> int:
        return self._server_id

    @server_id.setter
    def server_id(self, server_id: int) -> None:
        self._server_id = server_id

    @property
    def end_time(self):
        return self._end_time

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if type(other) is not type(self):
            return NotImplemented
        return (self._server_id == other._server_id and self._value == other._value
                and self._factor_type == other._factor_type and self._factor_source == other._factor_source
                and self._end_time == other._end_time)

    def __hash__(self) -> int:
        return hash((self._server_id, self._factor_type, self._factor_source, self._value, self._end_time))

    def __str__(self) -> str:
        return ("<Boost " + f"factor_type={self._factor_type}, factor_source={self._factor_source},"
                f" value={self._value}, end_time={self._end_time}" + ">")
