# github.com/Shran21
from __future__ import annotations

from rebsgo.protocol.messages import DebugReply
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.reply_base import ReplyBase


class DebugReplies(ReplyBase):
    UZENETEK = {
        "update_roles": (
            DebugReply.UpdateRoles.int_value,
            [("uint32", "new_role_bits")]),
        "process_state": (
            DebugReply.ProcessState.int_value,
            [("string", "state")]),
    }

    def __init__(self):
        super().__init__(ProtocolID.Debug)

    def message(self, msg: str):
        bw = self.new_message()
        bw.write_msg_type(DebugReply.Message.value)
        bw.write_string(str(msg))
        return bw

    def command(self, msg: str):
        bw = self.new_message()
        bw.write_msg_type(DebugReply.Command.int_value)
        bw.write_string(str(msg))
        return bw
