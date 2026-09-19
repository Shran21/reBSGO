# github.com/Shran21
from __future__ import annotations

import logging

from rebsgo.pilots.together.squad import SquadInvite
from rebsgo.protocol.messages import CommunityRequest
from rebsgo.protocol.community.squad_jump_row import SquadJumpRow
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.vocabulary.world import PlaceKind
from rebsgo.vocabulary.community import SquadJumpState

log = logging.getLogger(__name__)


class SquadRequests:
    def __init__(self, pilot_roster, csapat_nyilvantarto, writer):
        self._pilot_roster = pilot_roster
        self._party_registry = csapat_nyilvantarto
        self._user = None
        self._community_protocol = None
        self._writer = writer

    def seed_user(self, user) -> None:
        self._user = user
        self._community_protocol = user.protocol_of(ProtocolID.Community)

    KEZELOK = {
        CommunityRequest.SquadJumpState: "_on_squad_jump_state",
        CommunityRequest.PartyChatInvite: "_on_party_chat_invite",
        CommunityRequest.PartyInvitePlayer: "_on_party_invite_player",
        CommunityRequest.PartyAppointLeader: "_on_party_appoint_leader",
        CommunityRequest.PartyAccept: "_on_party_accept",
        CommunityRequest.PartyDismissPlayer: "_on_party_dismiss_player",
        CommunityRequest.PartyLeave: "_on_party_leave",
    }

    def handle_message(self, client_message, br) -> None:
        current_player = self._user.pilot_of()
        current_party = current_player.party()
        kezelo = self.KEZELOK.get(client_message)
        if kezelo is None:
            return
        getattr(self, kezelo)(client_message, br, current_party, current_player)

    def _on_squad_jump_state(self, client_message, br, current_party, current_player) -> None:
        party_member_ids = br.read_uint32_array()
        if current_party is None:
            log.error('%sparty jump state asked with no party around', self._user.user_log())
            return
        party = current_party
        any_outside_party = any(not party.is_in_party(id) for id in party_member_ids)
        if any_outside_party:
            log.error('%san id in the list is outside the party', self._user.user_log())
            return
        party_jump_users = party.party_users_by_ids(party_member_ids)
        ftl_records = []
        init_location = current_player.location
        for party_jump_user in party_jump_users:
            same_sector = party_jump_user.pilot_of().location.sector_id == init_location.sector_id
            if not same_sector:
                continue
            party_member_in_space = \
                party_jump_user.pilot_of().location.game_location == PlaceKind.Space
            if not party_member_in_space:
                continue
            party_member_is_online = party_jump_user.connection() is not None
            if not party_member_is_online:
                continue
            ftl_records.append(SquadJumpRow(party_jump_user, SquadJumpState.Ready))
        self._user.send(self._writer.party_member_ftl_state(ftl_records))

    def _on_party_chat_invite(self, client_message, br, current_party, current_player) -> None:
        user_name_to_invite = br.read_string()
        log.info('%sparty chat invite: %s', self._user.user_log(), user_name_to_invite)
        user_inv = self._get_user(user_name_to_invite)
        if user_inv is None:
            log.warning('%sinvite by name found nobody', self._user.user_log())
            return
        self._party_invite(user_inv)

    def _on_party_invite_player(self, client_message, br, current_party, current_player) -> None:
        user_id = br.read_uint32()
        log.info('%sparty invite: %s', self._user.user_log(), user_id)
        user_inv = self._get_user(user_id)
        if user_inv is None:
            log.warning('%sinvite aimed at a pilot that does not exist', self._user.user_log())
            return
        self._party_invite(user_inv)

    def _on_party_appoint_leader(self, client_message, br, current_party, current_player) -> None:
        new_leader_id = br.read_uint32()
        if current_party is None:
            log.warning('%sSquad new leader but player has no party', self._user.user_log())
            return
        party = current_party
        leader_char = party.leader().pilot_of()
        if leader_char.user_id_of() == new_leader_id:
            log.warning('%snew leader equals the old one', self._user.user_log())
            return
        party.hand_leadership_to(new_leader_id)
        self._send_to_party(party, self._community_protocol.replies.party(party))

        mixed_factions = any(
            tag.pilot_of().faction != self._user.pilot_of().faction
            for tag in party.members_copy())
        if mixed_factions:
            for tag in party.members():
                if (abstract_connection := tag.connection()) is not None:
                    abstract_connection.close_connection(
                        "a member belongs to the other faction")

    def _on_party_accept(self, client_message, br, current_party, current_player) -> None:
        party_id = br.read_uint32()
        inviter_id = br.read_uint32()
        accept = br.read_boolean()

        bejegyzes = SquadInvite(inviter_id, self._user.pilot_of().user_id_of(), party_id)
        history = self._party_registry.party_send_to_history
        was_invited = bejegyzes in history
        history.discard(bejegyzes)
        if not was_invited:
            log.error('%s tried to slip into a squad uninvited: user_id %s, squad %s,'
                      ' naming %s as the inviter', self._user.user_log(),
                      current_player.user_id_of(), party_id, inviter_id)
            return

        if current_player.party() is not None:
            log.info('%s was in a squad already', self._user.user_log())
            return

        inviter = self._get_user(inviter_id)
        if inviter is None:
            log.info('%sthe pilot who sent the invite is gone', self._user.user_log())
            return

        inviter_char = inviter.pilot_of()
        inviter_party = inviter_char.party()
        if inviter_party is None:
            log.warning('%sinvite accepted, but the squad behind it no longer exists',
                        self._user.user_log())
            return
        if inviter_party.party_id() != party_id:
            log.warning('%sSquad accept but partyID was not equal!', self._user.user_log())
            return
        if not accept:
            inviter.send(self._writer.party_ignore(current_player.name, False))
            if inviter_party.member_count() < 2:
                self._party_registry.remove_party(inviter_party.party_id())
                inviter_char.join_party(None)
            return
        inviter_party.enrol(self._user)

        self._send_to_party(inviter_party, self._community_protocol.replies.party(inviter_party))

    def _on_party_dismiss_player(self, client_message, br, current_party, current_player) -> None:
        player_id = br.read_uint32()
        if current_party is None:
            log.warning('%sdismissal without any party in existence', self._user.user_log())
            return
        if current_party.leader().pilot_of().user_id_of() != current_player.user_id_of():
            log.warning('%sdismissal requested by a non-leader', self._user.user_log())
            return
        member_removed = current_party.remove_member_by_id(player_id)
        member_removed.send(self._community_protocol.replies.no_party())
        if current_party.member_count() < 2:
            current_party.remove_member(self._user)
            self._party_registry.remove_party(current_party)
            self._user.send(self._community_protocol.replies.no_party())
        else:
            self._send_to_party(current_party, self._community_protocol.replies.party(current_party))

    def _on_party_leave(self, client_message, br, current_party, current_player) -> None:
        if current_party is None:
            log.warning('%sleft-party message from someone without a party',
                        self._user.user_log())
            return
        party = current_party
        self.eject_from_party(self._user, party)


    def eject_from_party(self, user, party) -> None:
        removed_user = party.remove_member(user)
        user.send(self._community_protocol.replies.no_party())
        if party.member_count() < 2:
            self._send_to_party(party, self._community_protocol.replies.no_party())
            for tag in party.members():
                party.remove_member(tag)
            self._party_registry.remove_party(party)
        else:
            send_party = self._community_protocol.replies.party(party)
            self._send_to_party(party, send_party)

    def _send_to_party(self, party, bw) -> None:
        for tag in party.members():
            tag.send(bw)

    def _get_user(self, azonosito_vagy_nev):
        return self._pilot_roster.anyhow(azonosito_vagy_nev)

    def _party_invite(self, meghivando) -> None:
        current_player = self._user.pilot_of()
        other_player = meghivando.pilot_of()

        if current_player.faction != other_player.faction:
            log.warning('an invite crossed the faction line, from %s to %s',
                        current_player.player_log, other_player.player_log)
            return

        current_opt_party = current_player.party()
        other_opt_party = other_player.party()

        if other_opt_party is not None:
            self._user.send(self._writer.party_ignore(other_player.name, True))
        else:
            current_party = current_opt_party if current_opt_party is not None \
                else self._party_registry.open_party(self._user)
            self._user.pilot_of().join_party(current_party)
            self._party_registry.party_send_to_history.add(
                SquadInvite(self._user.pilot_of().user_id_of(), other_player.user_id_of(),
                            current_party.party_id()))
            meghivando.send(self._writer.squad_invite(current_party))

    def drop_invites(self) -> None:
        history = self._party_registry.party_send_to_history
        to_remove = [bejegyzes for bejegyzes in history if bejegyzes.inviter == self._user.pilot_of().user_id_of()]
        for bejegyzes in to_remove:
            history.discard(bejegyzes)
