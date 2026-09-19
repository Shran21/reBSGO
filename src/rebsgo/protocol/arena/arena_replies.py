# github.com/Shran21
from __future__ import annotations

from rebsgo.protocol.messages import ArenaReply
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.reply_base import ReplyBase


class ArenaReplies(ReplyBase):
    UZENETEK = {
        "arena_duel_invite_slave": (
            ArenaReply.ArenaDuelInviteSlave.short_value,
            [("uint32", "challenger_player_id"), ("date_time", "expiry_time")]),
        "arena_invite": (
            ArenaReply.ArenaInvite.short_value,
            [("date_time", "expiry_time")]),
        "arena_back_to_queue": (
            ArenaReply.ArenaBackToQueue.short_value,
            [("uint32", "player_id"), ("byte", "reason")]),
        "arena_failed": (
            ArenaReply.ArenaFailed.short_value,
            [("uint32", "player_id"), ("byte", "reason")]),
        "arena_won": (
            ArenaReply.ArenaWon.short_value,
            [("guid", "reward_guid"), ("uint32", "counter_type"),
             ("int32", "old_value"), ("int32", "new_value")]),
        "arena_lost": (
            ArenaReply.ArenaLost.short_value,
            [("uint32", "counter_type"), ("int32", "old_value"),
             ("int32", "new_value")]),
        "arena_init": (
            ArenaReply.ArenaInit.short_value,
            [("date_time", "time_begin"), ("date_time", "time_end"),
             ("uint32", "mark_object_id"), ("uint32", "own_object_id")]),
        "arena_out_of_range": (
            ArenaReply.ArenaOutOfRange.short_value,
            [("uint32", "object_id"), ("date_time", "time")]),
        "arena_capture_point": (
            ArenaReply.ArenaCapturePoint.short_value,
            [("uint32", "object_id"), ("date_time", "time")]),
        "arena_out_of_capture_point": (
            ArenaReply.ArenaOutOfCapturePoint.short_value,
            [("uint32", "object_id")]),
        "arena_respawn": (
            ArenaReply.ArenaRespawn.short_value,
            [("uint32", "player_id"), ("date_time", "respawn_time")]),
    }

    def __init__(self):
        super().__init__(ProtocolID.Arena)

    def simple(self, server_message):
        bw = self.new_message()
        bw.write_msg_type(server_message.short_value)
        return bw

    @property
    def arena_closed(self):
        return self.simple(ArenaReply.ArenaClosed)

    @property
    def arena_party_found(self):
        return self.simple(ArenaReply.ArenaPartyFound)

    @property
    def arena_outer_range_ok(self):
        return self.simple(ArenaReply.ArenaOuterRangeOk)
