# github.com/Shran21

from __future__ import annotations

import logging

from rebsgo.config.config import Config
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.protocol_book_replies import replies_for
from rebsgo.world.sectors.sector_parts import SectorStep
from rebsgo.vocabulary.combat import ManeuverKind
from rebsgo.vocabulary.world import DepartureCause, ObjectKind
from rebsgo.geometry.maths.maths import Maths
from rebsgo.helpers.rolling_latency_stats import (
    SECTOR_MOVEMENT_PACKET_WARN_COUNT,
    SECTOR_TIMER_WARN_INTERVAL_MS,
    now_ms,
    should_warn_count,
    should_warn_interval,
)

log = logging.getLogger(__name__)
_CONFIG = Config.instance()
_OUT_OF_SECTOR_LIMIT = _CONFIG.float("rebsgo.sector.out-of-sector-limit", 50_000.0)


class MovementStep(SectorStep):
    def __init__(self, tick, objektumok, kimeno_sor, takarito, share_book):
        self._tick = tick
        self._space_objects = objektumok
        self._sector_sender = kimeno_sor
        self._remover = takarito
        self._share_book = share_book
        self._last_warn_ms = 0.0
        self._last_stats = {
            "has_clients": 0,
            "objects": 0,
            "new_maneuvers": 0,
            "movement_packets": 0,
            "out_of_sector_objects": 0,
        }

    def run(self) -> None:
        copy_tick = self._tick.copy()

        space_objects_except_players = self._space_objects.objects_other_than(
            ObjectKind.Asteroid,
            ObjectKind.Planetoid,
            ObjectKind.Planet,
            ObjectKind.Debris)
        self.refresh_for_party(space_objects_except_players, self._tick.delta_time(), copy_tick)

    def refresh_for_party(self, objektumok, dt: float, ora_masolas) -> None:
        movement_bws = []
        has_clients = self._sector_sender.has_clients()
        space_replies = (
            replies_for(ProtocolID.Game) if has_clients else None
        )
        object_count = 0
        new_maneuver_count = 0
        out_of_sector_candidates = []
        for space_object in objektumok:
            object_count += 1
            mover = space_object.mover_of()

            with mover.frissites_alatt:
                mover.move(ora_masolas, dt)

                if mover.is_new_maneuver():
                    new_maneuver_count += 1
                    mover.note_movement_tick(ora_masolas)
                    if not has_clients:
                        continue

                    if (mover.current_maneuver.maneuver_type == ManeuverKind.Rest
                        and space_object.mover_of().frame_tick is not None):
                        movement_protocol_buffer = space_replies.move(space_object)
                    else:
                        try:
                            movement_protocol_buffer = space_replies.sync_move(space_object)
                        except ValueError:
                            movement_protocol_buffer = None
                            log.exception('while serializing synced movement')

                    mover.mark_maneuver_fresh(False)
                    if movement_protocol_buffer is not None:
                        movement_bws.append(movement_protocol_buffer)
            out_of_sector_candidates.append((space_object, mover))
        out_of_sector_stats = self._out_of_sector_handling_batch(out_of_sector_candidates)
        self._sector_sender.push_to_everyone(movement_bws)
        movement_packet_count = len(movement_bws)
        self._last_stats = {
            "has_clients": 1 if has_clients else 0,
            "objects": object_count,
            "new_maneuvers": new_maneuver_count,
            "movement_packets": movement_packet_count,
            "out_of_sector_objects": out_of_sector_stats["out_of_sector_objects"],
        }
        if (should_warn_count(movement_packet_count, SECTOR_MOVEMENT_PACKET_WARN_COUNT)
            and should_warn_interval(self._last_warn_ms, SECTOR_TIMER_WARN_INTERVAL_MS)):
            self._last_warn_ms = now_ms()
            log.warning(
                "High sector movement broadcast objects=%s new_maneuvers=%s movement_packets=%s threshold=%s",
                object_count,
                new_maneuver_count,
                movement_packet_count,
                SECTOR_MOVEMENT_PACKET_WARN_COUNT,
            )

    def _out_of_sector_handling_batch(self, candidates) -> dict:
        mutatok = {"out_of_sector_objects": 0}
        for space_object, mover in candidates:
            if self._out_of_sector_handling(space_object, mover):
                mutatok["out_of_sector_objects"] += 1
        return mutatok

    def _out_of_sector_handling(self, space_object, mover) -> bool:
        if space_object.space_entity_type.of_kind(
                ObjectKind.Asteroid,
                ObjectKind.Planet,
                ObjectKind.Planetoid,
                ObjectKind.Debris):
            return False
        is_out_of_sector = self._is_out_of_sector(mover.position_of())
        if is_out_of_sector:
            if space_object.space_entity_type == ObjectKind.Comet:
                self._share_book.remove_claim(space_object)
            self._remover.note_removal_cause(space_object, DepartureCause.Death)
            return True
        return False

    def _is_out_of_sector(self, position) -> bool:
        return (Maths.abs(position.x) > _OUT_OF_SECTOR_LIMIT
                or Maths.abs(position.y) > _OUT_OF_SECTOR_LIMIT
                or Maths.abs(position.z) > _OUT_OF_SECTOR_LIMIT)

    def last_stats(self) -> dict:
        return dict(self._last_stats)
