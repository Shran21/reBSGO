# github.com/Shran21

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from rebsgo.config.config import Config
from rebsgo.gamedata.from_json.template_readers import mine_tuning
from rebsgo.gamedata.cards.misc_cards import TallyCardKind
from rebsgo.gamedata.reading import AbilityActionKind, ConsumableEffectKind, ObjectStat, Price, ShipAbilityAffect, ShipAbilityTargetTier, ShipConsumableOption, ShipSlotType
from rebsgo.geometry.maths.geometry3d import within_range, weapon_reaches, point_position_relative_to
from rebsgo.geometry.maths.maths import Maths
from rebsgo.geometry.primitives.vector3 import Vector3
from rebsgo.helpers.floats import FLOAT_MAX_VALUE
from rebsgo.native.hotpath import nearest_radius_id, log_native_event
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.protocol_book_replies import replies_for, game_replies
from rebsgo.vocabulary.combat import ManeuverKind, WeaponEffect
from rebsgo.vocabulary.pilot import Faction, Gear, ResourceKind
from rebsgo.vocabulary.world import ObjectKind, WellKnownCard
from rebsgo.world.movement.maneuvers import DirectionalManeuver, FollowManeuver, PulseManeuver, StaticLaunchManeuver, TargetLaunchManeuver, PitchYawTurnPlan
from rebsgo.world.objects.bodies import Planetoid
from rebsgo.world.objects.ships import PlayerShip, Ship
from rebsgo.world.sectors.powers.nuclear_missile_stats import apply_to_missile_stats, ensure_aoe_stats
from rebsgo.world.sectors.powers.stealth import deactivate_player_stealth, is_cloaked_player, is_inside_visual_detection_radius
from rebsgo.world.sectors.ship_tweak import ShipTweak
from rebsgo.world.sectors.sides import Stance, relation
from rebsgo.world.sectors.spatial.radius_candidates import (
    build_complete_spatial_index,
    ordered_radius_candidates,
)
import logging
from rebsgo.gamedata.from_json.template_readers import world_timers
from dataclasses import dataclass


_CONFIG = Config.instance()
_FLARE_MISSILE_SPATIAL_INDEX_ENABLED = _CONFIG.bool("rebsgo.sector.spatial-index.flare-missile-enabled", True)
_FLARE_MISSILE_SPATIAL_INDEX_CELL_SIZE = _CONFIG.float("rebsgo.sector.spatial-index.flare-missile-cell-size", 5000.0)
_FLARE_MISSILE_SPATIAL_INDEX_MIN_OBJECTS = _CONFIG.int("rebsgo.sector.spatial-index.flare-missile-min-objects", 32)
_AREA_TARGET_SPATIAL_INDEX_ENABLED = _CONFIG.bool("rebsgo.sector.spatial-index.ability-area-enabled", True)
_AREA_TARGET_SPATIAL_INDEX_CELL_SIZE = _CONFIG.float("rebsgo.sector.spatial-index.ability-area-cell-size", 5000.0)
_AREA_TARGET_SPATIAL_INDEX_MIN_OBJECTS = _CONFIG.int("rebsgo.sector.spatial-index.ability-area-min-objects", 32)


log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Elsutes:
    ship: object
    slot: object
    targets: object
    auto: bool
    ctx: object


class Deed(ABC):
    def __init__(self, elsutes: Elsutes):
        self._elsutes = elsutes
        self._casting_ship = elsutes.ship
        self._caster_stats = elsutes.ship.space_subscribe_info()
        self._casting_slot = elsutes.slot
        self._ability = elsutes.slot.ship_ability()
        self._system = elsutes.slot.ship_system
        self._chosen_targets = elsutes.targets
        self._is_auto_cast_ability = elsutes.auto
        self._ctx = elsutes.ctx
        self._regulation_card = elsutes.ctx.blueprint().sector_cards().regulation_card()
        self._started_at = 0
        self._cooldown = 0.0
        self._pp_cost = 0.0
        self._diff = 0
        self._last_failure_reason = None

    def _ready_to_fire(self) -> bool:
        self._last_failure_reason = None
        self._started_at = self._ctx.tick().time_stamp()
        if self._is_action_disabled_by_short_circuit():
            self._last_failure_reason = "short_circuit"
            return False
        self._cooldown = self._ability.item_buff_add.stat(ObjectStat.Cooldown)
        self._pp_cost = self._ability.item_buff_add.stat(ObjectStat.PowerPointCost)
        last_used_plus_cooldown = int((self._system.time_of_last_use + self._cooldown) * 1000)
        self._diff = self._started_at - last_used_plus_cooldown

        if self._diff < 0:
            self._last_failure_reason = "cooldown"
            return False

        if self._caster_stats.pp < self._pp_cost:
            self._last_failure_reason = "insufficient_power"
            return False
        if not self._consumables_available(self._casting_ship, self._casting_slot):
            self._last_failure_reason = "missing_consumable"
            return False
        if self._ability.ship_ability_card.ship_ability_affect == ShipAbilityAffect.Selected:
            if len(self._chosen_targets) > 1:
                closest = self._closest_selected_target()
                self._chosen_targets.clear()
                if closest is not None:
                    self._chosen_targets.append(closest)

        if isinstance(self._casting_ship, PlayerShip):
            self._casting_ship.visibility_of().settle_ghost_jump()

        return True

    def _closest_selected_target(self):
        caster_pos = self._casting_ship.mover_of().position_of()
        try:
            feljegyzesek = []
            by_id = {}
            for jelolt in self._chosen_targets:
                candidate_id = jelolt.id_in_space()
                helyzet = jelolt.mover_of().position_of()
                feljegyzesek.append((candidate_id, helyzet.x, helyzet.y, helyzet.z))
                by_id[candidate_id] = jelolt
            closest_id = nearest_radius_id(
                feljegyzesek,
                (caster_pos.x, caster_pos.y, caster_pos.z),
                FLOAT_MAX_VALUE,
            )
            if closest_id is not None:
                log_native_event(
                    log,
                    "ability_closest_target_lookup_used",
                    "Ability closest-target lookup candidates=%s selected=%s",
                    len(feljegyzesek),
                    closest_id,
                )
                return by_id.get(closest_id)
        except Exception:
            log.exception("Ability closest-target lookup failed; falling back to Python scan")

        closest = None
        closest_dist_sq = FLOAT_MAX_VALUE
        for jelolt in self._chosen_targets:
            dist_sq = jelolt.mover_of().position_of().sq_distance_to(caster_pos)
            if dist_sq < closest_dist_sq:
                closest_dist_sq = dist_sq
                closest = jelolt
        return closest

    def _settle_up(self) -> None:
        self._spend_consumables(self._casting_ship, self._casting_slot)
        self._system.note_use(self._started_at)
        self._caster_stats.set_power(self._caster_stats.pp - self._pp_cost)
        self._push_cast_with_slots()

    def process(self) -> bool:
        if not self._ready_to_fire():
            return False
        if not self._carry_out():
            if self._last_failure_reason is None:
                self._last_failure_reason = "internal"
            return False
        self._settle_up()
        return True

    @property
    def failure_reason(self):
        return self._last_failure_reason

    def _set_failure_reason(self, reason: str) -> None:
        self._last_failure_reason = reason

    @property
    def should_remove_auto_cast(self) -> bool:
        return False

    @abstractmethod
    def _carry_out(self) -> bool:
        ...

    def _consumables_available(self, caster, ship_slot) -> bool:
        if not caster.is_player():
            return True
        if (ship_slot.ship_ability().ship_ability_card.ship_consumable_option
            != ShipConsumableOption.Using):
            return True
        user = self._ctx.users().user(caster.pilot_id())
        if user is None:
            return False
        keszlet = user.pilot_of().hold.holds_stack_of(
            ship_slot.current_consumable.item_countable)
        return keszlet is not None and keszlet.count() > 0

    def _spend_consumables(self, caster, ship_slot) -> None:
        if not caster.is_player():
            return

        kepesseg = ship_slot.ship_ability()
        ability_card = kepesseg.ship_ability_card
        if ability_card.ship_consumable_option != ShipConsumableOption.Using:
            return

        type_ = ability_card.consumable_type

        player_ship = caster
        user = self._ctx.users().user(player_ship.pilot_id())
        if user is None:
            return

        client = user
        player = client.pilot_of()
        eredmeny = player.hold.holds_stack_of(ship_slot.current_consumable.item_countable)
        if eredmeny is None:
            return
        current_item_consumable = eredmeny
        from rebsgo.pilots.state.holdings.walks.hold_walk import HoldWalk
        hold_walker = HoldWalk(client, None)
        hold_walker.take_from_stack(current_item_consumable, 1, player.hold)

    def _push_cast_with_slots(self) -> None:
        if not self._casting_ship.is_player():
            return
        player_ship = self._casting_ship
        user = self._ctx.users().user(player_ship.pilot_id())
        if user is None:
            return


        game_protocol = user.protocol_of(ProtocolID.Game)
        player_protocol = user.protocol_of(ProtocolID.Pilot)

        self._ctx.sender().push_to(game_protocol.replies.cast(self._system.server_id), user)

        active_ship = user.pilot_of().hangar_of().active_ship()
        self._ctx.sender().push_to(player_protocol.replies.ship_slots(active_ship), user)

    def _tier_gate_passes(self, target) -> bool:
        if not isinstance(target, Ship):
            return True
        kartya = self._ability.ship_ability_card
        engedettek = kartya.target_tiers
        if ShipAbilityTargetTier.Any in engedettek:
            return True
        return bool(engedettek) and kartya.tier_of(target.ship_card_of().tier) in engedettek

    def _stance_toward(self, target) -> Stance:
        return relation(self._casting_ship, target, self._regulation_card.target_bracket_mode)

    def _is_action_disabled_by_short_circuit(self) -> bool:
        modifiers = self._caster_stats.modifiers
        if modifiers is None:
            return False

        action_type = self._ability.ship_ability_card.ability_action_type
        for modifier in modifiers.of_type(AbilityActionKind.ShortCircuit):
            affected = modifier.ship_ability().ship_ability_card.ability_action_types
            if len(affected) == 0 or action_type in affected:
                return True
        return False


