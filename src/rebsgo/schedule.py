# github.com/Shran21

from __future__ import annotations

import heapq
import itertools
import logging
import threading
import time

from rebsgo.helpers.rolling_latency_stats import SCHEDULED_TASK_WARN_MS, should_warn

log = logging.getLogger(__name__)


class _DelayLine:
    def __init__(self, name: str):
        self._name = name
        self._condition = threading.Condition()
        self._queue = []
        self._counter = itertools.count()
        self._thread = None
        self._closing = False
        self._drop_pending = False

    def enqueue(self, call) -> None:
        with self._condition:
            if self._closing:
                call.call_off()
                return
            heapq.heappush(self._queue, (call.deadline, next(self._counter), call))
            self._ensure_thread_locked()
            self._condition.notify()

    def nudge(self) -> None:
        with self._condition:
            self._condition.notify()

    def close(self, drop_pending: bool = False) -> None:
        with self._condition:
            self._closing = True
            self._drop_pending = self._drop_pending or drop_pending
            if drop_pending:
                for _deadline, _sequence, call in self._queue:
                    call.call_off()
            self._condition.notify_all()

    def wait_until_stopped(self, timeout_seconds: float) -> bool:
        thread = self._thread
        if thread is None:
            return True
        thread.join(max(0.0, timeout_seconds))
        return not thread.is_alive()

    def _ensure_thread_locked(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name=self._name, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while True:
            esedekes = None
            with self._condition:
                while True:
                    if self._drop_pending:
                        self._queue.clear()
                        return
                    if not self._queue:
                        if self._closing:
                            return
                        self._condition.wait()
                        continue
                    deadline, _sequence, jelolt = self._queue[0]
                    if jelolt.called_off:
                        heapq.heappop(self._queue)
                        continue
                    most = time.monotonic()
                    varakozas = deadline - most
                    if varakozas > 0:
                        self._condition.wait(varakozas)
                        continue
                    heapq.heappop(self._queue)
                    esedekes = jelolt
                    break
            if esedekes is not None:
                try:
                    esedekes.fire_if_due()
                except Exception:
                    log.exception("Delayed call raised")


_SHARED_DELAY_LINE = _DelayLine("delay-line")


class TimedCall:
    def __init__(self, seconds: float, fire, line: _DelayLine | None = None):
        self._deadline = time.monotonic() + max(0.0, seconds)
        self._fire = fire
        self._line = line or _SHARED_DELAY_LINE
        self._called_off = False
        self._fired = False
        self._firing = False
        self._queued = False
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self._queued:
                return
            self._queued = True
        self._line.enqueue(self)

    @property
    def deadline(self) -> float:
        return self._deadline

    def fire_if_due(self) -> None:
        with self._lock:
            if self._called_off or self._fired:
                return
            self._firing = True
        try:
            self._fire()
        finally:
            with self._lock:
                self._firing = False
                self._fired = True

    def call_off(self) -> bool:
        with self._lock:
            if self._fired or self._firing:
                return False
            elozoleg = self._called_off
            self._called_off = True
        self._line.nudge()
        return not elozoleg

    @property
    def called_off(self) -> bool:
        with self._lock:
            return self._called_off

    @property
    def settled(self) -> bool:
        with self._lock:
            return self._fired or self._called_off


class RecurringCall:
    def __init__(self, task_name: str, thread: threading.Thread, stop_event: threading.Event):
        self._task_name = task_name
        self._thread = thread
        self._stop_event = stop_event
        self._called_off = False

    def call_off(self) -> bool:
        if self.settled:
            return False
        elozoleg = self._called_off
        self._called_off = True
        self._stop_event.set()
        return not elozoleg

    @property
    def called_off(self) -> bool:
        return self._called_off

    @property
    def settled(self) -> bool:
        return not self._thread.is_alive()

    def join(self, timeout: float | None = None) -> None:
        self._thread.join(timeout)

    def name(self) -> str:
        return self._task_name


class Schedule:
    def __init__(self):
        self._delay_line = _DelayLine("delay-line-svc")
        self._recurring = []
        self._lock = threading.Lock()
        self._closing = False

    def every(self, period_seconds: float, fn, first_delay_seconds: float = 0.0,
              name: str | None = None) -> RecurringCall:
        task_name = name or getattr(fn, "__name__", "recurring")
        stop_event = threading.Event()

        def _loop():
            if first_delay_seconds > 0 and stop_event.wait(first_delay_seconds):
                return
            while not stop_event.is_set():
                kezdet = time.monotonic()
                try:
                    fn()
                except Exception:
                    log.exception("Recurring call %s raised", task_name)
                eltelt = time.monotonic() - kezdet
                eltelt_ms = eltelt * 1000.0
                if should_warn(eltelt_ms, period_seconds * 1000.0):
                    log.warning("Recurring call %s overran period elapsed_ms=%.1f period_ms=%.1f",
                                task_name, eltelt_ms, period_seconds * 1000.0)
                elif should_warn(eltelt_ms, SCHEDULED_TASK_WARN_MS):
                    log.warning("Recurring call %s slow elapsed_ms=%.1f threshold_ms=%.1f",
                                task_name, eltelt_ms, SCHEDULED_TASK_WARN_MS)
                stop_event.wait(max(0.0, period_seconds - eltelt))

        thread = threading.Thread(target=_loop, name="recurring-" + task_name, daemon=True)
        handle = RecurringCall(task_name, thread, stop_event)
        with self._lock:
            if self._closing:
                handle.call_off()
                return handle
            self._recurring.append(handle)
        thread.start()
        return handle

    def after(self, seconds: float, fn) -> TimedCall:
        def _fire():
            try:
                fn()
            except Exception:
                log.exception("Timed call raised")

        call = TimedCall(seconds, _fire, self._delay_line)
        call.start()
        return call

    def shutdown(self) -> None:
        with self._lock:
            self._closing = True
            handles = list(self._recurring)
        for handle in handles:
            handle.call_off()
        self._delay_line.close(drop_pending=False)

    def halt(self) -> None:
        with self._lock:
            self._closing = True
            handles = list(self._recurring)
        for handle in handles:
            handle.call_off()
        self._delay_line.close(drop_pending=True)

    def wait_until_stopped(self, timeout_seconds: float) -> bool:
        deadline = time.monotonic() + max(0.0, float(timeout_seconds))
        with self._lock:
            handles = list(self._recurring)
        for handle in handles:
            hatralevo = max(0.0, deadline - time.monotonic())
            handle.join(hatralevo)
        hatralevo = max(0.0, deadline - time.monotonic())
        line_done = self._delay_line.wait_until_stopped(hatralevo)
        return line_done and all(handle.settled for handle in handles)
