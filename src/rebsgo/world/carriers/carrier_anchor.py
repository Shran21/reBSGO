# github.com/Shran21
from __future__ import annotations

import logging
import random

from rebsgo.world.movement.maneuvers import RestManeuver
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.protocol_book_replies import replies_for
from rebsgo.protocol.pilot.pilot_steps import ReleaseCause
from rebsgo.vocabulary.world import VisibilityCause, ObjectKind
from rebsgo.geometry.primitives.euler3 import Euler3
from rebsgo.geometry.primitives.vector3 import Vector3
from rebsgo.gamedata.from_json.template_readers import world_timers

log = logging.getLogger(__name__)

_CARRIER_RELEASE_MIN_DISTANCE = world_timers().carrier_release_min_distance
_CARRIER_RELEASE_MAX_DISTANCE = world_timers().carrier_release_max_distance


def random_position_around_carrier(carrier_pos):
    return _random_release_position(carrier_pos)


def _random_release_position(carrier_pos):
    while True:
        irany = Vector3(random.uniform(-1.0, 1.0), random.uniform(-1.0, 1.0), random.uniform(-1.0, 1.0))
        hossz = irany.magnitude_
        if 1e-4 < hossz <= 1.0:
            break
    tavolsag = random.uniform(_CARRIER_RELEASE_MIN_DISTANCE, _CARRIER_RELEASE_MAX_DISTANCE)
    irany.mult_(tavolsag / hossz)
    return carrier_pos.copy().add_(irany)


def build_carrier_anchor_hold_move(ctx, carrier, player_ship, clear_new_maneuver: bool = True):
    if ctx is None or carrier is None or player_ship is None:
        return None

    try:
        carrier_movement = carrier.mover_of()
        carrier_pos = carrier_movement.position_of()
        carrier_euler = _carrier_euler(carrier_movement)
        return _move_player_ship_to_rest(ctx, player_ship, carrier_pos, carrier_euler, clear_new_maneuver)
    except Exception:
        log.exception(
            "Carrier anchor follow: could not sync ship to carrier player_id=%s carrier=%s",
            _safe_player_id(player_ship),
            _safe_object_id(carrier),
        )
        return None


def sync_anchored_ship_to_carrier(ctx, carrier, player_id: int, send_to_owner: bool = True) -> bool:
    if ctx is None or carrier is None:
        return False

    users = ctx.users()
    player_ship = users.ship_of_pilot(player_id)
    if player_ship is None:
        return False

    if not _is_player_ship_anchored_to_carrier(player_ship, carrier):
        return False

    movement_buffer = build_carrier_anchor_hold_move(ctx, carrier, player_ship, clear_new_maneuver=True)
    if movement_buffer is None:
        return False

    if send_to_owner:
        if (user := users.user(player_id)) is not None:
            user.send(movement_buffer)
    return True


def sync_all_carrier_anchor_followers(ctx) -> tuple[int, int]:
    if ctx is None:
        return 0, 0

    checked_carriers = 0
    synced_ships = 0
    for carrier in _iter_space_objects(ctx.space_objects()):
        if _is_removed(carrier):
            continue

        allapot = _space_object_state(carrier)
        if allapot is None:
            continue

        anchored_ids = allapot.anchored_ids_snapshot()
        if not anchored_ids:
            continue

        checked_carriers += 1
        for player_id in anchored_ids:
            if sync_anchored_ship_to_carrier(ctx, carrier, player_id, send_to_owner=True):
                synced_ships += 1
    return checked_carriers, synced_ships


def release_carrier_anchor(ctx, carrier, player_id: int) -> bool:
    if ctx is None or carrier is None:
        return False

    carrier.world_state_of().unanchor(player_id)
    users = ctx.users()
    player_ship = users.ship_of_pilot(player_id)
    if player_ship is None:
        log.warning("Carrier anchor release: anchored player ship is missing player_id=%s carrier=%s",
                    player_id, carrier.id_in_space())
        return False

    try:
        carrier_pos = carrier.mover_of().position_of()
        release_pos = _random_release_position(carrier_pos)
        release_euler = _carrier_euler(carrier.mover_of())
        player_ship.mover_of().queue_maneuver(RestManeuver(release_pos, release_euler))
    except Exception:
        log.exception("Carrier anchor release: could not move anchored ship player_id=%s carrier=%s",
                      player_id, carrier.id_in_space())
        return False

    visibility = player_ship.visibility_of()
    visibility.switch_visibility(True, VisibilityCause.Anchor)
    release_buffers = _build_release_state_and_movement(ctx, player_ship, visibility)

    user = users.user(player_id)
    owner_preposition_sent = False
    if user is not None:
        player_writer = replies_for(ProtocolID.Pilot)
        unanchor_buffer = player_writer.un_anchor(player_ship.id_in_space(), ReleaseCause.Default)
        owner_preposition_sent = _send_owner_release_batch(user, release_buffers, unanchor_buffer)

        if (party := user.pilot_of().party()) is not None:
            community_writer = replies_for(ProtocolID.Community)
            party.tell_squad(
                community_writer.party_anchor(carrier.pilot_id(), player_id, False))

    state_and_movement_flushed = _broadcast_release_state_and_movement(
        ctx, release_buffers, exclude_player_id=player_id if owner_preposition_sent else None)
    mover = player_ship.mover_of()
    is_new_maneuver = getattr(mover, "is_new_maneuver", None)
    movement_retry_queued = is_new_maneuver() if callable(is_new_maneuver) else None
    log.info(
        "Carrier anchor release: placed player %s at %s (carrier %s at %s, "
        "state_movement_flushed=%s, owner_preposition_sent=%s, movement_retry_queued=%s)",
        player_id, release_pos, carrier.id_in_space(), carrier_pos,
        state_and_movement_flushed, owner_preposition_sent, movement_retry_queued)

    return True


