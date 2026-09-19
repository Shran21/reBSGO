# github.com/Shran21
from __future__ import annotations

import time
from collections import deque

from rebsgo.config.config import Config


_CONFIG = Config.instance()

ENABLED = _CONFIG.bool("rebsgo.guardrails.enabled", False)

SECTOR_TICK_WARN_MS = _CONFIG.float("rebsgo.guardrails.sector-tick-warn-ms", 150.0)
SECTOR_TICK_WARN_INTERVAL_MS = _CONFIG.float("rebsgo.guardrails.sector-tick-warn-interval-ms", 10000.0)
SECTOR_HOTPATH_SUMMARY_ENABLED = _CONFIG.bool("rebsgo.guardrails.sector-hotpath-summary-enabled", ENABLED)
SECTOR_HOTPATH_SUMMARY_INTERVAL_MS = _CONFIG.float(
    "rebsgo.guardrails.sector-hotpath-summary-interval-ms", 60000.0)
SECTOR_HOTPATH_SUMMARY_SAMPLE_SIZE = _CONFIG.int("rebsgo.guardrails.sector-hotpath-summary-sample-size", 600)
SECTOR_TIMER_WARN_MS = _CONFIG.float("rebsgo.guardrails.sector-timer-warn-ms", 50.0)
SECTOR_TIMER_WARN_INTERVAL_MS = _CONFIG.float("rebsgo.guardrails.sector-timer-warn-interval-ms", 10000.0)
SECTOR_MOVEMENT_PACKET_WARN_COUNT = _CONFIG.int("rebsgo.guardrails.sector-movement-packet-warn-count", 250)
SECTOR_STATE_PACKET_WARN_COUNT = _CONFIG.int("rebsgo.guardrails.sector-state-packet-warn-count", 200)
SECTOR_PROPERTY_BUFFER_WARN_COUNT = _CONFIG.int("rebsgo.guardrails.sector-property-buffer-warn-count", 250)
SECTOR_COMBAT_OBJECT_WARN_COUNT = _CONFIG.int("rebsgo.guardrails.sector-combat-object-warn-count", 500)
SECTOR_ENTRY_OBJECT_WARN_COUNT = _CONFIG.int("rebsgo.guardrails.sector-entry-object-warn-count", 250)
SECTOR_ENTRY_PACKET_WARN_COUNT = _CONFIG.int("rebsgo.guardrails.sector-entry-packet-warn-count", 700)
SECTOR_NPC_TARGET_SCAN_WARN_CHECKS = _CONFIG.int("rebsgo.guardrails.sector-npc-target-scan-warn-checks", 5000)
SECTOR_SPAWN_COLLISION_SCAN_WARN_COUNT = _CONFIG.int(
    "rebsgo.guardrails.sector-spawn-collision-scan-warn-count", 1000)
SECTOR_PIPELINE_BUDGET_ENABLED = _CONFIG.bool("rebsgo.sector.pipeline-budget.enabled", True)
SECTOR_COMMAND_WARN_MS = _CONFIG.float("rebsgo.guardrails.sector-command-warn-ms", 100.0)
SECTOR_COMMAND_MAX_PLAYER_INPUT = _CONFIG.int("rebsgo.sector.command-queue.max-player-input-per-tick", 2048)
SECTOR_COMMAND_MAX_NORMAL = _CONFIG.int("rebsgo.sector.command-queue.max-normal-per-tick", 512)
SECTOR_NPC_AUTO_MAX_MS = _CONFIG.float("rebsgo.sector.npc-auto.max-ms-per-tick", 12.0)
SECTOR_NPC_AUTO_MAX_ITEMS = _CONFIG.int("rebsgo.sector.npc-auto.max-items-per-tick", 256)
SECTOR_NPC_TARGET_CACHE_TICKS = _CONFIG.int("rebsgo.sector.npc-target-cache-ticks", 10)
SECTOR_NPC_TARGET_PHASE_COUNT = _CONFIG.int("rebsgo.sector.npc-target-phase-count", 4)
SCHEDULED_TASK_WARN_MS = _CONFIG.float("rebsgo.guardrails.scheduled-task-warn-ms", 1000.0)
SENDER_SEND_WARN_MS = _CONFIG.float("rebsgo.guardrails.sender-send-warn-ms", 5000.0)
SENDER_QUEUE_WARN_SIZE = _CONFIG.int("rebsgo.guardrails.sender-queue-warn-size", 250)
SENDER_QUEUE_CRITICAL_SIZE = _CONFIG.int("rebsgo.guardrails.sender-queue-critical-size", 1000)
SENDER_QUEUE_WARN_INTERVAL_MS = _CONFIG.float("rebsgo.guardrails.sender-queue-warn-interval-ms", 5000.0)
SENDER_COALESCED_PACKET_WARN_COUNT = _CONFIG.int(
    "rebsgo.guardrails.sender-coalesced-packet-warn-count", 250)
