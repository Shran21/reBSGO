# github.com/Shran21
from __future__ import annotations

import logging
import threading

from rebsgo.world.sectors.mounts import SeatCount
from rebsgo.world.sectors.sector_command_queue import SectorCommandQueue
from rebsgo.world.sectors.sector_gating import SectorGating
from rebsgo.world.sectors.movement_step import MovementStep
from rebsgo.helpers.rolling_latency_stats import (
    ENABLED as GUARDRAILS_ENABLED,
    RollingLatencyStats,
    SECTOR_PIPELINE_BUDGET_ENABLED,
    SECTOR_HOTPATH_SUMMARY_ENABLED,
    SECTOR_HOTPATH_SUMMARY_INTERVAL_MS,
    SECTOR_TICK_WARN_INTERVAL_MS,
    SECTOR_TICK_WARN_MS,
    elapsed_ms,
    now_ms,
    should_warn,
)
from rebsgo.journal import hivasi_lanc

log = logging.getLogger(__name__)

_HOTPATH_STAGE_NAMES = (
    "tick",
    "join",
    "commands",
    "movement",
    "collision",
    "manual_ability",
    "auto_ability",
    "ability",
    "timers",
    "remover",
    "zone",
)
_HOTPATH_TIMER_NAMES = (
    "NpcSteering",
    "CombatClock",
    "MissileFlight",
    "MineTimer",
    "MovementPulse",
    "VisibilitySweep",
    "PropertyFlush",
    "StateFlush",
    "SpawnClock",
)


