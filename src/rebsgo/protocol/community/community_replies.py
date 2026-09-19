# github.com/Shran21
from __future__ import annotations

from rebsgo.world.carriers.carrier_mode import is_carrier_ship_card
from rebsgo.protocol.messages import CommunityReply
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.reply_base import ReplyBase


class _FriendDesc:
    def __init__(self, player_id: int, player_name: str):
        self._player_id = player_id
        self._player_name = player_name

    def to_wire(self, bw) -> None:
        bw.write_uint32(self._player_id)
        bw.write_string(self._player_name)


class CommunityReplies(ReplyBase):
    UZENETEK = {
        "required_recruit_level": (CommunityReply.RecruitLevel.int_value, [('uint32', 'level')]),
        "friend_invite": (CommunityReply.FriendInvite.int_value, [('uint32', 'inviter_id')]),
        "friend_accept": (CommunityReply.FriendAccept.int_value, [('uint32', 'player_id'), ('byte', 'result')]),
        "friend_remove": (CommunityReply.FriendRemove.int_value, [('uint32', 'friend_id')]),
        "chat_session_id": (CommunityReply.ChatSessionId.int_value, [('string', 'chat_session_id'), ('uint32', 'chat_project_id'), ('string', 'chat_language'), ('string', 'chat_server_url')]),
        "guild_start_error": (CommunityReply.GuildStartError.int_value, [('string', 'name_already_taken')]),
        "guild_quit": (CommunityReply.GuildQuit.int_value, []),
        "guild_remove": (CommunityReply.GuildRemove.int_value, [('uint32', 'player_id'), ('boolean', 'is_self_leave')]),
        "guild_invite": (CommunityReply.GuildInvite.int_value, [('uint32', 'guild_id'), ('string', 'guild_name'), ('uint32', 'inviter_id')]),
        "guild_info": (CommunityReply.GuildInfo.int_value, [('desc', 'guild_info_message')]),
        "guild_set_promotion": (CommunityReply.GuildSetPromotion.int_value, [('desc', 'guild_member_promotion_message')]),
        "guild_member_update": (CommunityReply.GuildMemberUpdate.int_value, [('desc', 'new_guild_member_info')]),
        "guild_invite_result": (CommunityReply.ClanInviteResult.int_value, [('desc', 'guild_invite_result_message')]),
        "guild_operation_result": (CommunityReply.ClanOperationResult.int_value, [('desc', 'guild_operation_result_message')]),
        "party_chat_invite_failed": (CommunityReply.PartyChatInviteFailed.int_value, [('string', 'user_name_to_invite')]),
        "party_anchor": (CommunityReply.PartyAnchor.int_value, [('uint32', 'carrier_player_id'), ('uint32', 'anchor_player_id'), ('boolean', 'is_anchored')]),
        "guild_set_change_permissions": (CommunityReply.GuildSetChangePermissions.int_value, [('byte', 'guild_role.value'), ('uint64', 'new_permissions')]),
        "guild_join_error": (CommunityReply.ClanJoinError.int_value, [('string', 'requested_wing_name'), ('byte', 'guild_join_error.byte')]),
        "guild_set_change_rank_name": (CommunityReply.GuildSetChangeRankName.int_value, [('byte', 'guild_role.value'), ('string', 'new_rank_name')]),
    }

    def __init__(self):
        super().__init__(ProtocolID.Community)

    def party(self, party):
        if party is None:
            return self.no_party()
        bw = self.new_message()
        bw.write_msg_type(CommunityReply.Squad.int_value)
        bw.write_uint32(party.party_id())
        bw.write_uint32(party.leader().pilot_of().user_id_of())
        members_ids_without_leader = {tag.pilot_of().user_id_of()
                                      for tag in party.members_without_leader()}
        bw.write_uint32_collection(members_ids_without_leader)
        bw.write_uint32_collection(self._get_carrier_member_ids(party))
        return bw

    @staticmethod
    def _get_carrier_member_ids(party):
        carrier_ids = set()
        for tag in party.members():
            player = tag.pilot_of()
            if not hasattr(player, "hangar_of"):
                continue
            hangar = player.hangar_of()
            if hangar is None:
                continue
            active_ship = hangar.active_ship()
            if active_ship is None:
                continue
            if is_carrier_ship_card(active_ship.ship_card_of()):
                carrier_ids.add(player.user_id_of())
        return carrier_ids

    def no_recruits(self):
        bw = self.new_message()
        bw.write_msg_type(CommunityReply.Recruits.int_value)
        bw.write_length(0)
        return bw

    def friend_add(self, friend_descs):
        bw = self.new_message()
        bw.write_msg_type(CommunityReply.FriendAdd.int_value)
        bw.write_desc_collection([
            desc if hasattr(desc, "to_wire") else _FriendDesc(desc[0], desc[1])
            for desc in friend_descs
        ])
        return bw

    def no_party(self):
        bw = self.new_message()
        bw.write_msg_type(CommunityReply.Squad.int_value)
        bw.write_uint32(0)
        bw.write_uint32(0)
        bw.write_length(0)
        bw.write_length(0)
        return bw

    def party_ignore(self, character_name: str, mar_csapatban: bool):
        bw = self.new_message()
        bw.write_msg_type(CommunityReply.PartyIgnore.int_value)
        bw.write_string(character_name)
        bw.write_byte(1 if mar_csapatban else 0)
        return bw

    def squad_invite(self, party):
        bw = self.new_message()
        bw.write_msg_type(CommunityReply.PartyInvite.int_value)
        bw.write_uint32(party.party_id())
        bw.write_uint32(party.leader().pilot_of().user_id_of())
        bw.write_string(party.leader().pilot_of().name)
        return bw

    def party_member_ftl_state(self, csapat_ugras_allapotok):
        bw = self.new_message()
        bw.write_msg_type(CommunityReply.SquadJumpState.int_value)
        bw.write_length(len(csapat_ugras_allapotok))
        for bejegyzes in csapat_ugras_allapotok:
            bw.write_uint32(bejegyzes.user().pilot_of().user_id_of())
            bw.write_byte(bejegyzes.state.value)
        return bw
