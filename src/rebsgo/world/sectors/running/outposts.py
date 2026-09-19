# github.com/Shran21

from __future__ import annotations

from dataclasses import dataclass

from contextlib import suppress

from rebsgo.geometry.maths.maths import Maths
from rebsgo.helpers.floats import f32
from rebsgo.vocabulary.pilot import Faction
from rebsgo.world.sectors.departures.notes import KilledNote
from rebsgo.vocabulary.world import DepartureCause, ObjectKind
from rebsgo.world.sectors.running.coming_and_going import DepartureWatcher
from rebsgo.gamedata.from_json.template_readers import readiness_terms


class OutpostPhase:
    _POINTS_PER_READINESS_PERCENT = readiness_terms().points_per_percent

    def __init__(self, faction, op_pont: int, tiltas_mp: float, can_outpost: bool, tick):
        self._faction = faction
        self._op_points = f32(float(op_pont))
        self._seconds_blocked = f32(tiltas_mp)
        self._die_time_stamp = 0
        self._can_outpost = can_outpost
        self._is_outpost_cached = False
        self._tick = tick

    @property
    def can_outpost(self) -> bool:
        return self._can_outpost

    def op_down(self, arg) -> None:
        if isinstance(arg, int):
            self._die_time_stamp = arg
            self._op_points = 0.0
        else:
            self.op_down(arg.time_stamp())

    def gain_points(self, novekedes: float) -> bool:
        if self.is_blocked():
            return True
        self._op_points = f32(self._op_points + f32(float(novekedes)))
        self._op_points = Maths.clamp_safe(self._op_points, 0.0, 3000.0)
        return False

    def increase_readiness_percent(self, percent: float) -> bool:
        return self.gain_points(f32(float(percent)) * self._POINTS_PER_READINESS_PERCENT)

    def lose_points(self, csokkenes: float) -> bool:
        if self.is_blocked():
            return True
        self._op_points = f32(self._op_points - f32(float(csokkenes)))
        self._op_points = max(self._op_points, 0.0)
        return False

    def is_blocked(self, most_ms=None) -> bool:
        if most_ms is None:
            return self.is_blocked(self._tick.time_stamp())
        delta = self._get_delta_block_time(most_ms)
        return delta < 0

    def _get_delta_block_time(self, most_ms: int) -> int:
        target_time_stamp = self._die_time_stamp + int(self._seconds_blocked) * 1000
        return most_ms - target_time_stamp

    def delta(self) -> float:
        if not self._can_outpost:
            return 0.0
        if self._die_time_stamp > 0:
            remaining_ms = ((self._die_time_stamp + int(self._seconds_blocked) * 1000)
                            - self._tick.time_stamp())
            if remaining_ms > 0:
                return f32(remaining_ms * -0.001)
        return 1.0 if self._op_points >= 900 else 0.0

    @property
    def is_outpost(self) -> bool:
        current_delta = self.delta()
        self._is_outpost_cached = current_delta == 1.0
        return self._is_outpost_cached

    @property
    def is_outpost_cached(self) -> bool:
        return self._is_outpost_cached

    @property
    def op_points(self) -> int:
        return int(round(self._op_points))


@dataclass(slots=True, eq=False)
class OutpostPhases:
    colonial_outpost_state: object
    cylon_outpost_state: object
    colonial_progress_template: object
    cylon_progress_template: object

    def template_from_faction(self, faction):
        if faction == Faction.Colonial:
            return self.colonial_progress_template
        if faction == Faction.Cylon:
            return self.cylon_progress_template
        raise ValueError(f'no outpost readiness template under faction {faction}')

    def inverted_template_for_faction(self, faction):
        if faction == Faction.Colonial:
            return self.cylon_progress_template
        if faction == Faction.Cylon:
            return self.colonial_progress_template
        raise ValueError(f'no outpost readiness template under faction {faction}')

    def state_for_faction(self, faction):
        if faction == Faction.Colonial:
            return self.colonial_outpost_state
        if faction == Faction.Cylon:
            return self.cylon_outpost_state
        raise ValueError('no outpost state exists for this faction')


class OutpostSiege(DepartureWatcher):
    def __init__(self, outpost_scoreboard, tick, damage_log, loot_ownership):
        self._tick = tick
        self._outpost_scoreboard = outpost_scoreboard
        self._damage_log = damage_log
        self._loot_ownership = loot_ownership

    def update_death(self, tavozas_leiras) -> None:
        space_object_to_remove = tavozas_leiras.departed_object
        entity_type = space_object_to_remove.space_entity_type

        if entity_type == ObjectKind.Pilot:
            if isinstance(tavozas_leiras, KilledNote):
                killer_obj = tavozas_leiras.killer_of()
                if killer_obj is not None and killer_obj.is_player():
                    pts_template = self._outpost_scoreboard.inverted_template_for_faction(space_object_to_remove.faction)
                    allapot = self._outpost_scoreboard.state_for_faction(killer_obj.faction)
                    allapot.gain_points(pts_template.pts_player_killed)
        elif entity_type == ObjectKind.Outpost:
            current_op_state = (self._outpost_scoreboard.colonial_outpost_state
                                if space_object_to_remove.faction == Faction.Colonial
                                else self._outpost_scoreboard.cylon_outpost_state)
            current_op_state.op_down(self._tick)
        elif entity_type == ObjectKind.BotFighter or entity_type == ObjectKind.WeaponPlatform:
            dmg_history = self._damage_log.damage_history(space_object_to_remove)
            if dmg_history is None:
                return
            kill_shot_dealer = dmg_history.kill_shot_dealer()
            if kill_shot_dealer is None:
                return

            if not kill_shot_dealer.dealer.is_player():
                return

            with suppress(ValueError):
                pts_template = self._outpost_scoreboard.inverted_template_for_faction(kill_shot_dealer.dealer.faction)
                op_state = self._outpost_scoreboard.state_for_faction(kill_shot_dealer.dealer.faction)
                op_state.gain_points(pts_template.pts_npc_killed)
        elif entity_type == ObjectKind.Asteroid:
            carries_loot = self._loot_ownership.carries_loot(space_object_to_remove)
            if not carries_loot:
                return

            kill_shot_damage = self._damage_log.kill_shot_dealer_of_object(space_object_to_remove)
            if kill_shot_damage is not None:
                dealer = kill_shot_damage.dealer
                if not dealer.is_player():
                    return

                pts_template = self._outpost_scoreboard.template_from_faction(dealer.faction)
                op_state = self._outpost_scoreboard.state_for_faction(dealer.faction)
                op_state.gain_points(pts_template.pts_asteroid_killed_with_ressources)

    def on_update(self, arg) -> None:
        removing_cause = arg.removal_cause_of()
        if removing_cause is None:
            raise TypeError('an object left without a cause')
        if removing_cause == DepartureCause.Death:
            self.update_death(arg)
