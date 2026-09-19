# github.com/Shran21
from __future__ import annotations

from functools import lru_cache

from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.protocol_book_replies import game_replies
from rebsgo.world.objects.ships import PlayerShip
from rebsgo.gamedata.from_json.small_readers import StealthConfigReader
from rebsgo.gamedata.reading import AbilityActionKind, ObjectStat


@lru_cache(maxsize=1)
def get_stealth_detection_visual_radius() -> float:
    return StealthConfigReader().fetch().stealth_detection_visual_radius


def is_cloaked_player(target) -> bool:
    return isinstance(target, PlayerShip) and target.world_state_of().is_cloaked


def get_detection_visual_radius(observer_ship, target) -> float:
    if is_cloaked_player(target):
        return get_stealth_detection_visual_radius()
    return observer_ship.space_subscribe_info().stat_or_default(ObjectStat.DetectionVisualRadius)


def is_inside_visual_detection_radius(observer_ship, target) -> bool:
    visual_radius = get_detection_visual_radius(observer_ship, target)
    visual_radius_sq = visual_radius * visual_radius
    distance_sq = observer_ship.mover_of().position_of().sq_distance_to(
        target.mover_of().position_of())
    return distance_sq < visual_radius_sq


def is_cloaked_outside_visual_detection(observer_ship, target) -> bool:
    return is_cloaked_player(target) and not is_inside_visual_detection_radius(observer_ship, target)


def get_stealth_slot_ids(player_ship) -> list[int]:
    rekeszek = player_ship.space_subscribe_info().ship_slots
    if rekeszek is None:
        return []

    parok = ((r.ship_ability(), r.ship_system) for r in rekeszek.values())
    return [rendszer.server_id for kepesseg, rendszer in parok
            if kepesseg is not None and rendszer is not None
            and kepesseg.ship_ability_card.ability_action_type == AbilityActionKind.ToggleStealth]


def remove_stealth_auto_casts(player_ship, cast_desk) -> list[int]:
    slot_ids = get_stealth_slot_ids(player_ship)
    if cast_desk is None:
        return slot_ids
    for slot_id in slot_ids:
        cast_desk.disarm_auto_cast(slot_id, player_ship.id_in_space())
    return slot_ids


def deactivate_player_stealth(ctx, player_ship, cast_desk=None) -> bool:
    if not is_cloaked_player(player_ship):
        return False

    player_ship.world_state_of().cloak(False)
    game = game_replies()
    ctx.sender().push_to_everyone(game.space_object_state(player_ship.world_state_of()))

    player_ship.visibility_of().finish_stealth()
    slot_ids = remove_stealth_auto_casts(player_ship, cast_desk)
    _send_stop_slot_abilities(ctx, player_ship, slot_ids)
    return True


def _send_stop_slot_abilities(ctx, player_ship, slot_ids: list[int]) -> None:
    if not player_ship.is_player():
        return
    user = ctx.users().user(player_ship.pilot_id())
    if user is None:
        return

    game_protocol = user.protocol_of(ProtocolID.Game)
    for slot_id in slot_ids:
        ctx.sender().push_to(game_protocol.replies.stop_slot_ability(slot_id), user)
