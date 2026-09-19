# github.com/Shran21
from __future__ import annotations

import logging

from rebsgo.config.config import Config
from rebsgo.world.sectors.harm.damage_line import DamageLine
from rebsgo.world.sectors.spatial.radius_candidates import (
    build_complete_spatial_index,
    ordered_radius_candidates,
)
from rebsgo.vocabulary.world import ObjectKind
from rebsgo.geometry.maths.maths import Maths
from rebsgo.world.combat_rules import splash_terms
from rebsgo.native.hotpath import filter_range_distance_sq, log_native_event
from rebsgo.gamedata.reading import ObjectStat
from rebsgo.helpers.dice import Dice
from rebsgo.helpers.floats import f32, fdiv

log = logging.getLogger(__name__)
_CONFIG = Config.instance()
_DAMAGE_AOE_SPATIAL_INDEX_ENABLED = _CONFIG.bool("rebsgo.sector.spatial-index.damage-aoe-enabled", True)
_DAMAGE_AOE_SPATIAL_INDEX_CELL_SIZE = _CONFIG.float("rebsgo.sector.spatial-index.damage-aoe-cell-size", 5000.0)
_DAMAGE_AOE_SPATIAL_INDEX_MIN_OBJECTS = _CONFIG.int("rebsgo.sector.spatial-index.damage-aoe-min-objects", 32)
_DAMAGE_AOE_SPATIAL_INDEX_MAX_CELLS_PER_OBJECT = _CONFIG.int(
    "rebsgo.sector.spatial-index.damage-aoe-max-cells-per-object", 512)