def get_toggle_upkeep_seconds(system) -> float:
    getter = getattr(system, "last_upkeep_of", None)
    if callable(getter):
        return getter()
    return system.time_of_last_use


def set_toggle_upkeep_seconds(system, seconds: float) -> None:
    setter = getattr(system, "note_upkeep", None)
    if callable(setter):
        setter(seconds)


class TransponderDeed(Deed):
    def __init__(self, elsutes: Elsutes, arrival_gate):
        super().__init__(elsutes)
        self._arrival_gate = arrival_gate

    def _carry_out(self) -> bool:
        transponder = self._ctx.object_forge.create_jump_target_transponder(
            self._casting_ship,
            self._ability.item_buff_add,
            self._started_at,
        )
        self._arrival_gate.admit_object(transponder)
        return True


class BoonDeed(Deed):
    def __init__(self, elsutes: Elsutes):
        super().__init__(elsutes)
    TAVOLSAG_TURES = world_timers().buff_range_tolerance

    def _carry_out(self) -> bool:
        if self._ability.ship_ability_card.ship_ability_affect == ShipAbilityAffect.Ignore:
            self._chosen_targets.append(self._casting_ship)

        honnan = self._casting_ship.mover_of().position_of()
        hatotav = self._ability.item_buff_add.stat_or_default(ObjectStat.MaxRange)

        for celpont in self._chosen_targets:
            hova = celpont.mover_of().position_of()
            if within_range(honnan, hova, 0, hatotav):
                celpont.space_subscribe_info().take_modifier(
                    ShipTweak.create(self._ability, self._system, self._started_at,
                                     self._casting_ship.pilot_id()))
                continue
            self._panasz_ha_tul_messze(honnan, hova, hatotav)
        return True

    def _panasz_ha_tul_messze(self, honnan, hova, hatotav: float) -> None:
        if not self._casting_ship.is_player():
            return
        tavolsag = Vector3.distance(honnan, hova)
        if tavolsag - hatotav <= self.TAVOLSAG_TURES:
            return
        log.warning(
            "buff beyond reach: pilot=%s tier=%s ability=%s distance=%s min=%s max=%s",
            self._casting_ship.pilot_id(),
            self._casting_ship.ship_card_of().tier,
            self._ability.ship_ability_card.card_guid_of(),
            tavolsag,
            self._ability.item_buff_add.stat_or_default(ObjectStat.MinRange),
            hatotav)


class BaneDeed(Deed):
    def __init__(self, elsutes: Elsutes, engagement):
        super().__init__(elsutes)
        self._engagement = engagement

    def _carry_out(self) -> bool:
        standard_duration = self._ability.item_buff_add.stat_or_default(ObjectStat.Duration)
        emitter_rate = self._caster_stats.stat(ObjectStat.PenetrationStrength)

        start_pos = self._casting_ship.mover_of().position_of()

        for target_space_object in self._chosen_targets:
            is_in_range = within_range(
                start_pos, target_space_object.mover_of().position_of(),
                0, self._ability.item_buff_add.stat_or_default(ObjectStat.MaxRange))
            fire_wall = target_space_object.space_subscribe_info().stat_or_default(ObjectStat.FirewallRating)
            if is_in_range:
                modifier = ShipTweak.create(self._ability, self._system, self._started_at,
                                            self._casting_ship.pilot_id())
                cleaned_duration = self._clean_duration(standard_duration, emitter_rate, fire_wall)
                modifier.item_buff_add.set_stat(ObjectStat.Duration, cleaned_duration)
                target_space_object.space_subscribe_info().take_modifier(modifier)

        if self._casting_ship.is_player():
            self._casting_ship.space_subscribe_info().note_combat_moment(self._ctx.tick().time_stamp())

        return True

    def _clean_duration(self, standard_duration: float, ado_ereje: float, fire_wall: float) -> float:
        return self._engagement.jam_duration(standard_duration, ado_ereje, fire_wall)


class JamMissileDeed(Deed):
    def __init__(self, elsutes: Elsutes):
        super().__init__(elsutes)
        self._game_writer = game_replies()

    def _carry_out(self) -> bool:
        hatotav = self._ability.item_buff_add.stat_or_default(ObjectStat.MaxRange)
        honnan = self._casting_ship.mover_of().position_of()
        for celpont in self._chosen_targets:
            if self._elteritheto(celpont, honnan, hatotav * hatotav):
                self._raketa_elteritese(celpont)
        return True

    def _elteritheto(self, celpont, honnan, hatotav_negyzet) -> bool:
        if celpont.space_entity_type != ObjectKind.Missile:
            log.error('missile jammer aimed at a non-missile (%s)', celpont.pilot_id())
            return False
        return (not celpont.is_removed()
                and honnan.sq_distance_to(celpont.mover_of().position_of()) <= hatotav_negyzet)

    def _raketa_elteritese(self, raketa) -> None:
        mozgato = raketa.mover_of()
        mozgato.queue_maneuver(DirectionalManeuver(mozgato.frame.euler3()))

        celpont = raketa.missile_launched_on_object
        if celpont is None:
            return
        if celpont.is_player():
            user = self._ctx.users().user(celpont.pilot_id())
            if user is None:
                return
            self._ctx.sender().push_to(
                self._game_writer.missile_decoyed(raketa.id_in_space()), user)
        raketa.forget_launch_of()


