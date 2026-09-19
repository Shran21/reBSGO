# github.com/Shran21
from __future__ import annotations

from rebsgo.wire.bytes.outgoing import Outgoing


class Remark(Outgoing):
    def __init__(self, index: int, phrase_raw: str, symbol=None):
        self._index = index
        self._phrase_raw = phrase_raw
        self._symbol = "" if symbol is None else symbol

    def to_wire(self, bw) -> None:
        bw.write_byte(self._index)
        bw.write_string(self._phrase_raw)
        Remark._elhagyott_mezok(bw)
        bw.write_string(self._symbol)

    @staticmethod
    def _elhagyott_mezok(bw) -> None:
        bw.write_string("")
        bw.write_uint32(0)
        bw.write_byte(0)
