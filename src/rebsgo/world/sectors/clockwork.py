# github.com/Shran21

from __future__ import annotations

from dataclasses import dataclass

from contextlib import suppress

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from rebsgo import paths
from rebsgo.config.config import Config
from rebsgo.gamedata.cards.misc_cards import TallyCardKind
from rebsgo.gamedata.cards.world_cards import GalaxyMapCard
from rebsgo.gamedata.from_json.game_data_loader import GameDataLoader
from rebsgo.gamedata.from_json.template_readers import (
    mine_tuning, readiness_terms, sector_event_terms, sector_rules)
from rebsgo.gamedata.npc_minds import NpcBehaviourSpec, template_of_tier
from rebsgo.gamedata.object_templates import WeaponPlatformSpec
from rebsgo.gamedata.reading import AbilityActionKind, ObjectStat, ShipAbilityAffect, ShipSlotType, TargetBracketMode
from rebsgo.gamedata.ship_parts.parts import CountableItem
from rebsgo.geometry.collider_shapes import AABB, CapsuleCollider, BoxCollider, SphereCollider
from rebsgo.geometry.maths.maths import Maths
from rebsgo.geometry.primitives.euler3 import Euler3
from rebsgo.geometry.primitives.common import CommonDirections
from rebsgo.geometry.primitives.transform import Transform
from rebsgo.geometry.primitives.vector2 import Vector2
from rebsgo.geometry.primitives.vector3 import Vector3
from rebsgo.helpers.dice import Dice
from rebsgo.helpers.floats import f32
from rebsgo.helpers.rolling_latency_stats import (
    ENABLED as GUARDRAILS_ENABLED,
    SECTOR_COMBAT_OBJECT_WARN_COUNT,
    SECTOR_MOVEMENT_PACKET_WARN_COUNT,
    SECTOR_NPC_TARGET_CACHE_TICKS,
    SECTOR_NPC_TARGET_PHASE_COUNT,
    SECTOR_NPC_TARGET_SCAN_WARN_CHECKS,
    SECTOR_PROPERTY_BUFFER_WARN_COUNT,
    SECTOR_STATE_PACKET_WARN_COUNT,
    SECTOR_TIMER_WARN_INTERVAL_MS,
    SECTOR_TIMER_WARN_MS,
    elapsed_ms,
    now_ms,
    should_warn,
    should_warn_count,
    should_warn_interval,
)
from rebsgo.native.hotpath import filter_possible_enemy_ids, should_use_native_relation_prefilter
from rebsgo.protocol.game.game_replies import GameReplies
from rebsgo.protocol.notification import MinerAlarm
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.protocol_book_replies import replies_for, game_replies
from rebsgo.vocabulary.combat import ManeuverKind
from rebsgo.vocabulary.pilot import ServerRoles, Faction, Gear, ResourceKind, ShipTrait
from rebsgo.vocabulary.world import VisibilityCause, ArrivalCause, PlaceKind, DepartureCause, ObjectKind
from rebsgo.world.carriers.carrier_anchor import sync_all_carrier_anchor_followers
from rebsgo.world.movement.maneuvers import DirectionalManeuver, NoRollManeuver, RestManeuver
from rebsgo.world.objects.ships import PlayerShip
from rebsgo.world.sectors.npc_minds import NpcGoalKind, PatrolGoal
from rebsgo.world.sectors.powers.power_bits import CastOrder
from rebsgo.world.sectors.powers.stealth import is_cloaked_outside_visual_detection, is_cloaked_player
from rebsgo.world.sectors.running.coming_and_going import DepartureWatcher
from rebsgo.world.sectors.sector_gating import (
    TIMER_MODE_FULL,
    TIMER_MODE_IDLE,
    TIMER_MODE_MAINTENANCE,
)
from rebsgo.world.sectors.sector_parts import SectorStep
from rebsgo.world.sectors.sides import Stance, relation
from rebsgo.world.sectors.spatial.radius_candidates import build_complete_spatial_index, ordered_radius_candidates, nearest_radius_candidate
from rebsgo.world.sectors.spatial.uniform_grid import UniformGridSpatialIndex
from rebsgo.world.sectors.heartbeat import Tick
import logging
import math
import random
import threading
import time
from rebsgo.gamedata.from_json.template_readers import world_timers
from rebsgo import journal


_CONFIG = Config.instance()
_MINE_TRIGGER_SPATIAL_INDEX_ENABLED = _CONFIG.bool("rebsgo.sector.spatial-index.mine-trigger-enabled", True)
_MINE_TRIGGER_SPATIAL_INDEX_CELL_SIZE = _CONFIG.float("rebsgo.sector.spatial-index.mine-trigger-cell-size", 5000.0)
_MINE_TRIGGER_SPATIAL_INDEX_MIN_OBJECTS = _CONFIG.int("rebsgo.sector.spatial-index.mine-trigger-min-objects", 32)
_EMPTY_GLOBAL_LOCK = threading.Lock()
_NPC_TARGET_SPATIAL_INDEX_ENABLED = _CONFIG.bool("rebsgo.sector.spatial-index.npc-targeting-enabled", True)
_NPC_TARGET_SPATIAL_INDEX_CELL_SIZE = _CONFIG.float("rebsgo.sector.spatial-index.npc-targeting-cell-size", 5000.0)
_NPC_TARGET_SPATIAL_INDEX_MIN_OBJECTS = _CONFIG.int("rebsgo.sector.spatial-index.npc-targeting-min-objects", 32)


class TickClock(ABC):
    __slots__ = ('sector_objects', 'stopped')

    def __init__(self, sector_objects):
        self.sector_objects = sector_objects
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True

    @abstractmethod
    def update(self, dt: float) -> None:
        pass

    def objektumok_kiveve(self, *fajtak):
        folyam = getattr(self.sector_objects,
                         "objects_other_than", None)
        if folyam is not None:
            return folyam(*fajtak)
        return self.sector_objects.space_objects_not_of_entity_type(*fajtak)


class AfterDelay(TickClock):
    def __init__(self, tick, sector_objects, utem_ora: int):
        super().__init__(sector_objects)
        self.delayed_ticks = max(1, utem_ora)
        self.tick = tick
        self.last_tick = tick.copy()

    @property
    def next_due_tick_value(self) -> int:
        return self.last_tick.value + self.delayed_ticks

    def is_due(self, ora_allas: int | None = None) -> bool:
        if ora_allas is None:
            ora_allas = self.tick.value
        return ora_allas >= self.next_due_tick_value

    def update_due(self) -> None:
        self.last_tick = self.tick.copy()
        self.on_due()

    def update(self, dt: float) -> None:
        if self.is_due():
            self.update_due()

    @abstractmethod
    def on_due(self) -> None:
        pass


def _visszatoltve(most: float, toltes: float, plafon: float, dt: float) -> float:
    return Maths.clamp_safe(f32(most + f32(toltes * dt)), 0, plafon)


class WatchStep:
    __slots__ = ('sector_objects',)

    def __init__(self, sector_objects):
        self.sector_objects = sector_objects

    def run(self) -> None:
        raise NotImplementedError


class SubsystemWatch(AfterDelay):
    def __init__(self, nev: str, csoport: str, tick, sector_objects,
                 utem_ora: int, lepesek):
        super().__init__(tick, sector_objects, utem_ora)
        self.sector_timer_name = nev
        self.sector_timer_group = csoport
        self._elozo_osztas = tick.value
        self._lepesek = [[lepes, max(1, koz), 0] for lepes, koz in lepesek]

    def steps_of(self):
        return tuple(bejegyzes[0] for bejegyzes in self._lepesek)

    def on_due(self) -> None:
        most = self.tick.value
        telt = most - self._elozo_osztas
        self._elozo_osztas = most
        for bejegyzes in self._lepesek:
            lepes, koz, eltelt = bejegyzes
            eltelt += telt
            if eltelt < koz:
                bejegyzes[2] = eltelt
                continue
            bejegyzes[2] = 0
            try:
                lepes.run()
            except Exception:
                log.exception("%s: the %s step fell over",
                              self.sector_timer_name, type(lepes).__name__)


class ShipRecovery(TickClock):
    NEM_REGENERAL = (ObjectKind.Asteroid, ObjectKind.Planetoid,
                     ObjectKind.Missile, ObjectKind.Planet)

    ENERGIA_NELKUL = frozenset((ObjectKind.MiningShip, ObjectKind.Comet))

    def __init__(self, sector_objects, jump_book, itt_levok):
        super().__init__(sector_objects)
        self._jump_book = jump_book
        self._sector_users = itt_levok

    def update(self, dt: float) -> None:
        for space_object in self.objektumok_kiveve(*self.NEM_REGENERAL):
            if space_object.is_removed():
                continue
            mutatok = space_object.space_subscribe_info()
            self._hajotest(mutatok, dt)
            if space_object.space_entity_type not in ShipRecovery.ENERGIA_NELKUL:
                self._energia(space_object, mutatok, dt)

    @staticmethod
    def _hajotest(mutatok, dt: float) -> None:
        if mutatok.is_in_combat:
            return
        toltodes = ShipRecovery._hull_visszatoltve(mutatok, dt)
        if toltodes is None:
            return
        most, uj = toltodes
        if uj < most:
            mutatok.limit_hull()
        else:
            mutatok.set_hull(uj)

    @staticmethod
    def _hull_visszatoltve(stats, dt: float):
        toltes = stats.stat(ObjectStat.HullRecovery)
        plafon = stats.stat(ObjectStat.MaxHullPoints)
        if toltes is None or plafon is None or toltes <= 0:
            return None
        most = stats.hp
        if most == plafon or most <= 0:
            return None
        return most, _visszatoltve(most, toltes, plafon, dt)

    def _energia(self, space_object, mutatok, dt: float) -> None:
        toltes = mutatok.stat(ObjectStat.PowerRecovery)
        plafon = mutatok.stat(ObjectStat.MaxPowerPoints)
        if toltes is None or plafon is None:
            return

        if space_object.is_player():
            if self._energiaja_befagyott(space_object):
                if mutatok.pp != 0:
                    mutatok.set_power(0)
                return
        elif toltes == 0 or mutatok.pp == plafon or plafon == 0:
            return

        uj = _visszatoltve(mutatok.pp, toltes, plafon, dt)
        if uj != mutatok.pp:
            mutatok.set_power(uj)

    def _energiaja_befagyott(self, space_object) -> bool:
        if self._jump_book.holds_object(space_object):
            return True
        felhasznalo = self._sector_users.user_unsafe(space_object.pilot_id())
        if felhasznalo.protocol_of(ProtocolID.Scene).logout_underway:
            return True
        return space_object.world_state_of().is_docking


class JumpTargetTransponderTimer(TickClock):
    def __init__(self, sector_objects, takarito):
        super().__init__(sector_objects)
        self._remover = takarito

    def update(self, dt: float) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for transponder in self.sector_objects.objects_of_kind(
                ObjectKind.Transponder):
            if transponder.is_removed():
                continue
            if now >= transponder.time_when_inactive:
                self._remover.note_removal_cause(transponder, DepartureCause.JumpOut)


log = logging.getLogger(__name__)


def _daily_ftl_cost_multiplier() -> float:
    try:
        from rebsgo.services import Services
        from rebsgo.runtime.daily_bonus_service import DailyBonusService
        return Services.get(DailyBonusService).ftl_cost_multiplier()
    except Exception:
        journal.eloszor(log, 'ftl-bonus', 'the daily FTL bonus is unreadable; jumps cost full price')
        return 1.0


class JumpCountdown(TickClock):
    def __init__(self, sector_objects, tick, jump_book, takarito, map_card, sector_desc, itt_levok):
        super().__init__(sector_objects)
        self._tick = tick
        self._jump_book = jump_book
        self._remover = takarito
        self._galaxy_map_card = map_card
        self._sector_desc = sector_desc
        self._users = itt_levok

    def update(self, dt: float) -> None:
        if self._sector_desc.sector_id == 9999:
            for user in self._users.users():
                if user.pilot_of().bgo_admin_roles.holds_any_role(
                        ServerRoles.Developer, ServerRoles.CommunityManager, ServerRoles.Mod):
                    continue
                ps = self._users.ship_of_pilot(user.pilot_of().user_id_of())
                if ps is not None:
                    if not self._jump_book.holds_object(ps.id_in_space()):
                        game_protocol = user.protocol_of(ProtocolID.Game)
                        game_protocol.jump_now(
                            self._jump_book,
                            GalaxyMapCard.start_sector(user.pilot_of().faction),
                            10,
                            False)

        while self._jump_book.has_expiring(self._tick):
            jump_schedule_item = self._jump_book.item()
            if jump_schedule_item is None:
                continue
            r = jump_schedule_item.entry

            if not r.is_player():
                self._remover.note_removal_cause(r, DepartureCause.JumpOut)
                continue

            remove_object = r.pilot_id()
            op_user = self._users.user(remove_object)
            if op_user is None:
                continue
            stars = self._galaxy_map_card.stars
            from_star = stars.get(self._sector_desc.sector_id)
            to_star = stars.get(jump_schedule_item.target_sector)
            if from_star is not None and to_star is not None:
                distance = Vector2.distance(from_star.position_of(), to_star.position_of())
                ftl_costs = r.space_subscribe_info().stat_or_default(ObjectStat.FtlCost)
                final_costs = f32(math.ceil(f32(ftl_costs * distance * _daily_ftl_cost_multiplier())))
                hold = op_user.pilot_of().hold
                tylium = hold.by_guid(ResourceKind.Tylium.guid)
                if tylium is None:
                    continue
                tylium.shrink_count(int(final_costs))
                from rebsgo.pilots.state.holdings.walks.hold_walk import HoldWalk
                hold_walker = HoldWalk(op_user, None)
                try:
                    hold_walker.take_from_stack(tylium, int(final_costs), hold)
                except ValueError:
                    log.info('%s cannot afford the FTL jump they just requested', op_user.user_log())
                    continue
            game_protocol = op_user.protocol_of(ProtocolID.Game)
            if (arrival_transform := jump_schedule_item.arrival_transform) is not None:
                op_user.pilot_of().arrive_at(arrival_transform)
            if len(jump_schedule_item.player_ids) == 0:
                game_protocol.jump_out_completed(None)
            else:
                game_protocol.jump_out_completed(jump_schedule_item.player_ids)
            self._remover.note_removal_cause(r, DepartureCause.JumpOut)


_MINE_TRIGGER_SPATIAL_INDEX_MAX_CELLS_PER_OBJECT = _CONFIG.int(
    "rebsgo.sector.spatial-index.mine-trigger-max-cells-per-object", 512)
TRIGGER_RADIUS = mine_tuning().trigger_radius
TRIGGER_RADIUS_SQ = TRIGGER_RADIUS * TRIGGER_RADIUS


class MineTimer(TickClock):
    def __init__(self, ctx, takarito, damage_book):
        super().__init__(ctx.space_objects())
        self._remover = takarito
        self._damage_book = damage_book
        self._tick = ctx.tick()
        self._last_stats = {
            "mines": 0,
            "armed_mines": 0,
            "ship_candidates": 0,
            "trigger_checks": 0,
            "triggers": 0,
            "spatial_enabled": 0,
            "spatial_cells": 0,
            "spatial_queries": 0,
            "spatial_candidates": 0,
        }

    def update(self, dt: float) -> None:
        mines = self.sector_objects.objects_of_kind(ObjectKind.Mine)

        time_stamp = self._tick.time_stamp()
        ship_candidates = None
        ship_spatial_index = None
        stats = {
            "mines": 0,
            "armed_mines": 0,
            "ship_candidates": 0,
            "trigger_checks": 0,
            "triggers": 0,
            "spatial_enabled": 0,
            "spatial_cells": 0,
            "spatial_queries": 0,
            "spatial_candidates": 0,
        }
        for mine in mines:
            stats["mines"] += 1
            if mine.is_removed():
                continue

            try:
                lejart = mine.tick_spawn_is_after(time_stamp)
            except Exception:
                journal.eloszor(log, 'mine-expiry',
                                'a mine could not answer its expiry check; removing it')
                self._remover.note_removal_cause(mine, DepartureCause.Death)
                continue
            if lejart:
                self._remover.note_removal_cause(mine, DepartureCause.Death)
                continue

            if not mine.is_armed(time_stamp):
                continue
            stats["armed_mines"] += 1

            if not mine.is_anchored:
                mover = mine.mover_of()
                mover.queue_maneuver(RestManeuver(
                    mover.position_of(),
                    Euler3.from_quaternion(mover.rotation_of())))
                mine.settle()

            if ship_candidates is None:
                ship_candidates = tuple(self.sector_objects.ships_stream_of())
                stats["ship_candidates"] = len(ship_candidates)
                ship_spatial_index = self._build_ship_spatial_index(ship_candidates)
                if ship_spatial_index is not None:
                    stats["spatial_enabled"] = 1
                    stats["spatial_cells"] = ship_spatial_index.stats.cells

            trigger_ship = self._find_trigger_ship(mine, ship_candidates, ship_spatial_index, stats)
            if trigger_ship is None:
                continue

            stats["triggers"] += 1
            self._damage_book.deal_damage_from_mine(mine)
            self._remover.note_removal_cause(mine, DepartureCause.Hit, trigger_ship)
        self._last_stats = stats

    def _find_trigger_ship(self, mine, ship_candidates=None, ship_spatial_index=None, stats=None):
        mine_position = mine.mover_of().position_of()
        if ship_candidates is None:
            ship_candidates = tuple(self.sector_objects.ships_stream_of())
        jeloltek = self._trigger_candidates(mine_position, ship_candidates, ship_spatial_index, stats)
        for ship in jeloltek:
            if stats is not None:
                stats["trigger_checks"] = stats.get("trigger_checks", 0) + 1
            if ship.is_removed():
                continue
            if not ship.faction.hostile_to(mine.faction):
                continue
            distance_sq = ship.mover_of().position_of().sq_distance_to(mine_position)
            if distance_sq <= TRIGGER_RADIUS_SQ:
                return ship
        return None

    @staticmethod
    def _trigger_candidates(mine_position, ship_candidates, ship_spatial_index, stats=None):
        return ordered_radius_candidates(ship_candidates, ship_spatial_index, mine_position, TRIGGER_RADIUS, stats=stats)

    @staticmethod
    def _build_ship_spatial_index(ship_candidates):
        if (not _MINE_TRIGGER_SPATIAL_INDEX_ENABLED
            or len(ship_candidates) < _MINE_TRIGGER_SPATIAL_INDEX_MIN_OBJECTS):
            return None
        return build_complete_spatial_index(
            ship_candidates,
            _MINE_TRIGGER_SPATIAL_INDEX_CELL_SIZE,
            _MINE_TRIGGER_SPATIAL_INDEX_MAX_CELLS_PER_OBJECT,
            log,
            "Mine trigger",
        )

    def last_stats(self) -> dict:
        return dict(self._last_stats)