SENDER_BATCH_ENABLED = _CONFIG.bool("rebsgo.sender.batch.enabled", True)
SENDER_MOVEMENT_COALESCING_ENABLED = _CONFIG.bool("rebsgo.sender.movement-coalescing.enabled", True)
SENDER_ENQUEUE_COALESCING_ENABLED = _CONFIG.bool("rebsgo.sender.enqueue-coalescing.enabled", True)
SENDER_PRIORITY_LANES_ENABLED = _CONFIG.bool("rebsgo.sender.priority-lanes.enabled", True)
SENDER_FLUSH_DRAIN_ENABLED = _CONFIG.bool("rebsgo.sender.flush-drain.enabled", True)
SENDER_FLUSH_DRAIN_MAX_ITEMS = _CONFIG.int("rebsgo.sender.flush-drain.max-items", 256)
SENDER_BROADCAST_PREFREEZE_ENABLED = _CONFIG.bool("rebsgo.sender.broadcast-prefreeze.enabled", True)
NATIVE_RUST_ENABLED = _CONFIG.bool("rebsgo.native.rust.enabled", True)
NATIVE_RUST_RADIUS_FILTER_ENABLED = _CONFIG.bool("rebsgo.native.rust.radius-filter.enabled", True)
NATIVE_RUST_RADIUS_FILTER_MIN_RECORDS = _CONFIG.int("rebsgo.native.rust.radius-filter.min-records", 32)
NATIVE_RUST_NEAREST_RADIUS_ENABLED = _CONFIG.bool("rebsgo.native.rust.nearest-radius.enabled", True)
NATIVE_RUST_NEAREST_RADIUS_MIN_RECORDS = _CONFIG.int(
    "rebsgo.native.rust.nearest-radius.min-records", NATIVE_RUST_RADIUS_FILTER_MIN_RECORDS)
NATIVE_RUST_OUT_OF_BOUNDS_ENABLED = _CONFIG.bool("rebsgo.native.rust.out-of-bounds.enabled", True)
NATIVE_RUST_OUT_OF_BOUNDS_MIN_RECORDS = _CONFIG.int("rebsgo.native.rust.out-of-bounds.min-records", 32)
NATIVE_RUST_SPATIAL_AABB_FILTER_ENABLED = _CONFIG.bool("rebsgo.native.rust.spatial-aabb-filter.enabled", True)
NATIVE_RUST_SPATIAL_PAIR_GENERATION_ENABLED = _CONFIG.bool(
    "rebsgo.native.rust.spatial-pair-generation.enabled", True)
NATIVE_RUST_SPATIAL_MIN_RECORDS = _CONFIG.int("rebsgo.native.rust.spatial.min-records", 32)
NATIVE_RUST_SPHERE_PAIR_FILTER_ENABLED = _CONFIG.bool("rebsgo.native.rust.sphere-pair-filter.enabled", True)
NATIVE_RUST_SPHERE_PAIR_FILTER_MIN_RECORDS = _CONFIG.int(
    "rebsgo.native.rust.sphere-pair-filter.min-records", 16)
