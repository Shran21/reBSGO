# github.com/Shran21
from __future__ import annotations

from contextlib import suppress

import logging
import queue
import threading
from dataclasses import dataclass, field
from itertools import count

from rebsgo.wire.bytes.wire_out import WireOut
from rebsgo.helpers.rolling_latency_stats import (
    ENABLED as GUARDRAILS_ENABLED,
    SENDER_BATCH_ENABLED,
    SENDER_COALESCED_PACKET_WARN_COUNT,
    SENDER_DRAIN_WARN_ITEMS,
    SENDER_ENQUEUE_COALESCING_ENABLED,
    SENDER_FLUSH_DRAIN_ENABLED,
    SENDER_FLUSH_DRAIN_MAX_ITEMS,
    SENDER_MOVEMENT_COALESCING_ENABLED,
    SENDER_PRIORITY_LANES_ENABLED,
    SENDER_QUEUE_AGE_WARN_MS,
    SENDER_QUEUE_CRITICAL_SIZE,
    SENDER_QUEUE_WARN_INTERVAL_MS,
    SENDER_QUEUE_WARN_SIZE,
    SENDER_SEND_WARN_MS,
    elapsed_ms,
    now_ms,
    should_warn,
    should_warn_count,
)

log = logging.getLogger(__name__)

PRIORITY_CRITICAL = 0
PRIORITY_INTERACTIVE = 1
PRIORITY_SNAPSHOT = 2


@dataclass(order=True)
class _QueueEntry:
    priority: int
    sequence: int
    envelope: object = field(compare=False)


@dataclass(frozen=True)
class _QueuedItem:
    item: object
    enqueue_ms: float


@dataclass(frozen=True)
class _CoalescedPacketSlot:
    key: object


class _PacketBatch:
    def __init__(self, packets):
        self._packets = tuple(packet for packet in packets if packet is not None)

    def __len__(self) -> int:
        return len(self._packets)

    def write_to(self, kimenet, should_write_packet=None) -> int:
        written = 0
        for packet in self._packets:
            if should_write_packet is not None and not should_write_packet(packet):
                continue
            packet.write_to(kimenet)
            written += 1
        return written

    @property
    def packets(self):
        return self._packets

    def priority(self) -> int:
        if not self._packets:
            return PRIORITY_CRITICAL
        return min(_packet_priority(packet) for packet in self._packets)


