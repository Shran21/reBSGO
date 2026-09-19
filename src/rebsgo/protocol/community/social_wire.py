# github.com/Shran21
from __future__ import annotations

from rebsgo.protocol.messages import CommunityRequest

import logging

from rebsgo.services import Services
from rebsgo.protocol.wire_base import BgoProtocol
from rebsgo.protocol.community.community_replies import CommunityReplies
from rebsgo.protocol.community.clan_join_error import ClanJoinError as _GuildJoinError
from rebsgo.protocol.community.clan_requests import ClanRequests
from rebsgo.protocol.community.squad_requests import SquadRequests
from rebsgo.protocol.protocol_id import ProtocolID


log = logging.getLogger(__name__)

_FRIEND_ACCEPTED = 1
_FRIEND_DECLINED = 2
_FRIEND_ALREADY_FRIEND = 3
_FRIEND_FAILED = 4


class CommunityProtocol(BgoProtocol):
    ClanJoinError = _GuildJoinError

    def __init__(self, ctx, pilot_roster, csapat_nyilvantarto, guild_registry, nemitas,
                 data_store=None):
        super().__init__(ProtocolID.Community, ctx)
        from rebsgo.chat.client.chat_link import ChatLink
        self._chat_api = Services.get(ChatLink)
        self._writer = CommunityReplies()
        self._pilot_roster = pilot_roster
        self._data_store = data_store
        self._guild_processing = ClanRequests(pilot_roster, guild_registry, self._writer)
        self._party_processing = SquadRequests(pilot_roster, csapat_nyilvantarto, self._writer)
        self._guild_registry = guild_registry
        self._chat_session_initialized = False
        self._chat_connected = False
        self._chat_access_blocker = nemitas

    @property
    def replies(self) -> CommunityReplies:
        return self._writer

    def seed_user(self, user) -> None:
        super().seed_user(user)
        self._guild_processing.seed_user(user)
        self._party_processing.seed_user(user)
        self._chat_session_initialized = False

    def on_gone(self) -> None:
        self._party_processing.drop_invites()

    @property
    def guild_processing(self) -> ClanRequests:
        return self._guild_processing

    @property
    def party_processing(self) -> SquadRequests:
        return self._party_processing

    KEZELOK = {
        CommunityRequest.RecruitLevel: "_on_recruit_level",
        CommunityRequest.FriendInvite: "_on_friend_invite",
        CommunityRequest.FriendAccept: "_on_friend_accept",
        CommunityRequest.FriendRemove: "_on_friend_remove",
        CommunityRequest.IgnoreAdd: "_on_ignore_add",
        CommunityRequest.ChatFleetAllowed: "_on_chat_fleet_allowed",
        CommunityRequest.ChatAuthFailed: "_on_chat_auth_failed",
        CommunityRequest.ChatConnected: "_on_chat_connected",
    }

    def read_message(self, msg_type, br) -> None:
        client_message = CommunityRequest.from_code(msg_type)
        user_char = self.user().pilot_of()
        self._party_processing.handle_message(client_message, br)
        self._guild_processing.handle_message(client_message, br)
        kezelo = self.KEZELOK.get(client_message)
        if kezelo is None:
            return
        getattr(self, kezelo)(msg_type, br)

    def _on_recruit_level(self, msg_type, br) -> None:
        szint = 0
        self.user().send(self._writer.required_recruit_level(szint))

    def _on_friend_invite(self, msg_type, br) -> None:
        friend_id = br.read_uint32()
        self._handle_friend_invite(friend_id)

    def _on_friend_accept(self, msg_type, br) -> None:
        player_id = br.read_uint32()
        ertek = br.read_byte()
        if not (ertek == 2 or ertek == 1):
            pass
        accepted = ertek == 1
        self._handle_friend_accept(player_id, accepted)

    def _on_friend_remove(self, msg_type, br) -> None:
        player_id = br.read_uint32()
        self._handle_friend_remove(player_id)

    def _on_ignore_add(self, msg_type, br) -> None:
        player_name = br.read_string()

    def _on_chat_fleet_allowed(self, msg_type, br) -> None:
        br.read_uint16()

    def _on_chat_auth_failed(self, msg_type, br) -> None:
        session_id = br.read_string()
        log.info('chat identification failed %s', self.user().user_log_simple)
        self._chat_connected = False

    def _on_chat_connected(self, msg_type, br) -> None:
        session_id = br.read_string()
        self._chat_connected = True
        player = self.user().pilot_of()
        self._chat_api.send_user_position(player.user_id_of(),
                                          player.location.sector_id,
                                          player.faction.value)
        if (party := player.party()) is not None:
            self._chat_api.squad_membership_changed(player.user_id_of(), party.party_id())
        if (klan := self._guild_registry.guild_of_player_id(player.user_id_of())) is not None:
            self._chat_api.guild_joined(player.user_id_of(), klan.id)


    @property
    def is_chat_connected(self) -> bool:
        return self._chat_connected

    def _handle_friend_invite(self, friend_id: int) -> None:
        current_user = self.user()
        current_player = current_user.pilot_of()
        current_player_id = current_player.user_id_of()
        if friend_id == current_player_id:
            current_user.send(self._writer.friend_accept(friend_id, _FRIEND_FAILED))
            return

        target_user = self._pilot_roster.by_id(friend_id)
        if (target_user is None or target_user.pilot_of() is None
            or not target_user.is_connected()):
            current_user.send(self._writer.friend_accept(friend_id, _FRIEND_FAILED))
            return

        current_friends = current_player.friends
        if current_friends.is_friend(friend_id):
            self._send_player_name(target_user.pilot_of(), current_user)
            current_user.send(self._writer.friend_accept(friend_id, _FRIEND_ALREADY_FRIEND))
            self._send_friend_list(current_user)
            return

        target_user.pilot_of().friends.note_invite(current_player_id)
        self._send_player_name(current_player, target_user)
        target_user.send(self._writer.friend_invite(current_player_id))

    def _handle_friend_accept(self, inviter_id: int, accepted: bool) -> None:
        current_user = self.user()
        current_player = current_user.pilot_of()
        current_player_id = current_player.user_id_of()
        current_friends = current_player.friends

        invite_was_pending = current_friends.befriend(inviter_id)
        inviter_user = self._pilot_roster.by_id(inviter_id)
        if inviter_user is None or inviter_user.pilot_of() is None:
            current_user.send(self._writer.friend_accept(inviter_id, _FRIEND_FAILED))
            return
        inviter_player = inviter_user.pilot_of()

        self._send_player_name(inviter_player, current_user)
        self._send_player_name(current_player, inviter_user)

        if not accepted:
            inviter_user.send(self._writer.friend_accept(current_player_id, _FRIEND_DECLINED))
            return

        if not invite_was_pending and not current_friends.is_friend(inviter_id):
            current_user.send(self._writer.friend_accept(inviter_id, _FRIEND_FAILED))
            return

        current_friends.befriend_pilot(inviter_id)
        inviter_player.friends.befriend_pilot(current_player_id)
        if self._data_store is not None:
            self._data_store.record_friendship(current_player_id, inviter_id)

        current_user.send(self._writer.friend_accept(inviter_id, _FRIEND_ACCEPTED))
        inviter_user.send(self._writer.friend_accept(current_player_id, _FRIEND_ACCEPTED))
        self._send_friend_list(current_user)
        self._send_friend_list(inviter_user)

    def _handle_friend_remove(self, friend_id: int) -> None:
        current_user = self.user()
        current_player = current_user.pilot_of()
        current_player.friends.remove_friend(friend_id)
        current_user.send(self._writer.friend_remove(friend_id))
        if self._data_store is not None:
            self._data_store.forget_friendship(current_player.user_id_of(), friend_id)

        target_user = self._pilot_roster.by_id(friend_id)
        if target_user is None or target_user.pilot_of() is None:
            return
        target_user.pilot_of().friends.remove_friend(current_player.user_id_of())
        target_user.send(self._writer.friend_remove(current_player.user_id_of()))

    def push_friend_list(self) -> None:
        user = self.user()
        if user is None or user.pilot_of() is None:
            return
        self._send_friend_list(user)

    def _send_friend_list(self, user) -> None:
        friend_ids = user.pilot_of().friends.friend_ids()
        hianyzo_nevek = {}
        for friend_id in friend_ids:
            friend_user = self._pilot_roster.by_id(friend_id)
            if friend_user is None or friend_user.pilot_of() is None:
                hianyzo_nevek[friend_id] = None
        if hianyzo_nevek and self._data_store is not None:
            hianyzo_nevek.update(self._data_store.friend_names(hianyzo_nevek))

        descs = []
        for friend_id in friend_ids:
            friend_user = self._pilot_roster.by_id(friend_id)
            if friend_user is not None and friend_user.pilot_of() is not None:
                descs.append((friend_id, friend_user.pilot_of().name))
                continue
            nev = hianyzo_nevek.get(friend_id)
            if nev:
                descs.append((friend_id, nev))
        user.send(self._writer.friend_add(descs))

    def _send_player_name(self, player, recipient_user) -> None:
        try:
            subscribe_protocol = recipient_user.protocol_of(ProtocolID.Subscribe)
            recipient_user.send(subscribe_protocol.replies.player_name(player.user_id_of(), player.name))
        except Exception:
            log.debug("friend player-name pre-send failed", exc_info=True)

    def push_chat_session(self, chat_session_id: str, chat_project_id: int, chat_language: str,
                          chat_cim: str) -> None:
        can_access_chat = self._chat_access_blocker.may_chat(self._user_id)
        if not can_access_chat:
            notification_protocol = self.user().protocol_of(ProtocolID.Notification)
            self.user().send(notification_protocol.replies.debug_message('chat blacklist'))
            return
        bw = self._writer.chat_session_id(chat_session_id, chat_project_id, chat_language, chat_cim)
        self._chat_session_initialized = True
        self.user().send(bw)

    @property
    def chat_session_ready(self) -> bool:
        return self._chat_session_initialized

    def resend_chat_session_id(self) -> None:
        chat_server_url = self.ctx.server_config.chat_server_address or ""
        trimmed = chat_server_url.strip()
        if len(trimmed) == 0 or trimmed == "127.0.0.1" or trimmed.lower() == "localhost":
            local_address = self.ctx.connection().local_host_address()
            if local_address.strip() != "":
                trimmed = local_address
        self.push_chat_session("", 860, "us", trimmed)