_FLARE_MISSILE_SPATIAL_INDEX_MAX_CELLS_PER_OBJECT = _CONFIG.int(
    "rebsgo.sector.spatial-index.flare-missile-max-cells-per-object", 512)


class FlareDeed(Deed):
    def __init__(self, elsutes: Elsutes, engagement):
        super().__init__(elsutes)
        self._space_objects = elsutes.ctx.space_objects()
        self._sector_sender = elsutes.ctx.sender()
        self._engagement = engagement

    def _carry_out(self) -> bool:
        if self._chosen_targets or self._ctx.users().empty:
            return False

        hatotav = self._ability.item_buff_add.stat_or_default(ObjectStat.FlareRange)
        honnan = self._casting_ship.mover_of().position_of()
        valaszok = replies_for(ProtocolID.Game)
        self._sector_sender.push_to_everyone(
            valaszok.flare_released(self._casting_ship.id_in_space()))

        for raketa in self._get_flare_candidate_missiles(honnan, hatotav):
            try:
                if self._elteritheto(raketa, honnan, hatotav):
                    self._eltevesztes(raketa, valaszok)
            except Exception:
                log.exception('flare effect fell over on one missile')
        return True

    def _elteritheto(self, raketa, honnan, hatotav: float) -> bool:
        if raketa.is_removed() or raketa.faction == self._casting_ship.faction or hatotav == 0:
            return False
        tavolsag_negyzet = Vector3.squared_distance(
            honnan, raketa.mover_of().position_of())
        if tavolsag_negyzet > hatotav * hatotav:
            return False
        esely = self._engagement.flare_odds(
            Maths.sqrt(tavolsag_negyzet), hatotav)
        return self._ctx.dice().passes(esely)

    def _eltevesztes(self, raketa, valaszok) -> None:
        mozgato = raketa.mover_of()
        if mozgato.current_maneuver.maneuver_type != ManeuverKind.TargetLaunch:
            return
        mozgato.queue_maneuver(DirectionalManeuver(mozgato.frame.euler3()))

        celpont = raketa.missile_launched_on_object
        if celpont is None:
            log.error('this missile carries no target')
            return
        raketa.forget_launch_of()
        if not celpont.is_player():
            return
        if (user := self._ctx.users().user(celpont.pilot_id())) is not None:
            self._ctx.sender().push_to(
                valaszok.missile_decoyed(raketa.id_in_space()), user)

    def _get_flare_candidate_missiles(self, caster_position, flare_range: float):
        raketak = tuple(self._space_objects.space_objects_of_entity_type(ObjectKind.Missile))
        if (not _FLARE_MISSILE_SPATIAL_INDEX_ENABLED
            or flare_range <= 0
            or len(raketak) < _FLARE_MISSILE_SPATIAL_INDEX_MIN_OBJECTS):
            return raketak
        try:
            sorszam = build_complete_spatial_index(
                raketak,
                _FLARE_MISSILE_SPATIAL_INDEX_CELL_SIZE,
                _FLARE_MISSILE_SPATIAL_INDEX_MAX_CELLS_PER_OBJECT,
                log,
                "Flare missile",
            )
            if sorszam is None:
                return raketak
            return ordered_radius_candidates(raketak, sorszam, caster_position, flare_range)
        except Exception:
            log.exception("Flare missile spatial query failed; falling back to the plain sweep")
            return raketak


class MineDeed(Deed):
    def __init__(self, elsutes: Elsutes, arrival_gate):
        super().__init__(elsutes)
        self._arrival_gate = arrival_gate

    def _carry_out(self) -> bool:
        ability_stats = self._ability.item_buff_add
        arming_seconds = ability_stats.stat_or_default(ObjectStat.Duration, 2.0)
        armed_at = self._started_at + int(arming_seconds * 1000)

        system_card = self._system.ship_system_card
        mine_tier = system_card.tier if system_card is not None else 1
        if mine_tier <= 0:
            mine_tier = 1

        mine_guid = self._get_mine_guid(mine_tier)
        mine = self._ctx.object_forge.create_mine(
            self._casting_ship, mine_guid, mine_tier, self._started_at, armed_at)

        mine_stats = mine.space_subscribe_info().stats_of
        mine_stats.merge_in(ability_stats)
        self._consumable_bonus_onto(mine_stats)
        hangolas = mine_tuning()
        if self._toltet_fajtaja() == "nuclear":
            for stat, mult in ((ObjectStat.MaxHullPoints, hangolas.hull_multiplier),
                               (ObjectStat.DamageHigh, hangolas.damage_multiplier),
                               (ObjectStat.DamageLow, hangolas.damage_multiplier)):
                if mine_stats.holds_stat(stat):
                    mine_stats.set_stat(stat, mine_stats.stat(stat) * mult)

        if not mine_stats.holds_stat(ObjectStat.AoeOuterRadius):
            mine_stats.set_stat(ObjectStat.AoeOuterRadius, hangolas.blast_radius)
        mine_stats.set_stat(ObjectStat.MaxPowerPoints, 0)
        mine.space_subscribe_info().set_hull(mine_stats.stat(ObjectStat.MaxHullPoints))
        mine.space_subscribe_info().cap_hull_and_power()

        self._eject_backwards(mine, mine_tier)
        self._arrival_gate.admit_object(mine)
        return True

    def _get_mine_guid(self, mine_tier: int) -> int:
        return mine_tuning().guid_for(self._toltet_fajtaja(), mine_tier)

    def _toltet_fajtaja(self) -> str:
        toltet = self._casting_slot.current_consumable
        kartya = None if toltet is None else toltet.ship_consumable_card
        if kartya is None:
            return "he"
        if kartya.effect_type == ConsumableEffectKind.DamageNuclear:
            return "nuclear"
        jelzok = kartya.consumable_attributes or []
        if "total_damage" in jelzok:
            return "efp"
        if "critical" in jelzok or "hq" in jelzok:
            return "cr"
        return "he"

    def _eject_backwards(self, mine, mine_tier: int) -> None:
        mover = mine.mover_of()
        mover.movement_options.shift_to(Gear.Regular)
        mover.movement_options.throttle_to(0)

        ship_position = self._casting_ship.mover_of().position_of()
        mine_position = mover.position_of()
        backward = Vector3.sub(mine_position, ship_position)
        if backward.magnitude_ < 0.001:
            return
        backward.normalize_()
        eject_speed = 20.0 + 5.0 * mine_tier
        mover.queue_maneuver(PulseManeuver(Vector3.mult(backward, eject_speed)))

    def _consumable_bonus_onto(self, mine_stats) -> None:
        bonus_stats = self._toltet_bonusza()
        if bonus_stats is None:
            return
        for kulcs, fraction in bonus_stats.all_stats.items():
            if mine_stats.holds_stat(kulcs):
                mine_stats.set_stat(kulcs, mine_stats.stat(kulcs) * (1.0 + fraction))

    def _toltet_bonusza(self):
        toltet = self._casting_slot.current_consumable
        if toltet is None:
            return None
        kartya = toltet.ship_consumable_card
        return None if kartya is None else kartya.item_buff_add


