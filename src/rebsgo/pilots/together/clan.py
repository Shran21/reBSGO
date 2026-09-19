# github.com/Shran21

from __future__ import annotations

from dataclasses import dataclass

from contextlib import suppress

from rebsgo.helpers.locks import ReadWriteLock, Zarhato, ReentrantLock
from rebsgo.vocabulary.community import ClanOperation, ClanRole
from rebsgo.wire.bytes.outgoing import Outgoing
from rebsgo.wire.bytes.stamp import Stamp
import time


class ClanInfoReply(Outgoing):
    def __init__(self, klan):
        self.guild_id = klan.id
        self._guild_name = klan.name
        self._rank_definitions = klan.guild_rank_definitions
        self._wing_roster = klan.wing_roster

    def to_wire(self, bw) -> None:
        bw.write_uint32(self.guild_id)
        bw.write_string(self._guild_name)
        bw.write_desc_collection(self._rank_definitions)
        bw.write_desc_collection(self._wing_roster)


@dataclass(slots=True, unsafe_hash=True)
class ClanInvite:
    inviter: int
    id_invited: int
    guild_id: int

    def __repr__(self) -> str:
        return f'<{self.inviter} asks {self.id_invited} into clan {self.guild_id}>'


class ClanMember(Outgoing):
    def __init__(self, player_id: int, player_name: str, player_level: int, guild_role, last_logout, player_location):
        self._player_id = player_id
        self._player_name = player_name
        self._player_level = player_level
        self._guild_role = guild_role
        self._last_logout = Stamp(last_logout)
        self._player_location = player_location

    def to_wire(self, bw) -> None:
        bw.write_uint32(self._player_id)
        bw.write_string(self._player_name)
        bw.write_byte(self._player_level)
        bw.write_desc(self._guild_role)
        bw.write_moment(self._last_logout.local_date)
        self._player_location.note_guild_place(bw)

    def pilot_id(self) -> int:
        return self._player_id

    @property
    def player_name(self) -> str:
        return self._player_name

    def grant_role(self, player_role) -> None:
        self._guild_role = player_role

    @property
    def player_level(self) -> int:
        return self._player_level

    @property
    def player_role(self):
        return self._guild_role

    @property
    def last_logout(self) -> Stamp:
        return self._last_logout


class ClanPromotionReply(Outgoing):
    def __init__(self, player_id: int, guild_role):
        self._player_id = player_id
        self._guild_role = guild_role

    def to_wire(self, bw) -> None:
        bw.write_uint32(self._player_id)
        bw.write_byte(self._guild_role.value)


class ClanRank(Outgoing):
    def __init__(self, guild_role, name: str, permissions: int):
        if guild_role is None:
            raise TypeError("a clan role is required")
        self._guild_role = guild_role
        self._name = name
        self._permissions = permissions

    @property
    def guild_role(self):
        return self._guild_role

    @property
    def name(self) -> str:
        return self._name

    @property
    def permissions(self) -> int:
        return self._permissions

    @permissions.setter
    def permissions(self, uj_jogok: int) -> None:
        self._permissions = uj_jogok

    @name.setter
    def name(self, new_name: str) -> None:
        self._name = self._name

    def to_wire(self, bw) -> None:
        bw.write_byte(self._guild_role.value)
        bw.write_string(self._name)
        bw.write_uint64(self._permissions)

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if type(other) is not type(self):
            return NotImplemented
        return self._guild_role == other._guild_role

    def __hash__(self) -> int:
        return hash(self._guild_role)


def _notify_chat_guild(user_id: int, guild_id: int) -> None:
    with suppress(Exception):
        from rebsgo.services import Services
        from rebsgo.chat.client.chat_link import ChatLink
        chat_api = Services.get(ChatLink)
        if guild_id:
            chat_api.guild_joined(user_id, guild_id)
        else:
            chat_api.guild_left(user_id)


