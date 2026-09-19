# github.com/Shran21
from __future__ import annotations

import logging
import heapq
from collections import deque
from itertools import count

from rebsgo.world.sectors.powers.power_bits import DeedSource
from rebsgo.world.sectors.powers.power_bits import CastOrder
from rebsgo.world.sectors.powers.stealth import is_cloaked_outside_visual_detection
from rebsgo.world.sectors.sector_parts import SectorStep
from rebsgo.world.objects.ships import PlayerShip
from rebsgo.gamedata.reading import ObjectStat
from rebsgo.helpers.rolling_latency_stats import (
    ABILITY_DIAGNOSTICS_ENABLED,
    PLAYER_INPUT_WARN_MS,
    SECTOR_NPC_AUTO_MAX_ITEMS,
    SECTOR_NPC_AUTO_MAX_MS,
    SECTOR_TIMER_WARN_INTERVAL_MS,
    elapsed_ms,
    now_ms,
    should_warn,
    should_warn_interval,
)
from rebsgo import journal

log = logging.getLogger(__name__)


class CastQueue(SectorStep):
    def __init__(self, ctx, engagement, damage_book, arrival_gate,
                 loot_ownership):
        self._ability_cast_requests = deque()
        self._auto_cast_abilities = {}
        self._ctx = ctx
        self._deed_source = DeedSource(ctx, engagement, damage_book,
                                       arrival_gate, loot_ownership, self)
        self._last_player_input_warn_ms = 0.0
        self._sector_id = self._resolve_sector_id(ctx)
        self._auto_cast_next_due_ms = {}
        self._auto_cast_due_heap = []
        self._auto_cast_due_sequence = count()
        self._auto_gond_nyom = {}
        self._last_stats = self._empty_stats()

    _auto_gond_nyom: dict

    def enqueue_cast(self, cast_request) -> None:
        if cast_request is not None:
            mark_if_missing = getattr(cast_request, "mark_enqueued_if_missing", None)
            if callable(mark_if_missing):
                mark_if_missing(now_ms())
            else:
                cast_request.mark_enqueued(now_ms())
        self._ability_cast_requests.append(cast_request)

    def arm_auto_cast(self, cast_request) -> None:
        if cast_request is None:
            raise TypeError('ability request absent')
        kulcs = self._key_of(cast_request)
        elozo = self._auto_cast_abilities.get(kulcs)
        self._auto_cast_abilities[kulcs] = cast_request
        if elozo is cast_request:
            self._ensure_auto_scheduled(kulcs, cast_request)
            return
        if elozo is not None and self._same_targets(elozo, cast_request):
            self._ensure_auto_scheduled(kulcs, cast_request)
            return
        self._schedule_auto_cast(kulcs, cast_request, self._next_due_ms_for_request(cast_request))

    def disarm_auto_cast(self, ability_id: int, object_id: int) -> None:
        kulcs = CastOrder.key_for(object_id, ability_id)
        self._auto_cast_abilities.pop(kulcs, None)
        self._auto_due_map().pop(kulcs, None)

    def drop_auto_casts_of(self, object_id: int) -> None:
        for ertek in list(self._auto_cast_abilities.values()):
            if ertek.casting_ship.id_in_space() == object_id:
                kulcs = self._key_of(ertek)
                self._auto_cast_abilities.pop(kulcs, None)
                self._auto_due_map().pop(kulcs, None)

    def remove_auto_cast_abilities_targeting_object(self, casting_object_id: int, target_object_id: int) -> None:
        for ertek in list(self._auto_cast_abilities.values()):
            if self._request_targets_object(ertek, casting_object_id, target_object_id):
                kulcs = self._key_of(ertek)
                self._auto_cast_abilities.pop(kulcs, None)
                self._auto_due_map().pop(kulcs, None)

        self._ability_cast_requests = deque(
            request for request in self._ability_cast_requests
            if not self._request_targets_object(request, casting_object_id, target_object_id))

    @staticmethod
    def _request_targets_object(request, casting_object_id: int, target_object_id: int) -> bool:
        if request.casting_ship.id_in_space() != casting_object_id:
            return False
        return target_object_id in request.target_ids

    @staticmethod
    def _key_of(request) -> int:
        return CastOrder.key_for(request.casting_ship.id_in_space(), request.ability_id)

    @staticmethod
    def _same_targets(first, second) -> bool:
        return set(first.target_ids) == set(second.target_ids)

    def run(self) -> None:
        self.begin_tick()
        self.run_manual_only(reset=False)
        self.run_auto_budgeted(reset=False, max_items=None, max_ms=None)
        self.run_manual_only(reset=False)
        self.finish_tick()

    def begin_tick(self) -> None:
        self._ensure_auto_scheduler_state()
        self._last_stats = self._empty_stats()
        self._last_stats["manual_pending_before"] = len(self._ability_cast_requests)
        self._last_stats["auto_pending_before"] = len(self._auto_cast_abilities)
        self._last_stats["auto_due_pending_before"] = len(self._auto_due_map())

    def finish_tick(self) -> None:
        self._last_stats["manual_pending"] = len(self._ability_cast_requests)
        self._last_stats["auto_pending"] = len(self._auto_cast_abilities)
        self._last_stats["auto_due_pending"] = len(self._auto_due_map())

    def run_manual_only(self, reset: bool = True) -> int:
        if reset:
            self.begin_tick()
        processed = 0
        while self._ability_cast_requests:
            cast_request = self._ability_cast_requests.popleft()
            wait_ms = self._manual_wait_ms(cast_request)
            if wait_ms > self._last_stats.get("max_manual_wait_ms", 0.0):
                self._last_stats["max_manual_wait_ms"] = wait_ms
            if self._warn_if_player_input_waited(cast_request, wait_ms):
                self._last_stats["manual_wait_warns"] = self._last_stats.get("manual_wait_warns", 0) + 1
            if self._process_request(cast_request):
                self._last_stats["manual_success"] = self._last_stats.get("manual_success", 0) + 1
            else:
                self._last_stats["manual_failed"] = self._last_stats.get("manual_failed", 0) + 1
            processed += 1
            self._last_stats["manual_processed"] = self._last_stats.get("manual_processed", 0) + 1
        if reset:
            self.finish_tick()
        return processed

    def run_auto_budgeted(
            self,
            reset: bool = True,
            max_items: int | None = SECTOR_NPC_AUTO_MAX_ITEMS,
            max_ms: float | None = SECTOR_NPC_AUTO_MAX_MS) -> int:
        self._ensure_auto_scheduler_state()
        if reset:
            self.begin_tick()
        self._bootstrap_auto_due_heap()
        tick_ms = self._current_tick_ms()
        started_ms = now_ms()
        processed = 0
        while True:
            if self._ability_cast_requests:
                break
            if max_items is not None and processed >= max(0, int(max_items)):
                self._last_stats["auto_budget_exhausted"] = True
                break
            if max_ms is not None and max_ms > 0 and elapsed_ms(started_ms) >= float(max_ms):
                self._last_stats["auto_budget_exhausted"] = True
                break
            due_item = self._pop_due_auto_cast(tick_ms)
            if due_item is None:
                self._last_stats["auto_skipped_not_due"] = len(self._auto_due_map())
                break
            kulcs, cast_request = due_item
            if self._process_request(cast_request):
                self._last_stats["auto_success"] = self._last_stats.get("auto_success", 0) + 1
            else:
                self._last_stats["auto_failed"] = self._last_stats.get("auto_failed", 0) + 1
            processed += 1
            self._last_stats["auto_processed"] = self._last_stats.get("auto_processed", 0) + 1
            if self._auto_cast_abilities.get(kulcs) is cast_request:
                self._schedule_auto_cast(
                    kulcs,
                    cast_request,
                    self._next_due_ms_for_request(cast_request),
                    force_next_tick=True,
                )
        if self._last_stats.get("auto_budget_exhausted"):
            self._last_stats["auto_due_pending"] = len(self._auto_due_map())
        if reset:
            self.finish_tick()
        return processed

    def _ensure_auto_scheduler_state(self) -> None:
        if not hasattr(self, "_auto_cast_next_due_ms"):
            self._auto_cast_next_due_ms = {}
        if not hasattr(self, "_auto_cast_due_heap"):
            self._auto_cast_due_heap = []
        if not hasattr(self, "_auto_cast_due_sequence"):
            self._auto_cast_due_sequence = count()

    def _auto_due_map(self) -> dict:
        self._ensure_auto_scheduler_state()
        return self._auto_cast_next_due_ms

    def _bootstrap_auto_due_heap(self) -> None:
        self._ensure_auto_scheduler_state()
        due_map = self._auto_cast_next_due_ms
        for kulcs, request in list(self._auto_cast_abilities.items()):
            if kulcs not in due_map:
                self._schedule_auto_cast(kulcs, request, self._next_due_ms_for_request(request))

    def _ensure_auto_scheduled(self, key: int, request) -> None:
        if key not in self._auto_due_map():
            self._schedule_auto_cast(key, request, self._next_due_ms_for_request(request))

    def _schedule_auto_cast(self, key: int, request, due_ms: int, force_next_tick: bool = False) -> None:
        self._ensure_auto_scheduler_state()
        most = self._current_tick_ms()
        due_ms = int(due_ms)
        if force_next_tick:
            due_ms = max(due_ms, most + 1)
        self._auto_cast_next_due_ms[key] = due_ms
        heapq.heappush(self._auto_cast_due_heap, (due_ms, next(self._auto_cast_due_sequence), key))

    def _pop_due_auto_cast(self, tick_ms: int):
        self._ensure_auto_scheduler_state()
        heap = self._auto_cast_due_heap
        due_map = self._auto_cast_next_due_ms
        while heap:
            due_ms, _, kulcs = heap[0]
            if due_ms > tick_ms:
                return None
            heapq.heappop(heap)
            if due_map.get(kulcs) != due_ms:
                continue
            cast_request = self._auto_cast_abilities.get(kulcs)
            if cast_request is None:
                due_map.pop(kulcs, None)
                continue
            due_map.pop(kulcs, None)
            return kulcs, cast_request
        return None

    def _next_due_ms_for_request(self, cast_request) -> int:
        most = self._current_tick_ms()
        try:
            casting_ship = self._resolve_current_casting_ship(cast_request)
            rekeszek = casting_ship.space_subscribe_info().ship_slots
            if rekeszek is None:
                return most
            slot = rekeszek.slot(cast_request.ability_id)
            if slot is None or slot.ship_system is None or slot.ship_ability() is None:
                return most
            kepesseg = slot.ship_ability()
            rendszer = slot.ship_system
            cooldown = kepesseg.item_buff_add.stat(ObjectStat.Cooldown)
            if cooldown <= 0:
                return most
            return max(most, int((rendszer.time_of_last_use + cooldown) * 1000))
        except Exception:
            journal.eloszor(log, 'cast-cooldown',
                            'an ability cooldown cannot be read; the cast is let through')
            return most

    def _resolve_current_casting_ship(self, cast_request):
        ctx = getattr(self, "_ctx", None)
        if ctx is None:
            return cast_request.casting_ship
        try:
            mostani = ctx.space_objects().ship_by_object_id(
                cast_request.casting_ship.id_in_space())
            return mostani if mostani is not None else cast_request.casting_ship
        except Exception:
            journal.eloszor(log, 'cast-ship',
                            'the casting ship cannot be looked up afresh; the queued one stands')
            return cast_request.casting_ship

    def _current_tick_ms(self) -> int:
        if (ctx := getattr(self, '_ctx', None)) is not None:
            try:
                return int(ctx.tick().time_stamp())
            except Exception:
                journal.eloszor(log, 'cast-tick', 'the sector clock is unreadable; wall time stands in')
        return int(now_ms())

    @staticmethod
    def _empty_stats() -> dict:
        return {
            "manual_processed": 0,
            "manual_success": 0,
            "manual_failed": 0,
            "auto_processed": 0,
            "auto_success": 0,
            "auto_failed": 0,
            "auto_skipped_not_due": 0,
            "manual_pending_before": 0,
            "auto_pending_before": 0,
            "auto_due_pending_before": 0,
            "manual_pending": 0,
            "auto_pending": 0,
            "auto_due_pending": 0,
            "auto_budget_exhausted": False,
            "max_manual_wait_ms": 0.0,
            "manual_wait_warns": 0,
        }

    def _process_request(self, cast_request) -> bool:
        if cast_request is None:
            return False

        casting_ship = self._ctx.space_objects().ship_by_object_id(
            cast_request.casting_ship.id_in_space())
        if casting_ship is None:
            self.disarm_auto_cast(cast_request.ability_id,
                                  cast_request.casting_ship.id_in_space())
            return False
        rekeszek = casting_ship.space_subscribe_info().ship_slots
        if rekeszek is None:
            return False
        casting_slot = rekeszek.slot(cast_request.ability_id)
        if casting_slot is None:
            return False
        if casting_slot.ship_ability() is None:
            return False
        to_call_on = []
        for obj_id in cast_request.target_ids:
            if (tmp_obj := self._ctx.space_objects().get(obj_id)) is not None:
                if tmp_obj.is_visible() and self._can_cast_on_target(casting_ship, tmp_obj):
                    to_call_on.append(tmp_obj)

        ability_action = self._deed_source.create(
            casting_ship, casting_slot, to_call_on, cast_request.fired_automatically)
        processed = bool(ability_action.process())
        if cast_request.fired_automatically and log.isEnabledFor(logging.DEBUG):
            kulcs = (casting_ship.id_in_space(), cast_request.ability_id)
            if processed:
                if self._auto_gond_nyom.pop(kulcs, None) is not None:
                    log.debug("auto-cast: #%s slot %s fires again",
                              casting_ship.id_in_space(), cast_request.ability_id)
            else:
                ok = str(ability_action.failure_reason)
                if self._auto_gond_nyom.get(kulcs) != ok:
                    self._auto_gond_nyom[kulcs] = ok
                    log.debug("auto-cast refused: #%s slot %s targets=%s resolved=%s | %s",
                              casting_ship.id_in_space(), cast_request.ability_id,
                              list(cast_request.target_ids),
                              [t.id_in_space() for t in to_call_on], ok)
        if (not processed
            and ABILITY_DIAGNOSTICS_ENABLED
            and not cast_request.fired_automatically):
            log.info(
                "Manual ability request failed sector=%s object_id=%s player_id=%s ability_id=%s "
                "targets=%s resolved_targets=%s reason=%s",
                self._sector_id,
                casting_ship.id_in_space(),
                casting_ship.pilot_id() if casting_ship.is_player() else None,
                cast_request.ability_id,
                cast_request.target_ids,
                [celpont.id_in_space() for celpont in to_call_on],
                ability_action.failure_reason,
            )
        if cast_request.fired_automatically and ability_action.should_remove_auto_cast:
            self.disarm_auto_cast(cast_request.ability_id, casting_ship.id_in_space())
            self._send_stop_slot_ability(casting_ship, cast_request.ability_id)
        return processed

    @staticmethod
    def _manual_wait_ms(cast_request) -> float:
        if cast_request is None:
            return 0.0
        enqueued_ms = cast_request.enqueued_ms
        if enqueued_ms is None:
            return 0.0
        return elapsed_ms(enqueued_ms)

    def _warn_if_player_input_waited(self, cast_request, wait_ms: float) -> bool:
        if not should_warn(wait_ms, PLAYER_INPUT_WARN_MS):
            return False
        if not should_warn_interval(self._last_player_input_warn_ms, SECTOR_TIMER_WARN_INTERVAL_MS):
            return False
        self._last_player_input_warn_ms = now_ms()
        casting_ship = cast_request.casting_ship
        log.warning(
            "Pilot ability input waited sector=%s object_id=%s player_id=%s ability_id=%s "
            "wait_ms=%.1f threshold_ms=%.1f pending_manual=%s pending_auto=%s",
            self._sector_id,
            casting_ship.id_in_space() if casting_ship is not None else None,
            casting_ship.pilot_id() if casting_ship is not None and casting_ship.is_player() else None,
            cast_request.ability_id,
            wait_ms,
            PLAYER_INPUT_WARN_MS,
            len(self._ability_cast_requests),
            len(self._auto_cast_abilities),
        )
        return True

    @staticmethod
    def _resolve_sector_id(ctx):
        try:
            return ctx.blueprint().sector_desc.sector_id
        except Exception:
            return None

    def _send_stop_slot_ability(self, caster, ability_id: int) -> None:
        if not caster.is_player():
            return
        user = self._ctx.users().user(caster.pilot_id())
        if user is None:
            return
        from rebsgo.protocol.protocol_id import ProtocolID
        game_protocol = user.protocol_of(ProtocolID.Game)
        if game_protocol is None:
            return
        self._ctx.sender().push_to(
            game_protocol.replies.stop_slot_ability(ability_id), user)

    @staticmethod
    def _can_cast_on_target(caster, target) -> bool:
        if not isinstance(target, PlayerShip):
            return True
        if not target.world_state_of().is_cloaked:
            return True
        if caster.is_player():
            return True
        return not is_cloaked_outside_visual_detection(caster, target)

    def last_stats(self) -> dict:
        return dict(getattr(self, "_last_stats", {}))
