# github.com/Shran21

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone
from rebsgo.config.config import Config
from rebsgo.world.movement.maneuvers import RestManeuver, DirectionalManeuver
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.protocol_book_replies import replies_for
from rebsgo.world.sectors.sector_parts import SectorStep
from rebsgo.vocabulary.world import ArrivalCause, ObjectKind, PlaceKind, DepartureCause
from rebsgo.geometry.primitives.euler3 import Euler3
from rebsgo.geometry.primitives.transform import Transform
from rebsgo.helpers.rolling_latency_stats import (
    ENABLED as GUARDRAILS_ENABLED,
    SECTOR_SPAWN_COLLISION_SCAN_WARN_COUNT,
    SECTOR_TIMER_WARN_INTERVAL_MS,
    now_ms,
    should_warn_count,
    should_warn_interval,
)
from rebsgo.helpers.notifying.watcher import Watcher
from rebsgo.services import Services
from rebsgo.world.carriers.carrier_anchor import release_carrier_anchors
from rebsgo.world.carriers.carrier_mode import is_carrier_space_object
from rebsgo.world.sectors.departures.notes import CollectedNote, KilledNote, LostLinkNote, DockedNote, HitNote, JumpedOutNote
from rebsgo.world.sectors.departures.object_left_just_removed import ObjectLeftJustRemoved
from rebsgo.vocabulary.pilot import Faction
from rebsgo.gamedata.cards.misc_cards import TallyCardKind
from rebsgo.gamedata.cards.world_cards import GalaxyMapCard
from rebsgo.gamedata.library import Catalogue
from rebsgo.helpers.small_helpers import DecayingCount
from rebsgo.gamedata.from_json.template_readers import world_timers


log = logging.getLogger(__name__)

_CONFIG = Config.instance()
_ENTRY_STREAMING_ENABLED = _CONFIG.bool("rebsgo.sector.entry-streaming.enabled", False)
_ENTRY_STREAMING_OBJECTS_PER_BATCH = max(
    1, _CONFIG.int("rebsgo.sector.entry-streaming.objects-per-batch", 96))
_ENTRY_STREAMING_MAX_BATCHES_PER_TICK = max(
    1, _CONFIG.int("rebsgo.sector.entry-streaming.max-batches-per-tick", 2))


