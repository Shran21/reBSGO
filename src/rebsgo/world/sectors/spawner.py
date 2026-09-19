# github.com/Shran21
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from threading import Lock

from rebsgo.services import Services
from rebsgo.world.carriers.carrier_mode import is_carrier_ship_card
from rebsgo.world.capitals.capital_roster import is_capital_guid
from rebsgo.world.movement.maneuvers import TurnManeuver
from rebsgo.world.movement.held_keys import QWEASD
from rebsgo.pilots.state.holdings.storages import ShipSlot, ShipSlots, SlotName
from rebsgo.world.sectors.spoils.drops import NpcSpoils, PvpSpoils
from rebsgo.world.sectors.npc_minds import DefendGoal, KillGoal
from rebsgo.world.objects.bodies import Asteroid, Comet, CargoObject, DebrisPile, JumpBeacon, Transponder, Planet, Planetoid
from rebsgo.world.objects.ships import PatrolBot, CruiserShip, MiningShip, Outpost, PlayerShip, WeaponPlatform
from rebsgo.world.objects.triggers import WorldTrigger
from rebsgo.world.objects.hazards import Mine, Missile
from rebsgo.world.objects.attachments import VisibleSet, ShipTraits, ShipHardpoints
from rebsgo.world.objects.numbers.kinds import ShipFeed, SpaceFeed
from rebsgo.vocabulary.pilot import ServerRoles, Faction, FactionGroup, Gear, OldShipRole, ShipTrait
from rebsgo.vocabulary.world import ArrivalCause, WellKnownObject, ObjectKind
from rebsgo.geometry.primitives.euler3 import Euler3
from rebsgo.geometry.primitives.transform import Transform
from rebsgo.geometry.primitives.vector3 import Vector3
from rebsgo.geometry.collider_shapes import SphereCollider
from rebsgo.gamedata.cards.card_view import CardView
from rebsgo.gamedata.cards.ship_cards import ShipSlotCard
from rebsgo.gamedata.library import Catalogue
from rebsgo.gamedata.collider_specs import AlignedBoxPlan, CapsulePlan, of_template, SpherePlan
from rebsgo.gamedata.loot_tables import LootByCard
from rebsgo.gamedata.npc_minds import outpost_template, platform_template
from rebsgo.gamedata.object_templates import PlanetSpec
from rebsgo.gamedata.ship_setups import first_best_config_for_guid, first_best_config_for_guid_and_level
from rebsgo.gamedata.ship_parts.parts import CountableItem, ShipSystem
from rebsgo.gamedata.from_json.small_readers import DefaultModelPaintFallbackReader
from rebsgo.gamedata.from_json.template_readers import NpcStatTemplateReader
from rebsgo.gamedata.reading import AbilityActionKind, ObjectStat, ObjectStats, ShipRole, ShipSlotType, SpotKind
from rebsgo.gamedata.from_json.combat_tuning_reader import fallback_systems
from rebsgo.helpers.dice import Dice
from rebsgo.helpers.carrier_transponder_diagnostics import (
    carrier_transponder_debug_enabled,
    format_ship_aspects,
    has_ship_aspect,
)
from rebsgo.helpers.color import Color
from rebsgo.helpers.floats import f32

log = logging.getLogger(__name__)

_LONG_MAX_VALUE = (1 << 63) - 1
_MISSING_COLLIDER_PREFABS_WARNED = set()
_MISSING_COLLIDER_PREFABS_WARN_LOCK = Lock()
_npc_stat_templates = None


def _get_npc_stat_templates():
    global _npc_stat_templates
    if _npc_stat_templates is None:
        _npc_stat_templates = NpcStatTemplateReader().fetch()
    return _npc_stat_templates


_FALLBACK_SLOTS_TOLD: set = set()

_default_model_paint_fallbacks = None


def _get_default_model_paint_fallbacks():
    global _default_model_paint_fallbacks
    if _default_model_paint_fallbacks is None:
        _default_model_paint_fallbacks = DefaultModelPaintFallbackReader().fetch()
    return _default_model_paint_fallbacks


def _is_stealth_ship_card(ship_card) -> bool:
    roles = ship_card.ship_roles or []
    return ShipRole.Stealth in roles or ship_card.ship_role_deprecated == OldShipRole.Stealth