class TailDeed(Deed):
    def __init__(self, elsutes: Elsutes):
        super().__init__(elsutes)

    def _carry_out(self) -> bool:
        if len(self._chosen_targets) != 1:
            return False

        celpont = self._chosen_targets[0]
        if celpont.is_removed() or not self._tier_gate_passes(celpont):
            return False

        caster_pos = self._casting_ship.mover_of().position_of()
        target_pos = celpont.mover_of().position_of()
        max_range = self._ability.item_buff_add.stat_or_default(ObjectStat.MaxRange)
        if max_range > 0 and not within_range(caster_pos, target_pos, 0, max_range):
            return False

        self._casting_ship.mover_of().queue_maneuver(FollowManeuver(celpont))
        return True


class SurveyDeed(Deed):
    def __init__(self, elsutes: Elsutes, loot_ownership):
        super().__init__(elsutes)
        self._loot_ownership = loot_ownership

    def _carry_out(self) -> bool:
        if not self._casting_ship.is_player():
            return False
        client = self._ctx.users().user(self._casting_ship.pilot_id())
        if client is None:
            return False

        game_protocol = client.protocol_of(ProtocolID.Game)
        terv = self._ctx.blueprint()
        return all(
            SurveyDeed.scan_process(
                client,
                game_protocol,
                celpont,
                self._loot_ownership,
                terv.sector_desc.mining_ship_config.cubit_price,
                self._ctx.sender(),
                terv.sector_cards().sector_card,
                terv.sector_desc.sector_id)
            for celpont in self._hatotavon_belul())

    def _hatotavon_belul(self):
        honnan = self._casting_ship.mover_of().position_of()
        hatotav = self._ability.item_buff_add.stat_or_default(ObjectStat.MaxRange)
        hatotav_negyzet = hatotav * hatotav
        for celpont in self._chosen_targets:
            if Vector3.squared_distance(
                    honnan, celpont.mover_of().position_of()) <= hatotav_negyzet:
                yield celpont

    @staticmethod
    def scan_process(user, game_protocol, target, loot_ownership, cubit_price, sender, sector_card, sector_id) -> bool:
        if not target.space_entity_type.of_kind(ObjectKind.Asteroid, ObjectKind.Planetoid):
            log.warning('scan pointed at something other than an asteroid')
            return False
        asteroid = target
        zsakmany = loot_ownership.get(asteroid)
        loot_desc = zsakmany
        resource = None if loot_desc is None else loot_desc.loot_items()[0].ship_item

        ar = Price()
        is_minable = False
        if isinstance(asteroid, Planetoid):
            planetoid = asteroid
            ar.add_item(ResourceKind.Cubits.guid, cubit_price)
            is_minable = not planetoid.owns_miner() and loot_desc is not None
        else:
            user.pilot_of().tally_desk.bump_counter(
                TallyCardKind.asteroids_scanned, sector_card.card_guid_of())

        bw = game_protocol.scan(asteroid.id_in_space(), resource, is_minable, ar,
                                datetime(1970, 1, 1, 0, 0, 0), sector_id)
        sender.push_to(bw, user)

        return True


class MendDeed(Deed):
    def __init__(self, elsutes: Elsutes):
        super().__init__(elsutes)

    def _carry_out(self) -> bool:
        max_hp = self._caster_stats.stat(ObjectStat.MaxHullPoints)
        max_pp = self._caster_stats.stat(ObjectStat.MaxPowerPoints)
        current_hp = self._caster_stats.hp
        current_pp = self._caster_stats.pp

        if self._ability.item_buff_add.holds_stat(ObjectStat.HullPointRestore):
            hp_restore = self._ability.item_buff_add.stat(ObjectStat.HullPointRestore)
            new_hp = Maths.min(max_hp, current_hp + hp_restore)
            self._caster_stats.set_hull(new_hp)
        if self._ability.item_buff_add.holds_stat(ObjectStat.PowerPointRestore):
            pp_restore = self._ability.item_buff_add.stat(ObjectStat.PowerPointRestore)
            new_pp = Maths.min(max_pp, current_pp + pp_restore)
            self._caster_stats.set_power(new_pp)
        return True


class ShortCircuitDeed(Deed):
    def __init__(self, elsutes: Elsutes, engagement):
        super().__init__(elsutes)
        self._engagement = engagement

    def _carry_out(self) -> bool:
        if not self._chosen_targets:
            return False

        kepesseg = self._ability.item_buff_add
        alap_hossz = kepesseg.stat_or_default(ObjectStat.Duration)
        ero = kepesseg.stat_or_default(
            ObjectStat.PenetrationStrength,
            self._caster_stats.stat_or_default(ObjectStat.PenetrationStrength))
        legkozelebb = kepesseg.stat_or_default(ObjectStat.MinRange)
        legtavolabb = kepesseg.stat_or_default(ObjectStat.MaxRange)
        honnan = self._casting_ship.mover_of().position_of()

        volt_talalat = False
        for celpont in self._chosen_targets:
            if celpont.is_removed() or not celpont.is_ship or not self._tier_gate_passes(celpont):
                continue
            if not within_range(
                    honnan, celpont.mover_of().position_of(),
                    legkozelebb, legtavolabb):
                continue
            self._emp_rarakasa(celpont, alap_hossz, ero)
            volt_talalat = True

        if volt_talalat and self._casting_ship.is_player():
            self._casting_ship.space_subscribe_info().note_combat_moment(
                self._ctx.tick().time_stamp())
        return volt_talalat

    def _emp_rarakasa(self, celpont, alap_hossz: float, ero: float) -> None:
        allapotok = celpont.space_subscribe_info()
        hossz = self._engagement.jam_duration(
            alap_hossz, ero, allapotok.stat_or_default(ObjectStat.FirewallRating))

        modosito = ShipTweak.create(self._ability, self._system, self._started_at,
                                    self._casting_ship.pilot_id())
        modosito.item_buff_add.set_stat(ObjectStat.Duration, hossz)
        allapotok.take_modifier(modosito)
        celpont.world_state_of().set_emp_on(True)


class SlideDeed(Deed):
    def __init__(self, elsutes: Elsutes):
        super().__init__(elsutes)

    def _carry_out(self) -> bool:
        slide = ShipTweak.create(self._ability, self._system, self._started_at,
                                 self._casting_ship.pilot_id())
        self._caster_stats.take_modifier(slide)
        beallitasok = self._casting_ship.mover_of().movement_options
        current_maneuver = self._casting_ship.mover_of().current_maneuver
        if isinstance(current_maneuver, PitchYawTurnPlan):
            turn_by_pitch_yaw_strikes_old = current_maneuver
            new_strafe_values = turn_by_pitch_yaw_strikes_old.strafe_direction.copy()
            new_strafe_values.x_to(new_strafe_values.x * 0.0)
            new_strafe_values.y_to(new_strafe_values.y * 0.0)
            turn_by_pitch_yaw_strikes_rcs_edition = PitchYawTurnPlan(
                turn_by_pitch_yaw_strikes_old.pitch_yaw_roll_factor.copy(),
                new_strafe_values,
                turn_by_pitch_yaw_strikes_old.strafe_magnitude)
            self._casting_ship.mover_of().queue_maneuver(turn_by_pitch_yaw_strikes_rcs_edition)
        beallitasok.shift_to(Gear.RCS)
        self._casting_ship.mover_of().flag_movement_dirty()
        return True