@dataclass(slots=True, unsafe_hash=True)
class _MiningHand:
    member: object
    is_owner: bool
    sector_id: int

    @staticmethod
    def owner_for(owner) -> "_MiningHand":
        return _MiningHand(owner, True, owner.pilot_of().sector_id)

    @staticmethod
    def enrol_member(member, sector_id: int) -> "_MiningHand":
        return _MiningHand(member, False, sector_id)

class _MiningCrew:

    def __init__(self, owner: _MiningHand, csapattagok=None):
        self._owner = owner
        self._party_members = set() if csapattagok is None else csapattagok

    @property
    def owner(self) -> _MiningHand:
        return self._owner

    @property
    def party_members(self):
        return self._party_members

    @property
    def in_a_party(self) -> bool:
        return len(self._party_members) != 0

    @property
    def everyone_watching(self) -> int:
        return len(self._party_members) + 1

    def all_party_members(self):
        full_members = [self._owner]
        full_members.extend(self._party_members)
        return full_members


class MinerRounds(TickClock):
    def __init__(self, ctx, mining_ship_config, galaxis_szorzo, spoils_split, takarito):
        super().__init__(ctx.space_objects())
        self._ctx = ctx
        self._mining_ship_config = mining_ship_config
        self._galaxy_bonus = galaxis_szorzo
        self._spoils_split = spoils_split
        self._remover = takarito

    def update(self, dt: float) -> None:
        ships = self.sector_objects.space_objects_of_entity_type(ObjectKind.MiningShip)
        current_tick_time_stamp = self._ctx.tick().time_stamp()

        for mining_ship in ships:
            self._handle_mining_ship_update(mining_ship, current_tick_time_stamp)

    def _handle_mining_ship_update(self, mining_ship, mostani_ora_ms: int) -> None:
        is_delay_over = self._check_is_mining_delay_over(mining_ship, mostani_ora_ms)
        if not is_delay_over:
            return

        owner = mining_ship.owner
        if owner.pilot_of().faction != mining_ship.faction:
            self._remover.note_removal_cause(mining_ship, DepartureCause.JumpOut)
            self._remover.note_removal_cause(mining_ship.attached_to_planetoid, DepartureCause.Death)
            return

        has_outpost = len(self.sector_objects.space_objects_of_entity_type(ObjectKind.Outpost)) > 0
        if has_outpost:
            income = self._ctx.dice().between_whole(250, 800)
        else:
            income = self._ctx.dice().between_whole(100, 250)
        map_bonus = self._galaxy_bonus.colo_mining_bonus if mining_ship.faction == Faction.Colonial \
            else self._galaxy_bonus.cylo_mining_bonus
        income = income + int(f32(f32(income) * map_bonus))
        from rebsgo.vocabulary.pilot import BoostKind
        income = int(income * owner.pilot_of().factors.multiplier_for(BoostKind.AsteroidYield))

        mining_ship.last_time_mining = mostani_ora_ms

        mining_users_of_interest = self._find_users_of_interest(owner)

        income = self._calculate_income(mining_users_of_interest, income)

        zsakmany = self._ctx.loot_ownership.get(mining_ship.attached_to_planetoid)
        if zsakmany is None:
            debug_protocol = owner.protocol_of(ProtocolID.Debug)
            debug_protocol.tell_console("ERROR: MinerRounds loot missing")
            return
        existing_loot = zsakmany
        resource = existing_loot.loot_items()[0].ship_item
        farmed = income if (resource.count() - income) > 0 else resource.count()
        resource.shrink_count(farmed)

        for mining_party_member in mining_users_of_interest.all_party_members():
            mining_reward = CountableItem.from_guid(
                resource.card_guid_of(), farmed // mining_users_of_interest.everyone_watching)
            self._spoils_split.ore_taken_out(mining_party_member.member, mining_reward)

        if farmed < income:
            self._remover.note_removal_cause(mining_ship, DepartureCause.JumpOut)
            self._remover.note_removal_cause(mining_ship.attached_to_planetoid, DepartureCause.Death)
        self._update_op_progress_count(mining_ship.faction)

    def _provide_users_of_interests_with_income(self, banyaszok, farmed_total: int, resource) -> None:
        adjusted_farmed = farmed_total // banyaszok.everyone_watching
        for party_member in banyaszok.all_party_members():
            mining_reward = CountableItem.from_guid(resource.card_guid_of(), adjusted_farmed)
            self._spoils_split.ore_taken_out(party_member.member, mining_reward)

    def _calculate_income(self, banyaszok, korabbi_bevetel: int) -> int:
        if not banyaszok.in_a_party:
            return korabbi_bevetel

        return korabbi_bevetel * banyaszok.everyone_watching

    def _check_is_mining_delay_over(self, mining_ship, mostani_ora_ms: int) -> bool:
        last_time_time_stamp = mining_ship.last_time_mining
        delay_in_ms = self._mining_ship_config.extract_delay * 1000

        diff = mostani_ora_ms - (last_time_time_stamp + delay_in_ms)
        return diff >= 0

    def _find_users_of_interest(self, user) -> _MiningCrew:
        player = user.pilot_of()
        party = player.party()
        if party is None:
            return _MiningCrew(_MiningHand.owner_for(user))
        member_copy = party.members_copy()
        members_of_interest = set()
        for party_member in member_copy:
            if not party_member.is_connected():
                continue
            if party_member == user:
                continue
            if party_member.pilot_of().location.game_location != PlaceKind.Space:
                continue
            members_of_interest.add(_MiningHand.enrol_member(
                party_member, party_member.pilot_of().location.sector_id))

        return _MiningCrew(_MiningHand.owner_for(user), members_of_interest)

    def _update_op_progress_count(self, faction) -> None:
        outpost_scoreboard = self._ctx.outpost_scoreboard
        op_state = outpost_scoreboard.colonial_outpost_state if faction == Faction.Colonial \
            else outpost_scoreboard.cylon_outpost_state
        progress_template = outpost_scoreboard.template_from_faction(faction)
        is_blocked = op_state.gain_points(progress_template.pts_mining_ship_income)


class MissileFlight(TickClock):
    def __init__(self, ctx, takarito):
        super().__init__(ctx.space_objects())
        self._remover = takarito
        self._tick = ctx.tick()

    def update(self, dt: float) -> None:
        missiles = self.sector_objects.objects_of_kind(ObjectKind.Missile)
        for raketa in missiles:
            if raketa.is_removed():
                continue

            ttl_over = raketa.tick_spawn_is_after(self._tick.time_stamp())
            if ttl_over:
                self._remover.note_removal_cause(raketa, DepartureCause.Death)
                continue

            self._drop_lock_if_target_cloaked(raketa)

    @staticmethod
    def _drop_lock_if_target_cloaked(missile) -> None:
        mover = missile.mover_of()
        if mover is None:
            return
        manover = mover.current_maneuver
        get_target = getattr(manover, "locked_target_of", None)
        if get_target is None or not is_cloaked_player(get_target()):
            return
        current_frame = mover.frame
        if current_frame is None:
            return
        mover.queue_maneuver(DirectionalManeuver(current_frame.euler3().copy()))


class ModifierExpiry(TickClock):
    def __init__(self, ctx):
        self._ctx = ctx
        super().__init__(ctx.space_objects())

    NINCS_MODOSITOJA = (ObjectKind.Asteroid, ObjectKind.Planetoid, ObjectKind.Missile)

    JELZOK = (
        (AbilityActionKind.ShortCircuit,
         lambda allapot: allapot.is_emp_on, "set_emp_on"),
        (AbilityActionKind.ActivatePaintTheTarget,
         lambda allapot: allapot.is_marked_by_carrier, "set_marked_by_carrier"),
        (AbilityActionKind.Fortify,
         lambda allapot: allapot.is_fortified, "set_fortified"),
    )

    def update(self, dt: float) -> None:
        for space_object in self.objektumok_kiveve(*self.NINCS_MODOSITOJA):
            modositok = space_object.space_subscribe_info().modifiers
            if modositok is None:
                continue

            lejartak = modositok.expired_ones()
            if lejartak:
                self._csuszas_vege(space_object, modositok, lejartak)
                space_object.space_subscribe_info().remove_modifiers(lejartak)

            allapot = space_object.world_state_of()
            for fajta, be_van, kikapcsol in self.JELZOK:
                if be_van(allapot) and next(iter(modositok.of_type_stream(fajta)), None) is None:
                    getattr(allapot, kikapcsol)(False)

    @staticmethod
    def _csuszas_vege(space_object, modositok, lejartak) -> None:
        csuszasok = [m.server_id for m in modositok.of_type(AbilityActionKind.Slide)]
        if not csuszasok or not all(cs in lejartak for cs in csuszasok):
            return
        mozgas = space_object.mover_of().movement_options
        if mozgas.gear_of == Gear.RCS:
            mozgas.shift_to(mozgas.last_gear)


_EMPTY_SECTOR_BURST_LIMIT = max(0, _CONFIG.int("rebsgo.sector.spawn-scheduler.empty-burst-limit", 64))
_ACTIVE_SECTOR_BURST_LIMIT = max(0, _CONFIG.int("rebsgo.sector.spawn-scheduler.active-burst-limit", 0))
_EMPTY_SECTOR_BURST_MAX_MS = max(0.0, _CONFIG.float("rebsgo.sector.spawn-scheduler.empty-burst-max-ms", 25.0))
_ACTIVE_SECTOR_BURST_MAX_MS = max(0.0, _CONFIG.float("rebsgo.sector.spawn-scheduler.active-burst-max-ms", 0.0))
_EMPTY_GLOBAL_BURST_LIMIT = max(0, _CONFIG.int("rebsgo.sector.spawn-scheduler.empty-global-burst-limit", 2))
_EMPTY_GLOBAL_WINDOW_MS = max(
    1.0, _CONFIG.float("rebsgo.sector.spawn-scheduler.empty-global-window-ms", 100.0))

_EMPTY_GLOBAL_WINDOW_STARTED = 0.0
_EMPTY_GLOBAL_USED = 0


class SpawnClock(TickClock):
    def __init__(self, sector_objects, spawn_runner, tick, itt_levok=None):
        super().__init__(sector_objects)
        self._spawn_runner = spawn_runner
        self._tick = tick
        self._sector_users = itt_levok
        self._last_stats = {
            "ready_items": 0,
            "spawned": 0,
            "burst_limit": 0,
            "burst_max_ms": 0.0,
            "global_budget_exhausted": False,
            "remaining_ready": False,
        }

    def update(self, dt: float) -> None:
        burst_limit = self._burst_limit()
        burst_max_ms = self._burst_max_ms()
        empty_sector = self._sector_is_deserted()
        if burst_limit > 0 or burst_max_ms > 0 or (empty_sector and _EMPTY_GLOBAL_BURST_LIMIT > 0):
            spawned, global_budget_exhausted = self._spawn_limited(burst_limit, burst_max_ms, empty_sector)
        else:
            all_ready_items = self._spawn_runner.all_timeout_items(self._tick)
            spawned = 0
            for schedule_item in all_ready_items:
                schedule_item.entry.spawn()
                spawned += 1
            global_budget_exhausted = False
        remaining_ready = self._has_remaining_ready_items()
        self._last_stats = {
            "ready_items": spawned,
            "spawned": spawned,
            "burst_limit": burst_limit,
            "burst_max_ms": burst_max_ms,
            "global_budget_exhausted": global_budget_exhausted,
            "remaining_ready": remaining_ready,
        }

    def last_stats(self) -> dict:
        return dict(self._last_stats)

    def _burst_limit(self) -> int:
        if self._sector_is_deserted():
            return _EMPTY_SECTOR_BURST_LIMIT
        return _ACTIVE_SECTOR_BURST_LIMIT

    def _burst_max_ms(self) -> float:
        if self._sector_is_deserted():
            return _EMPTY_SECTOR_BURST_MAX_MS
        return _ACTIVE_SECTOR_BURST_MAX_MS

    def _sector_is_deserted(self) -> bool:
        if self._sector_users is None:
            return False
        return getattr(self._sector_users, "empty", False)

    def _spawn_limited(self, burst_limit: int, burst_max_ms: float, empty_sector: bool) -> tuple[int, bool]:
        due_item = getattr(self._spawn_runner, "due_item", None)
        if not callable(due_item):
            return self._spawn_limited_batch_fallback(burst_limit), False

        started = time.perf_counter()
        spawned = 0
        global_budget_exhausted = False
        while True:
            if burst_limit > 0 and spawned >= burst_limit:
                break
            if burst_max_ms > 0 and spawned > 0 and (time.perf_counter() - started) * 1000.0 >= burst_max_ms:
                break
            if not self._has_remaining_ready_items():
                break
            if empty_sector and not _try_acquire_empty_global_budget():
                global_budget_exhausted = True
                break

            schedule_item = due_item(self._tick)
            if schedule_item is None:
                break
            schedule_item.entry.spawn()
            spawned += 1
        return spawned, global_budget_exhausted

    def _spawn_limited_batch_fallback(self, burst_limit: int) -> int:
        if burst_limit <= 0:
            burst_limit = 1
        all_ready_items = self._spawn_runner.timeout_items(self._tick, burst_limit)
        spawned = 0
        for schedule_item in all_ready_items:
            schedule_item.entry.spawn()
            spawned += 1
        return spawned

    def _has_remaining_ready_items(self) -> bool:
        has_timeout_items = getattr(self._spawn_runner, "has_timeout_items", None)
        if not callable(has_timeout_items):
            return False
        return bool(has_timeout_items(self._tick))


def _try_acquire_empty_global_budget() -> bool:
    if _EMPTY_GLOBAL_BURST_LIMIT <= 0:
        return True

    global _EMPTY_GLOBAL_WINDOW_STARTED, _EMPTY_GLOBAL_USED
    most = time.perf_counter() * 1000.0
    with _EMPTY_GLOBAL_LOCK:
        if most - _EMPTY_GLOBAL_WINDOW_STARTED >= _EMPTY_GLOBAL_WINDOW_MS:
            _EMPTY_GLOBAL_WINDOW_STARTED = most
            _EMPTY_GLOBAL_USED = 0
        if _EMPTY_GLOBAL_USED >= _EMPTY_GLOBAL_BURST_LIMIT:
            return False
        _EMPTY_GLOBAL_USED += 1
        return True


class VisibilitySweep(TickClock):
    def __init__(self, ctx, takarito):
        super().__init__(ctx.space_objects())
        self._ctx = ctx
        self._space_replies = GameReplies()
        self._remover = takarito

    def update(self, dt: float) -> None:
        bws = []
        own_ship_module_refreshes = []

        for user in self._ctx.users().users_of():
            ship = self._ctx.users().player_ship_unsafe(user.pilot_of().user_id_of())
            if ship is None:
                continue

            visibility = ship.visibility_of()

            game_protocol = user.protocol_of(ProtocolID.Game)
            complete_jump_flag = game_protocol.complete_jump_flag

            if complete_jump_flag.set_if(True, False):
                log.info("%s VisibilitySweep: complete_jump_flag was true, starting ghost jump", user.user_log())
                process_correct = visibility.begin_ghost_jump()
                log.info("%s VisibilitySweep: start_ghost_jump result=%s, visibility=%s",
                         user.user_log(), process_correct, visibility)

            if visibility.jump_in_needed(self._ctx.tick()):
                log.info("%s VisibilitySweep: required_jump_in=true, finishing ghost jump", user.user_log())
                visibility.settle_ghost_jump()
                log.info("%s VisibilitySweep: after finish_ghost_jump_in, visibility=%s", user.user_log(), visibility)

            if visibility.visibility_needs_push():
                log.info("%s VisibilitySweep: visibility requires update, is_visible=%s",
                         user.user_log(), visibility.is_visible())
                bw = self._space_replies.switch_visibility_as(ship.id_in_space(), visibility)
                if visibility.is_visible():
                    bws.append(bw)
                    if visibility.change_visibility_reason == VisibilityCause.Jump:
                        own_ship_module_refreshes.append((ship, user))
                    location = user.pilot_of().location
                    current_sector_id = location.sector_id
                    try:
                        is_enemy_base_sector = GalaxyMapCard.is_base_sector(
                            user.pilot_of().faction.opposing_side(), current_sector_id)
                        if (is_enemy_base_sector
                            and not user.pilot_of().bgo_admin_roles.holds_any_role(
                                    ServerRoles.Developer, ServerRoles.CommunityManager)):
                            log.error("Criticial warning, user is in enemy base sector=%s, current_faction=%s sectorID=%s",
                                      user.user_log(), user.pilot_of().faction, current_sector_id)
                            if not ship.is_removed():
                                self._remover.note_removal_cause(ship, DepartureCause.Death)
                    except RuntimeError:
                        log.error("visibility sweep met a pilot outside both factions")
                elif (not visibility.is_visible()
                      and visibility.change_visibility_reason == VisibilityCause.Anchor):
                    bws.append(bw)
                else:
                    self._ctx.sender().push_to(bw, user)
        self._ctx.sender().push_to_everyone(bws)
        for ship, user in own_ship_module_refreshes:
            self._ctx.sender().refresh_own_ship_modules_after_visibility(ship, user)


class BoostUpkeep(AfterDelay):
    def __init__(self, tick, sector_objects, utem_ora: int, itt_levok, sector_card):
        super().__init__(tick, sector_objects, utem_ora)
        self._sector_users = itt_levok
        self._sector_card = sector_card

    def on_due(self) -> None:
        for player_ship in self._sector_users.player_ships_collection:
            if player_ship.mover_of().movement_options.gear_of == Gear.Boost:
                self._boost_ara(player_ship)

    def _boost_ara(self, player_ship) -> None:
        from rebsgo.pilots.state.holdings.walks.hold_walk import HoldWalk

        user = self._sector_users.user(player_ship.pilot_id())
        if user is None:
            return
        hold = user.pilot_of().hold
        tylium = hold.by_guid(ResourceKind.Tylium.guid)
        if tylium is None:
            return

        ara = int(math.ceil(
            player_ship.space_subscribe_info().stat_or_default(ObjectStat.BoostCost)))
        try:
            HoldWalk(user).take_from_stack(tylium, ara, hold)
            user.pilot_of().tally_desk.bump_counter(
                TallyCardKind.tylium_burned, self._sector_card.card_guid_of(), ara)
        except ValueError:
            log.error("%s ran the tylium dry and cannot keep boosting %s",
                      user.user_log(), user.pilot_of().player_log)
            player_ship.mover_of().movement_options.shift_to(Gear.Regular)
            player_ship.mover_of().flag_movement_dirty()


class CarrierAnchorFollowTimer(AfterDelay):
    def __init__(self, ctx, utem_ora: int):
        super().__init__(ctx.tick(), ctx.space_objects(), utem_ora)
        self._ctx = ctx
        self._last_stats = {
            "carriers": 0,
            "synced_ships": 0,
        }

    def on_due(self) -> None:
        carriers, synced_ships = sync_all_carrier_anchor_followers(self._ctx)
        self._last_stats = {
            "carriers": carriers,
            "synced_ships": synced_ships,
        }

    def last_stats(self) -> dict:
        return dict(self._last_stats)


class CombatClock(AfterDelay):
    def __init__(self, tick, sector_objects, utem_ora: int, harc_ora: int):
        super().__init__(tick, sector_objects, utem_ora)
        self._combat_timer = harc_ora
        self._last_warn_ms = 0.0
        self._last_stats = {
            "ships": 0,
            "missiles": 0,
            "missile_targets": 0,
        }

    def on_due(self) -> None:
        current_time_stamp = self.tick.time_stamp()
        all_missiles = self.sector_objects.objects_of_kind(ObjectKind.Missile)
        missile_target_ids = {
            raketa.missile_launched_on_object.id_in_space()
            for raketa in all_missiles
            if raketa.missile_launched_on_object is not None
        }

        ship_count = 0
        for ship in self.sector_objects.ships_stream_of():
            ship_count += 1
            has_any_missile = ship.id_in_space() in missile_target_ids
            ship.space_subscribe_info().refresh_combat_state(self._combat_timer, current_time_stamp,
                                                             has_any_missile)
        missile_count = len(all_missiles)
        missile_target_count = len(missile_target_ids)
        self._last_stats = {
            "ships": ship_count,
            "missiles": missile_count,
            "missile_targets": missile_target_count,
        }
        object_count = ship_count + missile_count
        if (should_warn_count(object_count, SECTOR_COMBAT_OBJECT_WARN_COUNT)
            and should_warn_interval(self._last_warn_ms, SECTOR_TIMER_WARN_INTERVAL_MS)):
            self._last_warn_ms = now_ms()
            log.warning(
                "High combat timer object count ships=%s missiles=%s missile_targets=%s threshold=%s",
                ship_count,
                missile_count,
                missile_target_count,
                SECTOR_COMBAT_OBJECT_WARN_COUNT,
            )

    def last_stats(self) -> dict:
        return dict(self._last_stats)


class CometPass(AfterDelay):
    def __init__(self, tick, sector_objects, utem_ora: int, factory, arrival_gate, comet_layout):
        super().__init__(tick, sector_objects, utem_ora)
        self._factory = factory
        self._join_queue = arrival_gate
        self._comet_sector_desc = comet_layout

    def on_due(self) -> None:
        if not self._comet_sector_desc.activated:
            return

        elo = sum(1 for o in self.sector_objects.objects_of_kind(ObjectKind.Comet)
                  if not o.is_removed())
        for _i in range(self._comet_sector_desc.comet_counter - elo):
            tmp_comet = self._factory.hatch_comet(
                self._comet_sector_desc.comet_guid,
                magassag_sav=self._comet_sector_desc.height_band)
            self._join_queue.admit_object(tmp_comet)


class DebrisCargoTimer(AfterDelay):
    def __init__(self, tick, sector_objects, utem_ora: int, factory, arrival_gate, desc, dice):
        super().__init__(tick, sector_objects, utem_ora)
        self._factory = factory
        self._join_queue = arrival_gate
        self._desc = desc
        self._dice = dice
        self._spawned_debris_ids = []

    def _random_transform(self) -> Transform:
        r = self._desc.spawn_radius
        h = self._desc.spawn_height
        x = self._dice.between(-r, r)
        y = self._dice.between(-h, h)
        z = self._dice.between(-r, r)
        return Transform(Vector3(x, y, z))

    def on_due(self) -> None:
        if not self._desc.activated:
            return

        debris_guids = self._desc.debris_guids
        if debris_guids and self._desc.debris_count > 0:
            self._spawned_debris_ids = [oid for oid in self._spawned_debris_ids
                                        if self.sector_objects.get(oid) is not None]
            spawned = 0
            for _ in range(max(0, self._desc.debris_count - len(self._spawned_debris_ids))):
                guid = debris_guids[self._dice.between_whole(0, len(debris_guids) - 1)]
                try:
                    debris = self._factory.hatch_debris(guid, self._random_transform())
                    self._join_queue.admit_object(debris)
                    self._spawned_debris_ids.append(debris.id_in_space())
                    spawned += 1
                except Exception:
                    log.exception("debris pile spawn failed for guid %s", guid)
            if spawned > 0:
                log.info("DebrisCargoTimer: spawned %s debris-field pile(s) (field now %s)",
                         spawned, len(self._spawned_debris_ids))

        cargo_guid = self._desc.cargo_guid
        if cargo_guid and self._desc.cargo_max_count > 0:
            current_cargo = len(self.sector_objects.space_objects_of_entity_type(ObjectKind.CargoObject))
            if current_cargo < self._desc.cargo_max_count \
                    and self._dice.passes(self._desc.cargo_spawn_chance):
                try:
                    cargo = self._factory.create_cargo(cargo_guid, self._random_transform())
                    self._join_queue.admit_object(cargo)
                    log.info("DebrisCargoTimer: spawned cargo container id=%s guid=%s",
                             cargo.id_in_space(), cargo_guid)
                except Exception:
                    log.exception("cargo container spawn failed for guid %s", cargo_guid)


_FIELD_RANDOM = Config.instance().bool("rebsgo.debris.field-random", False)


class DebrisFieldTimer(AfterDelay):
    def __init__(self, tick, sector_objects, utem_ora: int, factory, arrival_gate, desc,
                 dice, sector_id: int = 0):
        super().__init__(tick, sector_objects, utem_ora)
        self._factory = factory
        self._join_queue = arrival_gate
        self._desc = desc
        if _FIELD_RANDOM:
            self._dice = dice
        else:
            self._dice = Dice((sector_id * 0x9E3779B1) & 0xFFFFFFFF)
        self._clusters = None
        self._decor_ids = {"pile": [], "wreck": [], "fragment": [], "wall": []}
        self._container_ids = None

    def _build_clusters(self) -> None:
        n = self._desc.field_count
        fr = self._desc.field_radius
        self._clusters = []
        for i in range(n):
            ang = (2.0 * math.pi * i / n) + self._dice.between(-0.35, 0.35)
            rad = fr * self._dice.between(0.45, 0.95) if n > 1 else \
                fr * self._dice.between(0.0, 0.4)
            self._clusters.append(Vector3(rad * math.cos(ang), 0.0, rad * math.sin(ang)))
        self._container_ids = [[] for _ in range(n)]
        log.info("DebrisFieldTimer: built %s cluster(s) (piles/wrecks/frag/walls per cluster=%s/%s/%s/%s, "
                 "containers/cluster=%s)", n, self._desc.piles_per_cluster, self._desc.wrecks_per_cluster,
                 self._desc.fragments_per_cluster, self._desc.walls_per_cluster,
                 self._desc.containers_per_cluster)

    def _scatter(self, center: Vector3) -> Transform:
        cr = self._desc.cluster_radius
        ch = self._desc.cluster_height
        r = cr * math.sqrt(self._dice.between(0.0, 1.0))
        th = self._dice.between(0.0, 2.0 * math.pi)
        x = center.x + r * math.cos(th)
        z = center.z + r * math.sin(th)
        y = center.y + self._dice.between(-ch, ch)
        rot = Euler3(self._dice.between(0.0, 360.0),
                     self._dice.between(0.0, 360.0),
                     self._dice.between(0.0, 360.0))
        return Transform(Vector3(x, y, z), rot)

    def _pick(self, guids):
        return guids[self._dice.between_whole(0, len(guids) - 1)]

    def _topup_decor(self, kind, guids, per_cluster) -> None:
        if per_cluster <= 0 or not guids:
            return
        celpont = per_cluster * len(self._clusters)
        alive = [oid for oid in self._decor_ids[kind] if self.sector_objects.get(oid) is not None]
        for k in range(celpont - len(alive)):
            cluster = self._clusters[(len(alive) + k) % len(self._clusters)]
            guid = self._pick(guids)
            try:
                debris = self._factory.hatch_debris(guid, self._scatter(cluster))
                self._join_queue.admit_object(debris)
                alive.append(debris.id_in_space())
            except Exception:
                log.exception("debris %s spawn failed for guid %s", kind, guid)
        self._decor_ids[kind] = alive

    def _maintain_containers(self) -> None:
        per = self._desc.containers_per_cluster
        if per <= 0:
            return
        cargo_guid = self._desc.cargo_guid
        for i, cluster in enumerate(self._clusters):
            self._container_ids[i] = [oid for oid in self._container_ids[i]
                                      if self.sector_objects.get(oid) is not None]
            if len(self._container_ids[i]) < per \
                    and self._dice.passes(self._desc.container_spawn_chance):
                try:
                    cargo = self._factory.create_cargo(cargo_guid, self._scatter(cluster))
                    self._join_queue.admit_object(cargo)
                    self._container_ids[i].append(cargo.id_in_space())
                except Exception:
                    log.exception("cargo container spawn failed for guid %s", cargo_guid)

    def on_due(self) -> None:
        if not self._desc.activated:
            return
        if self._clusters is None:
            self._build_clusters()
        self._topup_decor("pile", self._desc.pile_guids, self._desc.piles_per_cluster)
        self._topup_decor("wreck", self._desc.wreck_guids, self._desc.wrecks_per_cluster)
        self._topup_decor("fragment", self._desc.fragment_guids, self._desc.fragments_per_cluster)
        self._topup_decor("wall", self._desc.wall_guids, self._desc.walls_per_cluster)
        self._maintain_containers()


class ArrivalCountdown(AfterDelay):
    def __init__(self, ctx, utem_ora: int):
        super().__init__(ctx.tick(), ctx.space_objects(), utem_ora)
        self._jumping_in_ships = {}

    def on_due(self) -> None:
        current_time_stamp = self.tick.time_stamp()
        for object_id, join_time_stamp in list(self._jumping_in_ships.items()):
            time_up = join_time_stamp + 1000 * 10
            delta = current_time_stamp - time_up
            if delta < 0:
                continue
            self._jumping_in_ships.pop(object_id, None)


class LeaveCountdown(AfterDelay):
    def __init__(self, tick, sector_objects, utem_ora: int, pilotak, takarito):
        super().__init__(tick, sector_objects, utem_ora)
        self._users = pilotak
        self._remover = takarito

    def on_due(self) -> None:
        if self._users.empty:
            return

        most = datetime.now(timezone.utc)
        for user, kilepett in self._elhagyott_ulesek():
            player_ship = self._users.player_ship_unsafe(user.pilot_of().user_id_of())
            if kilepett.minutes_before(1, most):
                player_ship.mover_of().movement_options.drive_at(0)
                player_ship.mover_of().movement_options.shift_to(Gear.Regular)
            if kilepett.minutes_before(2, most):
                self._remover.note_removal_cause(player_ship, DepartureCause.Disconnection)

    def _elhagyott_ulesek(self):
        for user in self._users.users_of():
            if user.connection() is not None:
                continue
            kilepett = user.pilot_of().last_logout
            if kilepett is None:
                log.error("%sdisconnected but no logout date set", user.user_log())
                continue
            yield user, kilepett


class MiningHistoryTrim(WatchStep):
    def __init__(self, ctx, banyaszat):
        super().__init__(ctx.space_objects())
        self._mining_sector_operations = banyaszat

    def run(self) -> None:
        self._mining_sector_operations.drop_stale()


class MinerHunters(WatchStep):
    def __init__(self, ctx, mining_ship_config, object_forge, arrival_gate):
        super().__init__(ctx.space_objects())
        self.tick = ctx.tick()
        self._mining_ship_config = mining_ship_config
        self._object_forge = object_forge
        self._join_queue = arrival_gate
        self._dice = ctx.dice()

    def run(self) -> None:
        most = self.tick.time_stamp()
        varakozas = self._mining_ship_config.seconds_until_npc_spawns * 1000
        elso_varakozas = self._mining_ship_config.npc_initial_spawn_delay_seconds * 1000

        for mining_ship in self.sector_objects.space_objects_of_entity_type(ObjectKind.MiningShip):
            legutobb = mining_ship.last_time_assassin
            if legutobb == 0:
                mining_ship.last_time_assassin = most + elso_varakozas - varakozas
            elif most >= legutobb + varakozas and self._orgyilkosok_erkeznek(mining_ship):
                mining_ship.last_time_assassin = most

    def _orgyilkosok_erkeznek(self, mining_ship) -> bool:
        jelolt = [npc for npc in self._mining_ship_config.npc_guid_loot_ids
                  if npc.faction() != mining_ship.faction]
        if not jelolt:
            return False

        npc_guid_loot_id = self._dice.pick(jelolt)
        honnan = mining_ship.mover_of().transform_of()
        for _ in range(npc_guid_loot_id.count()):
            assassin_transform = self._orgyilkos_helye(honnan)
            new_assassin = self._object_forge.hatch_fighter(
                npc_guid_loot_id.npc_guid,
                [mining_ship],
                [],
                [],
                assassin_transform,
                NpcBehaviourSpec(
                    1,
                    400,
                    2500,
                    15,
                    False,
                    400),
                npc_guid_loot_id.loot_id)
            self._join_queue.admit_object(new_assassin)
        return True

    def _orgyilkos_helye(self, honnan):
        assassin_transform = honnan.copy()
        assassin_pos = assassin_transform.position_of()
        up_axis = assassin_transform.rotation_of().mult_(CommonDirections.UP)
        right_axis = assassin_transform.rotation_of().mult_(CommonDirections.RIGHT)
        forward_axis = assassin_transform.rotation_of().mult_(CommonDirections.FORWARD)
        assassin_pos.add_(assassin_transform.rotation_of().direction_().add_(
            up_axis.mult_(self._dice.between_wide(200, 1000))))
        assassin_pos.add_(assassin_transform.rotation_of().direction_().add_(
            right_axis.mult_(self._dice.between_wide(-600, 600))))
        assassin_pos.add_(assassin_transform.rotation_of().direction_().add_(
            forward_axis.mult_(self._dice.between_wide(450, 700))))
        return assassin_transform


class MovementPulse(AfterDelay):
    HEARTBEAT_INTERVAL_SECONDS = 7

    def __init__(self, tick, sector_objects, utem_ora: int, pilotak, sender):
        super().__init__(tick, sector_objects, utem_ora)
        self._users = pilotak
        self._sender = sender
        self._space_replies = game_replies()
        self._last_warn_ms = 0.0
        self._last_stats = {
            "has_clients": 0,
            "objects": 0,
            "movement_packets": 0,
        }

    def on_due(self) -> None:
        if self._users.empty:
            self._last_stats = {
                "has_clients": 0,
                "objects": 0,
                "movement_packets": 0,
            }
            return

        tick_cpy = self.tick.copy()
        self._beat_for_dynamic_objects(tick_cpy)

    def _beat_for_dynamic_objects(self, ora_masolat) -> None:
        stream = getattr(self.sector_objects, "objects_other_than", None)
        heart_beat_objects = (
            stream(
                ObjectKind.Asteroid,
                ObjectKind.Planetoid,
                ObjectKind.Planet,
                ObjectKind.WeaponPlatform,
                ObjectKind.MiningShip)
            if stream is not None else
            self.sector_objects.space_objects_not_of_entity_type(
                ObjectKind.Asteroid,
                ObjectKind.Planetoid,
                ObjectKind.Planet,
                ObjectKind.WeaponPlatform,
                ObjectKind.MiningShip)
        )

        bws = []
        object_count = 0

        for heart_beat_object in heart_beat_objects:
            object_count += 1
            if heart_beat_object.is_removed():
                continue

            utolso = heart_beat_object.mover_of().last_movement_update_tick
            if utolso is None or utolso.lags_by(self.tick, self.HEARTBEAT_INTERVAL_SECONDS):
                if heart_beat_object.mover_of().frame_tick is None:
                    continue
                heart_beat_object.mover_of().note_movement_tick(ora_masolat)
                try:
                    bws.append(self._space_replies.sync_move(heart_beat_object))
                except ValueError:
                    log.exception('inside the movement stage ')

        self._sender.push_to_everyone(bws)
        movement_packet_count = len(bws)
        self._last_stats = {
            "has_clients": 1,
            "objects": object_count,
            "movement_packets": movement_packet_count,
        }
        if (should_warn_count(movement_packet_count, SECTOR_MOVEMENT_PACKET_WARN_COUNT)
            and should_warn_interval(self._last_warn_ms, SECTOR_TIMER_WARN_INTERVAL_MS)):
            self._last_warn_ms = now_ms()
            log.warning(
                "High movement heartbeat broadcast objects=%s movement_packets=%s threshold=%s",
                object_count,
                movement_packet_count,
                SECTOR_MOVEMENT_PACKET_WARN_COUNT,
            )

    def last_stats(self) -> dict:
        return dict(self._last_stats)


class AnnounceRounds(AfterDelay, DepartureWatcher):
    TIME_DELAY = sector_event_terms().announce_interval_ms
    ERDEMI_SEB = sector_event_terms().announce_min_damage

    def __init__(self, tick, sector_objects, utem_ora, announcer, damage_log,
                 szektor_kartyak):
        super().__init__(tick, sector_objects, utem_ora)
        self._announcer = announcer
        self._damage_log = damage_log
        self._sector_cards = szektor_kartyak
        self._last_damage_record_for_notification = {}
        self._last_notification_update = {}

    def on_due(self) -> None:
        outposts = self.sector_objects.objects_of_kind(ObjectKind.Outpost)
        mining_ships = self.sector_objects.objects_of_kind(ObjectKind.MiningShip)

        for outpost in outposts:
            self._notify(outpost)
        for mining_ship in mining_ships:
            self._notify(mining_ship)

    def _notify(self, space_object) -> None:
        entity_type = space_object.space_entity_type
        if entity_type == ObjectKind.Outpost:
            self._notify_outpost(space_object)
        elif entity_type == ObjectKind.MiningShip:
            self._notify_mining_ship(space_object)

    def _notify_mining_ship(self, mining_ship) -> None:
        if not mining_ship.space_subscribe_info().is_in_combat:
            return
        tortenet = self._damage_log.damage_history(mining_ship)
        if tortenet is None or tortenet.last_damage is None:
            return

        vegzetes = tortenet.kill_shot_dealer() is not None

        def kiadhato(kulcs):
            return vegzetes or kulcs.mining_attack_kind() != MinerAlarm.ShipDrivenOff

        self._riasztas(mining_ship, tortenet.last_damage, kiadhato)

    def _notify_outpost(self, outpost) -> None:
        allapot = outpost.space_subscribe_info()
        if not allapot.is_in_combat:
            return
        plafon = allapot.stat(ObjectStat.MaxHullPoints)
        if allapot.hp > plafon - self.ERDEMI_SEB:
            return

        tortenet = self._damage_log.damage_history(outpost)
        if tortenet is None:
            return
        utolso_jatekostol = tortenet.last_damage_by_player()
        if utolso_jatekostol is None \
                and self._last_damage_record_for_notification.get(outpost.id_in_space()) is None:
            return

        self._riasztas(outpost, utolso_jatekostol)

    def _riasztas(self, space_object, mit_jegyezzunk, kiadhato=None) -> None:
        azonosito = space_object.id_in_space()
        legutobb = self._last_damage_record_for_notification.get(azonosito)
        kulcs = self._announcer.notification_key(space_object)

        uj_hir = legutobb is None or kulcs != self._last_notification_update.get(azonosito)
        if not uj_hir and (legutobb.time_stamp() + self.TIME_DELAY) >= self.tick.time_stamp():
            return
        if kiadhato is not None and not kiadhato(kulcs):
            return

        self._announcer.cry_attack(
            kulcs, self._sector_cards.sector_card.card_guid_of())
        self._last_damage_record_for_notification[azonosito] = mit_jegyezzunk
        self._last_notification_update[azonosito] = kulcs

    def on_update(self, arg) -> None:
        self._notify(arg.departed_object)

        self._last_notification_update.pop(arg.departed_object.id_in_space(), None)
        self._last_damage_record_for_notification.pop(arg.departed_object.id_in_space(), None)


_NPC_TARGET_SPATIAL_INDEX_MAX_CELLS_PER_OBJECT = _CONFIG.int(
    "rebsgo.sector.spatial-index.npc-targeting-max-cells-per-object", 512)
_SELF_ABILITY_ACTIONS = sector_rules(ObjectKind, AbilityActionKind).npc_self_abilities
_ENEMY_ABILITY_ACTIONS = sector_rules(ObjectKind, AbilityActionKind).npc_enemy_abilities
_DIAG_LOGGED_ACTIONS: set = set()


class NpcRounds(AfterDelay):
    def __init__(self, tick, sector_objects, utem_ora: int,
                 cast_desk, damage_log, szektor_kartyak):
        super().__init__(tick, sector_objects, utem_ora)
        self.cast_desk = cast_desk
        self.damage_log = damage_log
        self.sector_cards = szektor_kartyak
        self._target_cycle_candidates = None
        self._target_cycle_spatial_index = None
        self._targeting_trail = {}
        self._last_target_scan_warn_ms = 0.0
        self._target_cycle_stats = None
        self._last_stats = {
            "candidate_objects": 0,
            "npc_queries": 0,
            "relation_checks": 0,
            "cloak_checks": 0,
            "enemy_candidates": 0,
            "distance_checks": 0,
            "damage_history_checks": 0,
            "targets_found": 0,
            "spatial_enabled": 0,
            "spatial_cells": 0,
            "spatial_queries": 0,
            "spatial_candidates": 0,
            "native_relation_prefilter_used": 0,
            "native_relation_prefilter_candidates": 0,
            "native_relation_prefilter_matches": 0,
            "target_cache_hits": 0,
            "target_cache_misses": 0,
            "target_phase_skips": 0,
        }

    def _begin_targeting_cycle(self) -> None:
        jeloltek = tuple(self._iter_target_candidate_objects())
        self._target_cycle_candidates = jeloltek
        spatial_index = self._build_target_spatial_index(jeloltek)
        self._target_cycle_spatial_index = spatial_index
        spatial_stats = spatial_index.stats if spatial_index is not None else None
        self._target_cycle_stats = {
            "candidate_objects": len(jeloltek),
            "npc_queries": 0,
            "relation_checks": 0,
            "cloak_checks": 0,
            "enemy_candidates": 0,
            "distance_checks": 0,
            "damage_history_checks": 0,
            "targets_found": 0,
            "spatial_enabled": 1 if spatial_index is not None else 0,
            "spatial_cells": spatial_stats.cells if spatial_stats is not None else 0,
            "spatial_queries": 0,
            "spatial_candidates": 0,
            "native_relation_prefilter_used": 0,
            "native_relation_prefilter_candidates": 0,
            "native_relation_prefilter_matches": 0,
            "target_cache_hits": 0,
            "target_cache_misses": 0,
            "target_phase_skips": 0,
        }

    def _end_targeting_cycle(self, timer_name: str) -> None:
        mutatok = self._target_cycle_stats
        if mutatok is None:
            return
        self._last_stats = dict(mutatok)
        scan_checks = mutatok.get("relation_checks", 0) + mutatok.get("distance_checks", 0)
        if (should_warn_count(scan_checks, SECTOR_NPC_TARGET_SCAN_WARN_CHECKS)
            and should_warn_interval(self._last_target_scan_warn_ms, SECTOR_TIMER_WARN_INTERVAL_MS)):
            self._last_target_scan_warn_ms = now_ms()
            log.warning(
                "High NPC target scan timer=%s candidates=%s npc_queries=%s relation_checks=%s "
                "cloak_checks=%s enemy_candidates=%s distance_checks=%s damage_history_checks=%s "
                "targets_found=%s threshold=%s",
                timer_name,
                mutatok.get("candidate_objects", 0),
                mutatok.get("npc_queries", 0),
                mutatok.get("relation_checks", 0),
                mutatok.get("cloak_checks", 0),
                mutatok.get("enemy_candidates", 0),
                mutatok.get("distance_checks", 0),
                mutatok.get("damage_history_checks", 0),
                mutatok.get("targets_found", 0),
                SECTOR_NPC_TARGET_SCAN_WARN_CHECKS,
            )
        self._target_cycle_candidates = None
        self._target_cycle_spatial_index = None
        self._targeting_trail = {}
        self._target_cycle_stats = None

    def _record_targeting_stat(self, key: str, increment: int = 1) -> None:
        if (mutatok := getattr(self, '_target_cycle_stats', None)) is not None:
            mutatok[key] = mutatok.get(key, 0) + increment

    def last_stats(self) -> dict:
        return dict(getattr(self, "_last_stats", {}))

    def _update_weapons(self, ship, legkozelebbi) -> None:
        rekeszek = ship.space_subscribe_info().ship_slots
        if rekeszek is None:
            return
        for rekesz in rekeszek.values():
            if rekesz.ship_slot_card().ship_slot_type != ShipSlotType.weapon:
                continue
            if rekesz.ship_system is None or rekesz.ship_ability() is None:
                continue
            if legkozelebbi is None:
                self.cast_desk.disarm_auto_cast(
                    rekesz.ship_system.server_id, ship.id_in_space())
                continue
            self.cast_desk.arm_auto_cast(CastOrder(
                ship,
                rekesz.ship_system.server_id,
                True,
                legkozelebbi.id_in_space()))

    def _update_abilities(self, ship, legkozelebbi) -> None:
        rekeszek = ship.space_subscribe_info().ship_slots
        if rekeszek is None:
            return
        for rekesz in rekeszek.values():
            if rekesz.ship_slot_card().ship_slot_type == ShipSlotType.weapon:
                continue
            rendszer = rekesz.ship_system
            kepesseg = rekesz.ship_ability()
            if rendszer is None or kepesseg is None:
                continue
            action_type = kepesseg.ship_ability_card.ability_action_type
            if action_type not in _DIAG_LOGGED_ACTIONS:
                _DIAG_LOGGED_ACTIONS.add(action_type)
                log.info("NPC non-weapon ability carried: action_type=%s cooldown=%s system=%s",
                         action_type,
                         kepesseg.item_buff_add.stat(ObjectStat.Cooldown),
                         rendszer.ship_system_card.card_guid_of())
            if action_type in _SELF_ABILITY_ACTIONS:
                target_id = ship.id_in_space()
            elif action_type in _ENEMY_ABILITY_ACTIONS:
                if legkozelebbi is None:
                    self.cast_desk.disarm_auto_cast(
                        rendszer.server_id, ship.id_in_space())
                    continue
                target_id = legkozelebbi.id_in_space()
            else:
                continue
            self.cast_desk.arm_auto_cast(CastOrder(
                ship,
                rendszer.server_id,
                True,
                target_id))

    def _worst_aggressor(self, bot_fighter):
        object_history = self.damage_log.damage_history(bot_fighter)
        if object_history is None:
            return None
        max_aggro_distance = bot_fighter.behaviour_template.aggro_reach
        max_aggro_distance_sq = f32(max_aggro_distance * max_aggro_distance)
        bot_position = bot_fighter.mover_of().position_of()
        for highest_damage_done in list(object_history.by_damage_dealt):
            self._record_targeting_stat("damage_history_checks")
            if not (highest_damage_done.damage_so_far > 0):
                break

            dealer = highest_damage_done.dealer
            if dealer.removal_cause_of() is not None:
                object_history.forget_dealer(highest_damage_done)
                continue

            if self._is_cloaked_for_npc_targeting(bot_fighter, dealer):
                if log.isEnabledFor(logging.DEBUG):
                    log.debug("targeting: #%s passes over aggressor #%s: cloaked",
                              bot_fighter.id_in_space(), dealer.id_in_space())
                continue

            distance_sq = bot_position.sq_distance_to(dealer.mover_of().position_of())
            self._record_targeting_stat("distance_checks")
            if distance_sq > max_aggro_distance_sq:
                if log.isEnabledFor(logging.DEBUG):
                    log.debug("targeting: #%s drops aggressor #%s: %.0fm beyond"
                              " the %.0fm aggro reach (grudge forgotten)",
                              bot_fighter.id_in_space(), dealer.id_in_space(),
                              distance_sq ** 0.5, max_aggro_distance)
                object_history.forget_dealer(highest_damage_done)
                continue

            self._record_targeting_stat("targets_found")
            return dealer

        return None

    def _pick_target(self, bot):
        celpont = self._worst_aggressor(bot)
        if celpont is not None:
            self._log_targeting(bot, celpont, "retaliation: damage leader in reach")
            return celpont
        celpont = self._enemy_within_auto_aggro(bot)
        if celpont is not None:
            self._log_targeting(bot, celpont, "auto-aggro: hostile inside reach")
            return celpont

        if bot.wants_kills():
            kill_objective = next(
                (o for o in bot.npc_objectives if o.type == NpcGoalKind.Kill), None)
            if kill_objective is not None:
                celpont = kill_objective.objectives_to_kill[0]
                if not self._is_cloaked_for_npc_targeting(bot, celpont):
                    self._log_targeting(bot, celpont, "kill objective")
                    return celpont
        if log.isEnabledFor(logging.DEBUG):
            self._log_targeting(bot, None, self._why_no_target(bot))
        return None

    def _log_targeting(self, bot, celpont, ok: str) -> None:
        if not log.isEnabledFor(logging.DEBUG):
            if self._targeting_trail:
                self._targeting_trail.clear()
            return
        cel_id = None if celpont is None else celpont.id_in_space()
        elozo = self._targeting_trail.get(bot.id_in_space())
        if elozo == (cel_id, ok):
            return
        self._targeting_trail[bot.id_in_space()] = (cel_id, ok)
        kartya = getattr(bot, "ship_card_of", lambda: None)()
        log.debug("targeting: %s#%s (%s) -> %s | %s",
                  bot.space_entity_type.name, bot.id_in_space(),
                  kartya.card_guid_of() if kartya is not None else "?",
                  "none" if cel_id is None else f"#{cel_id}", ok)

    def _why_no_target(self, bot) -> str:
        bot_position = bot.mover_of().position_of()
        legkozelebbi, tavolsag = None, None
        for jelolt in self._hostiles_near(bot, None):
            if jelolt.id_in_space() == bot.id_in_space():
                continue
            d = bot_position.sq_distance_to(jelolt.mover_of().position_of()) ** 0.5
            if tavolsag is None or d < tavolsag:
                legkozelebbi, tavolsag = jelolt, d
        if legkozelebbi is None:
            return "no target: no hostile anywhere in the sector"
        reach = bot.behaviour_template.auto_aggro_distance
        sav = int(tavolsag // 500) * 500
        return (f"no target: nearest hostile #{legkozelebbi.id_in_space()}"
                f" ~{sav}-{sav + 500}m, auto-aggro reach {reach:.0f}m")

    def _enemy_within_auto_aggro(self, bot_fighter):
        auto_aggro_reach = bot_fighter.behaviour_template.auto_aggro_distance
        bot_position = bot_fighter.mover_of().position_of()
        potential_enemy_objects = self._hostiles_near(bot_fighter, auto_aggro_reach)
        celpont = nearest_radius_candidate(
            potential_enemy_objects,
            bot_position,
            auto_aggro_reach,
            stats=self._target_cycle_stats,
        )
        if celpont is not None:
            self._record_targeting_stat("targets_found")
        return celpont

    def _iter_target_candidate_objects(self):
        stream = getattr(self.sector_objects, "objects_other_than", None)
        yield from (
            stream(ObjectKind.Missile, ObjectKind.Planetoid, ObjectKind.Asteroid, ObjectKind.Planet)
            if stream is not None else
            self.sector_objects.space_objects_not_of_entity_type(
                ObjectKind.Missile, ObjectKind.Planetoid, ObjectKind.Asteroid, ObjectKind.Planet)
        )

    def _hostiles_near(self, against, query_radius=None):
        self._record_targeting_stat("npc_queries")
        target_bracket_mode = self.sector_cards.regulation_card().target_bracket_mode
        potential_objects = self._prefilter_possible_enemy_objects(
            self._scan_candidates(against, query_radius),
            against,
            target_bracket_mode,
        )
        for space_object in potential_objects:
            if space_object.id_in_space() == against.id_in_space():
                continue
            if isinstance(space_object, PlayerShip):
                self._record_targeting_stat("cloak_checks")
                if not space_object.is_visible():
                    continue
                if self._is_cloaked_for_npc_targeting(against, space_object):
                    continue
            self._record_targeting_stat("relation_checks")
            viszony = relation(
                space_object, against, target_bracket_mode)
            if viszony != Stance.Enemy:
                continue
            self._record_targeting_stat("enemy_candidates")
            yield space_object

    def _prefilter_possible_enemy_objects(self, potential_objects, against, target_bracket_mode):
        jeloltek = tuple(potential_objects)
        if not jeloltek:
            return jeloltek
        try:
            feljegyzesek = [
                (
                    jelolt.id_in_space(),
                    jelolt.faction.value,
                    jelolt.faction_group.value,
                )
                for jelolt in jeloltek
            ]
            native_will_run = should_use_native_relation_prefilter(len(feljegyzesek))
            allowed_ids = set(filter_possible_enemy_ids(
                feljegyzesek,
                against.id_in_space(),
                against.faction.value,
                against.faction_group.value,
                target_bracket_mode == TargetBracketMode.AllEnemy,
            ))
            self._record_targeting_stat("native_relation_prefilter_used", 1 if native_will_run else 0)
            self._record_targeting_stat("native_relation_prefilter_candidates", len(feljegyzesek))
            self._record_targeting_stat("native_relation_prefilter_matches", len(allowed_ids))
            return tuple(jelolt for jelolt in jeloltek if jelolt.id_in_space() in allowed_ids)
        except Exception:
            log.exception("NPC relation prefilter failed; falling back to Python relation scan")
            return jeloltek

    def _scan_candidates(self, against, query_radius):
        spatial_index = getattr(self, "_target_cycle_spatial_index", None)
        if spatial_index is not None and query_radius is not None:
            against_position = against.mover_of().position_of()
            potential_objects = getattr(self, "_target_cycle_candidates", None)
            if potential_objects is not None:
                return ordered_radius_candidates(
                    potential_objects,
                    spatial_index,
                    against_position,
                    query_radius,
                    stats=self._target_cycle_stats,
                )
            jeloltek = spatial_index.query_radius(against_position, query_radius)
            self._record_targeting_stat("spatial_queries")
            self._record_targeting_stat("spatial_candidates", len(jeloltek))
            return jeloltek
        potential_objects = getattr(self, "_target_cycle_candidates", None)
        if potential_objects is None:
            potential_objects = self._iter_target_candidate_objects()
        return potential_objects

    @staticmethod
    def _build_target_spatial_index(candidates):
        if (not _NPC_TARGET_SPATIAL_INDEX_ENABLED
            or len(candidates) < _NPC_TARGET_SPATIAL_INDEX_MIN_OBJECTS):
            return None
        try:
            sorszam = UniformGridSpatialIndex(
                _NPC_TARGET_SPATIAL_INDEX_CELL_SIZE,
                _NPC_TARGET_SPATIAL_INDEX_MAX_CELLS_PER_OBJECT,
            )
            sorszam.rebuild(candidates)
            if sorszam.stats.indexed_objects != len(candidates):
                return None
            return sorszam
        except Exception:
            log.exception("NPC target spatial index build failed; falling back to the plain sweep")
            return None

    @staticmethod
    def _is_cloaked_for_npc_targeting(observer_ship, target) -> bool:
        if not isinstance(target, PlayerShip):
            return False
        return is_cloaked_outside_visual_detection(observer_ship, target)


_outpost_beacon_timer_config = None
_ARRIVAL_ATTEMPTS = world_timers().arrival_attempts
_ARRIVAL_RESERVATION_SECONDS = world_timers().arrival_reservation_seconds
_ARRIVAL_OBSTACLE_BUFFER = world_timers().arrival_obstacle_buffer
_ARRIVAL_OBSTACLE_TYPES = (ObjectKind.Outpost, ObjectKind.WeaponPlatform)


def _beacon_settings():
    global _outpost_beacon_timer_config
    if _outpost_beacon_timer_config is None:
        from rebsgo.gamedata.from_json.template_readers import OutpostBeaconTemplateReader
        _outpost_beacon_timer_config = OutpostBeaconTemplateReader().fetch()
    return _outpost_beacon_timer_config


class OutpostBeaconTimer(WatchStep):
    def __init__(self, sector_objects, outpost_scoreboard, takarito,
                 factory, arrival_gate, sector_desc, map_card):
        super().__init__(sector_objects)
        self._outpost_scoreboard = outpost_scoreboard
        self._remover = takarito
        self._factory = factory
        self._join_queue = arrival_gate
        self._sector_desc = sector_desc
        self._star = None if map_card is None else map_card.star(sector_desc.sector_id)
        self._cfg = _beacon_settings()
        self._alive: dict = {}
        self._downed_at: dict = {}
        self._random = Dice()
        self._arrival_reservations = []

    def run(self) -> None:
        if self._cfg.empty:
            return
        for frakcio, allapot in ((Faction.Colonial, self._outpost_scoreboard.colonial_outpost_state),
                               (Faction.Cylon, self._outpost_scoreboard.cylon_outpost_state)):
            try:
                self._update_faction(frakcio, allapot)
            except Exception:
                log.exception("outpost beacon update failed for %s", frakcio)

    def is_beacon_active(self, faction) -> bool:
        return self._active_beacon(faction) is not None

    def arrival_transform_for(self, faction, player_id: int):
        beacon = self._active_beacon(faction)
        if beacon is None:
            return None
        base = beacon.mover_of().position_of()
        sugar = max(0.0, self._cfg.arrival_radius)
        helyzet, szog = self._random_arrival_position(base, sugar, player_id)
        self._arrival_reservations.append((time.monotonic(), int(player_id), helyzet))
        return Transform(helyzet, Euler3(0.0, math.degrees(szog) % 360.0, 0.0))

    def _random_arrival_position(self, base, radius: float, player_id: int):
        self._prune_arrival_reservations()
        if radius <= 0.0:
            return Vector3(base.x, base.y, base.z), 0.0

        min_distance = max(75.0, min(150.0, radius * 0.2))
        min_distance_sq = min_distance * min_distance
        best_position = None
        best_angle = 0.0
        best_clearance_sq = -1.0

        for _ in range(_ARRIVAL_ATTEMPTS):
            szog = self._random.between_fine(0.0, math.tau)
            tavolsag = math.sqrt(self._random.fine()) * radius
            helyzet = Vector3(
                base.x + tavolsag * math.cos(szog),
                base.y,
                base.z + tavolsag * math.sin(szog))
            if self._arrival_hits_static_defense(helyzet):
                continue
            clearance_sq = self._arrival_clearance_sq(helyzet, player_id)
            if clearance_sq >= min_distance_sq:
                return helyzet, szog
            if clearance_sq > best_clearance_sq:
                best_position = helyzet
                best_angle = szog
                best_clearance_sq = clearance_sq

        if best_position is None:
            return Vector3(base.x, base.y, base.z), 0.0
        return best_position, best_angle

    def _arrival_hits_static_defense(self, position) -> bool:
        for obj in self.sector_objects.space_objects_of_entity_types(*_ARRIVAL_OBSTACLE_TYPES):
            if obj.is_removed() or not obj.carries_collider:
                continue
            kozeppont, sugar = self._horizontal_collider_bounds(obj.collider_of())
            if kozeppont is None:
                continue
            if self._arrival_distance_sq(position, kozeppont) <= (sugar + _ARRIVAL_OBSTACLE_BUFFER) ** 2:
                return True
        return False

    @staticmethod
    def _horizontal_collider_bounds(collider):
        collider.sync_to_transform()
        if isinstance(collider, SphereCollider):
            return collider.center_point(), collider.radius_of()
        if isinstance(collider, CapsuleCollider):
            a = collider.end_a()
            b = collider.end_b()
            kozeppont = Vector3((a.x + b.x) * 0.5, (a.y + b.y) * 0.5, (a.z + b.z) * 0.5)
            segment_radius = math.sqrt(OutpostBeaconTimer._arrival_distance_sq(kozeppont, a))
            return kozeppont, segment_radius + collider.radius_of()
        if isinstance(collider, BoxCollider):
            kozeppont = collider.world_center()
            extents = collider.half_extents_of()
            return kozeppont, math.sqrt(extents.x * extents.x + extents.z * extents.z)
        kozeppont = collider.transform_of().position_of()
        return kozeppont, collider.cover_radius()

    def _arrival_clearance_sq(self, position, player_id: int) -> float:
        nearest_sq = math.inf
        for obj in self.sector_objects.space_objects_of_entity_type(ObjectKind.Pilot):
            if obj.is_removed() or obj.pilot_id() == player_id:
                continue
            other = obj.mover_of().position_of()
            nearest_sq = min(nearest_sq, self._arrival_distance_sq(position, other))
        for _, reserved_player_id, reserved_position in self._arrival_reservations:
            if reserved_player_id == player_id:
                continue
            nearest_sq = min(nearest_sq, self._arrival_distance_sq(position, reserved_position))
        return nearest_sq

    @staticmethod
    def _arrival_distance_sq(a, b) -> float:
        dx = a.x - b.x
        dz = a.z - b.z
        return dx * dx + dz * dz

    def _prune_arrival_reservations(self) -> None:
        expires_before = time.monotonic() - _ARRIVAL_RESERVATION_SECONDS
        self._arrival_reservations = [
            reservation for reservation in self._arrival_reservations
            if reservation[0] >= expires_before
        ]

    def _update_faction(self, faction, state) -> None:
        if not self._should_be_active(faction, state):
            self._despawn(faction)
            return
        if self._active_beacon(faction) is None and not self._still_down(faction):
            self._spawn_beacon(faction)

    def _still_down(self, faction) -> bool:
        mikor = self._downed_at.get(faction)
        if mikor is None:
            return False
        if time.monotonic() - mikor >= self._cfg.respawn_delay_seconds:
            self._downed_at.pop(faction, None)
            return False
        return True

    def _should_be_active(self, faction, state) -> bool:
        if faction not in self._cfg.beacons_by_faction:
            return False
        if not self._star_allows_beacon(faction):
            return False
        if self._outpost_of(faction) is None:
            return False
        readiness = state.op_points / 9.0
        return readiness >= self._cfg.min_readiness

    def _star_allows_beacon(self, faction) -> bool:
        if self._star is None:
            return False
        if faction == Faction.Colonial:
            return bool(self._star.can_colonial_jump_beacon)
        if faction == Faction.Cylon:
            return bool(self._star.can_cylon_jump_beacon)
        return False

    def _outpost_of(self, faction):
        for obj in self.sector_objects.space_objects_of_entity_type(ObjectKind.Outpost):
            if obj.faction == faction and not obj.is_removed():
                return obj
        return None

    def _active_beacon(self, faction):
        object_id = self._alive.get(faction)
        if object_id is None:
            return None
        obj = self.sector_objects.get(object_id)
        if obj is not None and not obj.is_removed():
            return obj
        self._alive.pop(faction, None)
        self._downed_at[faction] = time.monotonic()
        log.info("Outpost jump beacon lost: sector=%s faction=%s - no new one for %ss",
                 self._sector_desc.sector_id, faction, int(self._cfg.respawn_delay_seconds))
        return None

    def _spawn_beacon(self, faction) -> None:
        outpost = self._outpost_of(faction)
        if outpost is None:
            return
        beacon_def = self._cfg.beacons_by_faction.get(faction)
        if beacon_def is None:
            return
        kozeppont = outpost.mover_of().position_of()
        szog = math.radians(beacon_def.angle_degrees)
        helyzet = Vector3(
            kozeppont.x + self._cfg.spawn_radius * math.cos(szog),
            kozeppont.y + self._cfg.vertical_offset,
            kozeppont.z + self._cfg.spawn_radius * math.sin(szog))
        forgatas = Euler3(0.0, beacon_def.angle_degrees % 360.0, 0.0)
        try:
            beacon = self._factory.create_jump_beacon(
                beacon_def.card_guid, faction, Transform(helyzet, forgatas))
        except Exception:
            log.exception("could not spawn outpost jump beacon guid=%s faction=%s",
                          beacon_def.card_guid, faction)
            return
        self._join_queue.admit_object(beacon)
        self._alive[faction] = beacon.id_in_space()
        log.info("Outpost jump beacon spawned: sector=%s faction=%s object_id=%s",
                 self._sector_desc.sector_id, faction, beacon.id_in_space())

    def _despawn(self, faction) -> None:
        if (obj := self._active_beacon(faction)) is not None:
            self._remover.note_removal_cause(obj, DepartureCause.JustRemoved)
            log.info("Outpost jump beacon removed: sector=%s faction=%s object_id=%s",
                     self._sector_desc.sector_id, faction, obj.id_in_space())
        self._alive.pop(faction, None)


_BASE_READINESS_PERCENT_PER_MINUTE = readiness_terms().base_percent_per_minute
_READINESS_PLAYER_STEP = readiness_terms().per_extra_pilot


class ReadinessDrain(WatchStep):
    def __init__(self, tick, sector_objects, keses_ora: int, outpost_scoreboard, pilotak, sender,
                 decrease_delay_ticks: int | None = None):
        super().__init__(sector_objects)
        self.tick = tick
        self._outpost_scoreboard = outpost_scoreboard
        self._users = pilotak
        self._sender = sender
        self._space_replies = game_replies()
        self._decrease_delay_ticks = keses_ora if decrease_delay_ticks is None else decrease_delay_ticks
        self._last_decrease_tick = tick.copy()

    def run(self) -> None:
        if self._needs_decrease():
            self._auto_decrease(self._outpost_scoreboard.colonial_outpost_state, Faction.Colonial)
            self._auto_decrease(self._outpost_scoreboard.cylon_outpost_state, Faction.Cylon)
        self._auto_increase_from_player_presence(self._outpost_scoreboard.colonial_outpost_state, Faction.Colonial)
        self._auto_increase_from_player_presence(self._outpost_scoreboard.cylon_outpost_state, Faction.Cylon)
        if self._sender.has_clients():
            colonial_delta = self._outpost_scoreboard.colonial_outpost_state.delta()
            cylon_delta = self._outpost_scoreboard.cylon_outpost_state.delta()
            self._sender.push_to_everyone(
                self._space_replies.outpost_state_broadcast(
                    self._outpost_scoreboard.colonial_outpost_state.op_points,
                    colonial_delta,
                    self._outpost_scoreboard.cylon_outpost_state.op_points,
                    cylon_delta))


    def _needs_decrease(self) -> bool:
        tick_delta = self.tick.value - self._last_decrease_tick.value
        if tick_delta < self._decrease_delay_ticks:
            return False
        self._last_decrease_tick = self.tick.copy()
        return True

    def _auto_decrease(self, op, faction) -> None:
        if self._outpost_scoreboard is None:
            return
        op_progress_template = self._outpost_scoreboard.template_from_faction(faction)
        if op_progress_template is None:
            return
        op.lose_points(op_progress_template.pts_drain_per_second)

    def _auto_increase_from_player_presence(self, op, faction) -> None:
        if self._outpost_scoreboard is None or not op.can_outpost:
            return
        player_count = self._count_active_player_ships(faction)
        if player_count <= 0:
            return
        op.increase_readiness_percent(_readiness_percent_per_minute(player_count))

    def _count_active_player_ships(self, faction) -> int:
        return sum(
            1
            for obj in self.sector_objects.objects_of_kind(ObjectKind.Pilot)
            if obj.faction == faction and not obj.is_removed())


def _readiness_percent_per_minute(player_count: int) -> float:
    if player_count <= 0:
        return 0.0
    return _BASE_READINESS_PERCENT_PER_MINUTE + _READINESS_PLAYER_STEP * (player_count - 1)


class OutpostRepair(WatchStep):
    def __init__(self, sector_objects, galaxis_szorzo):
        super().__init__(sector_objects)
        self._galaxy_bonus = galaxis_szorzo

    def run(self) -> None:
        colo_op_bonus = self._galaxy_bonus.colo_op_bonus
        cylo_op_bonus = self._galaxy_bonus.cylo_op_bonus

        outposts = self.sector_objects.objects_of_kind(ObjectKind.Outpost)
        for outpost in outposts:
            bonus_to_use = colo_op_bonus if outpost.faction == Faction.Colonial else cylo_op_bonus
            stats_info = outpost.space_subscribe_info()
            mod_stats = stats_info.modified_for_stats_buff
            old = mod_stats.stat_or_default(ObjectStat.MaxHullPoints)
            if old == bonus_to_use:
                continue

            mod_stats.set_stat(ObjectStat.MaxHullPoints, bonus_to_use)
            stats_info.fold_in_stats()


_outpost_platform_timer_config = None


def _platform_settings():
    global _outpost_platform_timer_config
    if _outpost_platform_timer_config is None:
        from rebsgo.gamedata.from_json.template_readers import OutpostPlatformTemplateReader
        _outpost_platform_timer_config = OutpostPlatformTemplateReader().fetch()
    return _outpost_platform_timer_config


class OutpostPlatformTimer(WatchStep):
    def __init__(self, tick, sector_objects, outpost_scoreboard, takarito,
                 factory, arrival_gate):
        super().__init__(sector_objects)
        self._outpost_scoreboard = outpost_scoreboard
        self._remover = takarito
        self._factory = factory
        self._join_queue = arrival_gate
        self._cfg = _platform_settings()
        self._tick = tick
        self._alive: dict[tuple, list] = {}
        self._pending: dict[tuple, list] = {}
        self._active_by_faction: dict = {}

    def run(self) -> None:
        if self._cfg.empty:
            return
        for frakcio, allapot in ((Faction.Colonial, self._outpost_scoreboard.colonial_outpost_state),
                               (Faction.Cylon, self._outpost_scoreboard.cylon_outpost_state)):
            try:
                self._update_faction(frakcio, allapot)
            except Exception:
                log.exception("outpost platform update failed for %s", frakcio)

    def _outpost_of(self, faction):
        for obj in self.sector_objects.space_objects_of_entity_type(ObjectKind.Outpost):
            if obj.faction == faction and not obj.is_removed():
                return obj
        return None

    def _tier_def(self, tier_name):
        for t in self._cfg.tiers:
            if t[0] == tier_name:
                return t
        return None

    def _update_faction(self, faction, state) -> None:
        guids_by_tier = self._cfg.platforms_by_faction.get(faction)
        if guids_by_tier is None:
            return
        outpost = self._outpost_of(faction)
        readiness = state.op_points / 9.0
        active_tier = None
        if outpost is not None:
            for tier_name, threshold, count, sugar in reversed(self._cfg.tiers):
                if readiness >= threshold:
                    active_tier = tier_name
                    break

        for tier_name, threshold, count, sugar in self._cfg.tiers:
            if tier_name != active_tier:
                self._despawn((faction, tier_name))

        prev_active = self._active_by_faction.get(faction)
        self._active_by_faction[faction] = active_tier
        if active_tier is None:
            return

        kulcs = (faction, active_tier)
        _, _, count, sugar = self._tier_def(active_tier)
        guid = guids_by_tier[active_tier]
        most = self._tick.time_stamp()

        if prev_active != active_tier:
            self._pending[kulcs] = []
            self._alive[kulcs] = []
            self._spawn_platforms(faction, outpost, active_tier, guid, count, sugar, count)
            return

        alive = [oid for oid in self._alive.get(kulcs, []) if self._is_alive(oid)]
        self._alive[kulcs] = alive
        pending = self._pending.get(kulcs, [])
        deficit = count - len(alive) - len(pending)
        for _ in range(max(0, deficit)):
            pending.append(most + self._cfg.respawn_delay_seconds * 1000)
        kesz = [t for t in pending if t <= most]
        if kesz:
            self._spawn_platforms(faction, outpost, active_tier, guid, count, sugar, len(kesz))
        self._pending[kulcs] = [t for t in pending if t > most]

    def _is_alive(self, object_id: int) -> bool:
        obj = self.sector_objects.get(object_id)
        return obj is not None and not obj.is_removed()

    def _spawn_platforms(self, faction, outpost, tier_name, guid, count, radius, how_many) -> None:
        if outpost is None or how_many <= 0:
            return
        kozeppont = outpost.mover_of().position_of()
        kulcs = (faction, tier_name)
        alive = self._alive.setdefault(kulcs, [])
        tier_offset = {"medium": 0.4, "heavy": 0.8}.get(tier_name, 0.0)
        for _ in range(how_many):
            rekesz = len(alive) % count
            szog = 2 * math.pi * rekesz / count + tier_offset
            helyzet = Vector3(kozeppont.x + radius * math.cos(szog),
                              kozeppont.y + (60 if rekesz % 2 == 0 else -60),
                              kozeppont.z + radius * math.sin(szog))
            sablon = WeaponPlatformSpec(
                guid, ObjectKind.WeaponPlatform, ArrivalCause.JumpIn, 0, False,
                helyzet, Euler3(0.0, math.degrees(szog) % 360.0, 0.0), 1200.0, 2200.0, faction, [])
            try:
                platform = self._factory.hatch_platform(sablon)
            except Exception:
                log.exception("could not spawn %s outpost platform guid=%s", tier_name, guid)
                continue
            self._grant_ring_regeneration(platform)
            self._join_queue.admit_object(platform)
            alive.append(platform.id_in_space())
        log.info("Outpost platforms: %s %s now %s/%s", faction, tier_name, len(alive), count)

    def _grant_ring_regeneration(self, platform) -> None:
        resz = self._cfg.hull_recovery_percent_per_sec
        if resz <= 0:
            return
        mutatok = platform.space_subscribe_info()
        plafon = mutatok.stat_or_default(ObjectStat.MaxHullPoints)
        if plafon <= 0:
            return
        mutatok.stats_of.set_stat(ObjectStat.HullRecovery, f32(plafon * resz / 100.0))

    def _despawn(self, key) -> None:
        for object_id in self._alive.get(key, []):
            obj = self.sector_objects.get(object_id)
            if obj is not None and not obj.is_removed():
                self._remover.note_removal_cause(obj, DepartureCause.JumpOut)
        if self._alive.get(key):
            log.info("Outpost defense ring down: %s %s", key[0], key[1])
        self._alive[key] = []
        self._pending[key] = []


class OutpostArrivals(WatchStep):
    def __init__(self, sector_objects, outpost_scoreboard, takarito, factory,
                 arrival_gate, sector_desc):
        super().__init__(sector_objects)
        self._outpost_scoreboard = outpost_scoreboard
        self._remover = takarito
        self._factory = factory
        self._join_queue = arrival_gate
        self._sector_desc = sector_desc

    def run(self) -> None:
        current_outposts = self.sector_objects.space_objects_of_entity_type(ObjectKind.Outpost)
        oldalak = ((Faction.Colonial, self._outpost_scoreboard.colonial_outpost_state),
                   (Faction.Cylon, self._outpost_scoreboard.cylon_outpost_state))

        if not current_outposts:
            for oldal, _ in oldalak:
                if GalaxyMapCard.is_base_sector(oldal, self._sector_desc.sector_id):
                    self.spawn_op(oldal)
                    break

        for oldal, allapot in oldalak:
            if not allapot.is_outpost:
                self.sweep_away(oldal)
            elif not any(obj.faction == oldal for obj in current_outposts):
                self.spawn_op(oldal)

    def sweep_away(self, faction) -> None:
        if (GalaxyMapCard.is_base_sector(Faction.Colonial, self._sector_desc.sector_id)
            or GalaxyMapCard.is_base_sector(Faction.Cylon, self._sector_desc.sector_id)):
            return
        outposts = self.sector_objects.space_objects_of_entity_type(ObjectKind.Outpost)
        for outpost in outposts:
            if outpost.faction == faction:
                self._remover.note_removal_cause(outpost, DepartureCause.JumpOut)

    def spawn_op(self, faction) -> None:
        with suppress(RuntimeError):
            op = self._factory.hatch_outpost(faction)
            self._join_queue.admit_object(op)


class ComputerCooldown(AfterDelay):
    def __init__(self, tick, sector_objects, utem_ora: int):
        super().__init__(tick, sector_objects, utem_ora)

    def on_due(self) -> None:
        for space_object in self.sector_objects.objects_of_kind(
                ObjectKind.Pilot):
            try:
                mutatok = space_object.space_subscribe_info()
                modifier = mutatok.modifiers
                if modifier is None:
                    continue

                max_hp = mutatok.stat(ObjectStat.MaxHullPoints)
                if max_hp is None:
                    log.error('heal tally could not resolve the hull ceiling')
                    return

                modifiers = modifier
                for stat_key, stat_value in modifiers.strongest_remote_add().items():
                    if stat_key != ObjectStat.HullRecovery:
                        continue
                    new_value = f32(mutatok.hp + stat_value)
                    new_hp = Maths.clamp_safe(new_value, 0, max_hp)
                    mutatok.set_hull(new_hp)
            except Exception:
                log.exception('the heal tally fell over')


_STATE_INACTIVE = 0
_STATE_ACTIVE = 1
_STATE_SUCCESS = 2
_STATE_FAILED = 3
_RANK_BRONZE, _RANK_SILVER, _RANK_GOLD, _RANK_PLATINUM = 1, 2, 3, 4


class _EventConfig:
    def __init__(self, obj: dict):
        self.enabled = bool(obj.get("enabled", False))
        self.auto_disabled_sector_ids = {int(v) for v in obj.get("autoDisabledSectorIds", [])}
        self.interval_seconds = int(obj.get("intervalMinutes", 40)) * 60
        self.duration_seconds = int(obj.get("durationSeconds", 420))
        self.event_card_guid = int(obj.get("eventCardGuid", 0))
        self.state_update_seconds = int(obj.get("stateUpdateSeconds", 5))
        self.convoy_ships = {Faction[k]: int(v) for k, v in obj.get("convoyShips", {}).items()}
        self.attackers = {Faction[k]: [(int(e["guid"]), int(e["ownerGuid"])) for e in v]
                          for k, v in obj.get("attackers", {}).items()}
        self.waves = [(int(w.get("delaySeconds", 0)), int(w.get("count", 3)), int(w.get("gearLevel", 6)))
                      for w in obj.get("waves", [])]
        self.reward_pool = [(int(e["cardGuid"]), int(e["count"])) for e in obj.get("rewardPool", [])]
        self.empty_grace_seconds = int(obj.get("emptyGraceSeconds", 90))
        self.wave_gap_seconds = int(obj.get("waveGapSeconds", 20))
        self.max_alive_npcs = int(obj.get("maxAliveNpcs", 3))
        self.attacker_ratio = max(1, int(obj.get("attackerRatio", 3)))
        self.start_jitter_seconds = max(0, int(obj.get("startJitterMinutes", 20))) * 60
        self.repeat_last_wave = bool(obj.get("repeatLastWave", True))


def _masik_oldal(oldal):
    return Faction.Cylon if oldal == Faction.Colonial else Faction.Colonial


def esemeny_gyoztese(protect_mode: bool, success: bool, convoy_faction):
    gazda_nyert = success if protect_mode else not success
    return gazda_nyert, convoy_faction if gazda_nyert else _masik_oldal(convoy_faction)


def kovetkezo_hullam(hullamok, eddig: int, ellenseg_el: bool, ota_ms: int,
                     szunet_ms: int, ismetelheto: bool):
    if ellenseg_el or ota_ms < szunet_ms:
        return None
    if eddig < len(hullamok):
        return hullamok[eddig], True
    if ismetelheto and hullamok:
        return hullamok[-1], False
    return None


def _load_config():
    olvaso = GameDataLoader(paths.JATEKADAT / "templates" / "Event")
    for utvonal in olvaso.file_paths():
        if utvonal.name != "sector_events.json":
            continue
        if (obj := olvaso.read_json(utvonal)) is not None:
            return _EventConfig(obj)
    return _EventConfig({})


class SectorEventTimer(AfterDelay):
    def __init__(self, ctx, utem_ora: int, takarito, factory, arrival_gate):
        super().__init__(ctx.tick(), ctx.space_objects(), utem_ora)
        self._ctx = ctx
        self._remover = takarito
        self._factory = factory
        self._join_queue = arrival_gate
        self._config = _load_config()
        self._rng = random.Random()
        self._last_event_end_ms = ctx.tick().time_stamp()
        self._kovetkezo_inditas_ms = 0
        self._armed = False
        self._active = False
        self._event_object = None
        self._event_center = None
        self._convoy = None
        self._convoy_faction = None
        self._wave_faction = None
        self._protect_mode = False
        self._players_faction = None
        self._armed_ms = 0
        self._armed_state_sent = False
        self._start_ms = 0
        self._last_state_update_ms = 0
        self._waves_spawned = 0
        self._npc_ids = set()
        self._enemy_npc_ids = set()
        self._last_wave_ms = 0
        self._empty_since_ms = None
        self._kills_by_player = {}
        self._damage_by_player = {}
        self._force_start = False
        self._pending_marker_cleanup = False
        self._auto_start_disabled = self._sector_id() in self._config.auto_disabled_sector_ids
        self._sorsol_kovetkezo_inditast(self._last_event_end_ms)
        if self._auto_start_disabled:
            log.info("Sector event auto-start disabled in sector %s", self._sector_id())

    _TRIGGER_RADIUS = sector_event_terms().trigger_radius
    _ARM_TIMEOUT_SECONDS = sector_event_terms().arm_timeout_seconds
    _WHOIS_SYNC_MS = sector_event_terms().whois_sync_ms

    def _sorsol_kovetkezo_inditast(self, most: int) -> None:
        szoras = self._rng.uniform(0.0, self._config.start_jitter_seconds * 1000.0)
        self._kovetkezo_inditas_ms = most + self._config.interval_seconds * 1000 + szoras

    def force_start(self) -> bool:
        if self._active or self._armed:
            return False
        self._force_start = True
        return True

    @property
    def is_shown(self) -> bool:
        return self._armed or self._active

    def on_update(self, tavozas_leiras) -> None:
        if not self._active:
            return
        removed = tavozas_leiras.departed_object
        if self._convoy is not None and removed.id_in_space() == self._convoy.id_in_space():
            if tavozas_leiras.removal_cause_of() == DepartureCause.Death:
                killer = getattr(tavozas_leiras, "killer_of", lambda: None)()
                if killer is not None and killer.is_player():
                    pid = killer.pilot_id()
                    self._kills_by_player[pid] = self._kills_by_player.get(pid, 0) + 5
                    self._increment_freighters_killed(pid)
                self._finish(success=not self._protect_mode)
            return
        if removed.id_in_space() not in self._npc_ids:
            return
        self._npc_ids.discard(removed.id_in_space())
        self._enemy_npc_ids.discard(removed.id_in_space())
        if tavozas_leiras.removal_cause_of() != DepartureCause.Death:
            return
        killer = getattr(tavozas_leiras, "killer_of", lambda: None)()
        if killer is not None and killer.is_player():
            pid = killer.pilot_id()
            self._kills_by_player[pid] = self._kills_by_player.get(pid, 0) + 1

    def on_due(self) -> None:
        if self._pending_marker_cleanup:
            self._pending_marker_cleanup = False
            self._remove_event_marker()
        if not self._config.waves:
            return
        most = self.tick.time_stamp()

        if not self._armed and not self._active:
            if self._force_start:
                self._force_start = False
                if self._ctx.users().empty:
                    log.warning("Sector event force-start ignored: no players in sector")
                else:
                    self._arm_event(most)
                return
            if not self._config.enabled:
                return
            if self._auto_start_disabled:
                return
            if most < self._kovetkezo_inditas_ms:
                return
            if self._ctx.users().empty:
                self._sorsol_kovetkezo_inditast(most)
                return
            self._arm_event(most)
            return

        if self._armed:
            if self._ctx.users().empty or (most - self._armed_ms) / 1000.0 >= self._ARM_TIMEOUT_SECONDS:
                self._disarm()
                return
            if most - self._armed_ms >= self._WHOIS_SYNC_MS:
                if not self._armed_state_sent or most - self._last_state_update_ms >= self._config.state_update_seconds * 1000:
                    self._send_state(_STATE_INACTIVE)
                    self._last_state_update_ms = most
                    self._armed_state_sent = True
            if self._pilot_within_trigger():
                self._trigger_event(most)
            return

        if self._ctx.users().empty:
            if self._empty_since_ms is None:
                self._empty_since_ms = most
            elif most - self._empty_since_ms >= self._config.empty_grace_seconds * 1000:
                self._finish(success=False, verdict=False)
            return
        self._empty_since_ms = None
        elapsed = (most - self._start_ms) / 1000.0
        dontes = kovetkezo_hullam(
            self._config.waves, self._waves_spawned, self._hostiles_still_flying(),
            most - self._last_wave_ms, self._config.wave_gap_seconds * 1000,
            self._config.repeat_last_wave)
        if dontes is not None:
            (_, count, gear), elorelep = dontes
            self._spawn_wave(count, gear)
            if elorelep:
                self._waves_spawned += 1
        if most - self._last_state_update_ms >= self._config.state_update_seconds * 1000:
            self._send_state(_STATE_ACTIVE)
            self._send_protect_task()
            self._last_state_update_ms = most
        if elapsed >= self._config.duration_seconds:
            self._finish(success=self._protect_mode)

    def damage_landed(self, sebzes_sor) -> None:
        if not self._active:
            return
        tamado = sebzes_sor.from_
        if tamado is None or not tamado.is_player():
            return
        if not self._event_unit_against(tamado.faction, sebzes_sor.to):
            return
        pid = tamado.pilot_id()
        self._damage_by_player[pid] = self._damage_by_player.get(pid, 0.0) + sebzes_sor.damage

    def _event_unit_against(self, oldal, space_object) -> bool:
        if space_object is None or space_object.faction == oldal:
            return False
        if self._convoy is not None and space_object is self._convoy:
            return True
        return space_object.id_in_space() in self._npc_ids

    def _hostiles_still_flying(self) -> bool:
        objects = self._ctx.space_objects()
        for object_id in list(self._npc_ids):
            obj = objects.get(object_id)
            if obj is None or obj.is_removed():
                self._npc_ids.discard(object_id)
                self._enemy_npc_ids.discard(object_id)
        return bool(self._enemy_npc_ids)

    def _pilot_within_trigger(self) -> bool:
        if self._event_center is None:
            return False
        for user in self._ctx.users().users_of():
            ship = self._ctx.users().player_ship_unsafe(user.pilot_of().user_id_of())
            if ship is None or ship.is_removed():
                continue
            pos = ship.mover_of().position_of()
            dx = pos.x - self._event_center.x
            dy = pos.y - self._event_center.y
            dz = pos.z - self._event_center.z
            if dx * dx + dy * dy + dz * dz <= self._TRIGGER_RADIUS * self._TRIGGER_RADIUS:
                return True
        return False

    def _sector_id(self) -> int:
        try:
            return self._ctx.blueprint().sector_desc.sector_id
        except Exception:
            journal.eloszor(log, 'sector-id', 'a sector cannot name itself; -1 stands in')
            return -1

    def _majority_faction(self):
        colonial = cylon = 0
        for user in self._ctx.users().users_of():
            frakcio = user.pilot_of().faction
            if frakcio == Faction.Colonial:
                colonial += 1
            elif frakcio == Faction.Cylon:
                cylon += 1
        if colonial == 0 and cylon == 0:
            return None
        return Faction.Colonial if colonial >= cylon else Faction.Cylon

    def _increment_freighters_killed(self, player_id: int) -> None:
        from rebsgo.gamedata.cards.misc_cards import TallyCardKind
        user = self._ctx.users().user(player_id)
        if user is None:
            return
        try:
            user.pilot_of().tally_desk.bump_counter(
                TallyCardKind.freighters_killed, 0, 1)
        except Exception:
            log.exception("freighters_killed counter increment failed")

    def _remove_event_marker(self) -> None:
        obj = self._event_object
        self._event_object = None
        if obj is not None and not obj.is_removed():
            self._remover.note_removal_cause(obj, DepartureCause.JustRemoved)

    def _safe_remove(self, obj) -> None:
        if obj is not None and not obj.is_removed():
            self._remover.note_removal_cause(obj, DepartureCause.JumpOut)

    def _arm_event(self, now: int) -> None:
        self._remove_event_marker()
        players_faction = self._majority_faction()
        if players_faction is None:
            return
        enemy = _masik_oldal(players_faction)
        if enemy not in self._config.attackers or not self._config.attackers[enemy]:
            return
        convoy_choices = [f for f in (Faction.Colonial, Faction.Cylon) if f in self._config.convoy_ships]
        if not convoy_choices:
            return
        convoy_faction = self._rng.choice(convoy_choices)
        kozeppont = Vector3(0.0, 5000.0, 0.0)
        try:
            self._event_object = self._factory.create_sector_event(
                self._config.event_card_guid, Faction.Neutral, Transform(kozeppont, Euler3(0.0, 0.0, 0.0)))
        except Exception:
            log.exception("sector event arm failed")
            self._event_object = None
            self._last_event_end_ms = now
            self._sorsol_kovetkezo_inditast(now)
            return
        self._join_queue.admit_object(self._event_object)
        self._event_center = kozeppont
        self._players_faction = players_faction
        self._convoy_faction = convoy_faction
        self._wave_faction = enemy
        self._protect_mode = convoy_faction == players_faction
        self._armed = True
        self._armed_ms = now
        self._armed_state_sent = False
        self._last_state_update_ms = 0
        log.info("Sector event AVAILABLE: freighter=%s waves=%s protect=%s sector=%s event_obj=%s "
                 "(waiting for a player to enter %.0f)",
                 convoy_faction, enemy, self._protect_mode,
                 self._ctx.blueprint().sector_desc.sector_id,
                 self._event_object.id_in_space(), self._TRIGGER_RADIUS)

    def _trigger_event(self, now: int) -> None:
        kozeppont = self._event_center or Vector3(0.0, 5000.0, 0.0)
        try:
            platform_template = WeaponPlatformSpec(
                self._config.convoy_ships[self._convoy_faction], ObjectKind.WeaponPlatform,
                ArrivalCause.AlreadyExists, 0, False, kozeppont, Euler3(0.0, 0.0, 0.0),
                0.0, 0.0, self._convoy_faction, [])
            self._convoy = self._factory.hatch_platform(platform_template)
            self._convoy.ship_aspects.take_aspect(ShipTrait.StatsScrambler)
        except Exception:
            log.exception("freighter spawn failed")
            self._finish(success=False, verdict=False)
            return
        self._join_queue.admit_object(self._convoy)
        self._armed = False
        self._active = True
        self._start_ms = now
        self._last_state_update_ms = 0
        self._waves_spawned = 0
        self._npc_ids = set()
        self._enemy_npc_ids = set()
        self._kills_by_player = {}
        self._damage_by_player = {}
        self._send_state(_STATE_ACTIVE)
        self._send_protect_task()
        log.info("Sector event TRIGGERED: freighter jumped in faction=%s protect=%s sector=%s event_obj=%s freighter_obj=%s",
                 self._convoy_faction, self._protect_mode, self._ctx.blueprint().sector_desc.sector_id,
                 self._event_object.id_in_space() if self._event_object else None,
                 self._convoy.id_in_space())

    def _disarm(self) -> None:
        self._send_state(_STATE_INACTIVE, radius=0.0)
        self._remove_event_marker()
        self._armed = False
        self._event_object = None
        self._event_center = None
        self._last_event_end_ms = self.tick.time_stamp()
        self._sorsol_kovetkezo_inditast(self.tick.time_stamp())
        log.info("Sector event expired (nobody entered the zone)")

    def _spawn_wave(self, count: int, gear_level: int) -> None:
        if self._convoy is None:
            return
        self._retire_wave()
        keret = min(self._config.max_alive_npcs, count + max(1, count - 1))
        if keret <= 0:
            return
        self._last_wave_ms = self.tick.time_stamp()
        convoy_pos = self._convoy.mover_of().position_of()

        arany = max(1, self._config.attacker_ratio)
        kiseret = max(1, round(keret / (1 + arany)))
        tamadok = kiseret * arany
        self._spawn_group(self._convoy_faction, kiseret, gear_level, convoy_pos, 1600.0)
        self._spawn_group(_masik_oldal(self._convoy_faction), tamadok,
                          gear_level, convoy_pos, 2200.0)

    def _retire_wave(self) -> None:
        objects = self._ctx.space_objects()
        for object_id in list(self._npc_ids):
            obj = objects.get(object_id)
            if obj is not None and not obj.is_removed():
                self._remover.note_removal_cause(obj, DepartureCause.JumpOut)
        self._npc_ids.clear()
        self._enemy_npc_ids.clear()

    def _spawn_group(self, faction, count: int, gear_level: int, convoy_pos, ring: float) -> None:
        parosok = self._config.attackers.get(faction, [])
        if not parosok:
            return
        behaviour = template_of_tier(2, self._config.duration_seconds, False, 400)
        for i in range(count):
            guid, owner_guid = parosok[self._rng.randrange(len(parosok))]
            szog = 2 * math.pi * i / max(1, count) + self._rng.uniform(-0.3, 0.3)
            pos = Vector3(convoy_pos.x + ring * math.cos(szog),
                          convoy_pos.y + self._rng.uniform(-150, 150),
                          convoy_pos.z + ring * math.sin(szog))
            patrol = PatrolGoal(0, _patrol_box(convoy_pos, 2400.0))
            try:
                npc = self._factory.hatch_fighter(
                    guid, [], [], [patrol], Transform(pos, Euler3(0.0, 0.0, 0.0)), behaviour, [10],
                    owner_guid=owner_guid, gear_level=gear_level)
            except Exception:
                log.exception("sector event wave npc spawn failed guid=%s", guid)
                continue
            self._join_queue.admit_object(npc)
            self._npc_ids.add(npc.id_in_space())
            if faction == self._wave_faction:
                self._enemy_npc_ids.add(npc.id_in_space())
        log.info("Sector event wave: %s %s NPCs (gear %s)", count, faction, gear_level)

    def _send_protect_task(self) -> None:
        if self._event_object is None:
            return
        import datetime as _dt
        from rebsgo.protocol.notification import ProtectGoal
        from rebsgo.protocol.notification import EventGoalDetail
        from rebsgo.protocol.notification import EventPhase
        from rebsgo.vocabulary.world import EventGoalKind
        live = self._active and self._convoy is not None and not self._convoy.is_removed()
        vip = self._convoy if live else self._event_object
        task_state = EventPhase.Active if live else EventPhase.Inactive
        if live:
            hatralevo = max(0.0, self._config.duration_seconds - (self.tick.time_stamp() - self._start_ms) / 1000.0)
        else:
            hatralevo = float(self._config.duration_seconds)
        end_time = _dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(seconds=hatralevo)
        task = ProtectGoal(0, EventGoalKind.Protect, EventGoalDetail.FREIGHTER,
                           task_state, vip.id_in_space(), end_time)
        notification = replies_for(ProtocolID.Notification)
        bw = notification.sector_event_task(self._event_object.id_in_space(), [task])
        self._ctx.sender().push_to_everyone(bw)
        log.info("Sector event TASK sent: event_obj=%s vip=%s live=%s remaining=%.0fs",
                 self._event_object.id_in_space(), vip.id_in_space(), live, hatralevo)

    def _send_state(self, state_value: int, radius: float | None = None) -> None:
        if self._event_object is None:
            return
        anchor = self._convoy if self._convoy is not None and not self._convoy.is_removed() else self._event_object
        helyzet = anchor.mover_of().position_of()
        if radius is None:
            radius = self._TRIGGER_RADIUS
        notification = replies_for(ProtocolID.Notification)
        bw = notification.sector_event_state(
            self._event_object.id_in_space(), self._convoy_faction, state_value, helyzet, radius)
        self._ctx.sender().push_to_everyone(bw)

    def _finish(self, success: bool, verdict: bool = True) -> None:
        if not self._active and not self._armed:
            return
        self._active = False
        self._armed = False
        gazda_nyert, gyoztes = esemeny_gyoztese(
            self._protect_mode, success, self._convoy_faction)
        if verdict:
            self._send_state(_STATE_SUCCESS if gazda_nyert else _STATE_FAILED)
            self._distribute_rewards(gyoztes)
        for object_id in list(self._npc_ids):
            obj = self._ctx.space_objects().get(object_id)
            if obj is not None and not obj.is_removed():
                self._remover.note_removal_cause(obj, DepartureCause.JumpOut)
        if self._convoy is not None and not self._convoy.is_removed():
            self._remover.note_removal_cause(self._convoy, DepartureCause.JumpOut)
        self._send_state(_STATE_INACTIVE, radius=0.0)
        self._pending_marker_cleanup = True
        log.info("Sector event finished, success=%s winner=%s kills=%s damage=%s",
                 success, gyoztes if verdict else None, self._kills_by_player,
                 {pid: round(d) for pid, d in self._damage_by_player.items()})
        self._event_center = None
        self._convoy = None
        self._last_event_end_ms = self.tick.time_stamp()
        self._sorsol_kovetkezo_inditast(self.tick.time_stamp())

    def _jaroroszlopot_jelol(self, user, rank: int) -> None:
        try:
            from rebsgo.gamedata.from_json.template_readers import InterdictionCounterReader

            beallitas = InterdictionCounterReader().fetch()
            rang = _rang_neve(rank)
            asztal = user.pilot_of().tally_desk
            for tabla in ("rank_counters", "dynamic_counters"):
                if (guid := beallitas.get(tabla, {}).get(rang)):
                    asztal.bump_counter(guid, self._config.event_card_guid, 1)
        except Exception:
            log.exception("the interdiction tally would not move")

    def _distribute_rewards(self, gyoztes_oldal) -> None:
        eligible_damage = {}
        for player_id, damage in self._damage_by_player.items():
            if damage <= 0:
                continue
            user = self._ctx.users().user(player_id)
            if user is None:
                continue
            if user.pilot_of().faction != gyoztes_oldal:
                continue
            eligible_damage[player_id] = damage
        total_damage = sum(eligible_damage.values())
        if total_damage <= 0:
            return
        notification = replies_for(ProtocolID.Notification)
        from rebsgo.pilots.state.holdings.walks.storage_walk import deliver_item
        for player_id, damage in eligible_damage.items():
            user = self._ctx.users().user(player_id)
            if user is None:
                continue
            share = damage / total_damage
            if share >= 0.5:
                rank = _RANK_PLATINUM
            elif share >= 0.3:
                rank = _RANK_GOLD
            elif share >= 0.15:
                rank = _RANK_SILVER
            else:
                rank = _RANK_BRONZE
            items = []
            for card_guid, count in self._config.reward_pool:
                mennyiseg = max(1, int(count * share))
                items.append(CountableItem.from_guid(card_guid, mennyiseg))
            for tetel in items:
                deliver_item(user, tetel, user.pilot_of().hold)
            bw = notification.sector_event_reward(
                self._event_object.id_in_space(), self._config.event_card_guid, rank, items)
            user.send(bw)
            self._jaroroszlopot_jelol(user, rank)
            log.info('%s paid the sector event: share=%.2f rank=%s items=%s',
                     user.user_log_simple, share, rank,
                     ", ".join(f"{t.card_guid_of()}x{int(t.count())}" for t in items) or 'nothing')


def _rang_neve(rank: int) -> str:
    return {_RANK_PLATINUM: "Platinum", _RANK_GOLD: "Gold",
            _RANK_SILVER: "Silver", _RANK_BRONZE: "Bronze"}.get(rank, "")


def _patrol_box(center, half: float) -> AABB:
    return AABB(Vector3(center.x - half, center.y - 200.0, center.z - half),
                Vector3(center.x + half, center.y + 200.0, center.z + half))


class PropertyFlush(AfterDelay):
    def __init__(self, tick, sector_objects, utem_ora: int):
        super().__init__(tick, sector_objects, utem_ora)
        self._last_warn_ms = 0.0
        self._last_stats = {
            "objects": 0,
            "dirty_objects": 0,
            "sent_buffers": 0,
            "errors": 0,
        }

    def on_due(self) -> None:
        object_count = 0
        dirty_objects = 0
        sent_buffers = 0
        errors = 0
        for space_object in self.sector_objects.values():
            object_count += 1
            try:
                space_subscribe_info = space_object.space_subscribe_info()
                if not space_subscribe_info.has_pending_space_property_buffer:
                    continue
                dirty_objects += 1
                sent_buffers += space_subscribe_info.flush_property_buffer()
            except Exception:
                errors += 1
                log.exception("Unknown error in delayed update for send space subscribe info; space_object=%s",
                              space_object)
        self._last_stats = {
            "objects": object_count,
            "dirty_objects": dirty_objects,
            "sent_buffers": sent_buffers,
            "errors": errors,
        }
        if (should_warn_count(sent_buffers, SECTOR_PROPERTY_BUFFER_WARN_COUNT)
            and should_warn_interval(self._last_warn_ms, SECTOR_TIMER_WARN_INTERVAL_MS)):
            self._last_warn_ms = now_ms()
            log.warning(
                "High sector property buffer fanout objects=%s dirty_objects=%s sent_buffers=%s "
                "threshold=%s errors=%s",
                object_count,
                dirty_objects,
                sent_buffers,
                SECTOR_PROPERTY_BUFFER_WARN_COUNT,
                errors,
            )

    def last_stats(self) -> dict:
        return dict(self._last_stats)


class StateFlush(AfterDelay):
    def __init__(self, tick, sector_objects, utem_ora: int, sender):
        super().__init__(tick, sector_objects, utem_ora)
        self._sender = sender
        self._last_warn_ms = 0.0
        self._last_stats = {
            "has_clients": 0,
            "ships": 0,
            "changed_states": 0,
        }

    def on_due(self) -> None:
        if not self._sender.has_clients():
            self._last_stats = {
                "has_clients": 0,
                "ships": 0,
                "changed_states": 0,
            }
            return

        space_replies = replies_for(ProtocolID.Game)
        bws = []
        ship_count = 0

        for ship in self.sector_objects.ships_stream_of():
            ship_count += 1
            if ship.is_removed() or not ship.world_state_of().is_changed:
                continue

            bw = space_replies.space_object_state(ship.world_state_of())
            bws.append(bw)
        self._sender.push_to_everyone(bws)
        changed_states = len(bws)
        self._last_stats = {
            "has_clients": 1,
            "ships": ship_count,
            "changed_states": changed_states,
        }
        if (should_warn_count(changed_states, SECTOR_STATE_PACKET_WARN_COUNT)
            and should_warn_interval(self._last_warn_ms, SECTOR_TIMER_WARN_INTERVAL_MS)):
            self._last_warn_ms = now_ms()
            log.warning(
                "High sector state broadcast ships=%s changed_states=%s threshold=%s",
                ship_count,
                changed_states,
                SECTOR_STATE_PACKET_WARN_COUNT,
            )

    def last_stats(self) -> dict:
        return dict(self._last_stats)

    def _emp_stuff(self, ship) -> None:
        max_hp = ship.space_subscribe_info().stat(ObjectStat.MaxHullPoints)
        current_hp = ship.space_subscribe_info().hp

        allapot = ship.world_state_of()

        if max_hp > 1 and f32(max_hp * 0.2) > current_hp:
            if allapot.is_emp_on:
                return
            allapot.set_emp_on(True)
        else:
            if allapot.is_emp_on:
                return
            allapot.set_emp_on(False)


GROUP_ALWAYS = "always"
GROUP_CLIENT = "client"
GROUP_IDLE_HEAVY = "idle_heavy"
GROUP_MAINTENANCE = "maintenance"

_DEFAULT_MAINTENANCE_INTERVAL_TICKS = max(
    1,
    int(max(100, _CONFIG.int("rebsgo.sector.gating.maintenance-tick-ms", 5000)) / Tick.TIME_DELAY_MS),
)
_TIMER_GROUP_BY_NAME = {
    "BoostUpkeep": GROUP_CLIENT,
    "CarrierAnchorFollowTimer": GROUP_CLIENT,
    "LeaveCountdown": GROUP_CLIENT,
    "MovementPulse": GROUP_CLIENT,
    "PropertyFlush": GROUP_CLIENT,
    "StateFlush": GROUP_CLIENT,
    "VisibilitySweep": GROUP_CLIENT,

    "CombatClock": GROUP_IDLE_HEAVY,
    "ShipRecovery": GROUP_IDLE_HEAVY,
    "NpcSteering": GROUP_IDLE_HEAVY,
    "NpcUpkeep": GROUP_IDLE_HEAVY,
    "ComputerCooldown": GROUP_IDLE_HEAVY,
    "ModifierExpiry": GROUP_IDLE_HEAVY,

    "DebrisCargoTimer": GROUP_MAINTENANCE,
    "DebrisFieldTimer": GROUP_MAINTENANCE,
    "ArrivalCountdown": GROUP_MAINTENANCE,
    "JumpTargetTransponderTimer": GROUP_MAINTENANCE,
    "JumpCountdown": GROUP_MAINTENANCE,
    "MineTimer": GROUP_MAINTENANCE,
    "MinerRounds": GROUP_MAINTENANCE,
    "MissileFlight": GROUP_MAINTENANCE,
    "AnnounceRounds": GROUP_MAINTENANCE,
    "SectorEventTimer": GROUP_MAINTENANCE,
    "SpawnClock": GROUP_MAINTENANCE,
}


class ClockworkStep(SectorStep):
    def __init__(self, tick, orak, sector_id=None, maintenance_interval_ticks: int | None = None):
        self._tick = tick
        self._timers = tuple(orak)
        self._timer_groups = {id(ora): self._classify_timer(ora) for ora in self._timers}
        self.sector_id = sector_id
        self._maintenance_interval_ticks = max(
            1,
            _DEFAULT_MAINTENANCE_INTERVAL_TICKS
            if maintenance_interval_ticks is None else maintenance_interval_ticks,
        )
        self._last_maintenance_tick = -self._maintenance_interval_ticks
        self._last_slow_timer_warn_ms = 0.0
        self._last_stats = {
            "timers": len(self._timers),
            "due_delayed": 0,
            "skipped_delayed": 0,
            "skipped_gating": 0,
            "timer_mode": TIMER_MODE_FULL,
            "maintenance_due": 0,
            "slowest_timer": None,
            "slowest_timer_ms": 0.0,
            "timer_elapsed_ms_by_name": {},
            "timer_details": {},
        }

    def run(self, timer_mode: str = TIMER_MODE_FULL) -> None:
        dt = self._tick.delta_time()
        tick_value = self._tick.value
        timer_mode = self._normalise_timer_mode(timer_mode)
        maintenance_due = self._consume_maintenance_due(tick_value, timer_mode)
        if not GUARDRAILS_ENABLED:
            self._run_without_guardrails(dt, tick_value, timer_mode, maintenance_due)
            return

        self._run_with_guardrails(dt, tick_value, timer_mode, maintenance_due)

    def _run_without_guardrails(self, dt: float, ora_allas, timer_mode: str, maintenance_due: bool) -> None:
        due_delayed = 0
        skipped_delayed = 0
        skipped_gating = 0
        for ora in self._timers:
            if not self._should_run_timer(ora, timer_mode, maintenance_due):
                skipped_gating += 1
                continue
            if isinstance(ora, AfterDelay):
                if not ora.is_due(ora_allas):
                    skipped_delayed += 1
                    continue
                due_delayed += 1
                ora.update_due()
                continue
            ora.update(dt)
        self._last_stats = {
            "timers": len(self._timers),
            "due_delayed": due_delayed,
            "skipped_delayed": skipped_delayed,
            "skipped_gating": skipped_gating,
            "timer_mode": timer_mode,
            "maintenance_due": int(maintenance_due),
            "slowest_timer": None,
            "slowest_timer_ms": 0.0,
            "timer_elapsed_ms_by_name": {},
            "timer_details": {},
        }

    def _run_with_guardrails(self, dt: float, ora_allas, timer_mode: str, maintenance_due: bool) -> None:
        due_delayed = 0
        skipped_delayed = 0
        skipped_gating = 0
        slowest_timer = None
        slowest_timer_ms = 0.0
        timer_elapsed_ms_by_name = {}
        timer_details = {}
        for ora in self._timers:
            if not self._should_run_timer(ora, timer_mode, maintenance_due):
                skipped_gating += 1
                continue
            if isinstance(ora, AfterDelay):
                if not ora.is_due(ora_allas):
                    skipped_delayed += 1
                    continue
                due_delayed += 1
                elapsed = self._run_timer(ora, dt, due=True)
                if elapsed > slowest_timer_ms:
                    slowest_timer = getattr(ora, 'sector_timer_name', None) \
                        or ora.__class__.__name__
                    slowest_timer_ms = elapsed
                self._record_timer_elapsed(timer_elapsed_ms_by_name, ora, elapsed)
                self._collect_timer_details(ora, timer_details)
                continue
            elapsed = self._run_timer(ora, dt)
            if elapsed > slowest_timer_ms:
                slowest_timer = ora.__class__.__name__
                slowest_timer_ms = elapsed
            self._record_timer_elapsed(timer_elapsed_ms_by_name, ora, elapsed)
            self._collect_timer_details(ora, timer_details)
        self._last_stats = {
            "timers": len(self._timers),
            "due_delayed": due_delayed,
            "skipped_delayed": skipped_delayed,
            "skipped_gating": skipped_gating,
            "timer_mode": timer_mode,
            "maintenance_due": int(maintenance_due),
            "slowest_timer": slowest_timer,
            "slowest_timer_ms": slowest_timer_ms,
            "timer_elapsed_ms_by_name": timer_elapsed_ms_by_name,
            "timer_details": timer_details,
        }

    def _run_timer(self, timer, dt: float, due: bool = False) -> float:
        started_ms = now_ms()
        if due:
            timer.update_due()
        else:
            timer.update(dt)
        elapsed = elapsed_ms(started_ms)
        if (should_warn(elapsed, SECTOR_TIMER_WARN_MS)
            and should_warn_interval(self._last_slow_timer_warn_ms, SECTOR_TIMER_WARN_INTERVAL_MS)):
            self._last_slow_timer_warn_ms = now_ms()
            log.warning(
                "Slow sector timer sector=%s timer=%s elapsed_ms=%.1f threshold_ms=%.1f",
                self.sector_id,
                timer.__class__.__name__,
                elapsed,
                SECTOR_TIMER_WARN_MS,
            )
        return elapsed

    @staticmethod
    def _collect_timer_details(timer, timer_details: dict) -> None:
        last_stats = getattr(timer, "last_stats", None)
        if last_stats is None:
            return
        timer_details[timer.__class__.__name__] = last_stats()

    @staticmethod
    def _record_timer_elapsed(timer_elapsed_ms_by_name: dict, timer, elapsed_ms_value: float) -> None:
        timer_name = timer.__class__.__name__
        timer_elapsed_ms_by_name[timer_name] = timer_elapsed_ms_by_name.get(timer_name, 0.0) + elapsed_ms_value

    def timer_of_type(self, timer_cls):
        for ora in self._timers:
            if isinstance(ora, timer_cls):
                return ora
            for lepes in getattr(ora, "steps_of", lambda: ())():
                if isinstance(lepes, timer_cls):
                    return lepes
        return None

    def last_stats(self) -> dict:
        return dict(self._last_stats)

    @staticmethod
    def _normalise_timer_mode(timer_mode: str) -> str:
        if timer_mode in (TIMER_MODE_FULL, TIMER_MODE_IDLE, TIMER_MODE_MAINTENANCE):
            return timer_mode
        return TIMER_MODE_FULL

    def _consume_maintenance_due(self, ora_allas: int, timer_mode: str) -> bool:
        if timer_mode not in (TIMER_MODE_IDLE, TIMER_MODE_MAINTENANCE):
            return True
        if ora_allas - self._last_maintenance_tick < self._maintenance_interval_ticks:
            return False
        self._last_maintenance_tick = ora_allas
        return True

    def _should_run_timer(self, timer, timer_mode: str, maintenance_due: bool) -> bool:
        if timer_mode == TIMER_MODE_FULL:
            return True
        csoport = self._timer_group(timer)
        if timer_mode == TIMER_MODE_IDLE:
            if csoport in (GROUP_CLIENT, GROUP_IDLE_HEAVY):
                return False
            if csoport == GROUP_MAINTENANCE:
                return maintenance_due
            return True
        if timer_mode == TIMER_MODE_MAINTENANCE:
            if csoport in (GROUP_CLIENT, GROUP_IDLE_HEAVY):
                return False
            if csoport == GROUP_MAINTENANCE:
                return maintenance_due
            return True
        return True

    def _timer_group(self, timer) -> str:
        return self._timer_groups.get(id(timer), GROUP_ALWAYS)

    @staticmethod
    def _classify_timer(timer) -> str:
        explicit_group = getattr(timer, "sector_timer_group", None)
        if explicit_group in (GROUP_ALWAYS, GROUP_CLIENT, GROUP_IDLE_HEAVY, GROUP_MAINTENANCE):
            return explicit_group
        return _TIMER_GROUP_BY_NAME.get(timer.__class__.__name__, GROUP_ALWAYS)


class NpcSteering(NpcRounds):
    def __init__(self, tick, sector_objects, utem_ora, cast_desk, damage_log,
                 takarito, szektor_kartyak, dice):
        super().__init__(tick, sector_objects, utem_ora, cast_desk, damage_log,
                         szektor_kartyak)
        self._remover = takarito
        self._dice = dice
        self._target_cache = {}
        self._utolso_kor_ms = None

    def _alvas_beszamitasa(self) -> None:
        most = self.tick.time_stamp()
        elozo, self._utolso_kor_ms = self._utolso_kor_ms, most
        if elozo is None:
            return
        sajat_utem = self.delayed_ticks * Tick.TIME_DELAY_MS
        aludt = (most - elozo) - sajat_utem
        if aludt <= sajat_utem:
            return
        for bot in self.sector_objects.objects_of_kind(ObjectKind.BotFighter):
            bot.kor_szunetel(aludt)

    def on_due(self) -> None:
        self._alvas_beszamitasa()
        self._begin_targeting_cycle()
        try:
            moving_bot_fighter_movings = self.sector_objects.objects_of_kind(
                ObjectKind.BotFighter)
            for roaming_bot in moving_bot_fighter_movings:
                jumped_out = self._jump_out_npc_if_no_more_targets(roaming_bot)
                if jumped_out:
                    continue

                closest = self._pick_target_cached(roaming_bot)
                if closest is None and len(roaming_bot.patrol_objectives()) == 0:
                    continue

                self._update_weapons(roaming_bot, closest)

                self._update_abilities(roaming_bot, closest)

                if closest is None:
                    self.steer_bot(roaming_bot)
                else:
                    self.steer_bot(roaming_bot, closest)
        finally:
            self._end_targeting_cycle("NpcSteering")

    def _pick_target_cached(self, bot):
        cached = self._cached_target_for(bot)
        refresh_due = self._target_refresh_due(bot)
        if cached is not None and not refresh_due:
            self._record_targeting_stat("target_cache_hits")
            self._record_targeting_stat("target_phase_skips")
            return cached
        if cached is None:
            self._record_targeting_stat("target_cache_misses")

        celpont = self._pick_target(bot)
        self._store_cached_target(bot, celpont)
        return celpont

    def _target_refresh_due(self, bot) -> bool:
        phase_count = max(1, int(SECTOR_NPC_TARGET_PHASE_COUNT))
        if phase_count <= 1:
            return True
        try:
            return self.tick.value % phase_count == bot.id_in_space() % phase_count
        except Exception:
            journal.eloszor(log, 'npc-target-phase',
                            'the NPC target phase cannot be worked out; every bot re-targets')
            return True

    def _cached_target_for(self, bot):
        bejegyzes = self._target_cache.get(bot.id_in_space())
        if bejegyzes is None:
            return None
        target_id, expires_tick = bejegyzes
        try:
            if self.tick.value > expires_tick:
                self._target_cache.pop(bot.id_in_space(), None)
                return None
            celpont = self.sector_objects.get(target_id)
        except Exception:
            journal.eloszor(log, 'npc-target-cache',
                            'a cached NPC target cannot be read back; the cache entry is dropped')
            self._target_cache.pop(bot.id_in_space(), None)
            return None
        if not self._cached_target_is_valid(bot, celpont):
            self._target_cache.pop(bot.id_in_space(), None)
            return None
        return celpont

    def _store_cached_target(self, bot, target) -> None:
        npc_id = bot.id_in_space()
        if target is None or not self._cached_target_is_valid(bot, target):
            self._target_cache.pop(npc_id, None)
            return
        cache_ticks = max(0, int(SECTOR_NPC_TARGET_CACHE_TICKS))
        if cache_ticks <= 0:
            self._target_cache.pop(npc_id, None)
            return
        self._target_cache[npc_id] = (target.id_in_space(), self.tick.value + cache_ticks)

    def _cached_target_is_valid(self, bot, target) -> bool:
        if target is None:
            return False
        if target.id_in_space() == bot.id_in_space():
            return False
        get_removing_cause = getattr(target, "removal_cause_of", None)
        if callable(get_removing_cause) and get_removing_cause() is not None:
            return False
        try:
            if self._is_cloaked_for_npc_targeting(bot, target):
                return False
            target_bracket_mode = self.sector_cards.regulation_card().target_bracket_mode
            if relation(target, bot, target_bracket_mode) != Stance.Enemy:
                return False
            max_aggro_distance = bot.behaviour_template.aggro_reach
            max_aggro_distance_sq = max_aggro_distance * max_aggro_distance
            target_position = target.mover_of().position_of()
            npc_position = bot.mover_of().position_of()
            return npc_position.sq_distance_to(target_position) <= max_aggro_distance_sq
        except Exception:
            journal.eloszor(log, 'npc-target-valid',
                            'an NPC cannot judge its own target; it is treated as invalid')
            return False

    def steer_bot(self, bot, legkozelebbi=None) -> None:
        if legkozelebbi is None:
            self._patrol_next_leg(bot)
        else:
            self._update_bot_maneuver_target(bot, legkozelebbi)

    def _patrol_next_leg(self, bot) -> None:
        korzet = bot.patrol_objectives()
        if not korzet:
            return
        doboz = korzet[0]
        if doboz is None:
            log.error('a patrolling ship carries an empty patrol goal - leaving it as it flies')
            return

        NpcSteering._mozgasban_tartas(bot)
        mozgato = bot.mover_of()
        if doboz.within_box(mozgato.position_of()):
            return

        cel = Vector3.of_array(self._dice.point_between(
            doboz.box_to_patrol_in.min().to_array_,
            doboz.box_to_patrol_in.max().to_array_))
        mozgato.queue_maneuver(DirectionalManeuver(
            Euler3.direction(cel.sub_(mozgato.position_of()))))

    @staticmethod
    def _mozgasban_tartas(bot) -> None:
        mozgato = bot.mover_of()
        manover = mozgato.current_maneuver
        if manover is None or manover.maneuver_type == ManeuverKind.Rest:
            mozgato.queue_maneuver(
                DirectionalManeuver(Euler3.from_quaternion(mozgato.rotation_of())))

        beallitas = mozgato.movement_options
        if beallitas.speed == 0:
            sebesseg = bot.space_subscribe_info().stat_or_default(ObjectStat.Speed)
            beallitas.set_speed(sebesseg)
            beallitas.throttle_to(sebesseg)

    def _update_bot_maneuver_target(self, roaming_bot, legkozelebbi) -> None:
        bot_position = roaming_bot.mover_of().position_of()
        target_position = legkozelebbi.mover_of().position_of()
        to_target = Vector3.sub(target_position, bot_position)

        closest_distance_sq = to_target.sq_magnitude_
        direction = Euler3.direction(to_target)
        is_direction_with_roll = self.tick.value % 5 == 0
        new_maneuver = DirectionalManeuver(direction) if is_direction_with_roll \
            else NoRollManeuver(direction)
        roaming_bot.mover_of().queue_maneuver(new_maneuver)

        halt_distance = roaming_bot.behaviour_template.halt_distance
        if (closest_distance_sq < halt_distance * halt_distance
            and legkozelebbi.mover_of().frame.linear_speed.magnitude_ < 5):
            sebesseg = 0
        else:
            sebesseg = roaming_bot.space_subscribe_info().stat_or_default(ObjectStat.Speed)

        roaming_bot.mover_of().movement_options.set_speed(sebesseg)
        roaming_bot.mover_of().movement_options.throttle_to(sebesseg)

    def _jump_out_npc_if_no_more_targets(self, roaming_bot) -> bool:
        kill_objectives = roaming_bot.kill_objectives()
        all_kill_objectives_gone = all(
            all(space_object.removal_cause_of() is not None for space_object in obj.objectives_to_kill)
            for obj in kill_objectives)

        life_time_end_time_stamp = int(
            f32(f32(roaming_bot.behaviour_template.lifespan_seconds * 1000)
                + roaming_bot.creating_time_stamp))
        life_time_is_over = (life_time_end_time_stamp - self.tick.time_stamp()) < 0
        bot_fighter_is_in_combat = roaming_bot.space_subscribe_info().is_in_combat

        if (all_kill_objectives_gone
            and life_time_is_over
            and (not bot_fighter_is_in_combat
                     or roaming_bot.behaviour_template.jumps_out_when_fighting_spec)):
            self._remover.note_removal_cause(roaming_bot, DepartureCause.JumpOut)
            return True

        return False


class NpcUpkeep(NpcRounds):
    def __init__(self, tick, sector_objects, delay, cast_desk, damage_log,
                 szektor_kartyak):
        super().__init__(tick, sector_objects, delay, cast_desk, damage_log,
                         szektor_kartyak)
        self._last_targets = {}

    def on_due(self) -> None:
        self._begin_targeting_cycle()
        try:
            stream = getattr(self.sector_objects, "objects_among_kinds", None)
            npc_ships = (
                stream(ObjectKind.WeaponPlatform, ObjectKind.Outpost)
                if stream is not None else
                self.sector_objects.space_objects_of_entity_types(
                    ObjectKind.WeaponPlatform,
                    ObjectKind.Outpost)
            )
            for npc_ship in npc_ships:
                closest = self._pick_target(npc_ship)
                last_target = self._last_targets.get(npc_ship.id_in_space())
                if (last_target is None and closest is None) or (closest is not None and closest == last_target):
                    continue
                self._last_targets[npc_ship.id_in_space()] = closest
                self._update_weapons(npc_ship, closest)
        finally:
            self._end_targeting_cycle("NpcUpkeep")

    def _update_weapons(self, ship, legkozelebbi) -> None:
        rekeszek = ship.space_subscribe_info().ship_slots
        if rekeszek is None:
            return
        for rekesz in rekeszek.values():
            if rekesz.ship_system is None:
                continue
            if rekesz.ship_slot_card().ship_slot_type != ShipSlotType.weapon:
                continue
            if legkozelebbi is None:
                self.cast_desk.disarm_auto_cast(
                    rekesz.ship_system.server_id, ship.id_in_space())
                if log.isEnabledFor(logging.DEBUG):
                    log.debug("weapons: #%s slot %s disarmed (no target)",
                              ship.id_in_space(), rekesz.ship_slot_card().slot_id)
                continue
            if rekesz.ship_ability() is None:
                if log.isEnabledFor(logging.DEBUG):
                    log.debug("weapons: #%s slot %s holds system %s with no ability"
                              " - it can never fire",
                              ship.id_in_space(), rekesz.ship_slot_card().slot_id,
                              rekesz.ship_system.card_guid_of())
                continue
            self.cast_desk.arm_auto_cast(CastOrder(
                ship, rekesz.ship_system.server_id, True,
                self._celpontja(ship, rekesz, legkozelebbi)))
            if log.isEnabledFor(logging.DEBUG):
                log.debug("weapons: #%s slot %s armed at #%s",
                          ship.id_in_space(), rekesz.ship_slot_card().slot_id,
                          legkozelebbi.id_in_space())

    def _celpontja(self, ship, slot, legkozelebbi):
        teruletre_hat = (slot.ship_system.card_guid_of() != 0
                         and slot.ship_ability().ship_ability_card.ship_ability_affect
                         == ShipAbilityAffect.Area)
        if teruletre_hat:
            return self._hostile_ids(ship, lambda space_object: True)
        return legkozelebbi.id_in_space()

    def _hostile_ids(self, me, predicate):
        return {obj.id_in_space() for obj in self.sector_objects.values()
                if obj.faction != me.faction and predicate(obj)}
