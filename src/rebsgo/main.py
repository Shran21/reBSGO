# github.com/Shran21
from __future__ import annotations

from contextlib import suppress

import logging
import logging.handlers
import threading
import time
from itertools import count

from rebsgo import journal
from rebsgo.admission import BelepesiAjto, JegyPecset, Jelszotar, Kapu, Nevsor
from rebsgo.startup import Startup
from rebsgo.services import Services
from rebsgo.chat.client.chat_link import ChatLink
from rebsgo.chat.server.chat_hub import ChatHub
from rebsgo.server_settings import ServerSettings
from rebsgo.runtime.chat_ban import ChatBan
from rebsgo.pilots.together.clan import ClanBook
from rebsgo.pilots.together.squad import SquadBook
from rebsgo.store.records.records import Records
from rebsgo.world.galaxy.galaxy_state import Galaxy
from rebsgo.runtime.runtime import Runtime
from rebsgo.world.combat_rules import LevelCurve
from rebsgo.world.loot_specs import LootSpecs
from rebsgo.runtime.sweeps import AssignmentSweep
from rebsgo.protocol.pilot.pilot_steps import NameRules
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.protocol_book_replies import replies_for
from rebsgo.world.sectors.building.sector_source import SectorSource
from rebsgo.world.sectors.building.sector_build import SectorScatter
from rebsgo.world.sectors.running.handicaps import Handicap
from rebsgo.world.sectors.announcing import Announcer
from rebsgo.world.sectors.running.registries import SectorBook
from rebsgo.runtime.pilot_roster import PilotRoster
from rebsgo.store.data_source import DataSource
from rebsgo.store.clans import SqliteClans
from rebsgo.store.assignments.sqlite_assignments import SqliteAssignments
from rebsgo.store.sqlite_storages import SqliteStorages
from rebsgo.store.sqlite_hangars import SqliteHangars
from rebsgo.store.sqlite_records import SqliteRecords
from rebsgo.game_metrics import JatekMerok
from rebsgo.schedule import TimedCall, Schedule
from rebsgo.gamedata.library import Catalogue
from rebsgo.gamedata.collider_specs import ShapePlans
from rebsgo.gamedata.boot_settings.server_params import ServerParams
from rebsgo.gamedata.from_json.card_loader import CardLoader
from rebsgo.gamedata.from_json.loaders import ColliderLoader, DropLoader, AreaLoader
from rebsgo.gamedata.from_json.sector_loader import SectorLoader

log = logging.getLogger(__name__)


class _WorkCrew:
    def __init__(self):
        self._threads = []
        self._shutdown = False
        self._lock = threading.Lock()
        self._counter = count(1)

    def launch(self, fn) -> None:
        def _target():
            try:
                fn()
            except Exception:
                log.exception("Worker thread raised")

        with self._lock:
            if self._shutdown:
                return
            self._cleanup_finished_threads_locked()
            t = threading.Thread(
                target=_target,
                name=f'crew-{next(self._counter)}',
                daemon=True,
            )
            self._threads.append(t)
        t.start()

    def after(self, seconds: float, fn) -> TimedCall:
        def _fire():
            try:
                fn()
            except Exception:
                log.exception("Timed worker call raised")

        call = TimedCall(seconds, _fire)
        with self._lock:
            if self._shutdown:
                call.call_off()
                return call
        call.start()
        return call

    def shutdown(self, wait: bool = False) -> None:
        with self._lock:
            self._shutdown = True
        if wait:
            self.wait_until_stopped(5)

    def wait_until_stopped(self, timeout_seconds: float) -> bool:
        deadline = time.monotonic() + max(0.0, timeout_seconds)
        with self._lock:
            self._cleanup_finished_threads_locked()
            threads = list(self._threads)
        for t in threads:
            hatralevo = max(0.0, deadline - time.monotonic())
            t.join(timeout=hatralevo)
        with self._lock:
            self._cleanup_finished_threads_locked()
            return all(not t.is_alive() for t in self._threads)

    def _cleanup_finished_threads_locked(self) -> None:
        self._threads = [t for t in self._threads if t.is_alive()]


