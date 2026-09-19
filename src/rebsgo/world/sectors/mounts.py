# github.com/Shran21

from __future__ import annotations

from rebsgo.vocabulary.pilot import Faction
from rebsgo.vocabulary.world import SlotCapKind
from rebsgo.wire.bytes.outgoing import Outgoing
from rebsgo.helpers.inheriting import csak_orokosen_at


class SectorSeats:
    def __init__(self, max_: int, current: int):
        csak_orokosen_at(self, SectorSeats)
        self._max = max_
        self._current = current

    def max(self) -> int:
        return self._max

    def advance_clock(self, current: int) -> None:
        self._current += current

    @property
    def current(self) -> int:
        return self._current


class FactionSeats(SectorSeats):
    def __init__(self, max_: int, current: int, faction):
        super().__init__(max_, current)
        self._faction = faction

    @property
    def faction(self):
        return self._faction


class SeatCount(Outgoing):
    def __init__(self):
        colonial_sector_slots = FactionSeats(100, 0, Faction.Colonial)
        cylon_sector_slots = FactionSeats(100, 0, Faction.Cylon)
        ship_sector_slots_map = {}
        self._colonial_sector_slots = colonial_sector_slots
        self._cylon_sector_slots = cylon_sector_slots
        self._ship_sector_slots_map = ship_sector_slots_map

    def to_wire(self, bw) -> None:
        meret = len(self._ship_sector_slots_map) + 3
        bw.write_length(meret)

        for ship_sector_slots in self._ship_sector_slots_map.values():
            bw.write_byte(1)
            bw.write_guid(ship_sector_slots.guid)
            bw.write_uint32(ship_sector_slots.current)
            bw.write_uint32(ship_sector_slots.max())

        bw.write_byte(0)
        bw.write_byte(SlotCapKind.Colonial.value)
        bw.write_uint32(self._colonial_sector_slots.current)
        bw.write_uint32(self._colonial_sector_slots.max())

        bw.write_byte(0)
        bw.write_byte(SlotCapKind.Cylon.value)
        bw.write_uint32(self._cylon_sector_slots.current)
        bw.write_uint32(self._cylon_sector_slots.max())

        bw.write_byte(0)
        bw.write_byte(SlotCapKind.Total.value)
        bw.write_uint32(self._colonial_sector_slots.current + self._cylon_sector_slots.current)
        bw.write_uint32(self._colonial_sector_slots.max() + self._cylon_sector_slots.max())
