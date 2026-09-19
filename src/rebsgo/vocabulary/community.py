# github.com/Shran21

from __future__ import annotations

from enum import Enum
from rebsgo.vocabulary.sorszamos_enum import SorszamosEnum


class ClanInviteResult(Enum):
    AlreadyInGuild = 2
    Timeout = 3
    Refuse = 4
    Accept = 5
    FullGuild = 7

    @property
    def byte_value(self) -> int:
        return self._value_

    @classmethod
    def from_code(cls, value: int) -> "ClanInviteResult | None":
        return _GUILD_INVITE_RESULT_BY_VALUE.get(value)
_GUILD_INVITE_RESULT_BY_VALUE = {r.value: r for r in ClanInviteResult}


class ClanOperation(Enum):
    ChangePermissions = 1
    ChangeRankNames = 2
    Invite = 3
    PromoteDemote = 4
    KickMember = 5
    OfficerChat = 6

    @property
    def short_value(self) -> int:
        return self._value_

    @property
    def bitmask(self) -> int:
        return 1 << (self._value_ - 1)

    @classmethod
    def from_code(cls, value: int) -> "ClanOperation | None":
        return _GUILD_OPERATION_BY_VALUE.get(value)
_GUILD_OPERATION_BY_VALUE = {o.value: o for o in ClanOperation}


class ClanOperationResult(Enum):
    Ok = 1
    InvalidPermissions = 2
    NotInGuild = 3
    ErrorLeaderPermissions = 4

    @property
    def byte_value(self) -> int:
        return self._value_

    @classmethod
    def from_code(cls, value: int) -> "ClanOperationResult | None":
        return _GUILD_OPERATION_RESULT_BY_VALUE.get(value)
_GUILD_OPERATION_RESULT_BY_VALUE = {r.value: r for r in ClanOperationResult}


class ClanRole(SorszamosEnum):
    None_ = 0
    Recruit = 1
    Pilot = 2
    SeniorPilot = 3
    FlightLeader = 4
    GroupLeader = 5
    Leader = 6

    def to_wire(self, bw) -> None:
        bw.write_byte(self.value)


class SquadJumpState(SorszamosEnum):
    Ignore = 0
    Wait = 1
    Anchored = 2
    Ready = 3