class Spawner:
    def __init__(self, object_id_pool, collider_plans, sector_desc, loot_ownership, zsakmany_sablonok, tick,
                 sector_card):
        self._catalogue = Services.get(Catalogue)
        self._object_id_pool = object_id_pool
        self._collider_templates = collider_plans
        self._sector_desc = sector_desc
        self._loot_ownership = loot_ownership
        self._loot_templates = zsakmany_sablonok
        self._tick = tick
        self._sector_card = sector_card
        self._dice = Dice()
        self._npc_stat_templates = _get_npc_stat_templates()

    def hatch_asteroid(self, aszteroida_sablon, szamolt_hp: float):
        guid = aszteroida_sablon.object_guid
        world_owner_cards = self._catalogue.world_owner_cards(guid)
        prefab_name = world_owner_cards.world_card().prefab_name
        collider_template = self._collider_templates.collider_template(prefab_name)

        free_id = self._object_id_pool.free_object_id(ObjectKind.Asteroid, Faction.Neutral)
        base_stats = ObjectStats()
        base_stats.set_stat(ObjectStat.MaxHullPoints, szamolt_hp)
        base_stats.set_stat(ObjectStat.MaxPowerPoints, 0.0)
        mutatok = SpaceFeed(free_id, base_stats)
        mutatok.set_hp_pp(szamolt_hp, 0)
        world_radius = world_owner_cards.world_card().radius_of()
        visual_radius = aszteroida_sablon.radius_of()
        if visual_radius <= 0 and world_radius > 0:
            visual_radius = world_radius
        collider_scale = 1.0
        if collider_template is not None:
            base_radius = Spawner._get_collider_radius(collider_template)
            if base_radius > 0 and visual_radius > 0:
                collider_scale = f32(visual_radius / base_radius)
        collider_radius = visual_radius
        final_collider_scale = collider_scale

        asteroid = Asteroid(free_id, world_owner_cards.owner_card, world_owner_cards.world_card(),
                            mutatok, visual_radius, aszteroida_sablon.rotation_speed)
        asteroid.fresh_mover(aszteroida_sablon.transform_of())

        if collider_template is not None:
            utkozotest = of_template(
                collider_template, asteroid.mover_of().transform_of(), final_collider_scale)
        else:
            utkozotest = SphereCollider(asteroid.mover_of().transform_of(), Vector3.zero(),
                                      collider_radius)
        asteroid.wear_collider(utkozotest)
        return asteroid

    def hatch_comet(self, object_guid: int, kelto_helyzet=None, magassag_sav=(3000, 7000)):
        if kelto_helyzet is not None:
            return self._create_comet_debris(object_guid, kelto_helyzet)

        free_id = self._object_id_pool.free_object_id(ObjectKind.Comet, Faction.Neutral)

        live_card = self._catalogue.cards_of(object_guid, CardView.World, CardView.Owner, CardView.Movement,
                                             CardView.NonShipStats)
        world_card = live_card.card(CardView.World)
        owner_card = live_card.card(CardView.Owner)
        movement_card = live_card.card(CardView.Movement)
        non_ship_stats_card = live_card.card(CardView.NonShipStats)

        mutatok = SpaceFeed(free_id, non_ship_stats_card.stats_of)
        mutatok.set_hull(mutatok.stat_or_default(ObjectStat.MaxHullPoints))
        mutatok.set_power(mutatok.stat_or_default(ObjectStat.MaxPowerPoints))

        comet = Comet(free_id, owner_card, world_card, movement_card, mutatok)

        x = self._dice.spread(self._sector_card.width)
        also, felso = magassag_sav
        y = self._dice.signed(self._dice.between_wide(also, felso))
        z = self._dice.spread(self._sector_card.length)

        pitch = f32(Spawner._signum(y) * 80.0)
        rnd_yaw = self._dice.spread(45)
        rnd_roll = self._dice.spread(45)
        euler3 = Euler3(pitch, rnd_yaw, rnd_roll)
        helyzet = Vector3(x, y, z)

        comet.fresh_mover(Transform(helyzet, euler3.quaternion))
        mover = comet.mover_of()

        comet_speed = comet.space_subscribe_info().stat(ObjectStat.Speed)
        turn_maneuver = TurnManeuver(QWEASD())
        mover.queue_maneuver(turn_maneuver)
        mover.take_movement_stats(comet.space_subscribe_info())
        mover.movement_options.shift_to(Gear.Regular)
        mover.movement_options.drive_at(comet_speed)

        collider_template = self._collider_templates.collider_template(comet.prefab_name)
        if collider_template is not None:
            utkozotest = of_template(collider_template, mover.transform_of())
            comet.wear_collider(utkozotest)

        self._loot_npc_template_setup_ids(comet, [LootByCard.Comet.value])

        return comet

    def _create_comet_debris(self, object_guid: int, kelto_helyzet):
        free_id = self._object_id_pool.free_object_id(ObjectKind.Comet, Faction.Neutral)

        world_owner_cards = self._catalogue.world_owner_cards(object_guid)
        debris_pile = DebrisPile(free_id, world_owner_cards.owner_card,
                                 world_owner_cards.world_card(), FactionGroup.Group0,
                                 SpaceFeed(free_id, ObjectStats()),
                                 Vector3.one().mult_(1), 0)
        transform = Transform()
        debris_pile.fresh_mover(transform)

        return debris_pile

    def hatch_cruiser(self, cirkalo_sablon):
        world_owner_card = self._catalogue.world_owner_cards(cirkalo_sablon.object_guid)
        ship_card = self._catalogue.card_of(cirkalo_sablon.object_guid, CardView.Ship)
        if ship_card is None:
            raise ValueError(f'hull card carries no cruiser id {cirkalo_sablon.object_guid}')

        free_id = self._object_id_pool.free_object_id(
            cirkalo_sablon.space_entity_type, cirkalo_sablon.faction)
        mutatok = ObjectStats()
        mutatok.merge_in(ship_card.stats_of)

        space_info = SpaceFeed(free_id, mutatok)

        cruiser_ship = CruiserShip(free_id, world_owner_card.owner_card, world_owner_card.world_card(),
                                   cirkalo_sablon.faction, FactionGroup.Group0, ShipHardpoints(), ShipTraits(),
                                   space_info, ship_card)

        cruiser_ship.fresh_mover(cirkalo_sablon.transform_of())
        space_info.cap_hull_and_power()

        self._wrap_collider(cruiser_ship)

        return cruiser_ship

    def hatch_debris(self, arg, transform=None):
        if isinstance(arg, int):
            guid = arg
            actual_transform = Transform.identity() if transform is None else transform
            world_owner_cards = self._catalogue.world_owner_cards(guid)

            free_id = self._object_id_pool.free_object_id(ObjectKind.Debris, Faction.Neutral)
            debris_pile = DebrisPile(free_id, world_owner_cards.owner_card,
                                     world_owner_cards.world_card(), FactionGroup.Group0,
                                     SpaceFeed(free_id, ObjectStats()),
                                     Vector3.one().mult_(1), 0)
            debris_pile.fresh_mover(actual_transform)
            return debris_pile

        debris_template = arg
        world_owner_cards = self._catalogue.world_owner_cards(debris_template.object_guid)

        free_id = self._object_id_pool.free_object_id(debris_template.space_entity_type, Faction.Neutral)
        debris_pile = DebrisPile(free_id, world_owner_cards.owner_card,
                                 world_owner_cards.world_card(), FactionGroup.Group0,
                                 SpaceFeed(free_id, ObjectStats()),
                                 Vector3.one().mult_(debris_template.scale), debris_template.rotation_speed)
        transform_obj = debris_template.transform_of()
        debris_pile.fresh_mover(transform_obj)

        self._wrap_collider(debris_pile, debris_template.scale)

        return debris_pile

    def create_cargo(self, object_guid: int, transform=None, range_: float = 1000.0):
        actual_transform = Transform.identity() if transform is None else transform
        world_owner_cards = self._catalogue.world_owner_cards(object_guid)

        free_id = self._object_id_pool.free_object_id(ObjectKind.CargoObject, Faction.Neutral)
        cargo = CargoObject(free_id, world_owner_cards.owner_card, world_owner_cards.world_card(),
                            Faction.Neutral, FactionGroup.Group0,
                            SpaceFeed(free_id, ObjectStats()),
                            range_, CargoObject.Interaction.Loot)
        cargo.fresh_mover(actual_transform)
        self._wrap_collider(cargo)
        self._loot_npc_template_setup_ids(cargo, [LootByCard.Cargo.value])
        return cargo

    def hatch_planetoid(self, planetoida_sablon):
        object_guid = planetoida_sablon.object_guid
        world_card = self._catalogue.card_of(object_guid, CardView.World)
        owner_card = self._catalogue.card_of(object_guid, CardView.Owner)
        if owner_card is None or world_card is None:
            raise ValueError('asteroid cards are absent')
        free_id = self._object_id_pool.free_object_id(ObjectKind.Planetoid, Faction.Neutral)

        obj_stats = ObjectStats({})

        obj_stats.set_stat(ObjectStat.MaxHullPoints, 1)
        obj_stats.set_stat(ObjectStat.MaxPowerPoints, 1)
        mutatok = SpaceFeed(free_id, obj_stats)
        mutatok.set_hp_pp(1, 1)

        planetoid = Planetoid(free_id, owner_card, world_card, mutatok, planetoida_sablon.radius_of())
        planetoid.fresh_mover(planetoida_sablon.transform_of())
        prefab_name = world_card.prefab_name
        collider_template = self._collider_templates.collider_template(prefab_name)
        if collider_template is not None:
            planetoid.wear_collider(of_template(
                collider_template, planetoid.mover_of().transform_of()))
        else:
            world_radius = world_card.radius_of()
            collider_radius = world_radius if world_radius > 0 else planetoida_sablon.radius_of()
            utkozotest = SphereCollider(planetoid.mover_of().transform_of(), Vector3.zero(),
                                      collider_radius)
            planetoid.wear_collider(utkozotest)
        return planetoid

    def hatch_planet(self, arg, transform=None):
        if isinstance(arg, PlanetSpec):
            return self._create_planet_from_template(arg)
        guid = arg
        return self._create_planet_from_template(
            PlanetSpec(
                guid,
                ArrivalCause.AlreadyExists,
                0,
                True,
                transform.position_of(),
                transform.rotation_euler3,
                1,
                Color(0, 0, 0.0, 0.0),
                Color(0.0, 0.0, 0.0, 0.0),
                0))

    def _create_planet_from_template(self, bolygo_sablon):
        faction = getattr(bolygo_sablon, "faction", Faction.Neutral) or Faction.Neutral
        free_id = self._object_id_pool.free_object_id(ObjectKind.Planet, faction)
        object_guid = bolygo_sablon.object_guid
        world_card = self._catalogue.card_of(object_guid, CardView.World)
        owner_card = self._catalogue.card_of(object_guid, CardView.Owner)
        if owner_card is None or world_card is None:
            raise ValueError('surface card absent')
        planet = Planet(free_id, owner_card, world_card, bolygo_sablon.position_of(),
                        bolygo_sablon.rotation_of().quaternion, bolygo_sablon.scale,
                        bolygo_sablon.color, bolygo_sablon.specular_color,
                        bolygo_sablon.shininess, faction)
        planet.fresh_mover(bolygo_sablon.transform_of())
        return planet

    def hatch_player_ship(self, player):
        active_ship = player.hangar_of().active_ship()
        ship_bindings = ShipHardpoints()
        aspects = ShipTraits()

        if (avionic_slot := active_ship.ship_slots.avionic_slot()) is not None:
            if active_ship.ship_card_of().tier == 1:
                aspects.take_aspect(ShipTrait.Dogfight)

        is_stealth_ship = _is_stealth_ship_card(active_ship.ship_card_of())
        if is_stealth_ship:
            aspects.take_aspect(ShipTrait.Stealth)

        if is_carrier_ship_card(active_ship.ship_card_of()):
            aspects.take_aspect(ShipTrait.Dock)

        aspects.take_aspect(ShipTrait.TransponderJump)

        if (paint_slot := active_ship.ship_slots.paint_slot()) is not None:
            card_guid = paint_slot.ship_system.card_guid_of()
            paint_card = self._catalogue.card_of(card_guid, CardView.ShipPaint)
            if paint_card is not None:
                ship_bindings.paint_with(paint_card)
        if ship_bindings.ship_system_paint_card is None:
            self._bind_default_model_paint_if_configured(active_ship, ship_bindings)

        roles = player.bgo_admin_roles
        tmp_role_bits = roles.role_bits
        if roles.wears_role(ServerRoles.Console):
            tmp_role_bits ^= ServerRoles.Console.value

        arena_group = getattr(player, "_arena_faction_group", None)
        group_for_id = arena_group if arena_group is not None else FactionGroup.Group0
        free_id = self._object_id_pool.free_object_id(
            ObjectKind.Pilot, player.faction, group_for_id)
        if carrier_transponder_debug_enabled():
            log.info(
                "CARRIER_TRANSPONDER_DIAG create_player_ship user=%s ship_object=%s faction=%s "
                "ship_card=%s transponder_jump=%s aspects=%s",
                player.user_id_of(), free_id, player.faction,
                active_ship.ship_card_of().card_guid_of(),
                has_ship_aspect(aspects, ShipTrait.TransponderJump),
                format_ship_aspects(aspects))
        player_ship = PlayerShip(free_id,
                                 active_ship.owner_card, active_ship.world_card(), active_ship.ship_card_of(),
                                 player.faction, FactionGroup.extract_faction_group(free_id), ship_bindings,
                                 aspects, player.user_id_of(),
                                 tmp_role_bits,
                                 VisibleSet(False), active_ship.ship_stats())
        mutatok = player_ship.space_subscribe_info()

        mutatok.skill_book = player.skill_book
        mutatok.fold_in_stats()
        mutatok.set_power(active_ship.ship_stats().pp)
        mutatok.set_hull(active_ship.ship_stats().hp)

        player_ship.fresh_mover(Transform())

        self._wrap_collider(player_ship)

        if (rekeszek := player_ship.space_subscribe_info().ship_slots) is not None:
            ship_guid = player_ship.ship_card_of().card_guid_of()
            bind_capital_models = is_capital_guid(ship_guid)
            if bind_capital_models:
                log.info("Binding capital battery models for ship %s user %s", ship_guid, player.user_id_of())
            if bind_capital_models or not is_capital_guid(ship_guid):
                ship_bindings.take_slots(
                    rekeszek, player_ship.ship_card_of().tier, is_capital=bind_capital_models,
                    ship_guid=ship_guid, is_stealth=is_stealth_ship,
                    prefab_name=active_ship.world_card().prefab_name)

        self._loot_player_setup(player_ship)
        return player_ship

    def _bind_default_model_paint_if_configured(self, active_ship, ship_bindings) -> str | None:
        ship_card = active_ship.ship_card_of()
        ship_object_key = ship_card.ship_object_key
        paint_card_guid = _get_default_model_paint_fallbacks().paint_card_guid(ship_object_key)
        if paint_card_guid is None:
            return None
        paint_card = self._catalogue.card_of(paint_card_guid, CardView.ShipPaint)
        if paint_card is None:
            log.warning(
                "Default-model paint fallback skipped; paint card %s not found for shipObjectKey=%s ship_card=%s",
                paint_card_guid, ship_object_key, ship_card.card_guid_of())
            return None
        if not paint_card.uses_default_model:
            log.warning(
                "Default-model paint fallback skipped; paint card %s uses model %s for shipObjectKey=%s",
                paint_card_guid, paint_card.prefab_name, ship_object_key)
            return None
        paint_ship_card = self._catalogue.card_of(paint_card.ship_card_guid, CardView.Ship)
        paint_ship_object_key = None if paint_ship_card is None else paint_ship_card.ship_object_key
        if paint_ship_object_key != ship_object_key:
            log.warning(
                "Default-model paint fallback skipped; paint card %s belongs to shipCard=%s shipObjectKey=%s, "
                "active shipCard=%s shipObjectKey=%s",
                paint_card_guid, paint_card.ship_card_guid, paint_ship_object_key,
                ship_card.card_guid_of(), ship_object_key)
            return None
        ship_bindings.paint_with(paint_card)
        return "default-model-fallback"

    @staticmethod
    def _get_collider_radius(utkozo_sablon):
        if isinstance(utkozo_sablon, SpherePlan):
            return utkozo_sablon.radius_of()
        if isinstance(utkozo_sablon, CapsulePlan):
            return max(f32(utkozo_sablon.height * 0.5), utkozo_sablon.radius_of())
        if isinstance(utkozo_sablon, AlignedBoxPlan):
            return max(utkozo_sablon.extents.x,
                       max(utkozo_sablon.extents.y, utkozo_sablon.extents.z))
        return 0.0

    def hatch_platform(self, platform_sablon):
        object_guid = platform_sablon.object_guid
        world_card = self._catalogue.card_of(object_guid, CardView.World)
        owner_card = self._catalogue.card_of(object_guid, CardView.Owner)
        ship_card = self._catalogue.card_of(object_guid, CardView.Ship)
        if owner_card is None or world_card is None or ship_card is None:
            log.error("create object guid=%s missing cards: owner=%s world=%s ship=%s",
                      object_guid, owner_card is not None, world_card is not None, ship_card is not None)
            raise ValueError("Spawner; could not find cards!")

        free_id = self._object_id_pool.free_object_id(
            ObjectKind.WeaponPlatform, platform_sablon.faction)
        base_stats = ship_card.stats_of
        safe_stats = ObjectStats() if base_stats is None else ObjectStats(base_stats)
        if base_stats is None:
            safe_stats.set_stat(ObjectStat.MaxHullPoints, 2000.0)
            safe_stats.set_stat(ObjectStat.MaxPowerPoints, 1000.0)
            log.debug('weapon platform %s arrived statless - stock numbers substituted', object_guid)
        min_power_recovery = f32(25.0 * max(1, min(3, ship_card.tier)))
        current_recovery = safe_stats.stat(ObjectStat.PowerRecovery)
        if current_recovery is None or current_recovery < min_power_recovery:
            safe_stats.set_stat(ObjectStat.PowerRecovery, min_power_recovery)
        mutatok = ShipFeed(free_id, safe_stats)
        mutatok.set_hull(mutatok.stat_or_default(ObjectStat.MaxHullPoints))
        mutatok.set_power(mutatok.stat_or_default(ObjectStat.MaxPowerPoints))

        weapon_platform = WeaponPlatform(
            free_id, owner_card, world_card, ship_card,
            platform_sablon.faction, mutatok,
            platform_template(ship_card.tier, platform_sablon),
            self._tick.time_stamp())
        weapon_platform.fresh_mover(platform_sablon.transform_of())

        self._wrap_collider(weapon_platform)

        mutatok.ship_slots = ShipSlots()
        self._setup_weapon_config(weapon_platform)

        return self._loot_npc_template_setup_template(weapon_platform, platform_sablon)

    def hatch_outpost(self, faction):
        op_template = None
        for sablon in self._sector_desc.space_object_templates:
            if sablon.space_entity_type == ObjectKind.Outpost and sablon.faction == faction:
                op_template = sablon
                break
        if op_template is None:
            raise RuntimeError('outpost due to spawn without a template to build from')

        object_guid = op_template.object_guid
        world_card = self._catalogue.card_of(object_guid, CardView.World)
        owner_card = self._catalogue.card_of(object_guid, CardView.Owner)
        ship_card = self._catalogue.card_of(object_guid, CardView.Ship)
        if owner_card is None or world_card is None or ship_card is None:
            log.error("create object guid=%s missing cards: owner=%s world=%s ship=%s",
                      object_guid, owner_card is not None, world_card is not None, ship_card is not None)
            raise ValueError("Spawner; could not find cards!")

        free_id = self._object_id_pool.free_object_id(ObjectKind.Outpost, op_template.faction)

        mutatok = ShipFeed(free_id, ObjectStats(ship_card.stats_of))
        mutatok.set_hull(mutatok.stat(ObjectStat.MaxHullPoints))
        mutatok.set_power(mutatok.stat(ObjectStat.MaxPowerPoints))

        outpost = Outpost(free_id, owner_card, world_card, ship_card,
                          op_template.faction, mutatok, outpost_template(),
                          self._tick.time_stamp(),
                          ShipTraits())

        outpost.fresh_mover(op_template.transform_of())
        self._wrap_collider(outpost)
        mutatok.ship_slots = ShipSlots()
        self._setup_weapon_config(outpost)

        return self._loot_npc_template_setup_template(outpost, op_template)

    def hatch_miner(self, user, planetoid):
        player = user.pilot_of()
        guid = WellKnownObject.ColonialMiningShip.value if player.faction == Faction.Colonial \
            else WellKnownObject.CylonMiningShip.value

        mining_ship_card = self._catalogue.card_of(guid, CardView.Ship)
        if mining_ship_card is None:
            raise ValueError('mining request lacks a hull card')
        owner_card = self._catalogue.card_of(mining_ship_card.card_guid_of(), CardView.Owner)
        world_card = self._catalogue.card_of(mining_ship_card.card_guid_of(), CardView.World)
        if world_card is None or owner_card is None:
            raise ValueError('mining ship request missing its world or owner card')
        free_id = self._object_id_pool.free_object_id(ObjectKind.MiningShip, player.faction)

        mining_stats = ObjectStats()
        mining_stats.merge_in(mining_ship_card.stats_of)
        min_mining_ship_max_hp = 10000.0
        current_max_hp = mining_stats.stat_or_default(ObjectStat.MaxHullPoints)
        if current_max_hp < min_mining_ship_max_hp:
            mining_stats.set_stat(ObjectStat.MaxHullPoints, min_mining_ship_max_hp)
        ship_stats_info = ShipFeed(free_id, mining_stats)
        mining_ship = MiningShip(free_id, owner_card, world_card, player.faction,
                                 ship_stats_info, user, planetoid, mining_ship_card)

        ship_stats_info.cap_hull_and_power()

        planetoid.set_mining_ship(mining_ship, self._tick)

        mining_ship.last_time_mining = self._tick.time_stamp()

        mining_spot = None
        for spot in planetoid.world_card().spots:
            if spot.type == SpotKind.Mining:
                mining_spot = spot
                break
        if mining_spot is None:
            raise RuntimeError('mining ship asked with no deposit in sight')

        spot_local_transform = mining_spot.local_transform()
        planetoid_transform = planetoid.mover_of().transform_of()
        mining_relative_transform = spot_local_transform.into_world_space(planetoid_transform)

        mining_ship.fresh_mover(mining_relative_transform)
        self._wrap_collider(mining_ship)

        return self._loot_npc_template_setup_ids(mining_ship, [LootByCard.MiningShip.value])

    def hatch_missile(self, caster, target, spot_desc, missile_guid: int, kelt_ora_ms: int):
        owner_card = self._catalogue.card_of(missile_guid, CardView.Owner)
        world_card = self._catalogue.card_of(missile_guid, CardView.World)
        movement_card = self._catalogue.card_of(missile_guid, CardView.Movement)
        caster_ship_tier = caster.ship_card_of().tier
        missile_tier = 1 if caster_ship_tier <= 0 else caster_ship_tier

        if movement_card is None or world_card is None or owner_card is None:
            missing_cards = "mozgás: %s, világ: %s, tulajdonos: %s" % (
                "MISSING" if movement_card is None else "PRESENT",
                "MISSING" if world_card is None else "PRESENT",
                "MISSING" if owner_card is None else "PRESENT")
            raise ValueError(f'Spawner could not find required cards for missileGUID {missile_guid}. state: ' + missing_cards)

        local_transform = spot_desc.local_transform()
        global_transform = caster.mover_of().transform_of()
        relative_transform = local_transform.into_world_space(global_transform)

        free_id = self._object_id_pool.free_object_id(ObjectKind.Missile, caster.faction)
        raketa = Missile(free_id, owner_card, world_card, movement_card, caster.faction,
                         caster.faction_group, SpaceFeed(free_id, ObjectStats()), caster,
                         target, missile_tier, spot_desc.object_point_server_hash, 1.0, kelt_ora_ms)
        raketa.fresh_mover(relative_transform)
        casting_tier = caster.ship_card_of().tier
        missile_radius = f32(10.0 + f32(3.5 * casting_tier))
        sphere_collider = SphereCollider(raketa.mover_of().transform_of(), Vector3.zero(),
                                         missile_radius)
        raketa.wear_collider(sphere_collider)

        if caster.is_player():
            self._loot_npc_template_setup_ids(raketa, [LootByCard.Missile.value])

        return raketa

    def create_mine(self, caster, mine_guid: int, mine_tier: int, kelt_ora_ms: int,
                    armed_at_time_stamp: int):
        owner_card = self._catalogue.card_of(mine_guid, CardView.Owner)
        world_card = self._catalogue.card_of(mine_guid, CardView.World)
        movement_card = self._catalogue.card_of(mine_guid, CardView.Movement)
        if owner_card is None or world_card is None or movement_card is None:
            raise ValueError(f'Spawner could not find required cards for mineGUID {mine_guid}')

        local_transform = Transform(Vector3(0.0, 0.0, -10.0))
        global_transform = caster.mover_of().transform_of()
        drop_transform = local_transform.into_world_space(global_transform)

        free_id = self._object_id_pool.free_object_id(ObjectKind.Mine, caster.faction)
        mine = Mine(free_id, owner_card, world_card, movement_card, caster.faction,
                    caster.faction_group, SpaceFeed(free_id, ObjectStats()),
                    caster, mine_tier, kelt_ora_ms, armed_at_time_stamp)
        mine.fresh_mover(drop_transform)

        if caster.is_player():
            self._loot_npc_template_setup_ids(mine, [LootByCard.Missile.value])

        return mine

    def hatch_fighter(self, guid, kiirtandok, vedendok, jaror_celok, start_position,
                      behaviour_template, *zsakmany_ids, owner_guid=None, gear_level=1):
        if len(zsakmany_ids) == 1 and isinstance(zsakmany_ids[0], (list, tuple)):
            zsakmany_ids = tuple(zsakmany_ids[0])
        if owner_guid is not None and os.environ.get("REBSGO_NO_PAIRING") \
                and self._catalogue.card_of(guid, CardView.Owner) is not None:
            owner_guid = None
        owner_card = self._catalogue.card_of(guid if owner_guid is None else owner_guid, CardView.Owner)
        world_card = self._catalogue.card_of(guid, CardView.World)
        ship_card = self._catalogue.card_of(guid, CardView.Ship)

        if owner_card is None or world_card is None or ship_card is None:
            raise ValueError(f'guid {guid} at least one card is absent {owner_card is not None} {world_card is not None} '
                             + str(ship_card is not None))

        free_id = self._object_id_pool.free_object_id(
            ObjectKind.BotFighter, ship_card.faction, FactionGroup.Group0)
        npc_base_stats = ship_card.stats_of.copy()
        for stat, ertek in self._npc_stat_templates.overrides_for(guid, owner_card.level).items():
            npc_base_stats.set_stat(stat, f32(ertek))
        space_subscribe_info = ShipFeed(free_id, npc_base_stats)
        full_objective_lst = []
        KillGoal(0, kiirtandok)
        DefendGoal(1, vedendok)
        full_objective_lst.extend(jaror_celok)
        roaming_bot = PatrolBot(free_id, owner_card, world_card, ship_card, ship_card.faction,
                                FactionGroup.Group0, ShipHardpoints(), ShipTraits(), space_subscribe_info,
                                behaviour_template, full_objective_lst, self._tick.time_stamp())
        roaming_bot.fresh_mover(start_position)
        space_subscribe_info.cap_hull_and_power()
        space_subscribe_info.ship_slots = ShipSlots()

        self._wrap_collider(roaming_bot)

        self._setup_weapon_config(roaming_bot, owner_card.level)
        self._upgrade_ship_loadout_to_level(roaming_bot, gear_level)
        space_subscribe_info.cap_hull_and_power()

        return self._loot_npc_template_setup_ids(roaming_bot, list(zsakmany_ids))

    def _loot_player_setup(self, player_ship) -> None:
        tier = player_ship.ship_card_of().tier
        if (loot_template := self._loot_templates.get(20 + tier - 1)) is not None:
            self._loot_ownership.stash_loot(player_ship, PvpSpoils(loot_template))

    def _loot_npc_template_setup_ids(self, space_object, ids):
        if ids is None:
            return space_object
        loot_template_lst = self._get_template_lst(ids)
        self._loot_ownership.stash_loot(space_object, NpcSpoils(loot_template_lst))
        return space_object

    def _loot_npc_template_setup_template(self, space_object, objektum_sablon):
        loot_template_ids = objektum_sablon.loot_template_ids
        if loot_template_ids is None:
            return space_object
        loot_template_lst = self._get_template_lst(loot_template_ids)
        self._loot_ownership.stash_loot(space_object, NpcSpoils(loot_template_lst))
        return space_object

    def _wrap_collider(self, space_object, scale: float = 1) -> None:
        utkozotest = self._collider_templates.collider_template(space_object.prefab_name)
        if utkozotest is not None:
            c = utkozotest
            space_object.wear_collider(of_template(
                c, space_object.mover_of().transform_of(), scale))
        else:
            transform = space_object.mover_of().transform_of()
            space_object.wear_collider(SphereCollider(transform, Vector3.zero(), f32(1.0 * scale)))
            self._warn_missing_collider_once(space_object.prefab_name)

    @staticmethod
    def _warn_missing_collider_once(prefab_name: str) -> None:
        with _MISSING_COLLIDER_PREFABS_WARN_LOCK:
            if prefab_name in _MISSING_COLLIDER_PREFABS_WARNED:
                return
            _MISSING_COLLIDER_PREFABS_WARNED.add(prefab_name)
        log.info('prefab %s ships without a collider template - substituting a sphere', prefab_name)

    def create_sector_event(self, event_card_guid: int, faction, transform):
        owner_card = self._catalogue.card_of(event_card_guid, CardView.Owner)
        world_card = self._catalogue.card_of(event_card_guid, CardView.World)
        event_card = self._catalogue.card_of(event_card_guid, CardView.SectorEvent)
        if owner_card is None or world_card is None or event_card is None:
            raise ValueError(f'SectorEvent cards missing for guid {event_card_guid}')
        free_id = self._object_id_pool.free_object_id(ObjectKind.SectorEvent, faction)
        mutatok = SpaceFeed(free_id, ObjectStats())
        from rebsgo.world.objects.triggers import SectorEvent
        event = SectorEvent(free_id, owner_card, world_card, faction, FactionGroup.Group0,
                            mutatok, event_card)
        event.fresh_mover(transform)
        return event

    def create_jump_beacon(self, card_guid: int, faction, transform):
        owner_card = self._catalogue.card_of(card_guid, CardView.Owner)
        world_card = self._catalogue.card_of(card_guid, CardView.World)
        ship_card = self._catalogue.card_of(card_guid, CardView.Ship)
        if owner_card is None or world_card is None or ship_card is None:
            log.error("create jump beacon guid=%s missing cards: owner=%s world=%s ship=%s",
                      card_guid, owner_card is not None, world_card is not None,
                      ship_card is not None)
            raise ValueError(f'JumpBeacon cards missing for guid {card_guid}')

        free_id = self._object_id_pool.free_object_id(ObjectKind.JumpBeacon, faction)
        base_stats = ObjectStats(ship_card.stats_of)
        mutatok = ShipFeed(free_id, base_stats)
        mutatok.cap_hull_and_power()

        beacon = JumpBeacon(free_id, owner_card, world_card, faction, FactionGroup.Group0,
                            ShipHardpoints(), ShipTraits(), mutatok, ship_card)
        beacon.fresh_mover(transform)
        self._wrap_collider(beacon)
        return beacon

    def create_jump_target_transponder(self, caster, ability_stats, kelt_ora_ms: int):
        faction = caster.faction
        card_guid = fallback_systems().jump_beacon_guid(faction)
        owner_card = self._catalogue.card_of(card_guid, CardView.Owner)
        world_card = self._catalogue.card_of(card_guid, CardView.World)
        ship_card = self._catalogue.card_of(card_guid, CardView.Ship)
        if owner_card is None or world_card is None or ship_card is None:
            raise ValueError(f'Transponder cards missing for guid {card_guid}')

        free_id = self._object_id_pool.free_object_id(ObjectKind.Transponder, faction)
        base_stats = ObjectStats(ship_card.stats_of)
        base_stats.merge_in(ability_stats)
        base_stats.set_stat(ObjectStat.MaxPowerPoints, 0)
        mutatok = ShipFeed(free_id, base_stats)
        mutatok.set_hull(base_stats.stat_or_default(ObjectStat.MaxHullPoints))
        mutatok.cap_hull_and_power()

        most = datetime.fromtimestamp(kelt_ora_ms * 0.001, tz=timezone.utc).replace(tzinfo=None)
        active_at = most + timedelta(seconds=ability_stats.stat_or_default(ObjectStat.Duration))
        inactive_at = most + timedelta(seconds=ability_stats.stat_or_default(ObjectStat.LifeTime, 60.0))

        transponder = Transponder(
            free_id, owner_card, world_card, faction, FactionGroup.Group0, mutatok, active_at, inactive_at)
        transponder.fresh_mover(caster.mover_of().transform_of().copy())
        self._wrap_collider(transponder)
        return transponder

    def hatch_trigger(self):
        free_id = self._object_id_pool.free_object_id(ObjectKind.Trigger, Faction.Neutral)
        guid = 39
        owner_card = self._catalogue.card_of(guid, CardView.Owner)
        world_card = self._catalogue.card_of(guid, CardView.World)
        movement_card = self._catalogue.card_of(guid, CardView.Movement)

        if movement_card is None or world_card is None or owner_card is None:
            raise ValueError('a card the missile needs is absent')

        bsgo_trigger = WorldTrigger(free_id, owner_card, world_card, ObjectKind.Trigger,
                                   Faction.Neutral, FactionGroup.Group0, SpaceFeed(free_id, ObjectStats()),
                                   "TestTrigger", Vector3.zero(), 1000)
        bsgo_trigger.fresh_mover(Transform())
        return bsgo_trigger

    def _get_template_lst(self, ids):
        eredmeny = []
        for loot_id in ids:
            if (opt := self._loot_templates.get(loot_id)) is not None:
                eredmeny.append(opt)
        return eredmeny

    @staticmethod
    def _get_fallback_system_guid(slot_type, ship_tier: int) -> int:
        return fallback_systems().guid_for(slot_type, ship_tier)

    @staticmethod
    def _get_npc_missile_system_guid(ship_tier: int) -> int:
        return fallback_systems().missile_guid_for(ship_tier)

    @staticmethod
    def _is_missile_ability(kepesseg_kartya) -> bool:
        if kepesseg_kartya is None:
            return False
        return kepesseg_kartya.ability_action_type in (
            AbilityActionKind.FireMissle, AbilityActionKind.FireLightMissile,
            AbilityActionKind.FireHeavyMissile, AbilityActionKind.FireTorpedo)

    def _ensure_npc_missile_slot(self, ship, slots) -> bool:
        entity_type = ship.space_entity_type
        tier = max(1, min(3, ship.ship_card_of().tier))
        if entity_type == ObjectKind.BotFighter:
            desired = 1
        elif entity_type == ObjectKind.WeaponPlatform:
            desired = tier
        else:
            return False
        missile_guid = Spawner._get_npc_missile_system_guid(tier)
        if missile_guid == 0:
            return False
        present = 0
        for rekesz in slots.values():
            kepesseg = rekesz.ship_ability()
            if kepesseg is not None and Spawner._is_missile_ability(kepesseg.ship_ability_card):
                present += 1
        converted = False
        for rekesz in slots.values():
            if present >= desired:
                break
            if rekesz.ship_slot_card().ship_slot_type != ShipSlotType.weapon:
                continue
            kepesseg = rekesz.ship_ability()
            if kepesseg is not None and Spawner._is_missile_ability(kepesseg.ship_ability_card):
                continue
            rekesz.add_ship_item(ShipSystem.from_guid(missile_guid))
            present += 1
            converted = True
        return converted

    @staticmethod
    def _weapon_spots_usable(rekesz_kartyak) -> bool:
        if rekesz_kartyak is None or len(rekesz_kartyak) == 0:
            return False
        for ship_slot_card in rekesz_kartyak:
            if ship_slot_card is None:
                continue
            if (ship_slot_card.ship_slot_type == ShipSlotType.weapon
                and ship_slot_card.object_point_server_hash > 0):
                return True
        return False

    def _weapon_slots_from_world_card(self, ship, slots) -> bool:
        world_card = ship.world_card()
        if world_card is None or world_card.spots is None:
            return False

        tier = max(1, min(3, ship.ship_card_of().tier))
        fallback_weapon_guid = Spawner._get_fallback_system_guid(ShipSlotType.weapon, tier)
        if fallback_weapon_guid == 0:
            return False

        slot_id = max((meglevo.ship_slot_card().slot_id + 1 for meglevo in slots.values()),
                      default=1)
        fegyver_helyek = [spot for spot in world_card.spots if spot.type == SpotKind.Weapon]
        for sorszam, spot in enumerate(fegyver_helyek, start=slot_id):
            ship_slot = ShipSlot(
                SlotName(ship.ship_card_of().hangar_id, sorszam),
                ShipSlotCard(sorszam, spot.object_point_name,
                             spot.object_point_server_hash, ShipSlotType.weapon, tier))
            ship_slot.add_ship_item(ShipSystem.from_guid(fallback_weapon_guid))
            slots.take_slot(ship_slot)

        if fegyver_helyek:
            guid = ship.ship_card_of().card_guid_of()
            if guid not in _FALLBACK_SLOTS_TOLD:
                _FALLBACK_SLOTS_TOLD.add(guid)
                log.info("Spawner: created %s fallback weapon slots from WorldCard for guid %s"
                         " (further spawns of this hull stay quiet)",
                         slot_id + len(fegyver_helyek) - 1, guid)
        return bool(fegyver_helyek)

    def _setup_weapon_config(self, ship, level: int = -1) -> None:
        if level == -1:
            ship_config_template = first_best_config_for_guid(
                ship.ship_card_of().card_guid_of())
        else:
            ship_config_template = first_best_config_for_guid_and_level(
                ship.ship_card_of().card_guid_of(), level)

        mutatok = ship.space_subscribe_info()
        rekeszek = mutatok.ship_slots
        if rekeszek is None:
            log.error('ship card %s arrived with no slots at all',
                      ship.ship_card_of().card_guid_of())
            return

        if ship_config_template is None:
            equipped = False
            ship_slot_cards = ship.ship_card_of().ship_slot_cards
            use_world_spots = not Spawner._weapon_spots_usable(ship_slot_cards)

            if use_world_spots:
                equipped = self._weapon_slots_from_world_card(ship, rekeszek)
            else:
                for ship_slot_card in ship_slot_cards:
                    fallback_guid = Spawner._get_fallback_system_guid(
                        ship_slot_card.ship_slot_type, ship.ship_card_of().tier)
                    if fallback_guid == 0:
                        continue
                    ship_slot = ShipSlot(
                        SlotName(ship.ship_card_of().hangar_id, ship_slot_card.slot_id),
                        ship_slot_card)
                    ship_slot.add_ship_item(ShipSystem.from_guid(fallback_guid))
                    rekeszek.take_slot(ship_slot)
                    equipped = True
            if equipped:
                ship.bindings_of().take_slots(rekeszek, ship.ship_card_of().tier, prefab_name=ship.world_card().prefab_name)
                ship.space_subscribe_info().fold_in_stats()
            if self._ensure_npc_missile_slot(ship, rekeszek):
                ship.bindings_of().take_slots(rekeszek, ship.ship_card_of().tier, prefab_name=ship.world_card().prefab_name)
                ship.space_subscribe_info().fold_in_stats()
            log.debug("Spawner: no ShipSetupSpec for guid %s, fallback weapons equipped=%s",
                      ship.ship_card_of().card_guid_of(), equipped)
            return

        for ship_slot_card in ship.ship_card_of().ship_slot_cards:
            talalt_slot = None
            for slot_config in ship_config_template.slot_configs:
                if slot_config.slot_id == ship_slot_card.slot_id:
                    talalt_slot = slot_config
                    break
            if talalt_slot is None:
                fallback_guid = Spawner._get_fallback_system_guid(
                    ship_slot_card.ship_slot_type, ship.ship_card_of().tier)
                if fallback_guid == 0:
                    continue
                ship_slot = ShipSlot(
                    SlotName(ship.ship_card_of().hangar_id, ship_slot_card.slot_id),
                    ship_slot_card)
                ship_slot.add_ship_item(ShipSystem.from_guid(fallback_guid))
                rekeszek.take_slot(ship_slot)
                continue
            slot_config = talalt_slot
            ship_slot = ShipSlot(
                SlotName(ship.ship_card_of().hangar_id, ship_slot_card.slot_id),
                ship_slot_card)
            ship_system = ShipSystem.from_guid(slot_config.item_guid)
            ship_slot.add_ship_item(ship_system)
            if slot_config.consumable_guid != 0:
                ship_slot.current_consumable = CountableItem.from_guid(slot_config.consumable_guid,
                                                                       _LONG_MAX_VALUE)

            rekeszek.take_slot(ship_slot)
        if not Spawner._weapon_spots_usable(ship.ship_card_of().ship_slot_cards):
            self._weapon_slots_from_world_card(ship, rekeszek)
        ship.bindings_of().take_slots(rekeszek, ship.ship_card_of().tier, prefab_name=ship.world_card().prefab_name)
        if (paint_slot := rekeszek.paint_slot()) is not None:
            paint_card = self._catalogue.card_of(
                paint_slot.ship_system.card_guid_of(), CardView.ShipPaint)
            if paint_card is not None:
                ship.bindings_of().paint_with(paint_card)
        ship.space_subscribe_info().fold_in_stats()
        if self._ensure_npc_missile_slot(ship, rekeszek):
            ship.bindings_of().take_slots(rekeszek, ship.ship_card_of().tier, prefab_name=ship.world_card().prefab_name)
            ship.space_subscribe_info().fold_in_stats()

    def _upgrade_system_guid_to_level(self, system_guid: int, target_level: int) -> int:
        kartya = self._catalogue.card_of(system_guid, CardView.ShipSystem)
        if kartya is None:
            return system_guid
        while kartya.level < target_level and kartya.next_card_guid != 0:
            nxt = self._catalogue.card_of(kartya.next_card_guid, CardView.ShipSystem)
            if nxt is None:
                break
            kartya = nxt
        return kartya.card_guid_of()

    def _upgrade_ship_loadout_to_level(self, ship, gear_level: int) -> None:
        if gear_level <= 1 or os.environ.get("REBSGO_NO_GEAR"):
            return
        rekeszek = ship.space_subscribe_info().ship_slots
        if rekeszek is None:
            return
        valtozott = False
        for rekesz in rekeszek.values():
            rendszer = rekesz.ship_system
            if rendszer is None:
                continue
            cur_guid = rendszer.ship_system_card.card_guid_of()
            new_guid = self._upgrade_system_guid_to_level(cur_guid, gear_level)
            if new_guid != cur_guid:
                rekesz.add_ship_item(ShipSystem.from_guid(new_guid))
                valtozott = True
        if valtozott:
            ship.bindings_of().take_slots(rekeszek, ship.ship_card_of().tier, prefab_name=ship.world_card().prefab_name)
            ship.space_subscribe_info().fold_in_stats()

    @staticmethod
    def _signum(x: float) -> float:
        if x != x:
            return x
        if x > 0:
            return 1.0
        if x < 0:
            return -1.0
        return x