def build_application_bootstrap(data_store: Records | None = None,
                                server_settings: ServerParams | None = None,
                                db_path: str | None = None) -> Startup:
    if server_settings is None:
        server_settings = ServerParams()

    executor_service = _WorkCrew()
    scheduled_service = Schedule()

    catalogue = Catalogue(CardLoader())

    sqlite_store = None
    data_source = None
    if data_store is None:
        from rebsgo.config.config import Config
        data_source = DataSource(db_path or Config.instance().string("rebsgo.db")
                                 or "./sqlite/bgo_server.db")
        sqlite_hangar = SqliteHangars(data_source)
        sqlite_containers = SqliteStorages(data_source, server_settings)
        sqlite_missions = SqliteAssignments(data_source, catalogue)
        sqlite_guild_processor = SqliteClans(data_source, None)
        sqlite_store = SqliteRecords(
            data_source, server_settings, None, catalogue,
            sqlite_hangar, sqlite_containers, sqlite_missions, sqlite_guild_processor)
        sqlite_guild_processor._sqlite_store = sqlite_store
        data_store = sqlite_store

    name_validation = NameRules(data_store)
    pilot_roster = PilotRoster(name_validation)
    jelszotar = Jelszotar(data_source or data_store)
    kapu = Kapu(JegyPecset(), Nevsor(), jelszotar)
    party_registry = SquadBook()
    guild_registry = ClanBook()
    chat_access_blocker = ChatBan()
    level_curve = LevelCurve()
    merok = JatekMerok(None, pilot_roster)

    Services.register_instance(Catalogue, catalogue)
    Services.register_instance(ServerParams, server_settings)
    Services.register_instance(Records, data_store)
    Services.register_instance(JatekMerok, merok)

    data_store.stored_guilds(guild_registry)

    collider_plans = ShapePlans(ColliderLoader())
    sector_templates = SectorLoader().sector_templates()
    zone_templates = AreaLoader().zone_template()
    loot_templates = LootSpecs(DropLoader().loot_templates())
    galaxy_bonus = Handicap()
    announcer = Announcer(pilot_roster)
    sector_random_generation_utils = SectorScatter(catalogue)

    sector_source = SectorSource(
        sector_templates, zone_templates, galaxy_bonus, collider_plans, loot_templates,
        announcer, catalogue, merok, server_settings, pilot_roster)
    sector_book = SectorBook(
        sector_source, catalogue, merok, sector_random_generation_utils, executor_service)
    galaxy = Galaxy(catalogue, sector_book, galaxy_bonus)

    configuration = ServerSettings(pilot_roster, server_settings)
    server_listener = configuration.server_listener

    pilot_wire = replies_for(ProtocolID.Pilot)
    mission_updater = AssignmentSweep(pilot_roster, pilot_wire, executor_service)
    if sqlite_store is not None:
        sqlite_store._mission_updater = mission_updater

    from rebsgo.config.config import Config
    from rebsgo.runtime.sweeps import TallySweep
    from rebsgo.runtime.sweeps import BoostSweep
    from rebsgo.runtime.sweeps import IdleSweep
    from rebsgo.runtime.sweeps import PeriodicSave

    minutes_offline_before_kick = Config.instance().int(
        "rebsgo.idle.minutes-before-kick", 15)
    counter_updater = TallySweep(pilot_roster, pilot_wire)
    factor_updater = BoostSweep(pilot_roster)
    snapshot_account_safe = PeriodicSave(pilot_roster, data_store)
    inactive_kicker = IdleSweep(pilot_roster, data_store, minutes_offline_before_kick, party_registry)

    scheduled_service.every(1.0, galaxy.run, name="Galaxy")
    scheduled_service.every(5.0, pilot_roster.update, name="PilotRoster.update")
    scheduled_service.every(3.0, counter_updater.run, name="TallySweep")
    scheduled_service.every(60.0, factor_updater.run, name="BoostSweep")
    scheduled_service.every(120.0, snapshot_account_safe.run, name="PeriodicSave")
    scheduled_service.every(60.0, inactive_kicker.run, name="IdleSweep")

    from rebsgo.world.capitals.capital_roster import CapitalRoster
    capital_roster = CapitalRoster(pilot_roster, galaxy)
    Services.register_instance(CapitalRoster, capital_roster)
    scheduled_service.every(30.0, capital_roster.tick, name="CapitalRoster")

    from rebsgo.runtime.revenant_haunt import RevenantHaunt
    revenant_haunt = RevenantHaunt(sector_book)
    Services.register_instance(RevenantHaunt, revenant_haunt)
    scheduled_service.every(revenant_haunt.sweep_seconds, revenant_haunt.run,
                            name="RevenantHaunt")

    from rebsgo.runtime.drone_swarm import DroneSwarm
    drone_swarm = DroneSwarm(sector_book)
    Services.register_instance(DroneSwarm, drone_swarm)
    scheduled_service.every(drone_swarm.sweep_seconds, drone_swarm.run,
                            name="DroneSwarm")

    from rebsgo.pilots.talking.dialog_trees import DialogTrees, TalkState
    Services.register_instance(DialogTrees, DialogTrees())
    Services.register_instance(TalkState, TalkState())

    from rebsgo.config.config import Config
    panel_kulcs = (Config.instance().string("REBSGO_PANEL_TOKEN") or "").strip()
    if panel_kulcs:
        from rebsgo.runtime.console_gateway import ConsoleGateway
        from rebsgo.runtime.panel_door import PanelDoor
        console_gateway = ConsoleGateway(
            pilot_roster, sector_book, chat_access_blocker, catalogue,
            server_settings, scheduled_service, merok, galaxy, data_source)
        panel_door = PanelDoor(panel_kulcs, pilot_roster, data_store,
                               port=Config.instance().int("REBSGO_NET_PANEL_DOOR_PORT", 27053),
                               console_gateway=console_gateway,
                               sector_book=sector_book,
                               kapu=kapu)
        panel_door.start()
        Services.register_instance(PanelDoor, panel_door)
    else:
        log.info("panel door not started: REBSGO_PANEL_TOKEN is unset")

    from rebsgo.runtime.playtime_clerk import PlaytimeClerk
    playtime_clerk = PlaytimeClerk(pilot_roster, 60.0)
    Services.register_instance(PlaytimeClerk, playtime_clerk)
    scheduled_service.every(playtime_clerk.interval_seconds, playtime_clerk.run,
                            name="PlaytimeClerk")

    from rebsgo.pilots.standings.medal_desk import MedalDesk
    Services.register_instance(MedalDesk, MedalDesk(pilot_roster))

    from rebsgo.pilots.standings.ranking_log import RankingLog
    ranking_history = RankingLog(pilot_roster, data_store, 24 * 3600.0)
    Services.register_instance(RankingLog, ranking_history)
    try:
        ranking_history.run()
    except Exception:
        log.exception("initial RankingLog build failed")
    scheduled_service.every(60.0, ranking_history.run, name="RankingLog")

    from rebsgo.pilots.standings.tournament_log import TournamentLog
    tournament_log = TournamentLog(data_store)
    Services.register_instance(TournamentLog, tournament_log)
    try:
        tournament_log.run()
    except Exception:
        log.exception("initial TournamentLog build failed")
    scheduled_service.every(300.0, tournament_log.run, name="TournamentLog")

    from rebsgo.runtime.daily_bonus_service import DailyBonusService
    daily_bonus_service = DailyBonusService(pilot_roster)
    Services.register_instance(DailyBonusService, daily_bonus_service)
    scheduled_service.every(60.0, daily_bonus_service.run, name="DailyBonus")
    from rebsgo.runtime.daily_bonus_service import LoginStreakService
    login_streak_service = LoginStreakService(pilot_roster)
    Services.register_instance(LoginStreakService, login_streak_service)
    scheduled_service.every(60.0, login_streak_service.run, name="LoginStreak")

    from rebsgo.protocol.arena.arena_desk import ArenaDesk, _load_config
    Services.register_instance(ArenaDesk, ArenaDesk(sector_book, pilot_roster))

    try:
        arena_cfg = _load_config()
        arena_sector = sector_book.sector_source.create_arena_sector(
            arena_cfg["arenaSectorId"], arena_cfg["arenaSceneBaseSectorId"])
        sector_book.register_sector(arena_sector)
        from rebsgo.gamedata.reading import MapStarInfo
        from rebsgo.vocabulary.pilot import Faction
        from rebsgo.geometry.primitives.vector2 import Vector2
        gm_card = catalogue.map_card
        base_star = gm_card.star(arena_cfg["arenaSceneBaseSectorId"])
        if base_star is not None and gm_card.star(arena_cfg["arenaSectorId"]) is None:
            gm_card.stars[arena_cfg["arenaSectorId"]] = MapStarInfo(
                arena_cfg["arenaSectorId"], Vector2(-100000.0, -100000.0), base_star.gui_index,
                Faction.Neutral, 0, 0, base_star.sector_guid,
                False, False, False, False, False, False)
        log.info("dedicated arena sector %s created (scene base %s)",
                 arena_cfg["arenaSectorId"], arena_cfg["arenaSceneBaseSectorId"])
    except Exception:
        log.exception("failed to create dedicated arena sector at startup")

    anyakonyv = None
    if server_settings.registration_open:
        from rebsgo.admission.enrolment import Anyakonyv
        anyakonyv = Anyakonyv(data_source or data_store, jelszotar)
    login_server_listener = BelepesiAjto(kapu, server_settings.login_server_port,
                                         anyakonyv=anyakonyv)
    chat_server = ChatHub(server_settings)
    chat_api = ChatLink(server_settings)

    game_server = Runtime(
        executor_service,
        server_settings,
        galaxy,
        data_store,
        kapu,
        party_registry,
        guild_registry,
        server_listener,
        pilot_roster,
        sector_book,
        level_curve,
        scheduled_service,
        merok,
        chat_access_blocker,
        mission_updater,
        catalogue,
        configuration)

    bootstrap = Startup(
        chat_api, chat_server, login_server_listener, collider_plans,
        server_settings, game_server, catalogue, sector_book)

    Services.register_instance(ChatLink, chat_api)
    Services.register_instance(Startup, bootstrap)

    return bootstrap


def main(data_store: Records | None = None) -> None:
    import signal

    log_file = journal.bekapcsol()
    log.info("reBSGO server starting - github.com/Shran21")
    log.info("Logging to %s", log_file)
    bootstrap = build_application_bootstrap(data_store)
    bootstrap.on_start_up()

    stop_event = threading.Event()

    def _handle_term(_signum, _frame):
        stop_event.set()

    with suppress((ValueError, OSError)):
        signal.signal(signal.SIGTERM, _handle_term)

    with suppress(KeyboardInterrupt):
        stop_event.wait()
    bootstrap.on_shutdown()


if __name__ == "__main__":
    main()
