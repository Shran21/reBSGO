# github.com/Shran21
from __future__ import annotations

import logging
import time

from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.protocol_book_replies import replies_for, game_replies
from rebsgo.world.sectors.bumping.bounce import Bounce
from rebsgo.world.sectors.bumping.contact_sweep import ContactSweep
from rebsgo.world.sectors.building.sector_plan import SectorPlan
from rebsgo.world.sectors.building.sector_build import SectorServices
from rebsgo.world.sectors.overlap_filter import OverlapFilter
from rebsgo.world.sectors.powers.cast_queue import CastQueue
from rebsgo.world.sectors.harm.damage_roll import DamageRoll
from rebsgo.world.sectors.harm.damage_wear import WearFromDamage
from rebsgo.world.sectors.harm.damage_book import DamageBook
from rebsgo.world.sectors.harm.damage_wear import SectorDamageLog
from rebsgo.world.sectors.running.jumps import JumpBook
from rebsgo.world.sectors.spoils.tally_card_giver import TallyCardGiver
from rebsgo.world.sectors.spoils.loot_split import LootSplit
from rebsgo.world.sectors.spoils.shares import ShareBook
from rebsgo.world.sectors.spoils.who_hit_it import PvpKillLog
from rebsgo.world.sectors.spoils.drops import LootOwnership
from rebsgo.world.sectors.running.mining_in_sector import MiningInSector
from rebsgo.world.sectors.running.object_id_pool import ObjectIdPool
from rebsgo.world.sectors.running.outposts import OutpostPhases, OutpostPhase, OutpostSiege
from rebsgo.gamedata.from_json.template_readers import world_places
from rebsgo.world.combat_rules import Engagement
from rebsgo.world.sectors.running.coming_and_going import ArrivalQueue, Reaper
from rebsgo.world.sectors.running.outbox import SectorOutbox
from rebsgo.world.sectors.running.registries import SectorObjects, SectorPilots
from rebsgo.world.sectors.spawning import DynamicNpcRule, BirthAreas, SpawnRunner
from rebsgo.world.sectors.sector_loop import Sector
from rebsgo.world.sectors.sector_parts import SectorCatalogue
from rebsgo.world.sectors.spawner import Spawner
from rebsgo.world.sectors.heartbeat import Tick, utemre
from rebsgo.world.sectors.clockwork import GROUP_MAINTENANCE, BoostUpkeep, CometPass, CarrierAnchorFollowTimer, CombatClock, DebrisCargoTimer, DebrisFieldTimer, ShipRecovery, ArrivalCountdown, JumpTargetTransponderTimer, JumpCountdown, LeaveCountdown, MiningHistoryTrim, MinerHunters, MinerRounds, MineTimer, MissileFlight, MovementPulse, AnnounceRounds, NpcSteering, NpcUpkeep, SubsystemWatch, ReadinessDrain, OutpostBeaconTimer, OutpostRepair, OutpostPlatformTimer, SectorEventTimer, OutpostArrivals, ComputerCooldown, ModifierExpiry, PropertyFlush, StateFlush, SpawnClock, ClockworkStep, VisibilitySweep
from rebsgo.world.sectors.areas.areas import SectorAreas
from rebsgo.vocabulary.world import ArrivalCause, ObjectKind, WellKnownCard
from rebsgo.vocabulary.pilot import Faction, ResourceKind
from rebsgo.geometry.primitives.euler3 import Euler3
from rebsgo.geometry.primitives.vector3 import Vector3
from rebsgo.gamedata.cards.card_view import CardView
from rebsgo.gamedata.cards.ui_cards import GuiCard
from rebsgo.gamedata.cards.misc_cards import RegulationCard
from rebsgo.gamedata.cards.world_cards import SectorCard
from rebsgo.gamedata.sector_layout import AsteroidInfo, ResourceCeiling, MiningShipSetup, LootByNpc, OutpostProgressSpec, PlanetoidInfo, SpawnAreaSpec, ResourceSpec, SectorInfo
from rebsgo.gamedata.object_templates import BotSpec, CruiserSpec
from rebsgo.gamedata.reading import BackdropInfo, CameraFxInfo, FogInfo, TargetBracketMode
from rebsgo.helpers.dice import Dice
from rebsgo.helpers.color import Color

log = logging.getLogger(__name__)


