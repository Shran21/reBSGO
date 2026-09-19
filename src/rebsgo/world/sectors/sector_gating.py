# github.com/Shran21

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass

from rebsgo.config.config import Config
from rebsgo.helpers.rolling_latency_stats import now_ms

log = logging.getLogger(__name__)

MODE_OFF = "off"
MODE_EMPTY = "empty"
MODE_IDLE = "idle"
MODE_ADAPTIVE = "adaptive"

STATE_ACTIVE = "active"
STATE_EMPTY = "empty"
STATE_IDLE = "idle"
STATE_DEEP_IDLE = "deep_idle"

TIMER_MODE_FULL = "full"
TIMER_MODE_IDLE = "idle"
TIMER_MODE_MAINTENANCE = "maintenance"

ADAPTIVE_NORMAL = "normal"
ADAPTIVE_CONSERVE = "conserve"
ADAPTIVE_SHED = "shed"

_BOOL_TRUE = {"true", "1", "yes", "y", "on"}
_BOOL_FALSE = {"false", "0", "no", "n", "off"}


@dataclass(frozen=True)
class SectorGatingConfig:
    mode: str
    idle_after_ms: float
    deep_idle_after_ms: float
    deep_idle_tick_ms: float
    adaptive_load_high: float
    adaptive_load_shed: float
    adaptive_load_low: float
    adaptive_min_state_ms: float
    adaptive_poll_ms: float
    excluded_sector_ids: frozenset[int]
    log_transitions: bool

    @staticmethod
    def load() -> "SectorGatingConfig":
        config = Config.instance()
        legacy_empty_enabled = config.bool("rebsgo.sector.empty-gating", False)
        mode = _normalise_mode(config.string("rebsgo.sector.gating.mode", None), legacy_empty_enabled)
        idle_after_seconds = max(0, config.int("rebsgo.sector.gating.idle-after-seconds", 120))
        deep_idle_after_seconds = max(
            idle_after_seconds,
            config.int("rebsgo.sector.gating.deep-idle-after-seconds", 600),
        )
        return SectorGatingConfig(
            mode=mode,
            idle_after_ms=float(idle_after_seconds * 1000),
            deep_idle_after_ms=float(deep_idle_after_seconds * 1000),
            deep_idle_tick_ms=float(max(100, config.int("rebsgo.sector.gating.deep-idle-tick-ms", 1000))),
            adaptive_load_high=max(0.0, config.float("rebsgo.sector.gating.adaptive.load-high", 0.75)),
            adaptive_load_shed=max(0.0, config.float("rebsgo.sector.gating.adaptive.load-shed", 0.90)),
            adaptive_load_low=max(0.0, config.float("rebsgo.sector.gating.adaptive.load-low", 0.45)),
            adaptive_min_state_ms=float(max(
                0,
                config.int("rebsgo.sector.gating.adaptive.min-state-seconds", 120),
            ) * 1000),
            adaptive_poll_ms=float(max(
                1000,
                config.int("rebsgo.sector.gating.adaptive.poll-ms", 5000),
            )),
            excluded_sector_ids=frozenset(config.set_long("rebsgo.sector.gating.excluded-sector-ids")),
            log_transitions=config.bool("rebsgo.sector.gating.log-transitions", False),
        )


@dataclass(frozen=True)
class SectorGatingDecision:
    state: str
    timer_mode: str
    skip_simulation: bool
    deep_sleep: bool
    adaptive_level: str
    load_ratio: float
    idle_ms: float
    pending_work: bool

    @staticmethod
    def off() -> "SectorGatingDecision":
        return SectorGatingDecision(
            state=STATE_ACTIVE,
            timer_mode=TIMER_MODE_FULL,
            skip_simulation=False,
            deep_sleep=False,
            adaptive_level=ADAPTIVE_NORMAL,
            load_ratio=0.0,
            idle_ms=0.0,
            pending_work=False,
        )


class AdaptiveSectorLoad:
    _lock = threading.Lock()
    _last_poll_ms = 0.0
    _load_ratio = 0.0
    _state = ADAPTIVE_NORMAL
    _state_since_ms = 0.0

    @classmethod
    def current_state(cls, config: SectorGatingConfig, current_ms: float) -> tuple[str, float]:
        with cls._lock:
            if cls._state_since_ms <= 0:
                cls._state_since_ms = current_ms
            if current_ms - cls._last_poll_ms >= config.adaptive_poll_ms:
                cls._last_poll_ms = current_ms
                cls._load_ratio = _read_load_ratio()
                target_state = cls._target_state(config, cls._state, cls._load_ratio)
                if target_state != cls._state and current_ms - cls._state_since_ms >= config.adaptive_min_state_ms:
                    log.info(
                        "Adaptive sector gating load state changed %s -> %s load_ratio=%.2f",
                        cls._state,
                        target_state,
                        cls._load_ratio,
                    )
                    cls._state = target_state
                    cls._state_since_ms = current_ms
            return cls._state, cls._load_ratio

    @staticmethod
    def _target_state(config: SectorGatingConfig, current_state: str, load_ratio: float) -> str:
        if load_ratio >= config.adaptive_load_shed:
            return ADAPTIVE_SHED
        if load_ratio >= config.adaptive_load_high:
            return ADAPTIVE_CONSERVE
        if load_ratio <= config.adaptive_load_low:
            return ADAPTIVE_NORMAL
        return current_state