NATIVE_RUST_RANGE_DISTANCE_ENABLED = _CONFIG.bool("rebsgo.native.rust.range-distance.enabled", True)
NATIVE_RUST_RANGE_DISTANCE_MIN_RECORDS = _CONFIG.int("rebsgo.native.rust.range-distance.min-records", 32)
NATIVE_RUST_FUTURE_POSITIONS_ENABLED = _CONFIG.bool("rebsgo.native.rust.future-positions.enabled", True)
NATIVE_RUST_FUTURE_POSITIONS_MIN_RECORDS = _CONFIG.int("rebsgo.native.rust.future-positions.min-records", 64)
NATIVE_RUST_PACKET_SERIALIZATION_ENABLED = _CONFIG.bool("rebsgo.native.rust.packet-serialization.enabled", True)
NATIVE_RUST_DIAGNOSTICS_ENABLED = _CONFIG.bool("rebsgo.native.rust.diagnostics.enabled", False)
NATIVE_RUST_DIAGNOSTICS_SAMPLE_INTERVAL = _CONFIG.int(
    "rebsgo.native.rust.diagnostics.sample-interval", 1000)
SENDER_QUEUE_AGE_WARN_MS = _CONFIG.float("rebsgo.guardrails.sender-queue-age-warn-ms", 100.0)
SENDER_DRAIN_WARN_ITEMS = _CONFIG.int("rebsgo.guardrails.sender-drain-warn-items", 512)
PLAYER_INPUT_WARN_MS = _CONFIG.float("rebsgo.guardrails.pilot-input-warn-ms", 100.0)
ABILITY_DIAGNOSTICS_ENABLED = _CONFIG.bool("rebsgo.guardrails.ability-diagnostics.enabled", ENABLED)
DB_PLAYER_FETCH_WARN_MS = _CONFIG.float("rebsgo.guardrails.db-player-fetch-warn-ms", 500.0)
DB_PLAYER_WRITE_WARN_MS = _CONFIG.float("rebsgo.guardrails.db-player-write-warn-ms", 750.0)
DB_BULK_WRITE_WARN_MS = _CONFIG.float("rebsgo.guardrails.db-bulk-write-warn-ms", 2000.0)
GAMEDATA_FILE_WARN_MS = _CONFIG.float("rebsgo.guardrails.gamedata-file-warn-ms", 200.0)
GAMEDATA_TOTAL_WARN_MS = _CONFIG.float("rebsgo.guardrails.gamedata-total-warn-ms", 1000.0)
GAMEDATA_CACHE_WARN_MS = _CONFIG.float("rebsgo.guardrails.gamedata-cache-warn-ms", 200.0)


def now_ms() -> float:
    return time.perf_counter() * 1000.0


def elapsed_ms(start_ms: float) -> float:
    return now_ms() - start_ms


def should_warn(elapsed: float, threshold_ms: float) -> bool:
    return ENABLED and threshold_ms > 0 and elapsed >= threshold_ms


def should_warn_count(count: int, threshold: int) -> bool:
    return ENABLED and threshold > 0 and count >= threshold


def should_warn_interval(last_warn_ms: float, interval_ms: float, current_ms: float | None = None) -> bool:
    if not ENABLED:
        return False
    if interval_ms <= 0:
        return True
    if current_ms is None:
        current_ms = now_ms()
    return current_ms - last_warn_ms >= interval_ms


def warn_if_slow(log, elapsed: float, threshold_ms: float, message: str, *args) -> None:
    if should_warn(elapsed, threshold_ms):
        log.warning(message + ' elapsed_ms=%.1f threshold_ms=%.1f',
                    *args, elapsed, threshold_ms)


class RollingLatencyStats:
    def __init__(self, sample_size: int | None = None):
        if sample_size is None:
            sample_size = SECTOR_HOTPATH_SUMMARY_SAMPLE_SIZE
        self._samples = deque(maxlen=max(1, int(sample_size)))
        self._total_count = 0

    def add(self, value: float) -> None:
        self._samples.append(float(value))
        self._total_count += 1

    def snapshot(self) -> dict:
        ertekek = list(self._samples)
        if not ertekek:
            return {
                "count": 0,
                "total_count": self._total_count,
                "avg_ms": 0.0,
                "max_ms": 0.0,
                "p95_ms": 0.0,
            }
        sorted_values = sorted(ertekek)
        p95_index = min(len(sorted_values) - 1, int((len(sorted_values) - 1) * 0.95))
        return {
            "count": len(ertekek),
            "total_count": self._total_count,
            "avg_ms": sum(ertekek) / len(ertekek),
            "max_ms": max(ertekek),
            "p95_ms": sorted_values[p95_index],
        }
