# github.com/Shran21

from __future__ import annotations

import logging

from rebsgo.config.config import Config
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.protocol_book_replies import replies_for
from rebsgo.world.sectors.sector_parts import SectorStep
from rebsgo.vocabulary.combat import ManeuverKind
from rebsgo.world.movement.maneuvers import FollowManeuver
from rebsgo.vocabulary.world import DepartureCause, ObjectKind
from rebsgo.geometry.maths.maths import Maths
from rebsgo.helpers.rolling_latency_stats import (
    SECTOR_MOVEMENT_PACKET_WARN_COUNT,
    SENDER_BROADCAST_PREFREEZE_ENABLED,
    SECTOR_TIMER_WARN_INTERVAL_MS,
    now_ms,
    should_warn_count,
    should_warn_interval,
)

log = logging.getLogger(__name__)
_CONFIG = Config.instance()
_OUT_OF_SECTOR_LIMIT = _CONFIG.float("rebsgo.sector.out-of-sector-limit", 50_000.0)


def _followed(mover) -> list:
    # a FollowManeuver reads the followed ship's mover, and can write its advance_frame;
    # the type is compared, not isinstance(): a check against an ABC takes a lock
    return [maneuver.follow_target
            for maneuver in (getattr(mover, "maneuver", None), getattr(mover, "next_maneuver", None))
            if type(maneuver) is FollowManeuver]


def _has_moved(space_object) -> bool:
    return space_object is None or space_object.mover_of().frame_tick is not None


class MovementStep(SectorStep):
    def __init__(self, tick, objektumok, kimeno_sor, takarito, share_book, segedek=None):
        self._tick = tick
        self._space_objects = objektumok
        self._sector_sender = kimeno_sor
        self._remover = takarito
        self._share_book = share_book
        self._helpers = segedek
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
        has_clients = self._sector_sender.has_clients()
        space_replies = (
            replies_for(ProtocolID.Game) if has_clients else None
        )
        if self._helpers is not None:
            objektumok = list(objektumok)
            if self._helpers.pieces_for(len(objektumok)) > 1:
                self._refresh_split(objektumok, dt, ora_masolas, space_replies)
                return
        movement_bws = []
        object_count = 0
        new_maneuver_count = 0
        out_of_sector_candidates = []
        for space_object in objektumok:
            object_count += 1
            is_new, movement_protocol_buffer, check_place = self._move_one(
                space_object, ora_masolas, dt, space_replies)
            if is_new:
                new_maneuver_count += 1
            if movement_protocol_buffer is not None:
                movement_bws.append(movement_protocol_buffer)
            if check_place:
                out_of_sector_candidates.append((space_object, space_object.mover_of()))
        out_of_sector_stats = self._out_of_sector_handling_batch(out_of_sector_candidates)
        self._sector_sender.push_to_everyone(movement_bws)
        self._finish_stats(has_clients, object_count, new_maneuver_count, len(movement_bws),
                           out_of_sector_stats["out_of_sector_objects"])

    def _move_one(self, space_object, ora_masolas, dt: float, space_replies) -> tuple:
        """(a fresh maneuver?, its movement packet, is its place to be checked?)"""
        mover = space_object.mover_of()
        with mover.frissites_alatt:
            mover.move(ora_masolas, dt)

            if not mover.is_new_maneuver():
                return False, None, True
            mover.note_movement_tick(ora_masolas)
            if space_replies is None:
                return True, None, False

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
            return True, movement_protocol_buffer, True

    def _move_chunk(self, chunk, ora_masolas, dt: float, space_replies, side_by_side: bool) -> tuple:
        new_maneuvers = 0
        packets = []
        leaving = []
        held_back = []
        for space_object in chunk:
            if side_by_side and _followed(space_object.mover_of()):
                held_back.append(space_object)
                continue
            is_new, movement_protocol_buffer, check_place = self._move_one(
                space_object, ora_masolas, dt, space_replies)
            if is_new:
                new_maneuvers += 1
            if movement_protocol_buffer is not None:
                if side_by_side and SENDER_BROADCAST_PREFREEZE_ENABLED:
                    movement_protocol_buffer.frozen_bytes()
                packets.append(movement_protocol_buffer)
            if check_place and self._leaves_sector(space_object, space_object.mover_of()):
                leaving.append(space_object)
        return new_maneuvers, packets, leaving, held_back

    def _refresh_split(self, objektumok, dt: float, ora_masolas, space_replies) -> None:
        # Followers move first, alone: following reads the followed ship's mover,
        # where it was last tick. Every other object touches only its own, so those
        # move side by side. Following a ship that has never moved yet waits for it.
        followers = []
        late = []
        others = []
        for space_object in objektumok:
            followed = _followed(space_object.mover_of())
            if not followed:
                others.append(space_object)
            elif all(_has_moved(target) for target in followed):
                followers.append(space_object)
            else:
                late.append(space_object)
        parts = [self._move_chunk(followers, ora_masolas, dt, space_replies, False)]
        parts.extend(self._helpers.split(
            "movement", lambda chunk: self._move_chunk(chunk, ora_masolas, dt, space_replies, True), others))
        late.extend(space_object for part in parts for space_object in part[3])
        if late:
            parts.append(self._move_chunk(late, ora_masolas, dt, space_replies, False))

        movement_bws = [packet for part in parts for packet in part[1]]
        leaving = 0
        for part in parts:
            for space_object in part[2]:
                self._drop_out_of_sector(space_object)
                leaving += 1
        self._sector_sender.push_to_everyone(movement_bws)
        self._finish_stats(space_replies is not None, len(objektumok), sum(part[0] for part in parts),
                           len(movement_bws), leaving)

    def _finish_stats(self, has_clients: bool, object_count: int, new_maneuver_count: int,
                      movement_packet_count: int, out_of_sector_objects: int) -> None:
        self._last_stats = {
            "has_clients": 1 if has_clients else 0,
            "objects": object_count,
            "new_maneuvers": new_maneuver_count,
            "movement_packets": movement_packet_count,
            "out_of_sector_objects": out_of_sector_objects,
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
        if self._leaves_sector(space_object, mover):
            self._drop_out_of_sector(space_object)
            return True
        return False

    def _leaves_sector(self, space_object, mover) -> bool:
        if space_object.space_entity_type.of_kind(
                ObjectKind.Asteroid,
                ObjectKind.Planet,
                ObjectKind.Planetoid,
                ObjectKind.Debris):
            return False
        return self._is_out_of_sector(mover.position_of())

    def _drop_out_of_sector(self, space_object) -> None:
        if space_object.space_entity_type == ObjectKind.Comet:
            self._share_book.remove_claim(space_object)
        self._remover.note_removal_cause(space_object, DepartureCause.Death)

    def _is_out_of_sector(self, position) -> bool:
        return (Maths.abs(position.x) > _OUT_OF_SECTOR_LIMIT
                or Maths.abs(position.y) > _OUT_OF_SECTOR_LIMIT
                or Maths.abs(position.z) > _OUT_OF_SECTOR_LIMIT)

    def last_stats(self) -> dict:
        return dict(self._last_stats)
