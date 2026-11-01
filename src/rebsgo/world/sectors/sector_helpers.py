# github.com/Shran21
from __future__ import annotations

import logging
import os
import queue
import threading
import time

from rebsgo.config.config import Config
from rebsgo.helpers.thread_structs import own_converters

log = logging.getLogger(__name__)
_CONFIG = Config.instance()

# A sector runs on one thread, so a crowded sector is capped at one core however
# many the machine has. Its heavy, per-object phases (movement, collision tests)
# are split here into small contiguous pieces, which the sector thread and the
# sector's own helper threads take one by one; the sector thread waits for the
# last of them before anything reads the results. What changes shared state
# (removals, damage, sending) stays on the sector thread, in the same order as
# before.
# A piece no helper has taken yet the sector thread takes itself, so a helper the
# system leaves waiting for a core (a busy machine) cannot hold the sector up: at
# worst the sector does all of it alone, as it did before.
# Splitting has a price, so only a sector whose ticks stay heavy does it: from a
# tick time of busy-tick-ms on (a slow moving average, spikes cut), until it falls
# well below. And when waiting for helpers the system put aside costs the sector
# more than the helpers save it, the sector works alone for a while.
ENABLED = _CONFIG.bool("rebsgo.sector.parallel.enabled", True)
_HELPERS = _CONFIG.int("rebsgo.sector.parallel.helpers", 0)
_MIN_CHUNK = max(1, _CONFIG.int("rebsgo.sector.parallel.min-chunk", 24))
_BUSY_TICK_MS = max(0.0, _CONFIG.float("rebsgo.sector.parallel.busy-tick-ms", 20.0))
_CALM_SHARE = 0.4
_SPIKE_CAP = 3.0
_LOAD_WEIGHT = 0.02
_PIECES_PER_THREAD = 3
_IDLE_STOP_SECONDS = 300.0
_GAIN_WEIGHT = 0.05
_SETTLE_SECONDS = 2.0
_LOSS_SHARE = 0.5
_LOSS_FLOOR = 0.002
_ALONE_SECONDS = 60.0
_ALONE_MAX_SECONDS = 960.0
_FORGIVE_SECONDS = 300.0
_SLOW_WAIT_SECONDS = 10.0
# A tick's phases split one after the other, a fraction of a millisecond apart:
# a helper that has just finished looks this long for the next split before it
# sleeps. The sector thread does not sleep on the pieces still running at all,
# up to _WATCH_SECONDS: it watches them, giving way to others - a thread woken
# from sleep can wait for a core for milliseconds (power saving), and the whole
# sector waits with it.
_SPIN_SECONDS = 0.0001
_WATCH_SECONDS = 0.02


def _auto_size() -> int:
    cores = (os.process_cpu_count() if hasattr(os, "process_cpu_count") else None) or os.cpu_count() or 1
    # one core stays for the rest of the server: a helper sharing a core with a busy
    # thread gets put aside by the system, and the sector waits for it
    return max(0, min(3, cores - 2))


class _Piece:
    # Each piece has its own claim, flag and event: one counter shared by all
    # would make the threads queue up for its lock just as they all finish.
    __slots__ = ("work", "chunk", "result", "error", "done", "finished", "took", "_claim")

    def __init__(self, work, chunk):
        self.work = work
        self.chunk = chunk
        self.result = None
        self.error = None
        self.done = False
        self.finished = threading.Event()
        self.took = 0.0
        self._claim = threading.Lock()

    def take(self) -> bool:
        return self._claim.acquire(blocking=False)

    def run(self) -> None:
        started = time.perf_counter()
        try:
            self.result = self.work(self.chunk)
        except Exception as baj:
            self.error = baj
        finally:
            self.took = time.perf_counter() - started
            self.done = True
            self.finished.set()


def _take_and_run(pieces, start: int) -> int:
    ran = 0
    for index in range(len(pieces)):
        piece = pieces[(start + index) % len(pieces)]
        if piece.take():
            piece.run()
            ran += 1
    return ran