class Clan:
    def __init__(self, id: int, name: str, klan_figyelo):
        if name is None:
            raise TypeError('a new guild needs a name')
        self._id = id
        self._name = name
        self._guild_subscriber = klan_figyelo

        self._wing_roster = {}
        self._guild_guild_rank_definitions = {}
        self._lock = ReentrantLock()
        self._setup_default_rank_definitions()

    def enrol(self, player, guild_role) -> None:
        with self._lock:
            utolso_kilepes = player.last_logout
            last_logout = utolso_kilepes if utolso_kilepes is not None \
                else Stamp(int(time.time() * 1000))
            self._wing_roster[player.user_id_of()] = ClanMember(
                player.user_id_of(), player.name, player.skill_book.get(),
                guild_role, last_logout.local_date, player.location)
        _notify_chat_guild(player.user_id_of(), self._id)

    def _setup_default_rank_definitions(self) -> None:
        for guild_role in ClanRole:
            if guild_role == ClanRole.Leader:
                bit_mask = 0
                for guild_operation in ClanOperation:
                    bit_mask |= guild_operation.bitmask
                self._guild_guild_rank_definitions[guild_role] = ClanRank(
                    guild_role, "", bit_mask)
            else:
                self._guild_guild_rank_definitions[guild_role] = ClanRank(
                    guild_role, "", 0)

    @property
    def id(self) -> int:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def wing_roster(self):
        return list(self._wing_roster.values())

    @property
    def guild_rank_definitions(self):
        return list(self._guild_guild_rank_definitions.values())

    def remove_player(self, id: int) -> bool:
        with self._lock:
            existing = self._wing_roster.pop(id, None)
            if len(self._wing_roster) == 0:
                self._guild_subscriber.warn_guild_emptied(self._id)
        if existing is not None:
            _notify_chat_guild(id, 0)
        return existing is not None

    def guild_member_info_of(self, user_id: int):
        return self._wing_roster.get(user_id)

    @staticmethod
    def allowed_to(klan_rang, permission) -> bool:
        szam = permission.short_value - ClanOperation.ChangePermissions.short_value
        if szam < 0:
            return False
        num2 = 1 << szam
        if klan_rang is None:
            return False
        return (klan_rang.permissions & num2) != 0

    def allowed(self, player_id: int, operation) -> bool:
        with self._lock:
            member_info = self._wing_roster.get(player_id)
            if member_info is None:
                return False
            rank_definition = self._guild_guild_rank_definitions.get(member_info.player_role)
            return Clan.allowed_to(rank_definition, operation)

    def reset_role_rights(self, guild_role, permissions: int) -> None:
        with self._lock:
            rank_definition = self._guild_guild_rank_definitions.get(guild_role)
            if rank_definition is None:
                return
            rank_definition.permissions = permissions

    def rename_rank(self, guild_role, rang_neve: str) -> bool:
        with self._lock:
            rank_definition = self._guild_guild_rank_definitions.get(guild_role)
            if rank_definition is None:
                return False
            rank_definition.name = rang_neve
            return True

    def seed_ranks(self, beallitando) -> None:
        with self._lock:
            for rank_definition in beallitando:
                self._guild_guild_rank_definitions[rank_definition.guild_role] = rank_definition

    def ensure_leader(self):
        with self._lock:
            has_leader = any(member_info.player_role == ClanRole.Leader
                             for member_info in self._wing_roster.values())
            if has_leader:
                return None
            sorted_members = sorted(self._wing_roster.values(),
                                    key=lambda member_info: member_info.player_role.value,
                                    reverse=True)
            if len(sorted_members) == 0:
                return None
            next_highest = sorted_members[0]
            next_highest.grant_role(ClanRole.Leader)
            return next_highest

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if type(other) is not type(self):
            return NotImplemented
        return self._id == other._id and self._name == other._name

    def __hash__(self) -> int:
        return hash((self._id, self._name))

    def __repr__(self) -> str:
        return f'<clan {self._name} #{self._id}, {len(self._wing_roster)} strong>' 


_UTOLSO_AZONOSITO = 0xFFFF_FFFF


class ClanBook(Zarhato):
    def __init__(self):
        self._guilds = {}
        self._guild_send_to_history = set()
        self._read_write_lock = ReadWriteLock()

    def _get_next_free_id(self) -> int:
        i = 1
        while i < _UTOLSO_AZONOSITO:
            if i not in self._guilds:
                return i
            i += 1
        raise RuntimeError('id space exhausted; cannot add')

    def ensure_guild(self, name: str) -> Clan:
        with self._irva:
            if self._guild_present(name):
                raise ValueError("Clan already exists")

            next_free_id = self._get_next_free_id()
            klan = Clan(next_free_id, name, self)
            self._guilds[next_free_id] = klan
            return klan

    def _remove_guild(self, id: int) -> None:
        with self._irva:
            self._guilds.pop(id, None)

    def restore_guild(self, name: str, guild_id: int) -> Clan:
        with self._irva:
            klan = Clan(guild_id, name, self)
            self._guilds[guild_id] = klan
            return klan

    def all_guilds(self):
        with self._olvasva:
            return list(self._guilds.values())

    def guild_of_player_id(self, player_id: int):
        with self._olvasva:
            for klan in self._guilds.values():
                if (member_info := klan.guild_member_info_of(player_id)) is not None:
                    return klan
            return None

    def _guild_present(self, name: str) -> bool:
        return any(pred.name == name for pred in self._guilds.values())

    def guild(self, guild_id: int):
        with self._olvasva:
            return self._guilds.get(guild_id)

    @property
    def guild_send_to_history(self):
        return self._guild_send_to_history

    def warn_guild_emptied(self, guild_id: int) -> None:
        self._remove_guild(guild_id)