class SectorSource:
    def __init__(self, sector_templates, zone_templates, galaxis_szorzo, collider_plans, zsakmany_sablonok,
                 announcer, catalogue, merok, server_settings, pilot_roster):
        self._sector_templates = sector_templates
        self._zone_templates = zone_templates
        self._galaxy_bonus = galaxis_szorzo
        self._collider_templates = collider_plans
        self._loot_templates = zsakmany_sablonok
        self._announcer = announcer
        self._catalogue = catalogue
        self._merok = merok
        self._server_settings = server_settings
        self._pilot_roster = pilot_roster

    def _extract_sector_cards(self, id: int) -> SectorCatalogue:
        map_card = self._catalogue.card_of(WellKnownCard.GalaxyMap.value, CardView.GalaxyMap)
        if map_card is None:
            raise RuntimeError('galaxy map card absent')

        sector_card = self._catalogue.sector_card_by_id(id)
        if sector_card is None:
            fallback_guid = SectorSource._fallback_sector_card_guid(id)

            fallback_sector_card = self._catalogue.card_of(fallback_guid, CardView.Sector)
            if fallback_sector_card is not None:
                sector_card = fallback_sector_card
            else:
                created = SectorSource._create_fallback_sector_card(id, fallback_guid)
                self._catalogue.take_card(created)
                log.warning("Created fallback SectorCard for sector_id=%s (cardGuid=%s, regulation_guid=%s)",
                            id, created.card_guid_of(), created.regulation_card_guid)
                sector_card = created

            if self._catalogue.card_of(fallback_guid, CardView.GUI) is None:
                self._catalogue.take_card(GuiCard(
                    fallback_guid,
                    f'sector{id}',
                    0,
                    "",
                    0,
                    "",
                    "",
                    "",
                    []))
                log.warning("Created fallback GuiCard mapping for sector_id=%s (guid=%s)", id, fallback_guid)

        regulation_guid = sector_card.regulation_card_guid
        if regulation_guid == 0:
            regulation_card = SectorSource._create_fallback_regulation_card(0)
            log.warning("SectorId=%s has regulation_guid=0; using fallback RegulationCard without catalogue entry.", id)
        else:
            regulation_card = self._catalogue.card_of(regulation_guid, CardView.Regulation)
            if regulation_card is None:
                regulation_card = SectorSource._create_fallback_regulation_card(regulation_guid)
                self._catalogue.take_card(regulation_card)
                log.warning("Created fallback RegulationCard guid=%s for sector_id=%s", regulation_guid, id)

        return SectorCatalogue(sector_card, regulation_card, map_card)

    @staticmethod
    def _fallback_sector_card_guid(sector_id: int) -> int:
        return 3_400_000_000 + sector_id

    @staticmethod
    def _create_fallback_sector_card(sector_id: int, star_card_guid: int) -> SectorCard:
        regulation_guid = 3_500_000_000 + sector_id
        black = Color(0.0, 0.0, 0.0, 1.0)
        gray = Color(0.15, 0.15, 0.15, 1.0)

        empty_bg = BackdropInfo("", gray)

        return SectorCard(
            star_card_guid,
            24_000.0,
            6_000.0,
            24_000.0,
            regulation_guid,
            gray,
            black,
            0,
            black,
            0,
            empty_bg,
            empty_bg,
            empty_bg,
            empty_bg,
            [],
            [],
            [],
            FogInfo(False, black, 0.0, 0.0),
            CameraFxInfo(False),
            [])

    @staticmethod
    def _create_fallback_regulation_card(rules_guid: int) -> RegulationCard:
        return RegulationCard(
            rules_guid,
            {},
            {},
            TargetBracketMode.Default,
            True,
            [])

    def _prepare_blueprint(self, id: int, galaxis_kartya) -> SectorPlan:
        sector_desc = None
        for sablon in self._sector_templates:
            if sablon.sector_id == id:
                sector_desc = sablon
                break
        if sector_desc is None:
            log.warning("Missing SectorTemplate for sectorID=%s. Falling back to an in-code default template. "
                        "Loaded template sectorIDs=%s",
                        id, sorted(t.sector_id for t in self._sector_templates))
            sector_desc = SectorSource._create_fallback_sector_desc(id)

        sector_cards = self._extract_sector_cards(id)

        star = galaxis_kartya.star(id)
        if star is None:
            raise RuntimeError('the sector has no star')
        return SectorPlan(sector_desc, sector_cards, star)

    @staticmethod
    def _create_fallback_sector_desc(sector_id: int) -> SectorInfo:
        spawn_areas = [
            SpawnAreaSpec(
                1,
                Vector3(-1200.0, 0.0, -1200.0),
                Vector3(-800.0, 0.0, -800.0),
                Euler3.ZERO,
                Faction.Colonial),
            SpawnAreaSpec(
                2,
                Vector3(1200.0, 0.0, 1200.0),
                Vector3(800.0, 0.0, 800.0),
                Euler3(0.0, 180.0, 0.0),
                Faction.Cylon),
        ]

        none_resource = ResourceSpec(ResourceKind.None_, 1, 0.0, 0.0)

        asteroid_desc = AsteroidInfo(
            0,
            1,
            [1, 1],
            ResourceCeiling(0.0, 0.0, 0.0, 0.0),
            [none_resource])

        planetoid_desc = PlanetoidInfo(
            0,
            1,
            [none_resource],
            1,
            1)

        mining_ship_config = MiningShipSetup(
            1,
            1,
            0,
            [
                LootByNpc(0, 0, Faction.Colonial, 1),
                LootByNpc(0, 0, Faction.Cylon, 1),
            ],
            10_000_000,
            0,
            60)

        progress_template = OutpostProgressSpec(0, 0, 0, 0, 0)

        return SectorInfo(
            sector_id,
            0,
            spawn_areas,
            [],
            asteroid_desc,
            planetoid_desc,
            mining_ship_config,
            [],
            progress_template,
            progress_template,
            None)

    def _setup_outpost_states(self, szektor_terv, csillag_leiras, tick) -> OutpostPhases:
        helyek = world_places()
        szektor = szektor_terv.sector_desc.sector_id
        noveked = helyek.outpost_growth_seconds

        return OutpostPhases(
            OutpostPhase(Faction.Colonial, helyek.starting_points(szektor, "Colonial"),
                         noveked, csillag_leiras.can_colonial_outpost, tick),
            OutpostPhase(Faction.Cylon, helyek.starting_points(szektor, "Cylon"),
                         noveked, csillag_leiras.can_cylon_outpost, tick),
            szektor_terv.sector_desc.colonial_progress_template,
            szektor_terv.sector_desc.cylon_progress_template)

    def create_arena_sector(self, arena_id: int, scene_base_id: int) -> Sector:
        map_card = self._catalogue.card_of(WellKnownCard.GalaxyMap, CardView.GalaxyMap)
        if map_card is None:
            raise RuntimeError('the sector has no map card')
        base_star = map_card.star(scene_base_id)
        if base_star is None:
            raise RuntimeError("arena scene base sector %s has no star" % scene_base_id)
        arena_desc = SectorSource._create_fallback_sector_desc(arena_id)
        base_cards = self._extract_sector_cards(scene_base_id)
        blueprint = SectorPlan(arena_desc, base_cards, base_star)
        return self.open_sector(arena_id, terv=blueprint)

    def open_sector(self, id: int, terv: "SectorPlan | None" = None) -> Sector:
        tick = Tick(int(time.time() * 1000))
        space_replies = game_replies()

        map_card = self._catalogue.card_of(WellKnownCard.GalaxyMap, CardView.GalaxyMap)
        if map_card is None:
            raise RuntimeError('the sector has no map card')
        galaxy_card = map_card

        if terv is None:
            sector_blueprint = self._prepare_blueprint(id, galaxy_card)
            star_desc = galaxy_card.stars.get(id)
        else:
            sector_blueprint = terv
            star_desc = terv.star_desc
        op_states = self._setup_outpost_states(sector_blueprint, star_desc, tick)

        sector_users = SectorPilots()
        sector_objects = SectorObjects()

        spawn_areas = BirthAreas()
        for spawn_area_template in sector_blueprint.sector_desc.spawn_area_templates:
            spawn_areas.register_spawn(spawn_area_template)

        kuldo = SectorOutbox(sector_users, sector_blueprint.sector_desc.sector_id)
        damage_durability_modifier = WearFromDamage(sector_users, kuldo)

        damage_log = SectorDamageLog(sector_users)

        object_id_pool = ObjectIdPool()
        loot_ownership = LootOwnership()
        object_forge = Spawner(
            object_id_pool, self._collider_templates, sector_blueprint.sector_desc,
            loot_ownership, self._loot_templates, tick, sector_blueprint.sector_cards().sector_card)

        ctx = SectorServices(tick, sector_users, sector_objects, Dice(), kuldo, sector_blueprint,
                            object_id_pool, object_forge, op_states, loot_ownership)

        arrival_gate = ArrivalQueue(spawn_areas, tick, sector_users, sector_objects, kuldo,
                                    op_states, object_forge, space_replies)
        spawn_runner = SpawnRunner(spawn_areas, sector_blueprint.sector_desc, tick,
                                   object_forge, arrival_gate, loot_ownership,
                                   sector_objects)
        sector_outpost_progress = OutpostSiege(op_states, tick, damage_log, loot_ownership)

        from collections import deque
        remover = Reaper(deque(), ctx, space_replies)

        engagement = Engagement()
        jump_book = JumpBook(sector_users, tick)
        damage_roll = DamageRoll(engagement, tick)
        tally_giver = TallyCardGiver(sector_users, sector_blueprint.sector_cards().sector_card)

        pvp_kill_history = PvpKillLog()

        spoils_split = LootSplit(ctx.users(), ctx.dice(),
                                 replies_for(ProtocolID.Pilot),
                                 ctx.tick(), tally_giver, ctx.blueprint(),
                                 self._merok, self._server_settings,
                                 self._pilot_roster, pvp_kill_history)

        share_book = ShareBook(sector_users, loot_ownership, damage_log,
                               spoils_split, tally_giver)

        damage_book = DamageBook(ctx, damage_roll, share_book, remover,
                                 damage_log, damage_durability_modifier, space_replies)
        damage_book.watch_with(pvp_kill_history)

        cast_desk = CastQueue(ctx, engagement, damage_book,
                              arrival_gate, loot_ownership)

        mining_ship_operations = MiningInSector(
            sector_objects, share_book, arrival_gate, object_forge,
            ctx.blueprint().sector_cards())

        orak = self._setup_sector_update_timers(
            ctx, remover, ctx.blueprint().sector_desc.mining_ship_config, spoils_split, op_states,
            jump_book, spawn_runner, object_forge, arrival_gate,
            cast_desk, damage_log, galaxy_card, mining_ship_operations,
            damage_book)
        timer_updater = ClockworkStep(tick, orak, ctx.blueprint().sector_desc.sector_id)

        remover.watch_with(sector_outpost_progress)
        remover.watch_with(share_book)
        remover.watch_with(damage_log)
        remover.watch_with(loot_ownership)
        remover.watch_with(spawn_runner)
        remover.watch_with(object_id_pool)

        intersection_filter = OverlapFilter(ctx.blueprint().sector_cards().regulation_card())
        collision_resolution = Bounce(damage_book, remover)
        collision_updater = ContactSweep(sector_objects, collision_resolution, intersection_filter, tick)

        bot_spawn_template = ctx.blueprint().sector_desc.bot_spawn_templates
        if bot_spawn_template is None:
            log.info('sector %s has no bot spawn description', ctx.blueprint().sector_desc.sector_id)
        if bot_spawn_template is not None:
            for spawn_template in bot_spawn_template:
                for npc_spawn_entry in spawn_template.npc_spawn_entries:
                    for _i in range(npc_spawn_entry.count()):
                        bot_template = BotSpec(
                            npc_spawn_entry.guid,
                            ObjectKind.BotFighter,
                            ArrivalCause.JumpIn, int(spawn_template.respawn_time_death),
                            False,
                            [npc_spawn_entry.loot_id],
                            spawn_template.respawn_time_seconds,
                            False,
                            spawn_template.lifespan_seconds,
                            spawn_template.spawn_area,
                            owner_guid=npc_spawn_entry.owner_guid,
                            gear_level=npc_spawn_entry.gear_level)
                        dynamic_npc_spawn = DynamicNpcRule(bot_template, spawn_runner, object_forge, arrival_gate, ctx.dice())
                        spawn_runner.enqueue(dynamic_npc_spawn, 0)

        talalt_zona = None
        for zone_template in self._zone_templates:
            if zone_template.sector_guid == ctx.blueprint().sector_cards().sector_card.card_guid_of():
                talalt_zona = zone_template
                break
        sector_zone_management = SectorAreas(talalt_zona)

        sector = Sector(ctx, engagement, spawn_runner, arrival_gate, remover, damage_book, cast_desk, jump_book, timer_updater, collision_updater, sector_zone_management, mining_ship_operations, self._galaxy_bonus, self._loot_templates, spoils_split, share_book)

        self._build_sector_space_objects(sector, ctx.blueprint().sector_desc)
        self._queue_object_births(sector)

        return sector

    def _setup_sector_update_timers(self, ctx, takarito, mining_ship_config, spoils_split, outpost_scoreboard,
                                    jump_book, spawn_runner, factory, arrival_gate, cast_desk,
                                    damage_log, map_card, mining_ship_operations,
                                    damage_book):
        orak = []

        orak.append(MissileFlight(ctx, takarito))
        orak.append(MineTimer(ctx, takarito, damage_book))
        orak.append(JumpTargetTransponderTimer(ctx.space_objects(), takarito))
        sector_event_timer = SectorEventTimer(ctx, utemre(1), takarito,
                                              factory, arrival_gate)
        orak.append(sector_event_timer)
        takarito.watch_with(sector_event_timer)
        damage_book.watch_with(sector_event_timer)
        orak.append(VisibilitySweep(ctx, takarito))
        orak.append(CombatClock(ctx.tick(), ctx.space_objects(), utemre(1), 15))
        orak.append(MinerRounds(ctx, mining_ship_config, self._galaxy_bonus, spoils_split, takarito))

        orak.append(ArrivalCountdown(ctx, utemre(1)))

        space_objects = ctx.space_objects()
        users = ctx.users()
        tick = ctx.tick()
        sender = ctx.sender()
        sector_desc = ctx.blueprint().sector_desc
        sector_cards = ctx.blueprint().sector_cards()

        orak.append(JumpCountdown(space_objects, tick, jump_book, takarito, map_card, sector_desc, users))
        orak.append(ShipRecovery(space_objects, jump_book, users))
        orak.append(ComputerCooldown(tick, space_objects, utemre(1)))
        orak.append(SpawnClock(space_objects, spawn_runner, tick, users))

        cargo_sector_desc = sector_desc.cargo_sector_desc
        if cargo_sector_desc is not None and cargo_sector_desc.activated:
            orak.append(DebrisCargoTimer(
                tick, space_objects,
                utemre(cargo_sector_desc.delay_seconds),
                factory, arrival_gate, cargo_sector_desc, ctx.dice()))

        debris_field_desc = sector_desc.debris_field_desc
        if debris_field_desc is not None and debris_field_desc.activated:
            orak.append(DebrisFieldTimer(
                tick, space_objects,
                utemre(debris_field_desc.delay_seconds),
                factory, arrival_gate, debris_field_desc, ctx.dice(),
                sector_desc.sector_id))

        if sector_desc.colonial_progress_template is not None \
                and sector_desc.cylon_progress_template is not None:
            orak.append(SubsystemWatch("OutpostWatch", GROUP_MAINTENANCE,
                                       tick, space_objects, utemre(5), (
                (ReadinessDrain(tick, space_objects, utemre(60), outpost_scoreboard,
                                users, sender, utemre(7 * 60)), utemre(60)),
                (OutpostArrivals(space_objects, outpost_scoreboard, takarito,
                                 factory, arrival_gate, sector_desc), utemre(5)),
                (OutpostBeaconTimer(space_objects, outpost_scoreboard, takarito,
                                    factory, arrival_gate, sector_desc, map_card), utemre(10)),
                (OutpostRepair(space_objects, self._galaxy_bonus), utemre(60)),
                (OutpostPlatformTimer(tick, space_objects, outpost_scoreboard, takarito,
                                      factory, arrival_gate), utemre(10)),
            )))
        orak.append(StateFlush(tick, space_objects, utemre(1), sender))

        orak.append(PropertyFlush(tick, space_objects, utemre(0.1)))
        orak.append(CarrierAnchorFollowTimer(ctx, utemre(1)))
        orak.append(ModifierExpiry(ctx))
        orak.append(NpcUpkeep(tick, space_objects, utemre(5),
                              cast_desk, damage_log, sector_cards))
        orak.append(NpcSteering(tick, space_objects, utemre(3),
                                cast_desk, damage_log, takarito, sector_cards,
                                ctx.dice()))
        orak.append(MovementPulse(tick, space_objects, utemre(3), users, sender))
        orak.append(LeaveCountdown(tick, space_objects, utemre(10), users, takarito))
        orak.append(BoostUpkeep(tick, space_objects, utemre(1), users,
                                sector_cards.sector_card))

        if sector_desc.comet_layout.activated:
            orak.append(CometPass(
                tick, space_objects,
                utemre(max(1, sector_desc.comet_layout.delay_seconds)),
                factory, arrival_gate, sector_desc.comet_layout))

        notification_timer = AnnounceRounds(tick, space_objects, utemre(7),
                                            self._announcer, damage_log, sector_cards)
        orak.append(notification_timer)
        takarito.watch_with(notification_timer)

        orak.append(SubsystemWatch("MiningWatch", GROUP_MAINTENANCE,
                                   tick, space_objects, utemre(5), (
            (MinerHunters(ctx, mining_ship_config, factory, arrival_gate), utemre(5)),
            (MiningHistoryTrim(ctx, mining_ship_operations), utemre(10 * 60)),
        )))

        return orak

    def _schedule_spawn_space_object_cruisers(self, sector) -> None:
        sector_desc = sector.ctx.blueprint().sector_desc
        for space_object_template in sector_desc.space_object_templates:
            if isinstance(space_object_template, CruiserSpec):
                cruiser = sector.ctx.object_forge.hatch_cruiser(space_object_template)
                sector.arrival_gate.admit_object(cruiser)

    def _queue_object_births(self, sector) -> None:
        sector_desc = sector.ctx.blueprint().sector_desc
        space_object_templates = sector_desc.space_object_templates
        if not space_object_templates:
            log.info('sector %s carries no object templates, so nothing gets scheduled to spawn.',
                     sector_desc.sector_id)
            return

        for sablon in self._ujraszuletok(space_object_templates):
            mikor = 0 if sablon.spawns_at_once \
                else SectorSource._get_spawn_delay(sablon, sector_desc)
            try:
                sector.spawn_runner.enqueue(sector.spawn_runner.spawn_for(sablon), mikor)
            except (IndexError, ValueError) as rossz_sablon:
                log.warning(str(rossz_sablon))

    @staticmethod
    def _ujraszuletok(sablonok):
        egyszeriek = (ObjectKind.Outpost, ObjectKind.Planet, ObjectKind.Debris)
        return [sablon for sablon in sablonok
                if sablon is not None and sablon.space_entity_type is not None
                and not sablon.space_entity_type.of_kind(*egyszeriek)]

    @staticmethod
    def _get_spawn_delay(objektum_sablon, sector_desc):
        entity_type = objektum_sablon.space_entity_type
        if entity_type == ObjectKind.Asteroid:
            if sector_desc.asteroid_desc is None:
                return objektum_sablon.respawn_time
            return sector_desc.asteroid_desc.respawn_time
        if entity_type == ObjectKind.Planetoid:
            if sector_desc.planetoid_desc is None:
                return objektum_sablon.respawn_time
            return sector_desc.planetoid_desc.respawn_time
        return objektum_sablon.respawn_time

    def _build_sector_space_objects(self, sector, sector_desc) -> None:
        object_forge = sector.ctx.object_forge
        space_object_templates = sector_desc.space_object_templates
        if space_object_templates is None or len(space_object_templates) == 0:
            log.info('sector %s carries no object templates, so it opens empty.',
                     sector_desc.sector_id)
            return
        for space_object_template in space_object_templates:
            if space_object_template is None or space_object_template.space_entity_type is None:
                continue
            if space_object_template.space_entity_type == ObjectKind.Asteroid:
                continue
            if space_object_template.space_entity_type == ObjectKind.Planetoid:
                continue
            if space_object_template.space_entity_type == ObjectKind.WeaponPlatform:
                continue

            entity_type = space_object_template.space_entity_type
            if entity_type == ObjectKind.Planet:
                planet_template = space_object_template
                planet = object_forge.hatch_planet(planet_template)
                sector.arrival_gate.admit_object(planet)
            elif entity_type == ObjectKind.Debris:
                debris_template = space_object_template
                debris_pile = object_forge.hatch_debris(debris_template)
                sector.arrival_gate.admit_object(debris_pile)
