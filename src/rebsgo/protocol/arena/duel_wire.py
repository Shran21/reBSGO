# github.com/Shran21
from __future__ import annotations

from contextlib import suppress

import logging
from enum import Enum

from rebsgo.protocol.arena.arena_replies import ArenaReplies
from rebsgo.protocol.wire_base import BgoProtocol
from rebsgo.protocol.protocol_id import ProtocolID


log = logging.getLogger(__name__)


class _ClientMessage(Enum):
    Arena1vs1CheckIn = 1
    Arena3vs3MixedCheckIn = 2
    Arena3vs3MixedRandomCheckIn = 3
    ArenaDuelCheckIn = 4
    ArenaCancelCheckIn = 5
    ArenaInviteOk = 6
    ArenaInviteCancel = 7
    ArenaClose = 8

    @staticmethod
    def from_code(value: int):
        return _CM_BY_VALUE.get(value)


_CM_BY_VALUE = {member.value: member for member in _ClientMessage}

_CHECK_IN_MESSAGES = frozenset({
    _ClientMessage.Arena1vs1CheckIn, _ClientMessage.Arena3vs3MixedCheckIn,
    _ClientMessage.Arena3vs3MixedRandomCheckIn,
})


class ArenaProtocol(BgoProtocol):
    def __init__(self, ctx):
        super().__init__(ProtocolID.Arena, ctx)
        self._writer = ArenaReplies()

    def read_message(self, msg_type: int, br) -> None:
        client_message = _ClientMessage.from_code(msg_type)
        if client_message is None:
            log.error("ArenaProtocol could not handle reply_type: %s", msg_type)
            return
        manager = self._arena_desk()
        if client_message == _ClientMessage.ArenaDuelCheckIn:
            target_player_id = br.read_uint32()
            manager.duel_invite(self.user(), target_player_id)
        elif client_message in _CHECK_IN_MESSAGES:
            manager.check_in(self.user(), client_message.value)
        elif client_message == _ClientMessage.ArenaInviteOk:
            manager.invite_ok(self.user())
        elif client_message in (_ClientMessage.ArenaCancelCheckIn, _ClientMessage.ArenaInviteCancel,
                                _ClientMessage.ArenaClose):
            manager.cancel_check_in(self.user())
        else:
            log.error("ArenaProtocol could not handle reply_type: %s", client_message)

    def on_gone(self) -> None:
        with suppress(Exception):
            if (user := self.user()) is not None:
                self._arena_desk().on_gone(user)

    @staticmethod
    def _arena_desk():
        from rebsgo.services import Services
        from rebsgo.protocol.arena.arena_desk import ArenaDesk
        return Services.get(ArenaDesk)