class DamageRoll:
    def __init__(self, engagement, tick):
        self._engagement = engagement
        self._tick = tick
        self._dice = Dice()

    def damage_of_mining(self, from_, ellenseges_hajo, ability) -> DamageLine:
        item_buff_add_stats = ability.item_buff_add

        armor_piercing = item_buff_add_stats.stat_or_default(ObjectStat.ArmorPiercing)
        critical_attack = item_buff_add_stats.stat_or_default(ObjectStat.CriticalOffense)
        damage_mining = item_buff_add_stats.stat_or_default(ObjectStat.DamageMining) \
            if ellenseges_hajo.space_entity_type.of_kind(ObjectKind.Asteroid, ObjectKind.Comet) else 1.0
        dmg_low = f32(item_buff_add_stats.stat_or_default(ObjectStat.DamageLow) * damage_mining)
        dmg_high = f32(item_buff_add_stats.stat_or_default(ObjectStat.DamageHigh) * damage_mining)

        return self._calculate_damage(from_, ellenseges_hajo, armor_piercing, critical_attack, dmg_low, dmg_high)

    def damage_of_missile(self, missile, utkozo_hajo) -> DamageLine:
        missile_stats = missile.space_subscribe_info()
        armor_piercing = missile_stats.stat_or_default(ObjectStat.ArmorPiercing)
        critical_attack = missile_stats.stat_or_default(ObjectStat.CriticalOffense)
        dmg_low = missile_stats.stat_or_default(ObjectStat.DamageLow)
        dmg_high = missile_stats.stat_or_default(ObjectStat.DamageHigh)
        drain_low = missile_stats.stat_or_default(ObjectStat.DrainLow)
        drain_high = missile_stats.stat_or_default(ObjectStat.DrainHigh)

        return self._calculate_damage(missile.owner_object, utkozo_hajo, armor_piercing,
                                      critical_attack, dmg_low, dmg_high, drain_low, drain_high)

    SECONDARY_DAMAGE_CAP, SPLASH_OUTER_FLOOR = splash_terms()

    @staticmethod
    def splash_damage_mult(distance: float, aoe_inner_radius: float, aoe_outer_radius: float,
                           dropoff_index: float) -> float:
        if distance > aoe_outer_radius:
            return 0.0
        if aoe_outer_radius <= aoe_inner_radius:
            frac = 1.0
        else:
            frac = Maths.clamp01(fdiv(aoe_outer_radius - distance, aoe_outer_radius - aoe_inner_radius))
        dropoff = dropoff_index if dropoff_index and dropoff_index > 0 else 1.0
        cap = DamageRoll.SECONDARY_DAMAGE_CAP
        floor = DamageRoll.SPLASH_OUTER_FLOOR
        return floor + (cap - floor) * Maths.pow(frac, dropoff)

    def damage_of_torpedo(self, missile, objektumok, dropoff_index: float,
                          primary_target=None, exclude_targets=None):
        missile_stats = missile.space_subscribe_info()
        armor_piercing = missile_stats.stat_or_default(ObjectStat.ArmorPiercing)
        critical_attack = missile_stats.stat_or_default(ObjectStat.CriticalOffense)
        dmg_low = missile_stats.stat_or_default(ObjectStat.DamageLow)
        dmg_high = missile_stats.stat_or_default(ObjectStat.DamageHigh)

        drain_low = missile_stats.stat_or_default(ObjectStat.DrainLow)
        drain_high = missile_stats.stat_or_default(ObjectStat.DrainHigh)
        aoe_inner_radius = missile_stats.stat_or_default(ObjectStat.AoeInnerRadius)
        aoe_outer_radius = missile_stats.stat_or_default(ObjectStat.AoeOuterRadius)
        dropoff = dropoff_index if dropoff_index and dropoff_index > 0 else 1.0

        owner = missile.owner_object
        impact_pos = missile.mover_of().position_of()
        excluded = set() if exclude_targets is None else set(exclude_targets)
        eredmeny = []
        prepared_targets = []
        splash_records = []
        for ship in self._get_aoe_candidate_ships(objektumok, impact_pos, aoe_outer_radius, primary_target):
            if ship.is_removed() or ship in excluded:
                continue
            if not ship.faction.hostile_to(owner.faction):
                continue

            is_primary = primary_target is not None and ship == primary_target
            prepared_targets.append((ship, is_primary))
            if not is_primary:
                helyzet = ship.mover_of().position_of()
                splash_records.append((ship.id_in_space(), helyzet.x, helyzet.y, helyzet.z))

        splash_distance_sq_by_id = {}
        if splash_records:
            splash_distance_sq_by_id = dict(filter_range_distance_sq(
                splash_records,
                (impact_pos.x, impact_pos.y, impact_pos.z),
                0.0,
                aoe_outer_radius,
                True,
                True,
            ))
            log_native_event(
                log,
                "damage_torpedo_range_distance_used",
                "Damage torpedo range-distance candidates=%s matches=%s",
                len(splash_records),
                len(splash_distance_sq_by_id),
            )

        for ship, is_primary in prepared_targets:
            if is_primary:
                mult = 1.0
            else:
                distance_sq = splash_distance_sq_by_id.get(ship.id_in_space())
                if distance_sq is None:
                    continue
                tavolsag = Maths.sqrt(distance_sq)
                mult = DamageRoll.splash_damage_mult(
                    tavolsag, aoe_inner_radius, aoe_outer_radius, dropoff)
                if mult <= 0.0:
                    continue

            eredmeny.append(self._calculate_damage(
                owner, ship, armor_piercing, critical_attack,
                f32(dmg_low * mult), f32(dmg_high * mult), f32(drain_low * mult), f32(drain_high * mult)))
        return eredmeny

    def calculate_damage_from_mine(self, mine, objektumok):
        mine_stats = mine.space_subscribe_info()
        armor_piercing = mine_stats.stat_or_default(ObjectStat.ArmorPiercing)
        critical_attack = mine_stats.stat_or_default(ObjectStat.CriticalOffense)
        dmg_low = mine_stats.stat_or_default(ObjectStat.DamageLow)
        dmg_high = mine_stats.stat_or_default(ObjectStat.DamageHigh)
        drain_low = mine_stats.stat_or_default(ObjectStat.DrainLow)
        drain_high = mine_stats.stat_or_default(ObjectStat.DrainHigh)
        damage_radius = mine_stats.stat_or_default(ObjectStat.AoeOuterRadius)

        owner = mine.owner_object
        mine_position = mine.mover_of().position_of()
        eredmeny = []
        enemy_ships = []
        range_records = []
        for ship in self._get_aoe_candidate_ships(objektumok, mine_position, damage_radius):
            if ship.is_removed():
                continue
            if not ship.faction.hostile_to(mine.faction):
                continue
            helyzet = ship.mover_of().position_of()
            enemy_ships.append(ship)
            range_records.append((ship.id_in_space(), helyzet.x, helyzet.y, helyzet.z))

        in_range_ids = set()
        if range_records:
            in_range_ids = {
                object_id
                for object_id, _distance_sq in filter_range_distance_sq(
                    range_records,
                    (mine_position.x, mine_position.y, mine_position.z),
                    0.0,
                    damage_radius,
                    True,
                    False,
                )
            }
            log_native_event(
                log,
                "damage_mine_range_distance_used",
                "Damage mine range-distance candidates=%s matches=%s",
                len(range_records),
                len(in_range_ids),
            )

        for ship in enemy_ships:
            if ship.id_in_space() not in in_range_ids:
                continue
            eredmeny.append(self._calculate_damage(owner, ship, armor_piercing, critical_attack,
                                                 dmg_low, dmg_high, drain_low, drain_high))
        return eredmeny

    @staticmethod
    def _get_aoe_candidate_ships(objektumok, center, radius: float, always_include=None):
        ships = list(objektumok.ships_stream_of())
        if (not _DAMAGE_AOE_SPATIAL_INDEX_ENABLED
            or len(ships) < _DAMAGE_AOE_SPATIAL_INDEX_MIN_OBJECTS):
            return ships

        try:
            sorszam = build_complete_spatial_index(
                ships,
                _DAMAGE_AOE_SPATIAL_INDEX_CELL_SIZE,
                _DAMAGE_AOE_SPATIAL_INDEX_MAX_CELLS_PER_OBJECT,
                log,
                "Damage AoE",
            )
            if sorszam is None:
                return ships
            return ordered_radius_candidates(ships, sorszam, center, radius, always_include)
        except Exception:
            log.exception("Damage AoE spatial query failed; falling back to the plain sweep")
            return ships

    def damage_for(self, from_, to, ability) -> DamageLine:
        item_buff_add = ability.item_buff_add

        armor_piercing = item_buff_add.stat_or_default(ObjectStat.ArmorPiercing)
        critical_attack = item_buff_add.stat_or_default(ObjectStat.CriticalOffense)
        dmg_low = item_buff_add.stat_or_default(ObjectStat.DamageLow)
        dmg_high = item_buff_add.stat_or_default(ObjectStat.DamageHigh)
        drain_low = item_buff_add.stat_or_default(ObjectStat.DrainLow)
        drain_high = item_buff_add.stat_or_default(ObjectStat.DrainHigh)

        return self._calculate_damage(from_, to, armor_piercing, critical_attack, dmg_low, dmg_high,
                                      drain_low, drain_high)

    def _calculate_damage(self, sebzest_okozta, ellenseges_objektum, armor_piercing, kritikus_ero,
                          also_sebzes, felso_sebzes, drain_low: float = 0.0, drain_high: float = 0.0,
                          aoe_inner_radius: float = 0.0, aoe_outer_radius: float = 0.0,
                          aoe_dropoff_index: float = 0.0) -> DamageLine:
        enemy_ship_stats = ellenseges_objektum.space_subscribe_info()

        pancel = enemy_ship_stats.stat_or_default(ObjectStat.ArmorValue, 0.0)
        critical_def = enemy_ship_stats.stat_or_default(ObjectStat.CriticalDefense, 0.0)

        armor_multiplicator = self._engagement.armour_multiplier(pancel, armor_piercing)
        critical_chance = self._engagement.crit_chance(kritikus_ero, critical_def)
        dmg = self._engagement.damage_roll(self._dice, also_sebzes, felso_sebzes)

        is_crit = self._dice.passes(critical_chance)
        crit_mult = self._engagement.crit_multiplier(is_crit)

        drain = self._dice.between(drain_low, drain_high)
        if drain > 0.0:
            drain_resistance = enemy_ship_stats.stat_or_default(ObjectStat.DrainResistance)
            drain = Maths.max(drain - drain_resistance, 0.0)

        if aoe_inner_radius > 0.0 and aoe_outer_radius > 0:
            tavolsag = sebzest_okozta.mover_of().position_of().distance_(
                sebzest_okozta.mover_of().position_of())
            if tavolsag >= aoe_inner_radius and tavolsag <= aoe_outer_radius:
                mult = DamageRoll.cal_aoe_mult(aoe_inner_radius, aoe_outer_radius, tavolsag, aoe_dropoff_index)
                dmg = f32(dmg * mult)
                drain = f32(drain * mult)
                log.info('splash falloff: factor=%s at distance=%s', mult, tavolsag)

        if log.isEnabledFor(logging.DEBUG):
            log.debug(
                'hit #%s -> #%s: roll=%.1f crit=%s armor=%.1f piercing=%.1f'
                ' through=%.3f final=%.1f',
                sebzest_okozta.id_in_space(), ellenseges_objektum.id_in_space(),
                dmg, is_crit, pancel, armor_piercing, armor_multiplicator,
                dmg * crit_mult * armor_multiplicator)
        return DamageLine(sebzest_okozta, ellenseges_objektum, dmg * crit_mult * armor_multiplicator, drain,
                          is_crit, self._tick.time_stamp())

    @staticmethod
    def cal_aoe_mult(aoe_inner_radius: float, aoe_outer_radius: float, distance: float, aoe_dropoff_index: float) -> float:
        distance_ratio = Maths.clamp01(fdiv(distance - aoe_inner_radius, aoe_outer_radius))
        return Maths.pow(1 - distance_ratio, aoe_dropoff_index)

    def damage_of_collision(self, asteroid, other) -> DamageLine:
        current_hp = asteroid.space_subscribe_info().stat_or_default(
            ObjectStat.MaxHullPoints, asteroid.space_subscribe_info().hp)
        pancel = other.space_subscribe_info().stat_or_default(ObjectStat.ArmorValue)
        mult = self._engagement.armour_multiplier(pancel, 50)
        final_dmg = f32(0.5 * current_hp * mult)

        return DamageLine(asteroid, other, final_dmg, kritikus=False,
                          ekkor=self._tick.time_stamp())
