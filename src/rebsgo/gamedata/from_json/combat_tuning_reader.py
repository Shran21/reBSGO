# github.com/Shran21

from __future__ import annotations

import logging

from rebsgo.gamedata.from_json.game_data_loader import GameDataLoader
from rebsgo.gamedata.reading import ObjectStat, ShipSlotType
from rebsgo import paths

log = logging.getLogger(__name__)

ALAP_BESOROLAS = (
    (ObjectStat.AoeOuterRadius, ((1000, "line"), (750, "escort"), (500, "strike"))),
    (ObjectStat.MaxRange, ((2000, "line"), (1400, "escort"))),
)
ALAP_INDITO = "strike"
ALAP_AOE = {"line": (180.0, 800.0), "escort": (145.0, 620.0), "strike": (110.0, 435.0)}
ALAP_ELSZIVAS = 0.05


class NuclearTuning:
    def __init__(self, besorolas, alap_indito: str, aoe: dict, elszivas: float):
        self._besorolas = tuple(besorolas)
        self._alap_indito = alap_indito
        self._aoe = dict(aoe)
        self._elszivas = elszivas

    def launcher_of(self, kepesseg_kartya) -> str:
        mutatok = kepesseg_kartya.item_buff_add
        for stat, kuszobok in self._besorolas:
            ertek = mutatok.stat_or_default(stat)
            for kuszob, indito in kuszobok:
                if ertek >= kuszob:
                    return indito
        return self._alap_indito

    def aoe_radii(self, launcher: str) -> tuple[float, float]:
        return self._aoe.get(launcher, self._aoe[self._alap_indito])

    def drain_from_damage(self) -> float:
        return self._elszivas

    @staticmethod
    def alapertelmezett() -> "NuclearTuning":
        return NuclearTuning(ALAP_BESOROLAS, ALAP_INDITO, ALAP_AOE, ALAP_ELSZIVAS)


class FallbackSystems:
    LEGKISEBB_SZINT = 1
    LEGNAGYOBB_SZINT = 3

    def __init__(self, tabla: dict, raketak: dict | None = None, jelzofenyek: dict | None = None):
        self._tabla = tabla
        self._raketak = raketak or {}
        self._jelzofenyek = jelzofenyek or {}

    def guid_for(self, slot_type, ship_tier: int) -> int:
        if slot_type is None:
            return 0
        sorok = self._tabla.get(getattr(slot_type, "name", None))
        if sorok is None:
            return 0
        szint = max(self.LEGKISEBB_SZINT, min(self.LEGNAGYOBB_SZINT, ship_tier))
        return sorok.get(szint, sorok.get("default", 0))

    def missile_guid_for(self, ship_tier: int) -> int:
        szint = max(self.LEGKISEBB_SZINT, min(self.LEGNAGYOBB_SZINT, ship_tier))
        return self._raketak.get(szint, self._raketak.get(self.LEGKISEBB_SZINT, 0))

    def jump_beacon_guid(self, faction) -> int:
        return self._jelzofenyek.get(getattr(faction, "name", None), 0)

    @staticmethod
    def ures() -> "FallbackSystems":
        return FallbackSystems({})


class CombatTuningReader(GameDataLoader):
    def __init__(self, mappa: str):
        super().__init__(paths.JATEKADAT / "templates" / mappa)

    def _fajl(self, nev: str):
        for utvonal in self.file_paths():
            if utvonal.name == nev:
                if (obj := self.read_json(utvonal)) is not None:
                    return obj
        return None

    def fetch_nuclear_tuning(self) -> NuclearTuning:
        obj = self._fajl("nuclear_launchers.json")
        if obj is None:
            log.warning('nuclear_launchers.json absent - warheads run on built-in tuning')
            return NuclearTuning.alapertelmezett()

        besorolas = []
        for sav in obj.get("classifyBy", []):
            stat = getattr(ObjectStat, sav["stat"], None)
            if stat is None:
                log.warning("nuclear_launchers.json: ismeretlen stat: %s", sav["stat"])
                continue
            besorolas.append((stat, tuple(
                (float(k["atLeast"]), k["launcher"]) for k in sav.get("thresholds", []))))

        aoe = {nev: (float(r["inner"]), float(r["outer"]))
               for nev, r in obj.get("aoeByLauncher", {}).items()}
        return NuclearTuning(
            besorolas or ALAP_BESOROLAS,
            obj.get("defaultLauncher", ALAP_INDITO),
            aoe or ALAP_AOE,
            float(obj.get("drainFromDamage", ALAP_ELSZIVAS)))

    def fetch_fallback_systems(self) -> FallbackSystems:
        obj = self._fajl("fallback_systems.json")
        if obj is None:
            log.warning('fallback_systems.json absent - NPCs will fly with empty slots')
            return FallbackSystems.ures()

        tabla = {}
        for rekesz, sorok in obj.get("bySlotType", {}).items():
            if getattr(ShipSlotType, rekesz, None) is None:
                log.warning("fallback_systems.json: ismeretlen rekeszfajta: %s", rekesz)
                continue
            tabla[rekesz] = {("default" if k == "default" else int(k)): int(g)
                             for k, g in sorok.items()}

        def szamozott(nev):
            return {int(k): int(g) for k, g in (obj.get(nev) or {}).items() if k.isdigit()}

        jelzofenyek = {k: int(g) for k, g in (obj.get("jumpBeacons") or {}).items()
                       if k != "comment"}
        return FallbackSystems(tabla, szamozott("npcMissileSystems"), jelzofenyek)


_atom: NuclearTuning | None = None
_tartalek: FallbackSystems | None = None


def nuclear_tuning() -> NuclearTuning:
    global _atom
    if _atom is None:
        _atom = CombatTuningReader("Weapons").fetch_nuclear_tuning()
    return _atom


def fallback_systems() -> FallbackSystems:
    global _tartalek
    if _tartalek is None:
        _tartalek = CombatTuningReader("Loadout").fetch_fallback_systems()
    return _tartalek
