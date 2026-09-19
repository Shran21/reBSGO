# github.com/Shran21

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from rebsgo.helpers.locks import ReadWriteLock, ReentrantLock
import logging
from rebsgo.gamedata.from_json.template_readers import world_timers


class SquadInvite:
    def __init__(self, meghivo: int, meghivott_id: int, party_id: int):
        self._inviter = meghivo
        self._id_invited = meghivott_id
        self._party_id = party_id

    @property
    def inviter(self) -> int:
        return self._inviter

    @property
    def id_invited(self) -> int:
        return self._id_invited

    def party_id(self) -> int:
        return self._party_id

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not isinstance(other, SquadInvite):
            return False
        return (self._inviter == other._inviter and self._id_invited == other._id_invited
                and self._party_id == other._party_id)

    def __hash__(self) -> int:
        return hash((self._inviter, self._id_invited, self._party_id))

    def __repr__(self) -> str:
        return f'<{self._inviter} asks {self._id_invited} into squad {self._party_id}>'


log = logging.getLogger(__name__)


def _notify_chat_party(user_id: int, party_id: int) -> None:
    try:
        from rebsgo.services import Services
        from rebsgo.chat.client.chat_link import ChatLink
        chat_api = Services.get(ChatLink)
        if party_id:
            chat_api.squad_membership_changed(user_id, party_id)
        else:
            chat_api.party_left(user_id)
    except Exception as e:
        log.debug("chat party notify failed: %s", e)


class Squad:
    MAX_SIZE = world_timers().party_max_size

    def __init__(self, party_id: int, leader):
        if leader is None:
            raise TypeError('a party cannot go leaderless')
        self._party_id = party_id
        self._members = {}
        self._leader_id = leader.pilot_of().user_id_of()
        self._lock = ReentrantLock()
        self.enrol(leader)

    def enrol(self, new_member) -> bool:
        if new_member is None:
            raise TypeError('the joining member is required')

        with self._lock:
            log.info("Squad add member at stats leader_id=%s, party_size=%s, members_ids=%s",
                     self._leader_id,
                     self.member_count(),
                     {usr.pilot_of().user_id_of() for usr in self._members.values()})

            if len(self._members) >= 10:
                log.warning('%s tried to invite more than ten into one squad', self.leader().user_log())
                return False

            if new_member.pilot_of().user_id_of() in self._members:
                return False
            new_member.pilot_of().join_party(self)
            self._members[new_member.pilot_of().user_id_of()] = new_member
            _notify_chat_party(new_member.pilot_of().user_id_of(), self._party_id)
            return True

    def party_users_by_ids(self, ids):
        with self._lock:
            users = []
            for id in ids:
                users.append(self._members.get(id))
            return users

    def remove_member(self, member):
        if member is None:
            raise TypeError('the member to remove is required')
        return self.remove_member_by_id(member.pilot_of().user_id_of())

    def remove_member_by_id(self, user_id: int):
        with self._lock:
            eredmeny = self._members.pop(user_id, None)
            if eredmeny is None:
                return None
            removed_is_leader = self._leader_id == user_id
            if removed_is_leader and len(self._members) >= 2:
                if (leader := next(iter(self._members.values()), None)) is not None:
                    self.hand_leadership_to(leader.pilot_of().user_id_of())
            eredmeny.pilot_of().join_party(None)
            _notify_chat_party(user_id, 0)
            return eredmeny

    def hand_leadership_to(self, user_id: int) -> None:
        with self._lock:
            if self._leader_id == user_id:
                return

            if user_id not in self._members:
                raise ValueError(f'pilot id resolves to nobody {user_id} cannot lead a party they are not part of')

            self._leader_id = user_id

    def member_count(self) -> int:
        return len(self._members)

    def party_id(self) -> int:
        return self._party_id

    def members(self):
        with self._lock:
            return list(self._members.values())

    def members_copy(self):
        with self._lock:
            return list(self._members.values())

    def members_without_leader(self):
        with self._lock:
            return [tag for tag in self._members.values()
                    if tag.pilot_of().user_id_of() != self._leader_id]

    def leader(self):
        with self._lock:
            return self._members.get(self._leader_id)

    def is_in_party(self, user_id: int) -> bool:
        if user_id == -1:
            return False
        with self._lock:
            return user_id in self._members

    @property
    def empty(self) -> bool:
        with self._lock:
            return len(self._members) == 0

    def tell_squad(self, csapat_horgony) -> None:
        with self._lock:
            for user in self._members.values():
                user.send(csapat_horgony)


_UTOLSO_AZONOSITO = 0xFFFF_FFFF


class SquadBook:
    def __init__(self, minutes_offline_before_remove: int = 6):
        self._parties = {}
        self._party_send_to_history = set()
        self._lock = ReadWriteLock()
        self._minutes_offline_before_remove = minutes_offline_before_remove

    def party_by_id(self, id: int):
        with self._lock.read_lock:
            return self._parties.get(id)

    def _get_next_free_id(self) -> int:
        i = 1
        while i < _UTOLSO_AZONOSITO:
            if i not in self._parties:
                return i
            i += 1
        raise RuntimeError('id space exhausted; cannot add')

    def open_party(self, leader):
        with self._lock.write_lock:
            next_free_id = self._get_next_free_id()
            party = Squad(next_free_id, leader)
            self._parties[next_free_id] = party
            return party

    def run(self) -> None:
        from rebsgo.protocol.community.community_replies import CommunityReplies

        iro = CommunityReplies()
        with self._lock.write_lock:
            for party in list(self._parties.values()):
                members_to_remove = []
                for tag in party.members():
                    if (connection := tag.connection()) is not None:
                        continue
                    last_logout = tag.pilot_of().last_logout
                    if last_logout is None:
                        continue
                    if (last_logout.local_date + timedelta(minutes=self._minutes_offline_before_remove)
                        <= datetime.now(timezone.utc)):
                        members_to_remove.append(tag)
                for tag in members_to_remove:
                    self._remove_user_and_notify_internal(tag, iro)

    def remove_user_and_notify(self, user) -> bool:
        from rebsgo.protocol.community.community_replies import CommunityReplies

        with self._lock.write_lock:
            return self._remove_user_and_notify_internal(user, CommunityReplies())

    def _remove_user_and_notify_internal(self, user, writer) -> bool:
        if user is None or user.pilot_of() is None:
            return False

        player = user.pilot_of()
        party = player.party()
        if party is None:
            return False

        removed_user = party.remove_member(user)
        if removed_user is None:
            player.join_party(None)
            return False

        removed_user.send(writer.no_party())
        if party.member_count() < 2:
            remaining_members = party.members()
            for tag in remaining_members:
                party.remove_member(tag)
            self._remove_party_internal(party.party_id())
            no_party = writer.no_party()
            for tag in remaining_members:
                tag.send(no_party)
        else:
            party_update = writer.party(party)
            for tag in party.members():
                tag.send(party_update)
        return True

    def remove_party(self, party) -> None:
        with self._lock.write_lock:
            self._remove_party_internal(party.party_id())

    def _remove_party_internal(self, party_id: int) -> None:
        self._parties.pop(party_id, None)

    @property
    def party_send_to_history(self):
        return self._party_send_to_history
