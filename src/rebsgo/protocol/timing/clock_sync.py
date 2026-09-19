# github.com/Shran21
from __future__ import annotations

import time

from rebsgo.protocol.wire_base import BgoProtocol
from rebsgo.protocol.protocol_id import ProtocolID


class SyncProtocol(BgoProtocol):
    def __init__(self, ctx):
        super().__init__(ProtocolID.Sync, ctx)

    def read_message(self, msg_type: int, br) -> None:
        if msg_type == 0:
            self.user().send(self.write_sync_reply())

    def write_sync_reply(self):
        bw = self.new_message()
        bw.write_msg_type(1)
        bw.write_int64(int(time.time() * 1000))
        return bw
