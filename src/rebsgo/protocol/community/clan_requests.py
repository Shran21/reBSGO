# github.com/Shran21
from __future__ import annotations

import logging

from rebsgo.pilots.together.clan import ClanInfoReply, ClanInvite, ClanPromotionReply
from rebsgo.protocol.messages import CommunityRequest
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.vocabulary.community import ClanOperation, ClanRole

log = logging.getLogger(__name__)


class ClanRequests:
    def __init__(self, pilot_roster, guild_registry, writer):
        self._pilot_roster = pilot_roster
        self._guild_registry = guild_registry
        self._user = None
        self._community_protocol = None
        self._writer = writer

    def seed_user(self, user) -> None:
        self._user = user
        self._community_protocol = user.protocol_of(ProtocolID.Community)
        player = user.pilot_of()
        if player.guild() is None:
            guild = self._guild_registry.guild_of_player_id(player.user_id_of())
            if guild is not None:
                player.join_guild(guild)

    KEZELOK = {
        CommunityRequest.GuildChangeRankName: "_on_guild_change_rank_name",
        CommunityRequest.GuildChangeRankPermissions: "_on_guild_change_rank_permissions",
        CommunityRequest.GuildInvite: "_on_guild_invite",
        CommunityRequest.GuildAccept: "_on_guild_accept",
        CommunityRequest.GuildKick: "_on_guild_kick",
        CommunityRequest.GuildLeave: "_on_guild_leave",
        CommunityRequest.GuildPromote: "_on_guild_promote",
        CommunityRequest.GuildStart: "_on_guild_start",
    }

    def handle_message(self, client_message, br) -> None:
        current_player = self._user.pilot_of()
        guild = current_player.guild()
        kezelo = self.KEZELOK.get(client_message)
        if kezelo is None:
            return
        getattr(self, kezelo)(client_message, br, current_player, guild)

    def _on_guild_change_rank_name(self, client_message, br, current_player, guild) -> None:
        uint_role = br.read_uint32()
        role_name = br.read_string()
        if guild is None:
            log.error('%srank rename with no guild behind it', self._user.user_log())
            return
        can_change_rank_names = guild.allowed(current_player.user_id_of(), ClanOperation.ChangeRankNames)
        if not can_change_rank_names:
            log.error('%srank rename without the right to do so', self._user.user_log())
            return
        guild_role = ClanRole.from_code(uint_role)
        renamed = guild.rename_rank(guild_role, role_name)
        if not renamed:
            return
        self.tell_guild(guild, self._writer.guild_set_change_rank_name(guild_role, role_name))

    def _on_guild_change_rank_permissions(self, client_message, br, current_player, guild) -> None:
        uint_role = br.read_uint32()
        new_permissions = br.read_int64()
        if guild is None:
            log.error('%srank permission change with no guild behind it', self._user.user_log())
            return
        can_change_permissions = guild.allowed(current_player.user_id_of(), ClanOperation.ChangePermissions)
        if not can_change_permissions:
            return
        role = ClanRole.from_code(uint_role)
        if role is None:
            return
        guild.reset_role_rights(role, new_permissions)
        change_role_bw = self._community_protocol.replies.guild_set_change_permissions(role, new_permissions)
        self.tell_guild(guild, change_role_bw)

    def _on_guild_invite(self, client_message, br, current_player, guild) -> None:
        player_id = br.read_uint32()
        if guild is None:
            log.error('%sguild invite from a guild that is unresolvable', self._user.user_log())
            return
        has_invite_permissions = guild.allowed(current_player.user_id_of(), ClanOperation.Invite)
        log.info('%sguild invite, checking the right to send it: %s', self._user.user_log(),
                 has_invite_permissions)
        if not has_invite_permissions:
            return

        self._guild_registry.guild_send_to_history.add(
            ClanInvite(current_player.user_id_of(), player_id, guild.id))
        if (usr := self._pilot_roster.by_id(player_id)) is not None:
            usr.send(self._writer.guild_invite(guild.id, guild.name,
                                               current_player.user_id_of()))

    def _on_guild_accept(self, client_message, br, current_player, guild) -> None:
        uint_guild_id = br.read_uint32()
        inviter_id = br.read_uint32()
        accepted = br.read_boolean()

        if guild is not None:
            log.error('%s accepted a guild invite while already a member %s',
                      self._user.user_log(), current_player.user_id_of())
            return

        if not accepted:
            return

        inviting_history = self._guild_registry.guild_send_to_history
        bejegyzes = ClanInvite(inviter_id, current_player.user_id_of(), uint_guild_id)
        was_invited = bejegyzes in inviting_history
        inviting_history.discard(bejegyzes)
        if not was_invited:
            log.error('%s tried to slip into a clan uninvited: user_id %s, clan %s,'
                      ' naming %s as the inviter', self._user.user_log(),
                      current_player.user_id_of(), uint_guild_id, inviter_id)
            return

        accept_guild = self._guild_registry.guild(uint_guild_id)
        if accept_guild is None:
            log.error('%sAccepted guild was not present in guild_registry!',
                      self._user.user_log())
            return
        accepted_guild = accept_guild
        accepted_guild.enrol(self._user.pilot_of(), ClanRole.Recruit)
        current_player.join_guild(accepted_guild)
        self._user.send(self._writer.guild_info(ClanInfoReply(accepted_guild)))
        member_info = accepted_guild.guild_member_info_of(current_player.user_id_of())
        if member_info is not None:
            self.tell_guild(accepted_guild, self._writer.guild_member_update(member_info))

    def _on_guild_kick(self, client_message, br, current_player, guild) -> None:
        player_to_kick = br.read_uint32()
        if guild is None:
            return
        if (guild_member_info := guild.guild_member_info_of(player_to_kick)) is None:
            log.warning('%s asked to kick a guild member, but named nobody', self._user.user_log())
            return
        if (usr_to_kick := self._pilot_roster.by_id(player_to_kick)) is not None:
            usr_to_kick.pilot_of().join_guild(None)
            usr_to_kick.send(self._writer.guild_remove(usr_to_kick.pilot_of().user_id_of(), False))

        has_kick_permissions = guild.allowed(current_player.user_id_of(), ClanOperation.KickMember)
        if not has_kick_permissions:
            log.error('%skick denied for lack of rank', self._user.user_log())
        guild.remove_player(player_to_kick)

        guild_kick_bw = self._writer.guild_remove(player_to_kick, False)
        self.tell_guild(guild, guild_kick_bw)

    def _on_guild_leave(self, client_message, br, current_player, guild) -> None:
        if guild is None:
            return
        was_present = guild.remove_player(current_player.user_id_of())
        if not was_present:
            log.error('%sguild removal for someone the guild never listed',
                      self._user.user_log())
            return

        guild_leave_bw = self._writer.guild_remove(current_player.user_id_of(), True)
        self.tell_guild(guild, guild_leave_bw)
        self._user.send(self._writer.guild_quit())
        guild.remove_player(current_player.user_id_of())
        new_guild_member_info = guild.ensure_leader()
        if new_guild_member_info is not None:
            self.tell_guild(guild, self._writer.guild_member_update(new_guild_member_info))
        current_player.join_guild(None)

    def _on_guild_promote(self, client_message, br, current_player, guild) -> None:
        player_id = br.read_uint32()
        role = br.read_uint32()
        if guild is None:
            log.error('%sClan promote player but player has no guild to promote first user!',
                      self._user.user_log())
            return
        promoting_player = guild.guild_member_info_of(current_player.user_id_of())
        if promoting_player is None:
            log.error('%sthe pilot doing the promoting is not on the clan roster',
                      self._user.user_log())
            return
        to_promote_demote_member = guild.guild_member_info_of(player_id)
        if to_promote_demote_member is None:
            log.error('%sthe pilot being promoted is not on the clan roster',
                      self._user.user_log())
            return
        member_to_promote_or_demote = to_promote_demote_member
        new_role = ClanRole.from_code(role)
        if new_role is None:
            log.error('no such clan rank')
            return
        member_to_promote_or_demote.grant_role(new_role)
        guild_member_promotion_message = ClanPromotionReply(player_id, new_role)
        bw = self._writer.guild_set_promotion(guild_member_promotion_message)
        self.tell_guild(guild, bw)

    def _on_guild_start(self, client_message, br, current_player, guild) -> None:
        guild_name = br.read_string()
        if guild is not None:
            log.warning('%sguild founding blocked - founder already belongs to one',
                        self._user.user_log())
            return
        try:
            new_guild = self._guild_registry.ensure_guild(guild_name)
            log.info('%sguild founded %s', self._user.user_log(), guild_name)
            new_guild.enrol(self._user.pilot_of(), ClanRole.Leader)
            current_player.join_guild(new_guild)

            self._user.send(self._writer.guild_info(ClanInfoReply(new_guild)))
        except ValueError:
            bw = self._community_protocol.replies.guild_start_error(guild_name)
            self._user.send(bw)


    def tell_guild(self, guild, bw) -> None:
        for guild_member_info in guild.wing_roster:
            user = self._pilot_roster.by_id(guild_member_info.pilot_id())
            if user is not None:
                user.send(bw)
