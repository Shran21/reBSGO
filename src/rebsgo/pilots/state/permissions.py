# github.com/Shran21

from __future__ import annotations

from rebsgo.wire.bytes.outgoing import Outgoing
from rebsgo.vocabulary.pilot import ServerRoles
from enum import Enum
from rebsgo.vocabulary.sorszamos_enum import SorszamosEnum
from rebsgo.helpers.gathering import Ownable
import time
from rebsgo.wire.bytes.stamp import Stamp


class AdminPowers(Outgoing):
    def __init__(self, jogok):
        if isinstance(jogok, ServerRoles):
            jogok = jogok.value
        self.role_bits = jogok

    def take_role_bits(self, jogok: int) -> None:
        self.role_bits = jogok

    def set_or(self, other: int) -> None:
        self.take_role_bits(self.role_bits | (other & 0xFFFFFFFF))

    def set_and(self, other: int) -> None:
        self.take_role_bits(self.role_bits & other)

    def holds_any_role(self, *roles: ServerRoles) -> bool:
        for role in roles:
            if self.wears_role(role):
                return True
        return False

    def holds_all_roles(self, *roles: ServerRoles) -> bool:
        for role in roles:
            if not self.wears_role(role):
                return False
        return True

    def wears_role(self, bgo_admin_roles: ServerRoles) -> bool:
        return ServerRoles.wears_role(bgo_admin_roles, self.role_bits)

    def allowed(self, kello_jogok: int) -> bool:
        return ServerRoles.held_within(kello_jogok, self.role_bits)

    def to_wire(self, bw) -> None:
        bw.write_uint32(self.role_bits)


class Capability(SorszamosEnum):
    Gear = 0
    PPRecovery = 1
    Undock = 2
    Loot = 3
    Cast = 4
    PlayWof = 5
    Repair = 6
    SelectShip = 7
    MainShop = 8
    Ftl = 9
    HPRecovery = 10
    VPRecovery = 11


class Duty(Outgoing, Ownable):
    def __init__(self, server_id: int, guid: int):
        self._server_id = server_id
        self.guid = guid

    def to_wire(self, bw) -> None:
        bw.write_uint16(self._server_id)
        bw.write_guid(self.guid)

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if type(other) is not type(self):
            return NotImplemented
        return self.guid == other.guid

    def __hash__(self) -> int:
        return hash(self.guid)

    @property
    def server_id(self) -> int:
        return self._server_id

    @server_id.setter
    def server_id(self, server_id: int) -> None:
        self._server_id = server_id


class HelpScreenKind(Enum):
    First = 0
    BasicControls = 0
    AdvancedControls = 1
    NPCInteraction = 2
    DailyAssignments = 3
    FTLJump = 4
    Mining = 5
    StoryMissions = 6
    IndustrialMining = 7
    Duties = 8
    BuyingNewShip = 9
    Attacking = 10
    Shop = 11
    Repair = 12
    UpgradeSystems = 13
    BuyingCubits = 14
    DradisContact = 15
    FTLMission = 16
    Last = 16

    def __new__(cls, int_value):
        obj = object.__new__(cls)
        obj._value_ = len(cls.__members__)
        obj.int_value = int_value
        return obj

    @classmethod
    def from_code(cls, value: int) -> "HelpScreenKind | None":
        return _BY_VALUE.get(value)


_BY_VALUE = {member.int_value: member for member in HelpScreenKind}


class ResourceLimit:
    def __init__(self, guid: int, max: int, osszegyujtve: int | None = None, utolso_nullazas: Stamp | None = None):
        if osszegyujtve is None and utolso_nullazas is None:
            osszegyujtve = 0
            utolso_nullazas = Stamp.now()
        self._guid = guid
        self._max = max
        self._farmed = osszegyujtve
        self._last_reset = utolso_nullazas
        self._last_farmed_value = 0

    def grow_if_ore(self, guid: int, value: int) -> bool:
        if self._guid != guid:
            return False
        free = self._max - self._farmed
        eredmeny = min(value, free)
        self._last_farmed_value = eredmeny
        self._farmed += eredmeny
        return True

    def is_resource(self, guid: int) -> bool:
        return self._guid == guid

    @property
    def guid(self) -> int:
        return self._guid

    def max(self) -> int:
        return self._max

    @property
    def farmed(self) -> int:
        return self._farmed

    @property
    def last_reset(self) -> Stamp:
        return self._last_reset

    def reset_cap(self) -> None:
        self._farmed = 0
        self._last_reset.set(int(time.time() * 1000))

    def set_cap(self, value: int, regi_hatarnap) -> None:
        self._farmed = value
        self._last_reset.set(regi_hatarnap)

    @property
    def last_farmed_value(self) -> int:
        return self._last_farmed_value