class ArrivalQueue(SectorStep):
    MENTETT_HELY_PERC = world_timers().reserved_slot_minutes

    def __init__(self, keltohelyek, tick, pilotak, objektumok, kimeno_sor,
                 outpost_states, object_forge, space_replies):
        self._new_space_objects = deque()
        self._new_users = deque()
        self._spawn_areas = keltohelyek
        self._tick = tick
        self._users = pilotak
        self._space_objects = objektumok
        self._sector_sender = kimeno_sor
        self._outpost_states = outpost_states
        self._object_forge = object_forge
        self._space_replies = space_replies
        self._entry_payload_streams = deque()
        self._last_spawn_collision_scan_count = 0
        self._last_spawn_collision_warn_ms = 0.0
        self._last_spawn_collision_stats = {
            "attempts": 0,
            "collisions": 0,
            "scanned": 0,
        }
        self._wake_callback = None

    def wake_with(self, wake_callback) -> None:
        self._wake_callback = wake_callback

    def _wake_sector(self, reason: str) -> None:
        if (wake_callback := self._wake_callback) is not None:
            wake_callback(reason)

    def arrival_queue(self, user, jump_companions) -> None:
        log.info('pilot queued for admission')
        self._new_users.append(FirstArrival(user, jump_companions))
        self._wake_sector("user_join")

    def _user_joins_sector(self, new_user_obj) -> None:
        user = new_user_obj.user()
        log.info('%s arrives in the sector', user)
        self._users.clear_join_flag(user.pilot_of().user_id_of())
        user.send(self._space_replies.time_origin(self._tick.origin_time))
        colonial_delta = self._outpost_states.colonial_outpost_state.delta()
        cylon_delta = self._outpost_states.cylon_outpost_state.delta()
        user.send(self._space_replies.outpost_state_broadcast(
            self._outpost_states.colonial_outpost_state.op_points, colonial_delta,
            self._outpost_states.cylon_outpost_state.op_points, cylon_delta))

        player = user.pilot_of()

        player_ship = self._users.ship_of_pilot(player.user_id_of())
        if player_ship is not None:
            self._queue_space_objects_for_user(
                self._space_objects.values(),
                user,
                lambda user_id=user.pilot_of().user_id_of(): self._users.note_arrival_of(user_id),
            )
        else:
            new_player_ship = self._object_forge.hatch_player_ship(player)

            self._users.add(user, new_player_ship)
            self.admit_object(new_player_ship, new_user_obj.jump_companions)

    def run(self) -> None:
        while self._new_users:
            user_to_add = self._new_users.popleft()
            self._user_joins_sector(user_to_add)
        while self._new_space_objects:
            new_sp_obj = self._new_space_objects.popleft()

            new_sp_obj.space_subscribe_info().note_combat_moment(0)

            self._sector_sender.send_space_object_cards_to_all(new_sp_obj)
            self._sector_sender.send_who_is_to_all(new_sp_obj)

            mover = new_sp_obj.mover_of()
            try:
                mover.take_movement_stats(new_sp_obj.space_subscribe_info().stats_of)
            except Exception as e:
                log.error('applying movement limits fell over', exc_info=e)

            if new_sp_obj.space_entity_type.of_kind(
                    ObjectKind.JumpBeacon, ObjectKind.JumpBeacon):
                self._send_initial_static_jump_object_state(new_sp_obj)

            if new_sp_obj.is_player():
                user = self._users.user(new_sp_obj.pilot_id())
                if user is not None:
                    self._queue_space_objects_for_user(
                        self._space_objects.values(),
                        user,
                        lambda user_id=new_sp_obj.pilot_id(): self._users.note_arrival_of(user_id),
                    )
                else:
                    self._users.note_arrival_of(new_sp_obj.pilot_id())

            new_sp_obj.creating_cause = ArrivalCause.AlreadyExists
            self._space_objects.add(new_sp_obj)
        self._drain_entry_payload_streams()

    def _queue_space_objects_for_user(self, objektumok, user, on_complete) -> None:
        if not _ENTRY_STREAMING_ENABLED:
            self._sector_sender.stream_objects_to(objektumok, user)
            on_complete()
            return
        stream = self._sector_sender.create_space_objects_entry_stream(objektumok, user)
        self._entry_payload_streams.append((stream, on_complete))

    def _drain_entry_payload_streams(self) -> None:
        batches_sent = 0
        while self._entry_payload_streams and batches_sent < _ENTRY_STREAMING_MAX_BATCHES_PER_TICK:
            stream, on_complete = self._entry_payload_streams.popleft()
            user = stream.user()
            if not self._entry_stream_user_connected(user):
                log.info("Drop pending sector entry payload stream because user disconnected")
                continue
            kesz = stream.send_next(_ENTRY_STREAMING_OBJECTS_PER_BATCH)
            batches_sent += 1
            if kesz:
                on_complete()
            else:
                self._entry_payload_streams.append((stream, on_complete))

    @staticmethod
    def _entry_stream_user_connected(user) -> bool:
        is_connected = getattr(user, "is_connected", None)
        return not callable(is_connected) or is_connected()

    def _send_initial_static_jump_object_state(self, space_object) -> None:
        space_replies = replies_for(ProtocolID.Game)
        bws = [space_replies.space_object_state(space_object.world_state_of())]
        try:
            bws.append(space_replies.move(space_object))
        except Exception:
            log.exception("Could not send initial static jump object movement for object_id=%s",
                          space_object.id_in_space())
        self._sector_sender.push_to_everyone(bws)

    def admit_object(self, space_object, jump_companions=None) -> None:
        self._initialize_player_spawn(space_object, jump_companions)

        mover = space_object.mover_of()
        space_object.space_subscribe_info().on_movement_update(mover)

        if not mover.has_next_maneuver:
            rest = RestManeuver(mover.position_of(),
                                Euler3.from_quaternion(mover.rotation_of()))
            mover.queue_maneuver(rest)

        if space_object.space_entity_type.of_kind(
                ObjectKind.JumpBeacon, ObjectKind.JumpBeacon) \
                and mover.frame_tick is None:
            mover.move(self._tick.copy(), 0.0)

        self._new_space_objects.append(space_object)
        self._wake_sector("space_object")

    def has_pending_work(self) -> bool:
        return bool(self._new_users or self._new_space_objects or self._entry_payload_streams)

    def _initialize_player_spawn(self, space_object, jump_companions) -> None:
        if not space_object.is_player():
            return

        player_faction = space_object.faction
        spawn = self._spawn_areas.spawn_for(player_faction)
        if spawn is None:
            log.error('faction %s owns no spawn area here - parking the pilot at the origin', player_faction)
            space_object.mover_of().queue_maneuver(RestManeuver(Transform()))
            return

        spawn_transform = Transform()
        if self._apply_jump_arrival_transform(space_object, spawn_transform):
            space_object.mover_of().queue_maneuver(RestManeuver(spawn_transform))
            return
        already_has_spawn_transform = self._apply_stored_transform(space_object, spawn_transform)
        if not already_has_spawn_transform:
            HELYKERESES_PROBAK = 10
            base_collider = space_object.collider_of()
            if base_collider is None:
                log.warning("Pilot %s has no collider; skipping spawn collision checks", space_object.pilot_id())
                space_object.mover_of().queue_maneuver(RestManeuver(spawn_transform))
                return
            tmp_collider = base_collider.copy()
            spawn_collision_attempts = 0
            spawn_collision_collisions = 0
            spawn_collision_scans = 0

            for i in range(HELYKERESES_PROBAK):
                if i > 0:
                    log.warning('spawn point for %s came up blocked; attempt %s follows',
                                space_object.pilot_id(), i)

                spawn_transform.set_position_rotation(spawn.random_position, spawn.rotation_of())

                tmp_collider.transform_of().place_at(spawn_transform)
                tmp_collider.sync_to_transform()
                does_collide_with_any = self._collides_with_any(tmp_collider)
                spawn_collision_attempts += 1
                if GUARDRAILS_ENABLED:
                    spawn_collision_scans += self._last_spawn_collision_scan_count
                if not does_collide_with_any:
                    break
                spawn_collision_collisions += 1

            if GUARDRAILS_ENABLED:
                self._last_spawn_collision_stats = {
                    "attempts": spawn_collision_attempts,
                    "collisions": spawn_collision_collisions,
                    "scanned": spawn_collision_scans,
                }
                if (should_warn_count(spawn_collision_scans, SECTOR_SPAWN_COLLISION_SCAN_WARN_COUNT)
                    and should_warn_interval(
                            self._last_spawn_collision_warn_ms, SECTOR_TIMER_WARN_INTERVAL_MS)):
                    self._last_spawn_collision_warn_ms = now_ms()
                    log.warning(
                        "High spawn collision scan player=%s attempts=%s collisions=%s scanned=%s threshold=%s",
                        space_object.pilot_id(),
                        spawn_collision_attempts,
                        spawn_collision_collisions,
                        spawn_collision_scans,
                        SECTOR_SPAWN_COLLISION_SCAN_WARN_COUNT,
                    )

        space_object.mover_of().queue_maneuver(RestManeuver(spawn_transform))

    def _apply_jump_arrival_transform(self, space_object, kelto_helyzet) -> bool:
        user = self._users.user(space_object.pilot_id())
        if user is None:
            return False
        transform = user.pilot_of().consume_jump_arrival_transform()
        if transform is None:
            return False
        kelto_helyzet.place_at(transform)
        return True

    def _collides_with_any(self, tmp_collider) -> bool:
        if GUARDRAILS_ENABLED:
            return self._collides_with_any_measured(tmp_collider)
        self._last_spawn_collision_scan_count = 0
        talalatok = (o.collider_of().touch(tmp_collider)
                     for o in self._spawn_collision_candidates() if o.carries_collider)
        return any(t is not None and t.touch() for t in talalatok)

    def _collides_with_any_measured(self, tmp_collider) -> bool:
        scanned = 0
        for space_object in self._spawn_collision_candidates():
            scanned += 1
            if not space_object.carries_collider:
                continue
            collision_record = space_object.collider_of().touch(tmp_collider)
            if collision_record is not None and collision_record.touch():
                self._last_spawn_collision_scan_count = scanned
                return True
        self._last_spawn_collision_scan_count = scanned
        return False

    def _spawn_collision_candidates(self):
        stream = getattr(self._space_objects, "objects_other_than", None)
        if stream is not None:
            return stream(ObjectKind.Missile)
        return self._space_objects.space_objects_not_of_entity_type(ObjectKind.Missile)

    @property
    def last_spawn_collision_stats(self) -> dict:
        return dict(self._last_spawn_collision_stats)

    def _apply_stored_transform(self, space_object, kelto_helyzet) -> bool:
        if not space_object.is_player():
            raise ValueError('placement is a player-only move')

        transform_by_old_user_position = self._space_objects.transform_by_old_user_position
        old_user_position_key = LastPositionKey(space_object.pilot_id(), space_object.faction)
        if old_user_position_key in transform_by_old_user_position and self._is_user_transform_within_time_limit(old_user_position_key):
            old_position = transform_by_old_user_position[old_user_position_key]
            kelto_helyzet.place_at(old_position)
            return True
        return False

    def _is_user_transform_within_time_limit(self, regi_hely_kulcs) -> bool:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        duration_minutes = (now - regi_hely_kulcs.local_date_time).total_seconds() / 60
        return duration_minutes < ArrivalQueue.MENTETT_HELY_PERC