class SectorGating:
    def __init__(self, sector_id: int, config: SectorGatingConfig | None = None):
        self._sector_id = sector_id
        self._config = SectorGatingConfig.load() if config is None else config
        self._wake_event = threading.Event()
        self._empty_since_ms = now_ms()
        self._last_transition_key = None

    def wake(self, reason: str = "wake") -> None:
        self._wake_event.set()
        if self._config.log_transitions:
            log.debug("Sector[%s] gating wake reason=%s", self._sector_id, reason)

    def wait_deep_idle(self) -> None:
        self._wake_event.wait(self._config.deep_idle_tick_ms / 1000.0)
        self._wake_event.clear()

    def evaluate(self, users_empty: bool, pending_work: bool = False) -> SectorGatingDecision:
        current_ms = now_ms()
        decision = self._evaluate_at(current_ms, users_empty, pending_work)
        self._log_transition(decision)
        return decision

    def _evaluate_at(self, current_ms: float, users_empty: bool, pending_work: bool) -> SectorGatingDecision:
        config = self._config
        if config.mode == MODE_OFF or self._sector_id in config.excluded_sector_ids:
            self._empty_since_ms = current_ms if users_empty else 0.0
            return SectorGatingDecision.off()

        if not users_empty:
            self._empty_since_ms = 0.0
            return SectorGatingDecision.off()

        if self._empty_since_ms <= 0:
            self._empty_since_ms = current_ms
        idle_ms = current_ms - self._empty_since_ms

        adaptive_level = ADAPTIVE_NORMAL
        load_ratio = 0.0
        if config.mode == MODE_ADAPTIVE:
            adaptive_level, load_ratio = AdaptiveSectorLoad.current_state(config, current_ms)

        skip_simulation = config.mode in (MODE_EMPTY, MODE_IDLE, MODE_ADAPTIVE)
        allapot = STATE_EMPTY
        timer_mode = TIMER_MODE_FULL
        deep_sleep = False

        idle_allowed = config.mode in (MODE_IDLE, MODE_ADAPTIVE)
        deep_idle_allowed = config.mode == MODE_IDLE or (
            config.mode == MODE_ADAPTIVE and adaptive_level == ADAPTIVE_SHED
        )

        if idle_allowed and idle_ms >= config.idle_after_ms:
            allapot = STATE_IDLE
            timer_mode = TIMER_MODE_IDLE

        if deep_idle_allowed and idle_ms >= config.deep_idle_after_ms and not pending_work:
            allapot = STATE_DEEP_IDLE
            timer_mode = TIMER_MODE_MAINTENANCE
            deep_sleep = True

        return SectorGatingDecision(
            state=allapot,
            timer_mode=timer_mode,
            skip_simulation=skip_simulation,
            deep_sleep=deep_sleep,
            adaptive_level=adaptive_level,
            load_ratio=load_ratio,
            idle_ms=idle_ms,
            pending_work=pending_work,
        )

    def _log_transition(self, decision: SectorGatingDecision) -> None:
        if not self._config.log_transitions:
            return
        transition_key = (
            decision.state,
            decision.timer_mode,
            decision.skip_simulation,
            decision.deep_sleep,
            decision.adaptive_level,
            decision.pending_work,
        )
        if transition_key == self._last_transition_key:
            return
        self._last_transition_key = transition_key
        log.info(
            "Sector[%s] gating state=%s timer_mode=%s skip_simulation=%s deep_sleep=%s "
            "adaptive=%s load_ratio=%.2f idle_ms=%.0f pending_work=%s",
            self._sector_id,
            decision.state,
            decision.timer_mode,
            decision.skip_simulation,
            decision.deep_sleep,
            decision.adaptive_level,
            decision.load_ratio,
            decision.idle_ms,
            decision.pending_work,
        )


_MOD_SZAVAK = {
    **{szo: szo for szo in (MODE_OFF, MODE_EMPTY, MODE_IDLE, MODE_ADAPTIVE)},
    **{szo: MODE_OFF for szo in _BOOL_FALSE},
    **{szo: MODE_EMPTY for szo in _BOOL_TRUE},
}


def _normalise_mode(raw_mode: str | None, legacy_empty_enabled: bool) -> str:
    alapertelmezes = MODE_EMPTY if legacy_empty_enabled else MODE_OFF
    szo = (raw_mode or "").strip().lower()
    if szo == "":
        return alapertelmezes
    if szo in _MOD_SZAVAK:
        return _MOD_SZAVAK[szo]
    log.warning("Unknown sector gating mode=%s; falling back to legacy empty-gating=%s",
                raw_mode, legacy_empty_enabled)
    return alapertelmezes


def _read_load_ratio() -> float:
    try:
        load_1m = os.getloadavg()[0]
    except (AttributeError, OSError):
        return 0.0
    cpu_count = os.cpu_count() or 1
    return max(0.0, load_1m / float(cpu_count))
