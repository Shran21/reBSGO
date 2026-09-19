# github.com/Shran21

from __future__ import annotations

from functools import lru_cache
from rebsgo.gamedata.from_json.game_data_loader import GameDataLoader
from rebsgo.geometry.maths.maths import Maths
from rebsgo.helpers.floats import f32
from rebsgo.vocabulary.pilot import Gear
from rebsgo import paths
import logging
import math

log = logging.getLogger(__name__)

SZAZALEK = 0.01


@lru_cache(maxsize=1)
def _beallitasok() -> dict:
    olvaso = GameDataLoader(paths.JATEKADAT / "templates" / "Combat")
    for utvonal in olvaso.file_paths():
        if utvonal.name == "engagement.json":
            if (betoltve := olvaso.read_json(utvonal)) is not None:
                return betoltve
            break
    log.warning("engagement.json is missing; falling back to the shipped figures")
    return {}


def splash_terms() -> tuple[float, float]:
    szort = _beallitasok().get("splash", {})
    return szort.get("secondaryCap", 0.45), szort.get("outerFloor", 0.045)


class Engagement:
    def __init__(self, beallitasok: dict | None = None):
        adat = beallitasok if beallitasok is not None else _beallitasok()
        talalat = adat.get("hitOdds", {})
        kritikus = adat.get("critical", {})
        fakla = adat.get("flare", {})
        szort = adat.get("splash", {})

        self._even_match = talalat.get("evenMatchPercent", 67.5)
        self._per_point = talalat.get("percentPerPointOfEdge", 0.15)
        self._ceiling = talalat.get("ceiling", 0.95)
        self._floor = talalat.get("floor", 0.05)
        self._beyond_reach = talalat.get("beyondReachFloor", 0.0001)
        self._crit_floor = kritikus.get("floorPercent", 5.0)
        self._crit_per_point = kritikus.get("percentPerPointOfEdge", 0.15)
        self._crit_damage = kritikus.get("damageMultiplier", 2.0)
        pancel = adat.get("armour", {})
        self._armour_counts = bool(pancel.get("counts", False))
        self._armour_point_worth = float(pancel.get("perPointWorth", 100.0))
        self._armour_stop_cap = float(pancel.get("mostItWillStop", 0.6))
        if self._armour_counts and self._armour_point_worth <= 0:
            raise ValueError('engagement.json turns armour on with a perPointWorth of nothing')
        if not 0.0 <= self._armour_stop_cap < 1.0:
            raise ValueError('engagement.json armour ceiling must sit inside [0, 1)')
        self._flare_point_blank = fakla.get("atPointBlank", 0.95)
        self._flare_edge = fakla.get("atFullReach", 0.1)
        self._flare_span = self._flare_point_blank - self._flare_edge
        self._jam_scale = adat.get("jamming", {}).get("percentScale", SZAZALEK)
        self.splash_cap = szort.get("secondaryCap", 0.45)
        self.splash_floor = szort.get("outerFloor", 0.045)


    def basic_chance_to_hit(self, avoidance: float, accuracy: float) -> float:
        elony = avoidance - accuracy
        return Maths.clamp_safe(
            f32((self._even_match - self._per_point * elony) * SZAZALEK),
            self._floor, self._ceiling)

    def chance_to_hit(self, avoidance: float, accuracy: float,
                      max_range: float, sweet_spot: float, distance: float) -> float:
        eselye = self.basic_chance_to_hit(avoidance, accuracy)
        if distance <= sweet_spot:
            return eselye
        meredekseg = f32((self._beyond_reach - eselye) / (max_range - sweet_spot))
        indulas = f32(eselye - meredekseg * sweet_spot)
        return f32(distance * meredekseg + indulas)

    def avoidance_at_speed(self, teljes_kiteres: float, gaz_allas: float,
                           csucssebesseg: float, gear,
                           kiteres_halvanyulasa: float) -> float:
        if gear is None:
            log.error('gear level absent - a state this code rules out')
        if gear == Gear.Boost or kiteres_halvanyulasa == 0 or csucssebesseg == 0:
            return teljes_kiteres

        tartott = Maths.min(gaz_allas, csucssebesseg)
        hanyad = f32(tartott / csucssebesseg)
        also_hatar = f32(1.0 - kiteres_halvanyulasa)
        return f32(teljes_kiteres * Maths.max(hanyad, also_hatar))


    def armour_multiplier(self, armor: float, armor_piercing: float) -> float:
        if not self._armour_counts:
            return 1
        halo = Maths.max(0.0, armor - armor_piercing)
        if halo <= 0:
            return 1
        megfogott = halo / (halo + self._armour_point_worth)
        megfogott = Maths.min(megfogott, self._armour_stop_cap)
        return f32(1.0 - megfogott)

    def crit_chance(self, kritikus_tamadas: float, kritikus_vedelem: float) -> float:
        elony = kritikus_tamadas - kritikus_vedelem
        return Maths.clamp01(
            f32((self._crit_floor + (self._crit_per_point * elony)) * SZAZALEK))

    def crit_multiplier(self, kritikus_e: bool) -> float:
        return self._crit_damage if kritikus_e else 1.0

    def damage_roll(self, dice, lower: float, upper: float) -> float:
        return dice.between(lower, upper)


    def jam_duration(self, alap_hossz: float, ado_ereje: float,
                     ellenseges_tuzfal: float) -> float:
        eroszak = f32(1.0 + (ado_ereje * self._jam_scale))
        vedelem = f32(1.0 / (1.0 + (ellenseges_tuzfal * self._jam_scale)))
        return f32(alap_hossz * eroszak * vedelem)

    def flare_odds(self, distance: float, flare_range: float) -> float:
        if flare_range == 0:
            raise ValueError('jammer reach reads zero')
        kozelseg = f32(flare_range - distance)
        if kozelseg < 0:
            raise ValueError('distance beyond jammer reach is impossible here')
        meredekseg = f32(self._flare_span / flare_range)
        return f32(meredekseg * kozelseg + f32(self._flare_edge))


class LevelCurve:
    LEGMAGASABB_SZINT = 255

    def __init__(self, beallitasok: dict | None = None):
        adat = beallitasok if beallitasok is not None else _beallitasok()
        self._lepcso = adat.get("levelling", {}).get("experienceStep", 1000)

    def level_based_on_exp(self, experience: int) -> int:
        nyers = math.sqrt(experience / self._lepcso) + 1
        return int(min(LevelCurve.LEGMAGASABB_SZINT, max(1, nyers)))

    def exp_from_level(self, level: int) -> int:
        if level < 1:
            raise ValueError('level starts at one')
        return int(math.pow(level - 1, 2)) * self._lepcso
