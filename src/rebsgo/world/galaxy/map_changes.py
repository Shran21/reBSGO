# github.com/Shran21

from __future__ import annotations

from rebsgo.helpers.floats import f32
from rebsgo.protocol.starmap import GalaxyChange
from rebsgo.wire.bytes.outgoing import Outgoing

_IROK = {
    "frakcio": lambda bw, ertek: bw.write_byte(ertek.value),
    "bajt": lambda bw, ertek: bw.write_byte(ertek),
    "u32": lambda bw, ertek: bw.write_uint32(ertek),
    "i32": lambda bw, ertek: bw.write_int32(ertek),
    "tort": lambda bw, ertek: bw.write_single(ertek),
    "ido": lambda bw, ertek: bw.write_date_time(ertek),
    "leiro": lambda bw, ertek: bw.write_desc(ertek),
    "leirok": lambda bw, ertek: bw.write_desc_array(ertek),
}

_TORT_FAJTAK = frozenset({"tort"})


class GalaxyMapNotice(Outgoing):
    VALTOZAS = None
    ELRENDEZES: tuple = ()

    def __init__(self, faction, *ertekek):
        if self.VALTOZAS is None:
            raise TypeError("GalaxyMapNotice carries no news of its own")
        self.update_type = self.VALTOZAS
        self._faction = faction
        vart = tuple(self._sajat_mezok())
        if len(ertekek) != len(vart):
            raise TypeError(
                f"{type(self).__name__} wants {len(vart)} values, got {len(ertekek)}")
        for (nev, fajta), ertek in zip(vart, ertekek):
            setattr(self, "_" + nev, f32(ertek) if fajta in _TORT_FAJTAK else ertek)

    @classmethod
    def _sajat_mezok(cls):
        return ((nev, fajta) for nev, fajta in cls.ELRENDEZES if nev != "faction")

    def to_wire(self, bw) -> None:
        bw.write_byte(self.update_type.value)
        for nev, fajta in self.ELRENDEZES:
            _IROK[fajta](bw, getattr(self, "_" + nev))

    def __repr__(self) -> str:
        mezok = ", ".join(f"{nev}={getattr(self, '_' + nev)!r}"
                        for nev, _ in self.ELRENDEZES)
        return f"<{type(self).__name__} {mezok}>"


def _hirfajta(nev: str, valtozas, *elrendezes):
    fajta = type(nev, (GalaxyMapNotice,),
                 {"VALTOZAS": valtozas, "ELRENDEZES": tuple(elrendezes),
                  "__doc__": f"Galaxy-map news: {valtozas.name}."})
    fajta.__qualname__ = nev
    fajta.__module__ = __name__
    return fajta


ConquestPlaceNotice = _hirfajta(
    "ConquestPlaceNotice", GalaxyChange.ConquestLocation,
    ("faction", "frakcio"), ("sector_id", "i32"), ("conquest_expire_date", "ido"))

ConquestPriceNotice = _hirfajta(
    "ConquestPriceNotice", GalaxyChange.ConquestPrice,
    ("faction", "frakcio"), ("price", "u32"))

GalaxyRcpNotice = _hirfajta(
    "GalaxyRcpNotice", GalaxyChange.Rcp,
    ("faction", "frakcio"), ("rcp", "tort"))

SectorBeaconNotice = _hirfajta(
    "SectorBeaconNotice", GalaxyChange.SectorBeaconState,
    ("sector_id", "u32"), ("faction", "frakcio"), ("state", "tort"))

SectorAssignmentNotice = _hirfajta(
    "SectorAssignmentNotice", GalaxyChange.SectorDynamicMissions,
    ("sector_id", "u32"), ("faction", "frakcio"), ("dynamic_mission_count", "bajt"))

SectorMinerNotice = _hirfajta(
    "SectorMinerNotice", GalaxyChange.SectorMiningShips,
    ("sector_id", "u32"), ("faction", "frakcio"), ("mining_ship_count", "i32"))

SectorOutpostPointsNotice = _hirfajta(
    "SectorOutpostPointsNotice", GalaxyChange.SectorOutpostPoints,
    ("sector_id", "u32"), ("faction", "frakcio"), ("outpost_points", "i32"))

SectorOutpostPhaseNotice = _hirfajta(
    "SectorOutpostPhaseNotice", GalaxyChange.SectorOutpostState,
    ("sector_id", "u32"), ("faction", "frakcio"), ("delta", "tort"))

SectorSeatNotice = _hirfajta(
    "SectorSeatNotice", GalaxyChange.SectorPlayerSlots,
    ("sector_id", "u32"), ("faction", "frakcio"), ("sector_slot_data", "leiro"))

SectorPvpKillNotice = _hirfajta(
    "SectorPvpKillNotice", GalaxyChange.SectorPvPKills,
    ("sector_id", "u32"), ("faction", "frakcio"), ("kills_count", "i32"))

SectorTransponderNotice = _hirfajta(
    "SectorTransponderNotice", GalaxyChange.SectorJumpTargetTransponders,
    ("sector_id", "u32"), ("faction", "frakcio"),
    ("jump_target_transponder_descs", "leirok"))


class TransponderInfo(Outgoing):
    def __init__(self, player_id: int, party_id: int, space_id: int, expires: int):
        self._player_id = player_id
        self._party_id = party_id
        self._space_id = space_id
        self._expires = expires

    def to_wire(self, bw) -> None:
        for ertek in (self._player_id, self._party_id, self._space_id, self._expires):
            bw.write_uint32(ertek)


SectorTransponderNotice.TransponderInfo = TransponderInfo
