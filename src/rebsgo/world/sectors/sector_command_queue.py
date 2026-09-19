# github.com/Shran21
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from threading import Lock

from rebsgo.helpers.rolling_latency_stats import (
    ENABLED as GUARDRAILS_ENABLED,
    SECTOR_COMMAND_MAX_NORMAL,
    SECTOR_COMMAND_MAX_PLAYER_INPUT,
    SECTOR_COMMAND_WARN_MS,
    elapsed_ms,
    now_ms,
    should_warn,
)

log = logging.getLogger(__name__)

LANE_CRITICAL = "critical"
LANE_PLAYER_INPUT = "player_input"
LANE_NORMAL = "normal"
LANE_MAINTENANCE = "maintenance"

_LANES = (LANE_CRITICAL, LANE_PLAYER_INPUT, LANE_NORMAL, LANE_MAINTENANCE)


@dataclass
class SectorCommand:
    callback: object
    description: str
    enqueue_ms: float
    source: str
    coalesce_key: object | None = None
    cancelled: bool = False


class SectorCommandQueue:
    def __init__(self, sector_id: int | None = None):
        self._sector_id = sector_id
        self._lock = Lock()
        self._queues = {lane: deque() for lane in _LANES}
        self._coalesced_player_input = {}
        self._coalesced_player_input_replaced = 0
        self._last_stats = self._empty_stats()

    def enqueue_critical(self, callback, description: str = "critical", source: str = "unknown") -> None:
        self._enqueue(LANE_CRITICAL, callback, description, source)

    def enqueue_player_input(self, callback, description: str = "player_input", source: str = "unknown") -> None:
        self._enqueue(LANE_PLAYER_INPUT, callback, description, source)

    def enqueue_player_input_coalesced(
            self, callback, coalesce_key, description: str = "player_input", source: str = "unknown") -> None:
        if coalesce_key is None:
            self.enqueue_player_input(callback, description, source)
            return
        self._enqueue(LANE_PLAYER_INPUT, callback, description, source, coalesce_key)

    def enqueue_normal(self, callback, description: str = "normal", source: str = "unknown") -> None:
        self._enqueue(LANE_NORMAL, callback, description, source)

    def enqueue_maintenance(self, callback, description: str = "maintenance", source: str = "unknown") -> None:
        self._enqueue(LANE_MAINTENANCE, callback, description, source)

    def _enqueue(self, lane: str, callback, description: str, source: str, coalesce_key=None) -> None:
        if callback is None:
            return
        if lane not in self._queues:
            raise ValueError(f'unknown sector command lane {lane}')
        command = SectorCommand(callback, description, now_ms(), source, coalesce_key)
        with self._lock:
            if lane == LANE_PLAYER_INPUT and coalesce_key is not None:
                if (old_command := self._coalesced_player_input.get(coalesce_key)) is not None:
                    old_command.cancelled = True
                    self._coalesced_player_input_replaced += 1
                self._coalesced_player_input[coalesce_key] = command
            self._queues[lane].append(command)

    def run_critical(self) -> int:
        return self._drain_lane(LANE_CRITICAL, None)

    def run_player_input(self, max_items: int | None = None) -> int:
        if max_items is None:
            max_items = SECTOR_COMMAND_MAX_PLAYER_INPUT
        return self._drain_lane(LANE_PLAYER_INPUT, max_items)

    def run_normal(self, max_items: int | None = None) -> int:
        if max_items is None:
            max_items = SECTOR_COMMAND_MAX_NORMAL
        return self._drain_lane(LANE_NORMAL, max_items)

    def run_maintenance(self, max_items: int | None = None) -> int:
        return self._drain_lane(LANE_MAINTENANCE, max_items)

    def _drain_lane(self, lane: str, max_items: int | None) -> int:
        processed = 0
        while max_items is None or processed < max(0, max_items):
            command = self._pop(lane)
            if command is None:
                break
            wait_ms = elapsed_ms(command.enqueue_ms)
            try:
                command.callback()
            except Exception:
                log.exception(
                    "Sector command failed sector=%s lane=%s description=%s source=%s wait_ms=%.1f",
                    self._sector_id,
                    lane,
                    command.description,
                    command.source,
                    wait_ms,
                )
            processed += 1
            self._record_processed(lane, wait_ms)
            if GUARDRAILS_ENABLED and should_warn(wait_ms, SECTOR_COMMAND_WARN_MS):
                log.warning(
                    "Sector command waited sector=%s lane=%s description=%s source=%s "
                    "wait_ms=%.1f threshold_ms=%.1f pending=%s",
                    self._sector_id,
                    lane,
                    command.description,
                    command.source,
                    wait_ms,
                    SECTOR_COMMAND_WARN_MS,
                    self.pending_count(),
                )
        return processed

    def begin_tick(self) -> None:
        self._last_stats = self._empty_stats()
        self._last_stats["pending_before"] = self.pending_count()

    def finish_tick(self) -> None:
        self._last_stats["pending_after"] = self.pending_count()
        for lane in _LANES:
            self._last_stats["pending_" + lane] = self.pending_count(lane)
        self._last_stats["coalesced_player_input_replaced"] = self._consume_coalesced_player_input_replaced()

    def _pop(self, lane: str):
        with self._lock:
            queue = self._queues[lane]
            while queue:
                command = queue.popleft()
                if command.coalesce_key is not None:
                    mostani = self._coalesced_player_input.get(command.coalesce_key)
                    if mostani is command:
                        self._coalesced_player_input.pop(command.coalesce_key, None)
                if command.cancelled:
                    continue
                return command
            return None

    def pending_count(self, lane: str | None = None) -> int:
        with self._lock:
            if lane is not None:
                return sum(1 for command in self._queues[lane] if not command.cancelled)
            return sum(
                1
                for queue in self._queues.values()
                for command in queue
                if not command.cancelled
            )

    def has_pending_work(self) -> bool:
        return self.pending_count() > 0

    def _record_processed(self, lane: str, wait_ms: float) -> None:
        kulcs = "processed_" + lane
        self._last_stats[kulcs] = self._last_stats.get(kulcs, 0) + 1
        if wait_ms > self._last_stats.get("max_wait_ms", 0.0):
            self._last_stats["max_wait_ms"] = wait_ms

    def _consume_coalesced_player_input_replaced(self) -> int:
        with self._lock:
            replaced = self._coalesced_player_input_replaced
            self._coalesced_player_input_replaced = 0
            return replaced

    @staticmethod
    def _empty_stats() -> dict:
        return {
            "pending_before": 0,
            "pending_after": 0,
            "processed_critical": 0,
            "processed_player_input": 0,
            "processed_normal": 0,
            "processed_maintenance": 0,
            "pending_critical": 0,
            "pending_player_input": 0,
            "pending_normal": 0,
            "pending_maintenance": 0,
            "coalesced_player_input_replaced": 0,
            "max_wait_ms": 0.0,
        }

    def last_stats(self) -> dict:
        return dict(self._last_stats)