class StealthDeed(Deed):
    _MIN_UPKEEP_INTERVAL_SECONDS = world_timers().upkeep_min_interval_seconds

    def __init__(self, elsutes: Elsutes, cast_desk=None):
        super().__init__(elsutes)
        self._cast_desk = cast_desk

    def process(self) -> bool:
        self._remove_auto_cast = False
        self._last_failure_reason = None
        self._started_at = self._ctx.tick().time_stamp()
        allapot = self._casting_ship.world_state_of()

        is_cloaked = allapot.is_cloaked
        if is_cloaked:
            if self._is_boosting():
                self._set_failure_reason("boosting")
                self._deactivate(allapot, remove_auto_cast=True)
                return False
            self._apply_upkeep(allapot)
            return not self._remove_auto_cast

        if self._is_boosting():
            self._set_failure_reason("boosting")
            self._remove_auto_cast = True
            return False

        return self._activate(allapot)

    def _carry_out(self) -> bool:
        return False

    def _activate(self, state) -> bool:
        self._cooldown = self._ability.item_buff_add.stat_or_default(ObjectStat.Cooldown)
        self._pp_cost = self._ability.item_buff_add.stat_or_default(ObjectStat.PowerPointCost)
        last_used_plus_cooldown = int((self._system.time_of_last_use + self._cooldown) * 1000)
        if self._started_at - last_used_plus_cooldown < 0:
            self._set_failure_reason("cooldown")
            self._remove_auto_cast = True
            return False
        if self._caster_stats.pp < self._pp_cost:
            self._set_failure_reason("insufficient_power")
            self._remove_auto_cast = True
            return False
        if not self._consumables_available(self._casting_ship, self._casting_slot):
            self._set_failure_reason("missing_consumable")
            self._remove_auto_cast = True
            return False

        if isinstance(self._casting_ship, PlayerShip):
            self._casting_ship.visibility_of().settle_ghost_jump()

        self._spend_consumables(self._casting_ship, self._casting_slot)
        self._caster_stats.set_power(self._caster_stats.pp - self._pp_cost)
        self._system.note_use(self._started_at)
        set_toggle_upkeep_seconds(self._system, self._started_at * 0.001)
        self._set_cloaked_and_broadcast(True)
        self._push_cast_with_slots()
        return True

    def _apply_upkeep(self, state) -> None:
        now_seconds = self._started_at * 0.001
        elapsed_seconds = max(0.0, now_seconds - get_toggle_upkeep_seconds(self._system))
        if elapsed_seconds < self._MIN_UPKEEP_INTERVAL_SECONDS:
            return

        cost_per_second = self._ability.item_buff_add.stat_or_default(ObjectStat.PpCostPerSec)
        pp_cost = cost_per_second * elapsed_seconds
        if pp_cost <= 0:
            set_toggle_upkeep_seconds(self._system, now_seconds)
            return
        if self._caster_stats.pp < pp_cost:
            self._caster_stats.set_power(0)
            set_toggle_upkeep_seconds(self._system, now_seconds)
            self._deactivate(state, remove_auto_cast=True)
            return

        self._caster_stats.set_power(self._caster_stats.pp - pp_cost)
        set_toggle_upkeep_seconds(self._system, now_seconds)

    def _deactivate(self, state, remove_auto_cast: bool = False) -> None:
        if remove_auto_cast:
            self._remove_auto_cast = True
        if state.is_cloaked:
            self._set_cloaked_and_broadcast(False)
            self._send_player_stop_slot_ability()

    @property
    def should_remove_auto_cast(self) -> bool:
        return self._remove_auto_cast

    def _is_boosting(self) -> bool:
        mover = self._casting_ship.mover_of()
        if mover is None:
            return False
        return mover.movement_options.gear_of == Gear.Boost

    def _send_player_stop_slot_ability(self) -> None:
        if not self._casting_ship.is_player():
            return
        user = self._ctx.users().user(self._casting_ship.pilot_id())
        if user is None:
            return

        game_protocol = user.protocol_of(ProtocolID.Game)
        self._ctx.sender().push_to(
            game_protocol.replies.stop_slot_ability(self._system.server_id), user)

    def _set_cloaked_and_broadcast(self, cloaked: bool) -> None:
        allapot = self._casting_ship.world_state_of()
        if allapot.is_cloaked == cloaked:
            return
        allapot.cloak(cloaked)
        if cloaked:
            self._clear_carrier_mark()

        game = game_replies()
        self._ctx.sender().push_to_everyone(game.space_object_state(allapot))

        if cloaked:
            self._clear_out_of_visual_range_target_locks()

        if isinstance(self._casting_ship, PlayerShip):
            visibility = self._casting_ship.visibility_of()
            if cloaked:
                visibility.start_stealth()
            else:
                visibility.finish_stealth()

    def _clear_carrier_mark(self) -> None:
        mutatok = self._casting_ship.space_subscribe_info()
        if (modifiers := mutatok.modifiers) is not None:
            to_remove = {
                modifier.server_id
                for modifier in modifiers.of_type(AbilityActionKind.ActivatePaintTheTarget)
            }
            if to_remove:
                mutatok.remove_modifiers(to_remove)
        self._casting_ship.world_state_of().set_marked_by_carrier(False)

    def _clear_out_of_visual_range_target_locks(self) -> None:
        target_object_id = self._casting_ship.id_in_space()
        regulation_card = self._ctx.blueprint().sector_cards().regulation_card()
        target_bracket_mode = regulation_card.target_bracket_mode

        for observer_ship in self._iter_observer_ships():
            if observer_ship is self._casting_ship:
                continue
            if not self._is_enemy_observer(observer_ship, target_bracket_mode):
                continue
            observer_info = observer_ship.space_subscribe_info()
            observer_target = observer_info.target_object_id
            if observer_target is None or observer_target.get() != target_object_id:
                continue
            if is_inside_visual_detection_radius(observer_ship, self._casting_ship):
                continue

            observer_info.target_object_id = 0
            if self._cast_desk is not None:
                self._cast_desk.remove_auto_cast_abilities_targeting_object(
                    observer_ship.id_in_space(), target_object_id)

    def _iter_observer_ships(self):
        if hasattr(self._ctx, "space_objects"):
            space_objects = self._ctx.space_objects()
            if hasattr(space_objects, "ships_stream_of"):
                return list(space_objects.ships_stream_of())
        return list(self._ctx.users().player_ships_collection)

    def _is_enemy_observer(self, observer_ship, target_bracket_mode) -> bool:
        viszony = relation(observer_ship, self._casting_ship, target_bracket_mode)
        return viszony == Stance.Enemy


_TOGGLE_SYSTEM_MODIFIER_DURATION_SECONDS = world_timers().toggle_modifier_seconds


