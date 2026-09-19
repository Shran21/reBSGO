# github.com/Shran21

from __future__ import annotations

from abc import abstractmethod

from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.reply_base import ReplyBase
from rebsgo.helpers.log_tags import tag


class BgoProtocol(ReplyBase):
    def __init__(self, protocol_id: ProtocolID, ctx):
        super().__init__(protocol_id)
        self._user_id = -1
        self.ctx = ctx

    def user(self):
        return self.ctx.user()

    def seed_user(self, user) -> None:
        self.ctx.user(user)
        if user is not None:
            if self._user_id == -1:
                self._user_id = user.pilot_of().user_id_of()
            tag("userID", str(user.pilot_of().user_id_of()))
        self.mount_handlers()

    def mount_handlers(self) -> None:
        pass

    @abstractmethod
    def read_message(self, msg_type: int, br) -> None:
        ...

    def on_gone(self) -> None:
        pass

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if type(other) is not type(self):
            return NotImplemented
        if not super().__eq__(other):
            return False
        return self._user_id == other._user_id

    def __hash__(self) -> int:
        return hash((ReplyBase.__hash__(self), self._user_id))