class FirstArrival:
    def __init__(self, user, jump_companions):
        self._user = user
        self._jump_companions = jump_companions

    def user(self):
        return self._user

    @property
    def jump_companions(self):
        return self._jump_companions

    @property
    def jumping_together(self) -> bool:
        return self._jump_companions is not None and len(self._jump_companions) > 0

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not isinstance(other, FirstArrival):
            return False
        return self._user == other._user and self._jump_companions is other._jump_companions

    def __hash__(self) -> int:
        return hash((self._user, id(self._jump_companions)))

    def __repr__(self) -> str:
        return (f'<pilot {self._user.pilot_of().user_id_of()} arrives first,'
                f' with {self._jump_companions}>')


class DepartureWatcher(Watcher):
    pass


class LastPositionKey:
    def __init__(self, user_id: int, faction, idopont=None):
        self._user_id = user_id
        self._faction = faction
        if idopont is None:
            idopont = datetime.now(timezone.utc).replace(tzinfo=None)
        self._local_date_time = idopont

    def user_id(self) -> int:
        return self._user_id

    def faction(self):
        return self._faction

    @property
    def local_date_time(self) -> datetime:
        return self._local_date_time

    def __hash__(self) -> int:
        return hash((self._user_id, self._faction))

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if type(other) is not type(self):
            return NotImplemented
        return self._user_id == other._user_id and self._faction == other._faction

    def __repr__(self) -> str:
        return (f'<where pilot {self._user_id} of {self._faction} stood'
                f' at {self._local_date_time}>')


