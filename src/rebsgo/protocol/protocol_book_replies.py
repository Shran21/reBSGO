# github.com/Shran21

from __future__ import annotations

from rebsgo.protocol.community.community_replies import CommunityReplies
from rebsgo.protocol.debug.debug_replies import DebugReplies
from rebsgo.protocol.game.game_replies import GameReplies
from rebsgo.protocol.login import LoginReplies
from rebsgo.protocol.notification import NotificationReplies
from rebsgo.protocol.pilot.pilot_replies import PilotReplies
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.watching.watching import WatchReplies
from rebsgo.protocol.starmap import StarmapReplies

VALASZOK = {
    ProtocolID.Login: LoginReplies(),
    ProtocolID.Notification: NotificationReplies(),
    ProtocolID.Pilot: PilotReplies(),
    ProtocolID.Subscribe: WatchReplies(),
    ProtocolID.Community: CommunityReplies(),
    ProtocolID.Universe: StarmapReplies(),
    ProtocolID.Debug: DebugReplies(),
    ProtocolID.Game: GameReplies(),
}


def replies_for(protocol_id: ProtocolID):
    return VALASZOK.get(protocol_id)


def game_replies() -> GameReplies:
    return VALASZOK[ProtocolID.Game]


def debug_message(message: str):
    return VALASZOK[ProtocolID.Debug].message(message)
