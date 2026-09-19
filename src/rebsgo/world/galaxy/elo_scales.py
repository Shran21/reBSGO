# github.com/Shran21
from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from rebsgo.pilots.state.boosts.boost import Boost
from rebsgo.protocol.pilot.pilot_replies import PilotReplies
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.vocabulary.pilot import Faction, BoostSource, BoostKind
from rebsgo.geometry.maths.maths import Maths
from rebsgo.helpers.dice import Dice
from rebsgo.helpers.floats import f32

log = logging.getLogger(__name__)


class EloScales:
    def __init__(self, pilot_roster, boost_seconds: float):
        self._pilot_roster = pilot_roster
        self._writer = PilotReplies()
        self._colonial_counter = 0
        self._cylon_counter = 0
        self._boost_seconds = boost_seconds

        self._last_colonial_factors = []
        self._last_cylon_factors = []

    def set_count_faction(self, faction, count: int) -> None:
        if count < 0:
            raise ValueError('count below zero makes no sense')

        if faction == Faction.Colonial:
            self._colonial_counter = count
        elif faction == Faction.Cylon:
            self._cylon_counter = count
        else:
            raise ValueError(f'faction is neither of the playable two {faction}')

    def faction_bonus(self, melyik_frakcionak) -> float:
        elso = self._colonial_counter if melyik_frakcionak == Faction.Colonial else self._cylon_counter
        second = self._colonial_counter if melyik_frakcionak == Faction.Cylon else self._cylon_counter
        elo = self._elo_calc(elso, second)

        clamped_value = Maths.clamp(f32(f32(0.5 - elo) * 2.0), 0, 1)

        bd = float(Decimal(clamped_value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        return f32(bd)

    @property
    def boost_seconds(self) -> float:
        return self._boost_seconds

    def _elo_calc(self, egyik_pontszam: int, masik_pontszam: int) -> float:
        return f32(1 / (1 + math.pow(10, (masik_pontszam - egyik_pontszam) / 100.0)))

    def run(self) -> None:
        colonials = self._pilot_roster.user_list(
            lambda user: user.pilot_of().faction == Faction.Colonial and user.is_connected())
        cylons = self._pilot_roster.user_list(
            lambda user: user.pilot_of().faction == Faction.Cylon and user.is_connected())
        self.set_count_faction(Faction.Colonial, len(colonials))
        self.set_count_faction(Faction.Cylon, len(cylons))

        colonial_bonus = self.faction_bonus(Faction.Colonial)
        cylon_bonus = self.faction_bonus(Faction.Cylon)

        self._remove_old_factors()

        rnd = Dice()
        rnd_boni = rnd.between_fine(0.1, 2)
        log.info("RndBoni %s", rnd_boni)
        self._setup_bonus_for_faction(Faction.Colonial, colonial_bonus)
        self._setup_bonus_for_faction(Faction.Cylon, f32(rnd_boni))

        self._add_new_factors(colonials, self._last_colonial_factors)
        self._add_new_factors(cylons, self._last_cylon_factors)

        log.info("FactionScales updated for %s colonials, %s and %s cylons, %s",
                 len(colonials), colonial_bonus, len(cylons), cylon_bonus)
        self._remove_old_factors()

    def _remove_old_factors(self) -> None:
        now = datetime.now(timezone.utc)
        for user in self._pilot_roster.values():
            factors = user.pilot_of().factors
            of_source = factors.items_of_source(BoostSource.Faction)
            for szorzo in of_source:
                if szorzo.end_time < now:
                    factors.remove_item(szorzo.server_id)
            ids_removed = {f.server_id for f in of_source}
            user.send(self._writer.remove_factor_ids(ids_removed))

    def _setup_bonus_for_faction(self, faction, bonus: float) -> None:
        lst_to_use = self._last_colonial_factors if faction == Faction.Colonial else self._last_cylon_factors
        lst_to_use.clear()

        if bonus <= 0:
            return

        now = datetime.now(timezone.utc)
        zsakmany = Boost.lasting(BoostKind.Loot, BoostSource.Faction, bonus, now,
                                 self._boost_seconds)
        asteroid_yield = Boost.lasting(BoostKind.AsteroidYield, BoostSource.Faction, bonus, now,
                                       self._boost_seconds)

        lst_to_use.append(zsakmany)
        lst_to_use.append(asteroid_yield)

    def _add_new_factors(self, pilotak, hozzaadando_boostok) -> None:
        if len(hozzaadando_boostok) == 0:
            return

        for user in pilotak:
            factors = user.pilot_of().factors
            for szorzo in hozzaadando_boostok:
                factors.take_boost(szorzo)

            player_protocol = user.protocol_of(ProtocolID.Pilot)
            user.send(player_protocol.replies.factors(factors))