class Reaper(SectorStep):
    def __init__(self, tavozas_leirasok, ctx, space_replies):
        from rebsgo.game_metrics import JatekMerok

        self._ctx = ctx
        self._object_left_descriptions = tavozas_leirasok
        self._subscribers = []
        self._space_replies = space_replies
        self._user_ids_disconnected = set()
        self._user_ids_in_hold_for_remove = set()
        self._user_ids_notified_for_remove = deque()
        self._colonial_killed_counter = DecayingCount(Faction.Colonial)
        self._cylon_killed_counter = DecayingCount(Faction.Cylon)
        self._merok = Services.get(JatekMerok)

    def _add_object_died(self, obj, gyilkos) -> None:
        if obj.is_removed():
            log.warning('object %s left the world earlier, reason %s', obj.id_in_space(), obj.removing_cause_direct)
            return
        self._object_left_descriptions.append(KilledNote(obj, gyilkos))

    def note_removal_cause(self, space_object, removing_cause, tavozo_objektum=None) -> None:
        if space_object.is_removed():
            log.warning("WorldObject id=%s, type=%s is already removed, cause=%s, new_cause=%s",
                        space_object.id_in_space(), space_object.space_entity_type,
                        space_object.removal_cause_of(), removing_cause)
            return
        if is_carrier_space_object(space_object):
            release_carrier_anchors(self._ctx, space_object, f"remove {removing_cause}")
        if removing_cause == DepartureCause.Death:
            self._add_object_died(space_object, tavozo_objektum)
        elif removing_cause == DepartureCause.JumpOut:
            self._add_object_jump_out(space_object)
        elif removing_cause == DepartureCause.Disconnection:
            self._add_object_disconnected(space_object)
        elif removing_cause == DepartureCause.Dock:
            self._add_object_dock(space_object)
        elif removing_cause == DepartureCause.Hit:
            self._add_object_left_hit(space_object, tavozo_objektum)
        elif removing_cause == DepartureCause.JustRemoved:
            self._add_object_just_removed(space_object)
        elif removing_cause == DepartureCause.Collected:
            self._add_object_collected(space_object, tavozo_objektum)
        else:
            raise RuntimeError(str(removing_cause) + ' has no implementation yet')

    def respawn_choice_made(self, user_id: int) -> None:
        self._user_ids_notified_for_remove.append(user_id)

    def on_user_left(self, user_id: int) -> None:
        self._user_ids_disconnected.add(user_id)

    def _add_object_dock(self, obj) -> None:
        self._object_left_descriptions.append(DockedNote(obj))

    def _add_object_disconnected(self, obj) -> None:
        self._object_left_descriptions.append(LostLinkNote(obj))

    def _add_object_jump_out(self, obj) -> None:
        if obj.is_removed():
            Reaper._log_object_already_removed(obj)
            return
        self._object_left_descriptions.append(JumpedOutNote(obj))

    def _add_object_just_removed(self, obj) -> None:
        if obj.is_removed():
            Reaper._log_object_already_removed(obj)
            return
        self._object_left_descriptions.append(ObjectLeftJustRemoved(obj))

    def _add_object_collected(self, obj, gyujtes_mp=0) -> None:
        if obj.is_removed():
            Reaper._log_object_already_removed(obj)
            return
        self._object_left_descriptions.append(CollectedNote(obj, int(gyujtes_mp or 0)))

    def _add_object_left_hit(self, obj, talalat_erte) -> None:
        if obj.is_removed():
            Reaper._log_object_already_removed(obj)
            return
        self._object_left_descriptions.append(HitNote(obj, talalat_erte))

    def run(self) -> None:
        self._object_left_update()
        self._player_left_update()
        self._update_user_disconnected()

    def has_pending_work(self) -> bool:
        return bool(
            self._object_left_descriptions
            or self._user_ids_disconnected
            or self._user_ids_notified_for_remove
        )

    def _update_user_disconnected(self) -> None:
        for_removal = set()
        for id_of_disconnected_user in list(self._user_ids_disconnected):
            if (user := self._ctx.users().user(id_of_disconnected_user)) is not None:
                if user.is_connected():
                    for_removal.add(id_of_disconnected_user)
                    continue
            self._player_left_intermediate_handler(id_of_disconnected_user)
            for_removal.add(id_of_disconnected_user)
        self._user_ids_disconnected -= for_removal

    def _player_left_update(self) -> None:
        while self._user_ids_notified_for_remove:
            user_id_left = self._user_ids_notified_for_remove.popleft()

            contained = user_id_left in self._user_ids_in_hold_for_remove
            self._user_ids_in_hold_for_remove.discard(user_id_left)
            if not contained:
                continue

            removed_user = self._ctx.users().remove(user_id_left)
            if removed_user is not None and not removed_user.is_connected():
                self._player_left_intermediate_handler(user_id_left)

    def _player_left_intermediate_handler(self, player_id: int) -> None:
        for ertek in self._ctx.space_objects().values():
            if ertek.pilot_id() == player_id:
                continue

            ertek.space_subscribe_info().drop_subscriber(player_id)

    def _object_left_update(self) -> None:
        to_send = []
        start_users = self._ctx.users().users()
        while self._object_left_descriptions:
            desc = self._object_left_descriptions.popleft()
            to_send.append(desc)
            space_object_to_remove = desc.departed_object
            if space_object_to_remove.space_entity_type.of_kind(ObjectKind.MiningShip, ObjectKind.Outpost):
                space_object_to_remove.space_subscribe_info().clear_watchers()

            self._merok.object_gone(
                self._ctx.blueprint().sector_desc.sector_id,
                space_object_to_remove.space_entity_type, space_object_to_remove.faction,
                desc.removal_cause_of())

            if desc.removal_cause_of() == DepartureCause.Death:
                if space_object_to_remove.space_entity_type == ObjectKind.Pilot:
                    user = self._ctx.users().user(space_object_to_remove.pilot_id())
                    if user is not None:
                        if getattr(user.pilot_of(), "_arena_match", None) is None:
                            self._send_respawn_options(user)
                        left_death_desc = desc
                        if left_death_desc.killer_of() is not None:
                            killer_object = left_death_desc.killer_of()

                            tally_desk = user.pilot_of().tally_desk
                            sector_guid = self._ctx.blueprint().sector_cards().sector_card.card_guid_of()
                            tally_desk.bump_counter(TallyCardKind.total_deaths, sector_guid)
                            if killer_object.is_player():
                                killed_counter = self.kill_counter_faction(space_object_to_remove.faction)
                                killed_counter.mark_time()
                                tally_desk.bump_counter(TallyCardKind.pvp_deaths, sector_guid)
                            else:
                                tally_desk.bump_counter(TallyCardKind.pve_deaths, sector_guid)

            if space_object_to_remove.is_player():
                player_ship = space_object_to_remove
                removed_user = self._ctx.users().remove(player_ship.pilot_id())
                if not removed_user.is_connected():
                    self._player_left_intermediate_handler(player_ship.pilot_id())
                for op_or_mining_ship in self._ctx.space_objects().space_objects_of_entity_types(
                        ObjectKind.MiningShip, ObjectKind.Outpost):
                    op_or_mining_ship.space_subscribe_info().remove_subscriber(removed_user.protocol_of(ProtocolID.Game))

            try:
                self._notify_subscriber_object_left(desc)
            except Exception as ex:
                log.error("Watcher on_update failed during object removal (obj=%s, cause=%s)",
                          space_object_to_remove.id_in_space(), desc.removal_cause_of(), exc_info=ex)
            self._ctx.space_objects().remove(space_object_to_remove, desc.removal_cause_of())

            follow_missiles = self._ctx.space_objects().follow_missiles(space_object_to_remove)
            for follow_missile in follow_missiles:
                self._update_missile_target_dead(follow_missile)

        if len(start_users) == 0:
            return

        for object_left_description in to_send:
            bw = self._space_replies.object_left([object_left_description])
            self._ctx.sender().send_to_clients(bw, start_users)

    def _send_respawn_options(self, user) -> None:
        game_protocol = user.protocol_of(ProtocolID.Game)
        send_successfully = game_protocol.push_respawn_choices()
        if not send_successfully:
            last_respawn_options = game_protocol.last_respawn_options
            if (respawn_opts := last_respawn_options.get()) is not None:
                respawn_sector_id = (GalaxyMapCard.start_sector(user.pilot_of().faction)
                                     if len(respawn_opts.sector_ids) == 0
                                     else respawn_opts.sector_ids[0])

                star = Services.get(Catalogue).map_card.star(respawn_sector_id)
                if star is not None:
                    user.pilot_of().location.set_location(
                        PlaceKind.Room, star.id, star.sector_guid)

    def kill_counter_faction(self, faction) -> DecayingCount:
        return self._colonial_killed_counter if faction == Faction.Colonial else self._cylon_killed_counter

    def _update_missile_target_dead(self, missile) -> None:
        mover = missile.mover_of()
        mover.queue_maneuver(DirectionalManeuver(mover.frame.euler3()))

    def watch_with(self, figyelo) -> None:
        if figyelo is None:
            raise TypeError("a watcher is required")
        self._subscribers.append(figyelo)

    def _notify_subscriber_object_left(self, tavozas_leiras) -> None:
        for subscriber in self._subscribers:
            try:
                subscriber.on_update(tavozas_leiras)
            except Exception as ex:
                log.error("object-left subscriber %s failed", type(subscriber).__name__, exc_info=ex)

    @staticmethod
    def _log_object_already_removed(space_object) -> None:
        log.error('object %s left the world earlier; reason=%s', space_object.id_in_space(), space_object.removal_cause_of())
