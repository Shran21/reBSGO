# github.com/Shran21
from __future__ import annotations

from rebsgo.vocabulary.world import ObjectKind

CARRIER_TRANSPONDER_TARGET_ID_PREFIX = ObjectKind.SpaceLocationMarker.value
CARRIER_TRANSPONDER_TARGET_ID_PREFIX_MASK = 0xF0000000
CARRIER_TRANSPONDER_PLAYER_ID_MASK = 0x0FFFFFFF


def carrier_transponder_space_id(player_id: int) -> int:
    if player_id <= 0 or player_id > CARRIER_TRANSPONDER_PLAYER_ID_MASK:
        raise ValueError(f'player_id out of carrier transponder target id range: {player_id}')
    return CARRIER_TRANSPONDER_TARGET_ID_PREFIX | player_id


def try_get_carrier_transponder_player_id(space_id: int) -> int | None:
    if (space_id & CARRIER_TRANSPONDER_TARGET_ID_PREFIX_MASK) != CARRIER_TRANSPONDER_TARGET_ID_PREFIX:
        return None
    player_id = space_id & CARRIER_TRANSPONDER_PLAYER_ID_MASK
    return player_id if player_id > 0 else None