def _build_release_state_and_movement(ctx, player_ship, visibility):
    game_writer = replies_for(ProtocolID.Game)
    movement_buffer = _build_move_update(ctx, player_ship, clear_new_maneuver=False)
    if movement_buffer is None:
        return None

    visibility_buffer = game_writer.switch_visibility_as(player_ship.id_in_space(), visibility)
    visibility.visibility_needs_push()
    return visibility_buffer, movement_buffer


def _move_player_ship_to_rest(ctx, player_ship, position, euler, clear_new_maneuver: bool):
    mover = player_ship.mover_of()
    mover.queue_maneuver(RestManeuver(position, euler))
    return _build_move_update(ctx, player_ship, clear_new_maneuver)


def _build_move_update(ctx, player_ship, clear_new_maneuver: bool):
    tick_fn = getattr(ctx, "tick", None)
    if not callable(tick_fn):
        return None

    mover = player_ship.mover_of()
    move_fn = getattr(mover, "move", None)
    if not callable(move_fn):
        return None

    game_writer = replies_for(ProtocolID.Game)
    tick = tick_fn().copy()
    with mover.frissites_alatt:
        mover.move(tick, 0.0)
        mover.note_movement_tick(tick)
        movement_buffer = game_writer.move(player_ship)

    if clear_new_maneuver:
        mover.mark_maneuver_fresh(False)
    return movement_buffer


def _send_owner_release_batch(user, release_buffers, unanchor_buffer) -> bool:
    if release_buffers is None:
        user.send(unanchor_buffer)
        return False

    visibility_buffer, movement_buffer = release_buffers
    user.send([movement_buffer, unanchor_buffer, visibility_buffer])
    return True


def _broadcast_release_state_and_movement(ctx, release_buffers, exclude_player_id: int | None = None) -> bool:
    sender_fn = getattr(ctx, "sender", None)
    if release_buffers is None or not callable(sender_fn):
        return False

    sender = sender_fn()
    visibility_buffer, movement_buffer = release_buffers
    buffers = [visibility_buffer, movement_buffer]
    if exclude_player_id is not None and _send_release_buffers_to_other_clients(ctx, sender, buffers, exclude_player_id):
        return True
    sender.push_to_everyone(buffers)
    return True


def _send_release_buffers_to_other_clients(ctx, sender, buffers, exclude_player_id: int) -> bool:
    push_to_all = getattr(sender, "send_to_clients", None)
    users_fn = getattr(ctx, "users", None)
    if not callable(push_to_all) or not callable(users_fn):
        return False
    users = users_fn()
    get_users_collection = getattr(users, "users_of", None)
    if not callable(get_users_collection):
        return False

    recipients = [
        user for user in get_users_collection()
        if _user_id(user) != exclude_player_id
    ]
    if recipients:
        push_to_all(buffers, recipients)
    return True


def _user_id(user):
    get_player = getattr(user, "pilot_of", None)
    if not callable(get_player):
        return None
    player = get_player()
    get_user_id = getattr(player, "user_id_of", None)
    if not callable(get_user_id):
        return None
    return get_user_id()


def _carrier_euler(carrier_movement):
    get_rotation = getattr(carrier_movement, "rotation_of", None)
    if not callable(get_rotation):
        return Euler3.zero()
    return Euler3.from_quaternion(get_rotation())


def _is_player_ship_anchored_to_carrier(player_ship, carrier) -> bool:
    visibility_fn = getattr(player_ship, "visibility_of", None)
    if not callable(visibility_fn):
        return False
    visibility = visibility_fn()
    return (
        not visibility.is_visible()
        and visibility.change_visibility_reason == VisibilityCause.Anchor
        and visibility.anchored_object_id == carrier.id_in_space()
    )


def _iter_space_objects(objektumok):
    player_objects = getattr(objektumok, "objects_of_kind", None)
    if callable(player_objects):
        yield from player_objects(ObjectKind.Pilot)
        return

    values = getattr(objektumok, "values", None)
    if callable(values):
        yield from values()


def _space_object_state(space_object):
    state_fn = getattr(space_object, "world_state_of", None)
    if not callable(state_fn):
        return None
    return state_fn()


def _is_removed(space_object) -> bool:
    is_removed = getattr(space_object, "is_removed", None)
    return callable(is_removed) and is_removed()


def _safe_player_id(player_ship):
    pilot_id = getattr(player_ship, "pilot_id", None)
    if not callable(pilot_id):
        return None
    return pilot_id()


def _safe_object_id(space_object):
    id_in_space = getattr(space_object, "id_in_space", None)
    if not callable(id_in_space):
        return None
    return id_in_space()


def release_carrier_anchors(ctx, carrier, source: str = "") -> int:
    if ctx is None or carrier is None:
        return 0

    anchored_ids = carrier.world_state_of().anchored_ids_snapshot()
    released = 0
    for player_id in anchored_ids:
        if release_carrier_anchor(ctx, carrier, player_id):
            released += 1

    if released > 0:
        log.info("Released %s carrier anchors source=%s carrier=%s",
                 released, source, carrier.id_in_space())
    return released
