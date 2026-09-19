# github.com/Shran21
from __future__ import annotations

from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.messages import SettingReply
from rebsgo.protocol.reply_base import ReplyBase


class SettingReplies(ReplyBase):
    UZENETEK = {
        "input_bindings": (
            SettingReply.Keys.value,
            [("desc", "input_bindings")]),
        "settings": (SettingReply.Settings.value, [("desc", "user_settings")]),
    }

    def __init__(self):
        super().__init__(ProtocolID.Setting)