class ToggleDeed(Deed):
    _MIN_UPKEEP_INTERVAL_SECONDS = world_timers().upkeep_min_interval_seconds

    def __init__(self, elsutes: Elsutes):
        super().__init__(elsutes)
        self._remove_auto_cast = False

    def process(self) -> bool:
        self._remove_auto_cast = False
        self._last_failure_reason = None
        self._started_at = self._ctx.tick().time_stamp()

        if self._find_active_modifier() is not None:
            self._apply_upkeep()
            return not self._remove_auto_cast

        return self._activate()

    def _carry_out(self) -> bool:
        return False

    def _activate(self) -> bool:
        self._cooldown = self._ability.item_buff_add.stat_or_default(ObjectStat.Cooldown)
        self._pp_cost = self._ability.item_buff_add.stat_or_default(ObjectStat.PowerPointCost)
        last_used_plus_cooldown = int((self._system.time_of_last_use + self._cooldown) * 1000)
        if self._started_at - last_used_plus_cooldown < 0:
            self._set_failure_reason("cooldown")
            self._log_activation_blocked("cooldown")
            self._remove_auto_cast = True
            return False
        if self._caster_stats.pp < self._pp_cost:
            self._set_failure_reason("insufficient_power")
            self._log_activation_blocked("insufficient power")
            self._remove_auto_cast = True
            return False
        if not self._consumables_available(self._casting_ship, self._casting_slot):
            self._set_failure_reason("missing_consumable")
            self._log_activation_blocked("missing consumable")
            self._remove_auto_cast = True
            return False

        if isinstance(self._casting_ship, PlayerShip):
            self._casting_ship.visibility_of().settle_ghost_jump()

        item_buff_add = self._ability.item_buff_add.copy()
        item_buff_add.set_stat(ObjectStat.Duration, _TOGGLE_SYSTEM_MODIFIER_DURATION_SECONDS)
        modifier = ShipTweak.create_with_remote_buffs(
            self._ability,
            self._system,
            self._started_at,
            self._casting_ship.pilot_id(),
            item_buff_add,
            self._ability.ship_ability_card.toggle_system_add,
            self._ability.ship_ability_card.toggle_system_multiply,
        )
        self._caster_stats.take_modifier(modifier)
        self._spend_consumables(self._casting_ship, self._casting_slot)
        self._caster_stats.set_power(self._caster_stats.pp - self._pp_cost)
        self._system.note_use(self._started_at)
        set_toggle_upkeep_seconds(self._system, self._started_at * 0.001)
        self._push_cast_with_slots()
        return True

    def _apply_upkeep(self) -> None:
        now_seconds = self._started_at * 0.001
        elapsed_seconds = max(0.0, now_seconds - get_toggle_upkeep_seconds(self._system))
        if elapsed_seconds < self._MIN_UPKEEP_INTERVAL_SECONDS:
            return

        cost_per_second = self._ability.item_buff_add.stat_or_default(ObjectStat.PpCostPerSec)
        pp_cost = cost_per_second * elapsed_seconds
        if pp_cost <= 0:
            set_toggle_upkeep_seconds(self._system, now_seconds)
            return
        if self._caster_stats.pp < pp_cost:
            self._caster_stats.set_power(0)
            set_toggle_upkeep_seconds(self._system, now_seconds)
            self.deactivate(send_stop=True)
            self._remove_auto_cast = True
            return

        self._caster_stats.set_power(self._caster_stats.pp - pp_cost)
        set_toggle_upkeep_seconds(self._system, now_seconds)

    def deactivate(self, send_stop: bool = False) -> None:
        active = self._find_active_modifier()
        if active is None:
            return
        self._caster_stats.remove_modifiers({active.server_id})
        if send_stop:
            self._send_player_stop_slot_ability()

    def _log_activation_blocked(self, reason: str) -> None:
        log.info("Toggle system activation blocked (%s): ship=%s system=%s",
                 reason, self._casting_ship.id_in_space(), self._system.server_id)

    @property
    def should_remove_auto_cast(self) -> bool:
        return self._remove_auto_cast

    def _find_active_modifier(self):
        modifiers = self._caster_stats.modifiers
        if modifiers is None:
            return None
        system_id = self._system.server_id
        for modifier in modifiers.all():
            ship_system = modifier.ship_system
            if ship_system is not None and ship_system.server_id == system_id:
                return modifier
        return None

    def _send_player_stop_slot_ability(self) -> None:
        if not self._casting_ship.is_player():
            return
        user = self._ctx.users().user(self._casting_ship.pilot_id())
        if user is None:
            return
        game_protocol = user.protocol_of(ProtocolID.Game)
        self._ctx.sender().push_to(
            game_protocol.replies.stop_slot_ability(self._system.server_id), user)


class GunDeed(Deed):
    def __init__(self, elsutes: Elsutes, weapon_fx_type, engagement, damage_book, cast_desk=None):
        super().__init__(elsutes)
        self._spot_desc = None
        self._weapon_fx_type = weapon_fx_type
        self._dice = elsutes.ctx.dice()
        self._engagement = engagement
        self._damage_book = damage_book
        self._cast_desk = cast_desk

    def _ready_to_fire(self) -> bool:
        eredmeny = super()._ready_to_fire()
        if not eredmeny:
            return False
        if not self._planetoid_targets_allowed:
            self._chosen_targets[:] = [t for t in self._chosen_targets
                                       if t.space_entity_type != ObjectKind.Planetoid]
            if len(self._chosen_targets) == 0 and not self._can_cast_without_targets:
                return False
        spot_desc = self._casting_ship.world_card().spot(self._spot_hash_of)
        if spot_desc is None:
            return False
        self._spot_desc = spot_desc
        return True

    @property
    def _planetoid_targets_allowed(self) -> bool:
        return False

    @property
    def _can_cast_without_targets(self) -> bool:
        return False

    @property
    def _spot_hash_of(self) -> int:
        return self._casting_slot.ship_slot_card().object_point_server_hash

    def _target_size_fits(self, cel_merete: int) -> bool:
        return len(self._chosen_targets) == cel_merete

    def _reach_covers_target(self, target) -> bool:
        caster_transform = self._casting_ship.mover_of().transform_of()
        spot_transform = self._spot_desc.local_transform()
        target_pos = target.mover_of().position_of()

        min_range = self._get_min_range
        max_range = self._get_max_range()
        szog = self._ability.item_buff_add.stat_or_default(ObjectStat.Angle)
        if not self._casting_ship.mover_of().is_moving_object:
            szog = 360.0
        cone_angle = szog

        return weapon_reaches(caster_transform, spot_transform, target_pos,
                              min_range, max_range, cone_angle)

    @property
    def _get_min_range(self) -> float:
        return self._ability.item_buff_add.stat_or_default(ObjectStat.MinRange)

    def _get_max_range(self) -> float:
        return self._ability.item_buff_add.stat_or_default(ObjectStat.MaxRange)

    def _hit_roll_passes(self, target) -> bool:
        fegyver = self._ability.item_buff_add
        esely = self._engagement.chance_to_hit(
            self._kiteres_most(target),
            fegyver.stat_or_default(ObjectStat.Accuracy),
            fegyver.stat_or_default(ObjectStat.MaxRange),
            fegyver.stat_or_default(ObjectStat.OptimalRange),
            self._loves_tavolsaga(target))
        return self._dice.passes(esely)

    def _kiteres_most(self, target) -> float:
        statok = target.space_subscribe_info()
        repules = target.mover_of().current_maneuver.movement_options
        return self._engagement.avoidance_at_speed(
            statok.stat_or_default(ObjectStat.Avoidance),
            repules.throttle_speed,
            statok.stat_or_default(ObjectStat.Speed),
            repules.gear_of,
            statok.stat_or_default(ObjectStat.AvoidanceFading))

    def _loves_tavolsaga(self, target) -> float:
        honnan = point_position_relative_to(
            self._spot_desc.local_position,
            self._casting_ship.mover_of().position_of(),
            self._casting_ship.mover_of().rotation_of())
        return Vector3.distance(honnan, target.mover_of().position_of())

    def _break_stealth_on_weapon_fire(self, target) -> None:
        if is_cloaked_player(self._casting_ship):
            deactivate_player_stealth(self._ctx, self._casting_ship, self._cast_desk)
        if is_cloaked_player(target):
            deactivate_player_stealth(self._ctx, target, self._cast_desk)

    def _push_weapon_shot(self, fegyver_kulcs: int, target) -> None:
        if target is not None:
            if target.faction != Faction.Neutral:
                self._casting_ship.space_subscribe_info().note_combat_moment(self._started_at)
            target.space_subscribe_info().note_combat_moment(self._started_at)

        if self._weapon_fx_type == WeaponEffect.MissileLauncher:
            return

        space_replies = game_replies()

        target_id = target.id_in_space() if target is not None else 0
        weapon_shop_bw = space_replies.weapon_shot(
            self._casting_ship.id_in_space(), fegyver_kulcs, target_id, self._weapon_fx_type)

        self._ctx.sender().push_to_everyone(weapon_shop_bw)