class Sector:
    def __init__(self, ctx, engagement, spawn_runner, arrival_gate, takarito, damage_book, cast_desk, jump_book, timer_updater, utkozes_ora, teruletkezelo, banyaszat, galaxis_szorzo, zsakmany_sablonok, spoils_split, share_book):
        if ctx is None:
            raise TypeError('a sector context is required')
        self._ctx = ctx

        self._galaxy_bonus = galaxis_szorzo
        self._loot_templates = zsakmany_sablonok
        self._engagement = engagement

        self._spoils_split = spoils_split
        self._arrival_gate = arrival_gate
        self._spawn_runner = spawn_runner
        self._departures_desk = takarito

        self._sector_is_active = True

        self._share_book = share_book
        self._damage_book = damage_book
        self._cast_desk = cast_desk

        self._sector_slot_data = SeatCount()
        self._jump_book = jump_book
        self._timer_updater = timer_updater
        self._collision_updater = utkozes_ora
        self._sector_zone_management = teruletkezelo
        self._mining_sector_operations = banyaszat
        self._last_slow_tick_warn_ms = 0.0
        self._last_hotpath_summary_ms = now_ms() if SECTOR_HOTPATH_SUMMARY_ENABLED else 0.0
        self._hotpath_stats = {nev: RollingLatencyStats() for nev in _HOTPATH_STAGE_NAMES}
        self._hotpath_timer_stats = {nev: RollingLatencyStats() for nev in _HOTPATH_TIMER_NAMES}
        self._sector_movement_updater = MovementStep(
            ctx.tick(), ctx.space_objects(), ctx.sender(), self._departures_desk, self._share_book)
        self._sector_command_queue = SectorCommandQueue(self.id)
        self._gating = SectorGating(self.id)
        set_wake_callback = getattr(self._arrival_gate, "wake_with", None)
        if set_wake_callback is not None:
            set_wake_callback(self._gating.wake)

    @property
    def _evaluate_gating(self):
        return self._gating.evaluate(self._ctx.users().empty, self._has_pending_work())

    @property
    def arrival_gate(self):
        return self._arrival_gate

    @property
    def cast_desk(self):
        return self._cast_desk

    @property
    def colonial_op_state(self):
        return self._ctx.outpost_scoreboard.colonial_outpost_state

    @property
    def ctx(self):
        return self._ctx

    @property
    def cylon_op_state(self):
        return self._ctx.outpost_scoreboard.cylon_outpost_state

    @property
    def damage_book(self):
        return self._damage_book

    @property
    def departures_desk(self):
        return self._departures_desk

    @property
    def id(self) -> int:
        return self._ctx.blueprint().sector_desc.sector_id

    @property
    def is_zone(self) -> bool:
        return self._sector_zone_management.is_zone

    @property
    def jump_book(self):
        return self._jump_book

    @property
    def loot_ownership(self):
        return self._share_book.loot_ownership

    @property
    def mining_sector_operations(self):
        return self._mining_sector_operations

    @property
    def sector_guid(self) -> int:
        return self._ctx.blueprint().sector_cards().sector_card.card_guid_of()

    @property
    def sector_slot_data(self):
        return self._sector_slot_data

    @property
    def spawn_runner(self):
        return self._spawn_runner

    @property
    def spoils_split(self):
        return self._spoils_split

    @property
    def timer_updater(self):
        return self._timer_updater

    def close_sector(self) -> None:
        self._sector_is_active = False
        self._ctx.sender().shutdown()

    def command_queue_of(self):
        return self._sector_command_queue

    def run(self) -> None:
        current_thread = threading.current_thread()
        current_thread.name = current_thread.name + ' sector [' + str(self.id) + "]"

        while self._sector_is_active:
            try:
                self._wait_for_next_sector_tick()
                if not GUARDRAILS_ENABLED:
                    self._run_tick_without_guardrails()
                    continue

                tick_started_ms = now_ms()
                join_ms = command_ms = movement_ms = collision_ms = 0.0
                manual_ability_ms = auto_ability_ms = ability_ms = 0.0
                timers_ms = remover_ms = zone_ms = 0.0
                self._sector_command_queue.begin_tick()
                self._cast_desk.begin_tick()

                stage_started_ms = now_ms()
                self._arrival_gate.run()
                join_ms = elapsed_ms(stage_started_ms)
                gating_decision = self._evaluate_gating

                stage_started_ms = now_ms()
                self._run_input_sector_commands()
                command_ms = elapsed_ms(stage_started_ms)

                if not gating_decision.skip_simulation:
                    stage_started_ms = now_ms()
                    self._cast_desk.run_manual_only(reset=False)
                    manual_ability_ms += elapsed_ms(stage_started_ms)

                    stage_started_ms = now_ms()
                    self._sector_movement_updater.run()
                    movement_ms = elapsed_ms(stage_started_ms)

                    stage_started_ms = now_ms()
                    self._collision_updater.run()
                    collision_ms = elapsed_ms(stage_started_ms)

                    stage_started_ms = now_ms()
                    self._cast_desk.run_manual_only(reset=False)
                    manual_ability_ms += elapsed_ms(stage_started_ms)

                    stage_started_ms = now_ms()
                    self._run_auto_ability_stage()
                    auto_ability_ms = elapsed_ms(stage_started_ms)

                    stage_started_ms = now_ms()
                    self._sector_command_queue.run_normal()
                    command_ms += elapsed_ms(stage_started_ms)
                    ability_ms = manual_ability_ms + auto_ability_ms

                stage_started_ms = now_ms()
                self._timer_updater.run(gating_decision.timer_mode)
                timers_ms = elapsed_ms(stage_started_ms)

                stage_started_ms = now_ms()
                self._departures_desk.run()
                remover_ms = elapsed_ms(stage_started_ms)

                stage_started_ms = now_ms()
                self._sector_zone_management.run()
                zone_ms = elapsed_ms(stage_started_ms)
                self._sector_command_queue.finish_tick()
                self._cast_desk.finish_tick()

                tick_elapsed_ms = elapsed_ms(tick_started_ms)
                timer_stats = self._timer_updater.last_stats()
                movement_stats = self._sector_movement_updater.last_stats()
                collision_stats = self._collision_updater.last_stats()
                ability_stats = self._cast_desk.last_stats()
                command_stats = self._sector_command_queue.last_stats()
                self._record_hotpath_stats(
                    tick_elapsed_ms,
                    join_ms,
                    command_ms,
                    movement_ms,
                    collision_ms,
                    manual_ability_ms,
                    auto_ability_ms,
                    ability_ms,
                    timers_ms,
                    remover_ms,
                    zone_ms,
                    timer_stats,
                )
                self._maybe_log_hotpath_summary(now_ms(), ability_stats, command_stats)
                now_for_warn_ms = now_ms()
                should_log_slow_tick = (
                    should_warn(tick_elapsed_ms, SECTOR_TICK_WARN_MS)
                    and now_for_warn_ms - self._last_slow_tick_warn_ms >= SECTOR_TICK_WARN_INTERVAL_MS
                )
                if should_log_slow_tick:
                    self._last_slow_tick_warn_ms = now_for_warn_ms
                    timer_details = timer_stats.get("timer_details", {})
                    property_stats = timer_details.get("PropertyFlush", {})
                    state_stats = timer_details.get("StateFlush", {})
                    combat_stats = timer_details.get("CombatClock", {})
                    mine_stats = timer_details.get("MineTimer", {})
                    spawn_stats = timer_details.get("SpawnClock", {})
                    log.warning(
                        "Sector[%s] slow tick elapsed_ms=%.1f threshold_ms=%.1f users=%s objects=%s "
                        "gating_state=%s timer_mode=%s skip_simulation=%s adaptive=%s load_ratio=%.2f "
                        "idle_ms=%.0f pending_work=%s "
                        "join_ms=%.1f command_ms=%.1f movement_ms=%.1f collision_ms=%.1f "
                        "manual_ability_ms=%.1f auto_ability_ms=%.1f ability_ms=%.1f timers_ms=%.1f "
                        "remover_ms=%.1f zone_ms=%.1f movement_objects=%s new_maneuvers=%s "
                        "movement_packets=%s movement_out_of_sector=%s native_out_of_bounds_used=%s "
                        "native_out_of_bounds_candidates=%s native_out_of_bounds_fallbacks=%s "
                        "candidate_objects=%s moving_colliders=%s "
                        "contact_pairs=%s primitive_pairs=%s contact_collisions=%s spatial_enabled=%s "
                        "spatial_cells=%s spatial_global_objects=%s spatial_raw_pairs=%s "
                        "primitive_spatial_enabled=%s primitive_candidate_pairs=%s "
                        "sphere_pair_candidates=%s sphere_pair_rejected=%s timers=%s "
                        "due_delayed_timers=%s skipped_delayed_timers=%s skipped_gating_timers=%s "
                        "maintenance_due=%s slowest_timer=%s "
                        "slowest_timer_ms=%.1f property_dirty=%s property_sent=%s state_changed=%s "
                        "combat_ships=%s combat_missiles=%s combat_targets=%s "
                        "mine_count=%s mine_armed=%s mine_triggers=%s mine_spatial_enabled=%s "
                        "mine_spatial_queries=%s mine_spatial_candidates=%s "
                        "spawn_ready=%s spawn_spawned=%s spawn_burst_limit=%s spawn_burst_max_ms=%.1f "
                        "spawn_global_budget_exhausted=%s spawn_remaining_ready=%s "
                        "commands_before=%s commands_after=%s commands_player_processed=%s "
                        "commands_normal_processed=%s commands_max_wait_ms=%.1f "
                        "commands_coalesced_player_input=%s "
                        "ability_manual_processed=%s ability_auto_processed=%s "
                        "ability_auto_skipped_not_due=%s ability_pending_manual=%s "
                        "ability_pending_auto=%s ability_due_pending=%s ability_auto_budget_exhausted=%s "
                        "ability_manual_success=%s ability_manual_failed=%s ability_auto_success=%s "
                        "ability_auto_failed=%s ability_max_manual_wait_ms=%.1f",
                        self.id,
                        tick_elapsed_ms,
                        SECTOR_TICK_WARN_MS,
                        len(self._ctx.users().users_of()),
                        self._ctx.space_objects().size(),
                        gating_decision.state,
                        gating_decision.timer_mode,
                        gating_decision.skip_simulation,
                        gating_decision.adaptive_level,
                        gating_decision.load_ratio,
                        gating_decision.idle_ms,
                        gating_decision.pending_work,
                        join_ms,
                        command_ms,
                        movement_ms,
                        collision_ms,
                        manual_ability_ms,
                        auto_ability_ms,
                        ability_ms,
                        timers_ms,
                        remover_ms,
                        zone_ms,
                        movement_stats.get("objects", 0),
                        movement_stats.get("new_maneuvers", 0),
                        movement_stats.get("movement_packets", 0),
                        movement_stats.get("out_of_sector_objects", 0),
                        movement_stats.get("native_out_of_bounds_used", 0),
                        movement_stats.get("native_out_of_bounds_candidates", 0),
                        movement_stats.get("native_out_of_bounds_fallbacks", 0),
                        collision_stats.get("candidate_objects", 0),
                        collision_stats.get("moving_colliders", 0),
                        collision_stats.get("contact_pairs", 0),
                        collision_stats.get("primitive_pairs", 0),
                        collision_stats.get("contact_collisions", 0),
                        collision_stats.get("spatial_enabled", 0),
                        collision_stats.get("spatial_cells", 0),
                        collision_stats.get("spatial_global_objects", 0),
                        collision_stats.get("spatial_raw_pairs", 0),
                        collision_stats.get("primitive_spatial_enabled", 0),
                        collision_stats.get("primitive_candidate_pairs", 0),
                        collision_stats.get("sphere_pair_candidates", 0),
                        collision_stats.get("sphere_pair_rejected", 0),
                        timer_stats.get("timers", 0),
                        timer_stats.get("due_delayed", 0),
                        timer_stats.get("skipped_delayed", 0),
                        timer_stats.get("skipped_gating", 0),
                        timer_stats.get("maintenance_due", 0),
                        timer_stats.get("slowest_timer"),
                        timer_stats.get("slowest_timer_ms", 0.0),
                        property_stats.get("dirty_objects", 0),
                        property_stats.get("sent_buffers", 0),
                        state_stats.get("changed_states", 0),
                        combat_stats.get("ships", 0),
                        combat_stats.get("missiles", 0),
                        combat_stats.get("missile_targets", 0),
                        mine_stats.get("mines", 0),
                        mine_stats.get("armed_mines", 0),
                        mine_stats.get("triggers", 0),
                        mine_stats.get("spatial_enabled", 0),
                        mine_stats.get("spatial_queries", 0),
                        mine_stats.get("spatial_candidates", 0),
                        spawn_stats.get("ready_items", 0),
                        spawn_stats.get("spawned", 0),
                        spawn_stats.get("burst_limit", 0),
                        spawn_stats.get("burst_max_ms", 0.0),
                        spawn_stats.get("global_budget_exhausted", False),
                        spawn_stats.get("remaining_ready", False),
                        command_stats.get("pending_before", 0),
                        command_stats.get("pending_after", 0),
                        command_stats.get("processed_player_input", 0),
                        command_stats.get("processed_normal", 0),
                        command_stats.get("max_wait_ms", 0.0),
                        command_stats.get("coalesced_player_input_replaced", 0),
                        ability_stats.get("manual_processed", 0),
                        ability_stats.get("auto_processed", 0),
                        ability_stats.get("auto_skipped_not_due", 0),
                        ability_stats.get("manual_pending", 0),
                        ability_stats.get("auto_pending", 0),
                        ability_stats.get("auto_due_pending", 0),
                        ability_stats.get("auto_budget_exhausted", False),
                        ability_stats.get("manual_success", 0),
                        ability_stats.get("manual_failed", 0),
                        ability_stats.get("auto_success", 0),
                        ability_stats.get("auto_failed", 0),
                        ability_stats.get("max_manual_wait_ms", 0.0),
                    )
            except Exception as ex:
                log.error('Sector[%s] tick blew up %s', self.id, hivasi_lanc(ex))
        log.info("Sector[%s] deactivated, is_active-flag: %s", self.id, self._sector_is_active)

    def _has_pending_work(self) -> bool:
        join_has_pending = getattr(self._arrival_gate, "has_pending_work", None)
        remover_has_pending = getattr(self._departures_desk, "has_pending_work", None)
        return (
            (callable(join_has_pending) and join_has_pending())
            or (callable(remover_has_pending) and remover_has_pending())
            or self._sector_command_queue.has_pending_work()
        )

    def _maybe_log_hotpath_summary(self, now_for_summary_ms: float, ability_stats: dict, command_stats: dict) -> None:
        if not SECTOR_HOTPATH_SUMMARY_ENABLED:
            return
        if now_for_summary_ms - self._last_hotpath_summary_ms < SECTOR_HOTPATH_SUMMARY_INTERVAL_MS:
            return
        self._last_hotpath_summary_ms = now_for_summary_ms
        tick = self._hotpath_stats["tick"].snapshot()
        join = self._hotpath_stats["join"].snapshot()
        commands = self._hotpath_stats["commands"].snapshot()
        movement = self._hotpath_stats["movement"].snapshot()
        collision = self._hotpath_stats["collision"].snapshot()
        manual_ability = self._hotpath_stats["manual_ability"].snapshot()
        auto_ability = self._hotpath_stats["auto_ability"].snapshot()
        ability = self._hotpath_stats["ability"].snapshot()
        timers = self._hotpath_stats["timers"].snapshot()
        remover = self._hotpath_stats["remover"].snapshot()
        zone = self._hotpath_stats["zone"].snapshot()
        npc_dynamic = self._hotpath_timer_stats["NpcSteering"].snapshot()
        combat = self._hotpath_timer_stats["CombatClock"].snapshot()
        raketa = self._hotpath_timer_stats["MissileFlight"].snapshot()
        mine = self._hotpath_timer_stats["MineTimer"].snapshot()
        movement_heartbeat = self._hotpath_timer_stats["MovementPulse"].snapshot()
        visibility = self._hotpath_timer_stats["VisibilitySweep"].snapshot()
        properties = self._hotpath_timer_stats["PropertyFlush"].snapshot()
        allapot = self._hotpath_timer_stats["StateFlush"].snapshot()
        spawn = self._hotpath_timer_stats["SpawnClock"].snapshot()
        movement_stats = self._sector_movement_updater.last_stats()
        log.info(
            "Sector[%s] hotpath summary samples=%s total_ticks=%s users=%s objects=%s "
            "tick_avg_ms=%.1f tick_p95_ms=%.1f tick_max_ms=%.1f "
            "join_avg_ms=%.1f commands_avg_ms=%.1f commands_p95_ms=%.1f commands_max_ms=%.1f "
            "movement_avg_ms=%.1f movement_p95_ms=%.1f movement_max_ms=%.1f "
            "movement_out_of_sector=%s native_out_of_bounds_used=%s "
            "native_out_of_bounds_candidates=%s native_out_of_bounds_fallbacks=%s "
            "collision_avg_ms=%.1f collision_p95_ms=%.1f collision_max_ms=%.1f "
            "manual_ability_avg_ms=%.1f manual_ability_p95_ms=%.1f manual_ability_max_ms=%.1f "
            "auto_ability_avg_ms=%.1f auto_ability_p95_ms=%.1f auto_ability_max_ms=%.1f "
            "ability_avg_ms=%.1f ability_p95_ms=%.1f ability_max_ms=%.1f "
            "timers_avg_ms=%.1f timers_p95_ms=%.1f timers_max_ms=%.1f "
            "remover_avg_ms=%.1f zone_avg_ms=%.1f "
            "npc_dynamic_avg_ms=%.1f npc_dynamic_p95_ms=%.1f npc_dynamic_max_ms=%.1f "
            "combat_timer_avg_ms=%.1f combat_timer_p95_ms=%.1f combat_timer_max_ms=%.1f "
            "missile_timer_avg_ms=%.1f missile_timer_p95_ms=%.1f missile_timer_max_ms=%.1f "
            "mine_timer_avg_ms=%.1f mine_timer_p95_ms=%.1f mine_timer_max_ms=%.1f "
            "movement_heartbeat_avg_ms=%.1f visibility_avg_ms=%.1f "
            "property_timer_avg_ms=%.1f state_timer_avg_ms=%.1f "
            "spawn_scheduler_avg_ms=%.1f spawn_scheduler_p95_ms=%.1f spawn_scheduler_max_ms=%.1f "
            "commands_before=%s commands_after=%s commands_player_processed=%s commands_normal_processed=%s "
            "commands_max_wait_ms=%.1f commands_coalesced_player_input=%s "
            "ability_manual_processed=%s ability_auto_processed=%s ability_auto_skipped_not_due=%s "
            "ability_pending_manual=%s ability_pending_auto=%s ability_due_pending=%s "
            "ability_auto_budget_exhausted=%s ability_max_manual_wait_ms=%.1f",
            self.id,
            tick["count"],
            tick["total_count"],
            len(self._ctx.users().users_of()),
            self._ctx.space_objects().size(),
            tick["avg_ms"],
            tick["p95_ms"],
            tick["max_ms"],
            join["avg_ms"],
            commands["avg_ms"],
            commands["p95_ms"],
            commands["max_ms"],
            movement["avg_ms"],
            movement["p95_ms"],
            movement["max_ms"],
            movement_stats.get("out_of_sector_objects", 0),
            movement_stats.get("native_out_of_bounds_used", 0),
            movement_stats.get("native_out_of_bounds_candidates", 0),
            movement_stats.get("native_out_of_bounds_fallbacks", 0),
            collision["avg_ms"],
            collision["p95_ms"],
            collision["max_ms"],
            manual_ability["avg_ms"],
            manual_ability["p95_ms"],
            manual_ability["max_ms"],
            auto_ability["avg_ms"],
            auto_ability["p95_ms"],
            auto_ability["max_ms"],
            ability["avg_ms"],
            ability["p95_ms"],
            ability["max_ms"],
            timers["avg_ms"],
            timers["p95_ms"],
            timers["max_ms"],
            remover["avg_ms"],
            zone["avg_ms"],
            npc_dynamic["avg_ms"],
            npc_dynamic["p95_ms"],
            npc_dynamic["max_ms"],
            combat["avg_ms"],
            combat["p95_ms"],
            combat["max_ms"],
            raketa["avg_ms"],
            raketa["p95_ms"],
            raketa["max_ms"],
            mine["avg_ms"],
            mine["p95_ms"],
            mine["max_ms"],
            movement_heartbeat["avg_ms"],
            visibility["avg_ms"],
            properties["avg_ms"],
            allapot["avg_ms"],
            spawn["avg_ms"],
            spawn["p95_ms"],
            spawn["max_ms"],
            command_stats.get("pending_before", 0),
            command_stats.get("pending_after", 0),
            command_stats.get("processed_player_input", 0),
            command_stats.get("processed_normal", 0),
            command_stats.get("max_wait_ms", 0.0),
            command_stats.get("coalesced_player_input_replaced", 0),
            ability_stats.get("manual_processed", 0),
            ability_stats.get("auto_processed", 0),
            ability_stats.get("auto_skipped_not_due", 0),
            ability_stats.get("manual_pending", 0),
            ability_stats.get("auto_pending", 0),
            ability_stats.get("auto_due_pending", 0),
            ability_stats.get("auto_budget_exhausted", False),
            ability_stats.get("max_manual_wait_ms", 0.0),
        )

    def _record_hotpath_stats(self, tick_ms: float, join_ms: float, command_ms: float,
                              movement_ms: float, collision_ms: float, manual_ability_ms: float,
                              auto_ability_ms: float, ability_ms: float,
                              timers_ms: float, remover_ms: float, zone_ms: float,
                              timer_stats: dict) -> None:
        if not SECTOR_HOTPATH_SUMMARY_ENABLED:
            return
        stage_values = {
            "tick": tick_ms,
            "join": join_ms,
            "commands": command_ms,
            "movement": movement_ms,
            "collision": collision_ms,
            "manual_ability": manual_ability_ms,
            "auto_ability": auto_ability_ms,
            "ability": ability_ms,
            "timers": timers_ms,
            "remover": remover_ms,
            "zone": zone_ms,
        }
        for nev, ertek in stage_values.items():
            self._hotpath_stats[nev].add(ertek)
        timer_elapsed_ms_by_name = timer_stats.get("timer_elapsed_ms_by_name", {})
        for timer_name in _HOTPATH_TIMER_NAMES:
            self._hotpath_timer_stats[timer_name].add(timer_elapsed_ms_by_name.get(timer_name, 0.0))

    def _run_auto_ability_stage(self) -> None:
        if SECTOR_PIPELINE_BUDGET_ENABLED:
            self._cast_desk.run_auto_budgeted(reset=False)
            return
        self._cast_desk.run_auto_budgeted(reset=False, max_items=None, max_ms=None)

    def _run_input_sector_commands(self) -> None:
        self._sector_command_queue.run_critical()
        self._sector_command_queue.run_player_input()

    def _run_tick_without_guardrails(self) -> None:
        self._sector_command_queue.begin_tick()
        self._cast_desk.begin_tick()
        self._arrival_gate.run()
        gating_decision = self._evaluate_gating
        self._run_input_sector_commands()
        if not gating_decision.skip_simulation:
            self._cast_desk.run_manual_only(reset=False)
            self._sector_movement_updater.run()
            self._collision_updater.run()
            self._cast_desk.run_manual_only(reset=False)
            self._run_auto_ability_stage()
            self._sector_command_queue.run_normal()
        self._timer_updater.run(gating_decision.timer_mode)
        self._departures_desk.run()
        self._sector_zone_management.run()
        self._sector_command_queue.finish_tick()
        self._cast_desk.finish_tick()

    def _wait_for_next_sector_tick(self) -> None:
        gating_decision = self._evaluate_gating
        if gating_decision.deep_sleep:
            self._gating.wait_deep_idle()
            self._ctx.tick().sync_to_wall_clock()
            return
        self._ctx.tick().sleep_until_next_tick()