class SectorHelper(threading.Thread):
    def __init__(self, pool: "SectorHelpers", number: int):
        super().__init__(name=f"sector [{pool.sector_id}] helper-{number}", daemon=True)
        self._pool = pool
        self.jobs = queue.SimpleQueue()
        # written by this thread only; the panel copies them
        self.cpu_by_phase: dict[str, float] = {}

    def run(self) -> None:
        own_converters()
        job = self.jobs.get()
        while job is not None:
            phase, pieces, start = job
            started = time.thread_time()
            if _take_and_run(pieces, start):
                self.cpu_by_phase[phase] = self.cpu_by_phase.get(phase, 0.0) + time.thread_time() - started
            job = self._next_job()

    def _next_job(self):
        until = time.perf_counter() + _SPIN_SECONDS
        while self.jobs.empty() and time.perf_counter() < until:
            pass
        return self.jobs.get()

    def panel_info(self) -> dict:
        parent = self._pool.parent
        return {"role": "helper", "sector": self._pool.sector_id,
                "parent_tid": parent.native_id if parent is not None else None,
                "phases": {phase: round(spent, 3) for phase, spent in dict(self.cpu_by_phase).items()}}


class SectorHelpers:
    """The helper threads of one sector. Only the sector thread calls it.

    Helpers start the first time a heavy sector splits a phase, and stop after a
    few idle minutes, so a quiet sector has none."""

    def __init__(self, sector_id, size: int | None = None):
        self.sector_id = sector_id
        self.parent = None
        self._size = (_HELPERS if _HELPERS > 0 else _auto_size()) if size is None else max(0, size)
        self._helpers: list[SectorHelper] = []
        self._last_used = 0.0
        self._engaged = False
        self._load_ms = 0.0
        self._tick_started = None
        self._gain = 0.0
        self._loss = 0.0
        self._lost_this_tick = 0.0
        self._alone_until = 0.0
        self._alone_seconds = _ALONE_SECONDS
        self._engaged_since = 0.0
        self._helped_this_tick = 0.0

    def bind_parent(self, thread) -> None:
        self.parent = thread

    def tick_begins(self) -> None:
        self._tick_started = time.perf_counter()

    def tick_done(self) -> None:
        if self._tick_started is None:
            return
        # what the tick would have taken alone: its own time and what the helpers did
        helped, lost = self._helped_this_tick, self._lost_this_tick
        work_ms = min((time.perf_counter() - self._tick_started + helped) * 1000.0, _BUSY_TICK_MS * _SPIKE_CAP)
        self._tick_started = None
        self._helped_this_tick = self._lost_this_tick = 0.0
        self._load_ms += (work_ms - self._load_ms) * _LOAD_WEIGHT
        if not ENABLED or self._size <= 0:
            return
        if self._engaged:
            self._weigh_helpers(helped, lost)
        if self._engaged:
            if self._load_ms < _BUSY_TICK_MS * _CALM_SHARE:
                self._engaged = False
                log.info("Sector[%s] ticks are light again (%.1f ms): it stops splitting its phases",
                         self.sector_id, self._load_ms)
        elif self._load_ms > _BUSY_TICK_MS and time.monotonic() >= self._alone_until:
            self._engaged = True
            self._engaged_since = time.monotonic()
            self._gain = self._loss = 0.0
            log.info("Sector[%s] ticks are heavy (%.1f ms): it splits its phases among up to %s helper threads",
                     self.sector_id, self._load_ms, self._size)
        self.rest_if_idle()

    def pieces_for(self, count: int) -> int:
        """How many threads a phase of count items is worth (1: the sector thread alone)."""
        if not self._engaged or not ENABLED or self._size <= 0:
            return 1
        return max(1, min(self._size + 1, count // _MIN_CHUNK))

    def split(self, phase: str, work, items) -> list:
        """work(chunk) over contiguous pieces of items, the results in the items' order.

        Every piece finishes before the first error, if any, is raised."""
        threads = self.pieces_for(len(items))
        if threads > 1:
            threads = self._ensure(threads - 1) + 1
        if threads <= 1:
            return [work(items)]
        count = max(threads, min(threads * _PIECES_PER_THREAD, len(items) * _PIECES_PER_THREAD // _MIN_CHUNK))
        szelek = [len(items) * i // count for i in range(count + 1)]
        pieces = [_Piece(work, items[szelek[i]:szelek[i + 1]]) for i in range(count)]
        for number, helper in enumerate(self._helpers[:threads - 1], 1):
            helper.jobs.put((phase, pieces, count * number // threads))
        started = time.perf_counter()
        own_pieces = _take_and_run(pieces, 0)
        own_done = time.perf_counter()
        self._wait(pieces)
        own = own_done - started
        self._helped_this_tick += max(0.0, sum(piece.took for piece in pieces) - own)
        self._note_wait(time.perf_counter() - own_done, own / max(1, own_pieces))
        self._last_used = time.monotonic()
        for piece in pieces:
            if piece.error is not None:
                raise piece.error
        return [piece.result for piece in pieces]

    def _wait(self, pieces) -> None:
        # every piece is taken by now; some may still be running on a helper
        until = time.perf_counter() + _WATCH_SECONDS
        while not all(piece.done for piece in pieces):
            if time.perf_counter() > until:
                break
            time.sleep(0)
        else:
            return
        started = time.monotonic()
        for piece in pieces:
            while not piece.finished.wait(_SLOW_WAIT_SECONDS):
                log.warning("Sector[%s] still waiting for its helpers: waited_s=%.0f",
                            self.sector_id, time.monotonic() - started)

    def _note_wait(self, waited: float, piece_time: float) -> None:
        # lost: the sector thread, done with what it could take, waited for the rest
        # longer than a piece or two takes - a helper the system put aside mid-piece
        self._lost_this_tick += max(0.0, waited - 2.0 * piece_time)

    def _weigh_helpers(self, helped: float, lost: float) -> None:
        self._gain += (helped - self._gain) * _GAIN_WEIGHT
        self._loss += (lost - self._loss) * _GAIN_WEIGHT
        most = time.monotonic()
        if (most - self._engaged_since < _SETTLE_SECONDS or self._loss < _LOSS_FLOOR
                or self._loss < self._gain * _LOSS_SHARE):
            return
        if most - self._engaged_since > _FORGIVE_SECONDS:
            self._alone_seconds = _ALONE_SECONDS
        self._engaged = False
        self._alone_until = most + self._alone_seconds
        log.warning("Sector[%s] waiting for its helpers costs more than they save (%.1f ms vs %.1f ms a tick; "
                    "the system gives them a core late): it works alone for %.0f s",
                    self.sector_id, self._loss * 1000, self._gain * 1000, self._alone_seconds)
        self._alone_seconds = min(self._alone_seconds * 2.0, _ALONE_MAX_SECONDS)

    def _ensure(self, needed: int) -> int:
        while len(self._helpers) < needed:
            helper = SectorHelper(self, len(self._helpers) + 1)
            try:
                helper.start()
            except RuntimeError:
                log.exception("Sector[%s] could not start a helper thread; it carries on with %s",
                              self.sector_id, len(self._helpers))
                break
            self._helpers.append(helper)
        return min(needed, len(self._helpers))

    def rest_if_idle(self) -> None:
        if self._helpers and time.monotonic() - self._last_used > _IDLE_STOP_SECONDS:
            log.info("Sector[%s] stops its %s idle helper threads", self.sector_id, len(self._helpers))
            self.close()

    def close(self) -> None:
        helpers, self._helpers = self._helpers, []
        for helper in helpers:
            helper.jobs.put(None)