class PaintDeed(BaneDeed):
    def __init__(self, elsutes: Elsutes, engagement):
        super().__init__(elsutes, engagement)

    def _carry_out(self) -> bool:
        if len(self._chosen_targets) != 1:
            return False

        eredmeny = super()._carry_out()
        if not eredmeny:
            return False

        celpont = self._chosen_targets[0]
        celpont.world_state_of().set_marked_by_carrier(True)
        return True

    def _clean_duration(self, standard_duration: float, ado_ereje: float, fire_wall: float) -> float:
        return standard_duration


class SplashDeed(GunDeed):
    def __init__(self, elsutes: Elsutes, weapon_fx_type, engagement, damage_book):
        super().__init__(elsutes, weapon_fx_type, engagement, damage_book)

    def _deal_aoe_dmg(self) -> bool:
        spot_hash = self._spot_hash_of
        caster_faction = self._casting_ship.faction
        for celpont in self._chosen_targets:
            if celpont.is_removed():
                continue

            if not celpont.faction.hostile_to(caster_faction):
                continue

            if not self._reach_covers_target(celpont):
                continue

            if not self._hit_roll_passes(celpont):
                continue

            self._damage_book.hurt_by_ability(self._casting_ship, celpont, self._ability)

        self._push_weapon_shot(spot_hash, None)

        return True


class CannonDeed(GunDeed):
    def __init__(self, elsutes: Elsutes, engagement, damage_book, cast_desk=None, weapon_fx_type=None):
        if weapon_fx_type is None:
            kartya = elsutes.slot.ship_ability().ship_ability_card
            kinetikus = (kartya.ability_action_type == AbilityActionKind.FireKillCannon
                         or kartya.overwrite_action_type == AbilityActionKind.FireCannon)
            weapon_fx_type = WeaponEffect.Railgun if kinetikus else WeaponEffect.Gun
        super().__init__(elsutes, weapon_fx_type, engagement, damage_book, cast_desk)

    def _carry_out(self) -> bool:
        if not self._target_size_fits(1):
            self._set_failure_reason("target_count")
            return False

        celpont = self._chosen_targets[0]
        if celpont.is_removed() or not self._reach_covers_target(celpont):
            self._set_failure_reason("out_of_reach")
            return False

        self._break_stealth_on_weapon_fire(celpont)
        is_hit = self._hit_roll_passes(celpont)
        if is_hit:
            self._damage_book.hurt_by_ability(self._casting_ship, celpont, self._ability)
        self._push_weapon_shot(self._spot_hash_of, celpont)
        return True


class ShotgunDeed(CannonDeed):
    def __init__(self, elsutes: Elsutes, engagement, damage_book, cast_desk=None):
        super().__init__(elsutes, engagement, damage_book, cast_desk, WeaponEffect.Flechete)


class RepeaterDeed(CannonDeed):
    def __init__(self, elsutes: Elsutes, engagement, damage_book, cast_desk=None):
        super().__init__(elsutes, engagement, damage_book, cast_desk, WeaponEffect.MachineGun)


class MiningBeamDeed(GunDeed):
    def __init__(self, elsutes: Elsutes, engagement, damage_book):
        super().__init__(elsutes, WeaponEffect.Gun, engagement, damage_book)

    def _carry_out(self) -> bool:
        if not self._target_size_fits(1):
            return False

        celpont = self._chosen_targets[0]
        if celpont.is_removed() or not self._reach_covers_target(celpont):
            return False

        is_hit = self._hit_roll_passes(celpont)
        if is_hit:
            self._damage_book.hurt_by_mining(self._casting_ship, celpont, self._ability)
        self._push_weapon_shot(self._spot_hash_of, celpont)
        return True

    @property
    def _planetoid_targets_allowed(self) -> bool:
        return True


class MissileDeed(GunDeed):
    def __init__(self, elsutes: Elsutes, engagement, damage_book, arrival_gate, cast_desk=None):
        super().__init__(elsutes, WeaponEffect.MissileLauncher, engagement, damage_book, cast_desk)
        self._arrival_gate = arrival_gate

    INDITAS_AKADALYAI = (
        (lambda cel: cel.is_removed(), "target_removed"),
        (lambda cel: cel.space_entity_type == ObjectKind.Asteroid, "asteroid_target"),
    )

    def _carry_out(self) -> bool:
        if not self._target_size_fits(1):
            self._set_failure_reason("target_count")
            return False

        celpont = self._chosen_targets[0]
        for akadaly, ok in self.INDITAS_AKADALYAI:
            if akadaly(celpont):
                self._set_failure_reason(ok)
                return False
        if not self._reach_covers_target(celpont):
            self._set_failure_reason("out_of_range")
            return False

        loszerrel_megy, loszer = self._loszer_kartyaja()
        missile_guid = self._get_missile_guid(loszerrel_megy, loszer)
        if missile_guid == -1:
            self._set_failure_reason("missing_missile_consumable")
            return False

        self._break_stealth_on_weapon_fire(celpont)
        raketa = self._ctx.object_forge.hatch_missile(
            self._casting_ship, celpont, self._spot_desc, missile_guid, self._started_at)
        self._raketa_felszerelese(raketa, loszer if loszerrel_megy else None)
        raketa.mover_of().queue_maneuver(self._indito_manover(celpont))

        self._arrival_gate.admit_object(raketa)
        self._push_weapon_shot(self._spot_hash_of, celpont)
        return True

    def _loszer_kartyaja(self):
        loszerrel = (self._ability.ship_ability_card.ship_consumable_option
                     == ShipConsumableOption.Using)
        betoltve = self._casting_slot.current_consumable
        return loszerrel, (None if betoltve is None else betoltve.ship_consumable_card)

    def _raketa_felszerelese(self, missile, loszer) -> None:
        mutatok = missile.space_subscribe_info().stats_of
        mutatok.merge_in(self._ability.item_buff_add)
        if loszer is not None and loszer.effect_type == ConsumableEffectKind.DamageNuclear:
            apply_to_missile_stats(mutatok, self._ability.ship_ability_card, loszer)
            ensure_aoe_stats(mutatok, self._ability.ship_ability_card)
            mutatok.merge_in(loszer.item_buff_multiply)

        mozgas = missile.mover_of().movement_options
        mozgas.shift_to(Gear.Regular)
        mozgas.throttle_to(mutatok.stat(ObjectStat.Speed))
        mutatok.set_stat(ObjectStat.MaxPowerPoints, 0)
        missile.space_subscribe_info().set_hull(mutatok.stat(ObjectStat.MaxHullPoints))
        missile.space_subscribe_info().cap_hull_and_power()

    def _indito_manover(self, target):
        mozgato = self._casting_ship.mover_of()
        atadott_lendulet = (mozgato.frame.linear_speed.magnitude_ * 0.5
                            if mozgato.movement_options.gear_of == Gear.RCS else 0)
        keszito = TargetLaunchManeuver if mozgato.is_moving_object else StaticLaunchManeuver
        return keszito(self._casting_ship, self._spot_desc, atadott_lendulet, target)

    def _get_max_range(self) -> float:
        max_range = super()._get_max_range()
        if max_range > 0:
            return max_range

        action_type = self._ability.ship_ability_card.ability_action_type
        if action_type != AbilityActionKind.FireLightMissile:
            return max_range

        mutatok = self._ability.item_buff_add
        sebesseg = mutatok.stat_or_default(ObjectStat.Speed)
        life_time = mutatok.stat_or_default(ObjectStat.LifeTime)
        if sebesseg <= 0 or life_time <= 0:
            return max_range
        return sebesseg * life_time

    def _get_missile_guid(self, fogyoeszkozzel: bool, ship_consumable_card) -> int:
        if ship_consumable_card is None and fogyoeszkozzel:
            if not self._casting_ship.is_player():
                return WellKnownCard.MissileCard.value
            log.error('missile launch stalled - ammo card absent')
            return -1

        missile_guid = 0
        if not fogyoeszkozzel:
            missile_guid = WellKnownCard.MissileCard.value
        else:
            effect_type = ship_consumable_card.effect_type
            if effect_type is None:
                raise TypeError('the consumable card has no effect kind')
            if effect_type == ConsumableEffectKind.DamageNuclear:
                missile_guid = WellKnownCard.MissileNuke.value
                if ship_consumable_card.item_buff_add.holds_stat(ObjectStat.DamageHigh):
                    dmg_high = ship_consumable_card.item_buff_add.stat(ObjectStat.DamageHigh)
                    if dmg_high == 4.0:
                        missile_guid = WellKnownCard.MissileMiniNuke.value
            else:
                missile_guid = WellKnownCard.MissileCard.value

        return missile_guid