class QueuedOutbox:
    def __init__(self, kimenet):
        self._output_stream = kimenet
        self._bws = queue.PriorityQueue()
        self._sequence = count()
        self._send_failed = False
        self._shutdown_sender = False
        self._last_queue_warn_ms = 0.0
        self._last_queue_critical_warn_ms = 0.0
        self._last_queue_age_warn_ms = 0.0
        self._last_drain_warn_ms = 0.0
        self._last_coalesced_warn_ms = 0.0
        self._coalesced_packets_since_warn = 0
        self._coalescing_lock = threading.Lock()
        self._latest_coalescable_by_key = {}
        self._pending_coalescable_by_key = {}
        self._thread = None
        self._start()

    def _start(self) -> None:
        log.info("Start QueuedOutbox")

        def _run():
            try:
                while not self._shutdown_sender:
                    try:
                        bejegyzes = self._bws.get(timeout=5)
                    except queue.Empty:
                        continue
                    if bejegyzes is None or bejegyzes.envelope is None:
                        continue

                    kezdet = now_ms() if GUARDRAILS_ENABLED else 0.0
                    packets_written, items_drained, max_queue_age_ms = self._write_ready_items(bejegyzes)
                    if packets_written <= 0:
                        continue
                    self._output_stream.flush()
                    if GUARDRAILS_ENABLED:
                        elapsed = elapsed_ms(kezdet)
                        if should_warn(elapsed, SENDER_SEND_WARN_MS):
                            log.warning(
                                "Slow send call elapsed_ms=%.1f threshold_ms=%.1f queue_depth=%s packets=%s "
                                "drained_items=%s max_queue_age_ms=%.1f",
                                elapsed,
                                SENDER_SEND_WARN_MS,
                                self._safe_qsize(),
                                packets_written,
                                items_drained,
                                max_queue_age_ms,
                            )
                        self._warn_if_queue_age_high(max_queue_age_ms)
                        self._warn_if_drain_large(items_drained)
            except (OSError, BrokenPipeError):
                self._send_failed = True
            except Exception as e:
                log.error('the sender thread fell over', exc_info=e)

        thread = threading.Thread(target=_run, name="QueuedOutbox", daemon=True)
        self._thread = thread
        thread.start()

    def send(self, kimenet) -> bool:
        if isinstance(kimenet, WireOut):
            return self._send_single(kimenet)
        packets = tuple(packet for packet in kimenet if packet is not None)
        if not packets:
            return True
        if SENDER_BATCH_ENABLED:
            return self._send_packet_collection(packets)
        for packet in packets:
            if not self._send_single(packet):
                return False
        return True

    def _send_packet_collection(self, packets) -> bool:
        if not SENDER_ENQUEUE_COALESCING_ENABLED or not SENDER_MOVEMENT_COALESCING_ENABLED:
            return self._send_single(_PacketBatch(packets))

        reliable_segment = []
        for packet in packets:
            if self._coalesce_key(packet) is None:
                reliable_segment.append(packet)
                continue
            if reliable_segment:
                if not self._send_single(_PacketBatch(reliable_segment)):
                    return False
                reliable_segment = []
            if not self._send_coalescable_packet(packet):
                return False
        if reliable_segment:
            return self._send_single(_PacketBatch(reliable_segment))
        return True

    def _send_single(self, bw) -> bool:
        if (SENDER_ENQUEUE_COALESCING_ENABLED
            and SENDER_MOVEMENT_COALESCING_ENABLED
            and self._coalesce_key(bw) is not None):
            return self._send_coalescable_packet(bw)
        if self._send_failed or self._shutdown_sender:
            return False
        try:
            if not SENDER_ENQUEUE_COALESCING_ENABLED:
                self._track_coalescable_packets(bw)
            self._put_queued_item(bw, self._item_priority(bw))
            self._warn_if_queue_large()
        except queue.Full:
            log.error('enqueueing failed')
            return False
        return True

    def _send_coalescable_packet(self, packet) -> bool:
        kulcs = self._coalesce_key(packet)
        if kulcs is None or not SENDER_ENQUEUE_COALESCING_ENABLED or not SENDER_MOVEMENT_COALESCING_ENABLED:
            return self._send_single(packet)
        if self._send_failed or self._shutdown_sender:
            return False

        should_enqueue_slot = False
        with self._coalescing_lock:
            if kulcs not in self._pending_coalescable_by_key:
                should_enqueue_slot = True
            else:
                self._record_coalesced_skip()
            self._pending_coalescable_by_key[kulcs] = packet

        if not should_enqueue_slot:
            self._warn_if_queue_large()
            return True

        try:
            self._put_queued_item(_CoalescedPacketSlot(kulcs), PRIORITY_SNAPSHOT)
            self._warn_if_queue_large()
        except queue.Full:
            with self._coalescing_lock:
                if self._pending_coalescable_by_key.get(kulcs) is packet:
                    self._pending_coalescable_by_key.pop(kulcs, None)
            log.error('enqueueing failed')
            return False
        return True

    def _put_queued_item(self, item, priority: int) -> None:
        if not SENDER_PRIORITY_LANES_ENABLED:
            priority = PRIORITY_INTERACTIVE
        enqueue_ms = now_ms() if GUARDRAILS_ENABLED else 0.0
        self._bws.put_nowait(_QueueEntry(priority, next(self._sequence), _QueuedItem(item, enqueue_ms)))

    def shutdown(self) -> None:
        self._shutdown_sender = True
        with suppress(queue.Full):
            self._bws.put_nowait(_QueueEntry(PRIORITY_CRITICAL, next(self._sequence), None))

    def wait_until_stopped(self, timeout_seconds: float = 1.0) -> bool:
        thread = self._thread
        if thread is None:
            return True
        thread.join(max(0.0, timeout_seconds))
        return not thread.is_alive()

    def _safe_qsize(self) -> int:
        try:
            return self._bws.qsize()
        except NotImplementedError:
            return -1

    def _warn_if_queue_large(self) -> None:
        if not GUARDRAILS_ENABLED:
            return
        melyseg = self._safe_qsize()
        if melyseg < SENDER_QUEUE_WARN_SIZE:
            return
        most = now_ms()
        if (SENDER_QUEUE_CRITICAL_SIZE > 0
            and melyseg >= SENDER_QUEUE_CRITICAL_SIZE
            and most - self._last_queue_critical_warn_ms >= SENDER_QUEUE_WARN_INTERVAL_MS):
            self._last_queue_critical_warn_ms = most
            log.warning(
                "Sender queue depth is critical queue_depth=%s threshold=%s warn_threshold=%s",
                melyseg,
                SENDER_QUEUE_CRITICAL_SIZE,
                SENDER_QUEUE_WARN_SIZE,
            )
            return
        if most - self._last_queue_warn_ms < SENDER_QUEUE_WARN_INTERVAL_MS:
            return
        self._last_queue_warn_ms = most
        log.warning("Sender queue depth is high queue_depth=%s threshold=%s", melyseg, SENDER_QUEUE_WARN_SIZE)

    @staticmethod
    def _packet_count(item) -> int:
        if isinstance(item, _QueuedItem):
            return QueuedOutbox._packet_count(item.item)
        if isinstance(item, _CoalescedPacketSlot):
            return 1
        if isinstance(item, _PacketBatch):
            return len(item)
        return 1

    def _write_ready_items(self, first_entry: _QueueEntry) -> tuple[int, int, float]:
        bejegyzesek = [first_entry]
        if SENDER_FLUSH_DRAIN_ENABLED:
            max_items = max(1, SENDER_FLUSH_DRAIN_MAX_ITEMS)
            while len(bejegyzesek) < max_items:
                try:
                    bejegyzes = self._bws.get_nowait()
                except queue.Empty:
                    break
                if bejegyzes is not None:
                    bejegyzesek.append(bejegyzes)

        packets_written = 0
        max_queue_age_ms = 0.0
        for bejegyzes in bejegyzesek:
            envelope = bejegyzes.envelope
            if envelope is None:
                continue
            if isinstance(envelope, _QueuedItem) and GUARDRAILS_ENABLED:
                max_queue_age_ms = max(max_queue_age_ms, elapsed_ms(envelope.enqueue_ms))
            packets_written += self._write_envelope(envelope)
        return packets_written, len(bejegyzesek), max_queue_age_ms

    def _write_envelope(self, envelope) -> int:
        if isinstance(envelope, _QueuedItem):
            return self._write_item(envelope.item)
        return self._write_item(envelope)

    def _write_item(self, item) -> int:
        if isinstance(item, _QueuedItem):
            return self._write_item(item.item)
        if isinstance(item, _CoalescedPacketSlot):
            packet = self._pop_coalesced_packet(item.key)
            if packet is None:
                return 0
            packet.write_to(self._output_stream)
            return 1
        if isinstance(item, _PacketBatch):
            return item.write_to(self._output_stream, self._should_write_packet)
        if not self._should_write_packet(item):
            return 0
        item.write_to(self._output_stream)
        return 1

    def _pop_coalesced_packet(self, key):
        with self._coalescing_lock:
            return self._pending_coalescable_by_key.pop(key, None)

    def _track_coalescable_packets(self, item) -> None:
        if not SENDER_MOVEMENT_COALESCING_ENABLED:
            return
        packets = item.packets if isinstance(item, _PacketBatch) else (item,)
        tracked = []
        for packet in packets:
            kulcs = self._coalesce_key(packet)
            if kulcs is not None:
                tracked.append((kulcs, packet))
        if not tracked:
            return
        with self._coalescing_lock:
            for kulcs, packet in tracked:
                self._latest_coalescable_by_key[kulcs] = packet

    def _should_write_packet(self, packet) -> bool:
        kulcs = self._coalesce_key(packet)
        if kulcs is None or not SENDER_MOVEMENT_COALESCING_ENABLED:
            return True
        with self._coalescing_lock:
            latest = self._latest_coalescable_by_key.get(kulcs)
            if latest is not packet:
                self._record_coalesced_skip()
                return False
            self._latest_coalescable_by_key.pop(kulcs, None)
            return True

    def _record_coalesced_skip(self) -> None:
        if not GUARDRAILS_ENABLED:
            return
        self._coalesced_packets_since_warn = getattr(self, "_coalesced_packets_since_warn", 0) + 1
        if self._coalesced_packets_since_warn < SENDER_COALESCED_PACKET_WARN_COUNT:
            return
        most = now_ms()
        last_warn_ms = getattr(self, "_last_coalesced_warn_ms", 0.0)
        if most - last_warn_ms < SENDER_QUEUE_WARN_INTERVAL_MS:
            return
        skipped = self._coalesced_packets_since_warn
        self._coalesced_packets_since_warn = 0
        self._last_coalesced_warn_ms = most
        log.warning(
            "Sender movement coalescing skipped stale packets skipped=%s threshold=%s queue_depth=%s",
            skipped,
            SENDER_COALESCED_PACKET_WARN_COUNT,
            self._safe_qsize(),
        )

    @staticmethod
    def _coalesce_key(packet):
        return getattr(packet, "_rebsgo_coalesce_key", None)

    @staticmethod
    def _item_priority(item) -> int:
        if isinstance(item, _QueuedItem):
            return QueuedOutbox._item_priority(item.item)
        if isinstance(item, _CoalescedPacketSlot):
            return PRIORITY_SNAPSHOT
        if isinstance(item, _PacketBatch):
            return item.priority()
        return _packet_priority(item)

    def _warn_if_queue_age_high(self, max_queue_age_ms: float) -> None:
        if not should_warn(max_queue_age_ms, SENDER_QUEUE_AGE_WARN_MS):
            return
        most = now_ms()
        if most - self._last_queue_age_warn_ms < SENDER_QUEUE_WARN_INTERVAL_MS:
            return
        self._last_queue_age_warn_ms = most
        log.warning(
            "Sender queue age is high max_queue_age_ms=%.1f threshold_ms=%.1f queue_depth=%s",
            max_queue_age_ms,
            SENDER_QUEUE_AGE_WARN_MS,
            self._safe_qsize(),
        )

    def _warn_if_drain_large(self, items_drained: int) -> None:
        if not should_warn_count(items_drained, SENDER_DRAIN_WARN_ITEMS):
            return
        most = now_ms()
        if most - self._last_drain_warn_ms < SENDER_QUEUE_WARN_INTERVAL_MS:
            return
        self._last_drain_warn_ms = most
        log.warning(
            "Sender flush drained many queue items drained_items=%s threshold=%s queue_depth=%s",
            items_drained,
            SENDER_DRAIN_WARN_ITEMS,
            self._safe_qsize(),
        )


_NEVESITETT_RANG = {
    "critical": PRIORITY_CRITICAL,
    "interactive": PRIORITY_INTERACTIVE,
    "snapshot": PRIORITY_SNAPSHOT,
}


def _packet_priority(packet) -> int:
    rang = getattr(packet, "_rebsgo_sender_priority", None)
    if isinstance(rang, str):
        return _NEVESITETT_RANG.get(rang, PRIORITY_CRITICAL)
    if isinstance(rang, int):
        return min(max(rang, PRIORITY_CRITICAL), PRIORITY_SNAPSHOT)
    return PRIORITY_CRITICAL