class FortifyDeed(ToggleDeed):
    def process(self) -> bool:
        processed = super().process()
        if processed and self._find_active_modifier() is not None:
            self._set_fortified_and_broadcast(True)
        return processed

    def deactivate(self, send_stop: bool = False) -> None:
        had_modifier = self._find_active_modifier() is not None
        was_fortified = self._casting_ship.world_state_of().is_fortified
        super().deactivate(send_stop)
        if had_modifier or was_fortified:
            self._set_fortified_and_broadcast(False)

    def _set_fortified_and_broadcast(self, fortified: bool) -> None:
        allapot = self._casting_ship.world_state_of()
        if allapot.is_fortified == fortified:
            return
        allapot.set_fortified(fortified)
        object_id = self._safe_call(self._casting_ship, "id_in_space")
        player_id = self._safe_call(self._casting_ship, "pilot_id")
        log.info("Carrier fortified=%s ship=%s player=%s",
                 fortified, object_id, player_id)
        self._ctx.sender().push_to_everyone(
            game_replies().space_object_state(allapot))

    @staticmethod
    def _safe_call(obj, method_name: str):
        method = getattr(obj, method_name, None)
        return method() if callable(method) else None


class FlakDeed(SplashDeed):
    def __init__(self, elsutes: Elsutes, engagement, damage_book):
        super().__init__(elsutes, WeaponEffect.Flak, engagement, damage_book)

    def _carry_out(self) -> bool:
        self._weapon_fx_type = WeaponEffect.Flak
        return self._deal_aoe_dmg()


class PointDefenceDeed(SplashDeed):
    def __init__(self, elsutes: Elsutes, engagement, damage_book):
        super().__init__(elsutes, WeaponEffect.PointDefence, engagement, damage_book)

    def _carry_out(self) -> bool:
        return self._deal_aoe_dmg()


_AREA_TARGET_SPATIAL_INDEX_MAX_CELLS_PER_OBJECT = _CONFIG.int(
    "rebsgo.sector.spatial-index.ability-area-max-cells-per-object", 512)
_SHRAPNEL_CONSUMABLE_TYPE = 26008
_SHRAPNEL_ABILITY_GROUP_ID = 41011982


def is_shrapnel_burst_slot(kilovo_rekesz) -> bool:
    ship_system = kilovo_rekesz.ship_system
    kepesseg = kilovo_rekesz.ship_ability()
    if ship_system is None or kepesseg is None:
        return False

    system_card = ship_system.ship_system_card
    ability_card = kepesseg.ship_ability_card
    if system_card is None or ability_card is None:
        return False

    return (
        system_card.ship_slot_type == ShipSlotType.gun
        and system_card.tier == 4
        and ability_card.ability_action_type == AbilityActionKind.Flak
        and ability_card.ability_affect_of() == ShipAbilityAffect.Area
        and ability_card.ability_group_id == _SHRAPNEL_ABILITY_GROUP_ID
        and ability_card.consumable_type == _SHRAPNEL_CONSUMABLE_TYPE
        and ability_card.consumable_option_of() == ShipConsumableOption.NotUsing
    )


class ShrapnelDeed(SplashDeed):
    def __init__(self, elsutes: Elsutes, engagement, damage_book, cast_desk=None):
        super().__init__(elsutes, WeaponEffect.Shrapnel, engagement, damage_book)
        self._cast_desk = cast_desk

    @property
    def _can_cast_without_targets(self) -> bool:
        return not self._is_auto_cast_ability

    def _carry_out(self) -> bool:
        if not self._chosen_targets:
            self._chosen_targets[:] = self._collect_area_targets()
        for celpont in self._chosen_targets:
            if celpont.is_removed():
                continue
            if not celpont.faction.hostile_to(self._casting_ship.faction):
                continue
            if not self._reach_covers_target(celpont):
                continue
            if not self._hit_roll_passes(celpont):
                continue
            self._break_stealth_on_weapon_fire(celpont)
            self._damage_book.hurt_by_ability(self._casting_ship, celpont, self._ability)

        self._push_weapon_shot(self._spot_hash_of, None)
        return True

    def _collect_area_targets(self):
        space_objects = getattr(self._ctx, "space_objects", None)
        if space_objects is None:
            return []
        tarolo = space_objects()
        if tarolo is None:
            return []
        ships = tarolo.ships_stream_of() if hasattr(tarolo, "ships_stream_of") else tarolo.values()
        ships = self._prefilter_area_candidates(tuple(ships))
        return [
            celpont for celpont in ships
            if celpont is not self._casting_ship
            and not celpont.is_removed()
            and (not hasattr(celpont, "is_visible") or celpont.is_visible())
            and celpont.faction.hostile_to(self._casting_ship.faction)
        ]

    def _prefilter_area_candidates(self, ships):
        if (not _AREA_TARGET_SPATIAL_INDEX_ENABLED
            or len(ships) < _AREA_TARGET_SPATIAL_INDEX_MIN_OBJECTS):
            return ships
        max_range = self._get_max_range()
        if max_range <= 0:
            return ships
        try:
            sorszam = build_complete_spatial_index(
                ships,
                _AREA_TARGET_SPATIAL_INDEX_CELL_SIZE,
                _AREA_TARGET_SPATIAL_INDEX_MAX_CELLS_PER_OBJECT,
                log,
                "Ability area target",
            )
            if sorszam is None:
                return ships
            kozeppont = point_position_relative_to(
                self._spot_desc.local_position,
                self._casting_ship.mover_of().position_of(),
                self._casting_ship.mover_of().rotation_of(),
            )
            return ordered_radius_candidates(ships, sorszam, kozeppont, max_range)
        except Exception:
            log.exception("Ability area target spatial query failed; falling back to the plain sweep")
            return ships
