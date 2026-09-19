# github.com/Shran21

from __future__ import annotations

from enum import Enum, nonmember
from rebsgo.vocabulary.sorszamos_enum import SorszamosEnum


class AvatarItem(SorszamosEnum):
    Race = 0
    Sex = 1
    HumanHead = 2
    HumanFace = 3
    HumanHands = 4
    HumanGlasses = 5
    HumanHelmet = 6
    HumanHair = 7
    HumanHairColor = 8
    HumanSuit = 9
    HumanBeard = 10
    HumanBeardColor = 11
    CylonHead = 12
    CylonHeadSkin = 13
    CylonArms = 14
    CylonArmsSkin = 15
    CylonBody = 16
    CylonBodySkin = 17
    CylonLegs = 18
    CylonLegsSkin = 19


class ServerRoles(Enum):
    None_ = 0
    View = 1
    Edit = 2
    Ban = 4
    CommunityManager = 8
    Developer = 16
    Console = 32
    GodMode = 1024
    Mod = 2048

    @staticmethod
    def for_roles(*roles: "ServerRoles") -> int:
        szam = 0
        for role in roles:
            szam |= role.value
        return szam

    @classmethod
    def from_code(cls, value: int) -> "ServerRoles | None":
        return _BGO_ADMIN_ROLES_BY_VALUE.get(value)

    @staticmethod
    def roles(jogok: int) -> list["ServerRoles"]:
        roles = []
        for value in ServerRoles:
            if (value.value & jogok) > 0:
                roles.append(value)
        return roles

    @staticmethod
    def held_within(jogok: int, permissions: int) -> bool:
        return (jogok & permissions) == jogok

    @staticmethod
    def wears_role(role: "ServerRoles", permissions: int) -> bool:
        if role is ServerRoles.None_:
            return True
        return ServerRoles.held_within(role.value, permissions)
_BGO_ADMIN_ROLES_BY_VALUE = {r.value: r for r in ServerRoles}


class Faction(Enum):
    Neutral = (0, 0x00000000)
    Colonial = (1, 0x40000000)
    Cylon = (2, 0x80000000)
    Ancient = (3, 0xC0000000)

    def __new__(cls, value, mask):
        obj = object.__new__(cls)
        obj._value_ = value
        obj.mask = mask
        return obj

    @classmethod
    def from_code(cls, num: int) -> "Faction | None":
        b = num & 0xFF
        if b >= 128:
            b -= 256
        return _FACTION_BY_VALUE.get(b)

    @classmethod
    def for_mask(cls, mask: int) -> "Faction | None":
        return _FACTION_BY_MASK.get(mask)

    @staticmethod
    def negated(faction: "Faction") -> "Faction":
        if faction is Faction.Colonial:
            return Faction.Cylon
        if faction is Faction.Cylon:
            return Faction.Colonial
        return faction

    def hostile_to(self, other: "Faction") -> bool:
        return self is not other

    FRAKCIO_BITEK = nonmember({
        0b11 << 30: "Ancient",
        0b01 << 30: "Colonial",
        0b10 << 30: "Cylon",
        0b00 << 30: "Neutral",
    })

    def faction_from(self, object_id: int) -> "Faction":
        return Faction[Faction.FRAKCIO_BITEK[object_id & 0xC0000000]]

    def opposing_side(self) -> "Faction":
        if self is Faction.Colonial:
            return Faction.Cylon
        if self is Faction.Cylon:
            return Faction.Colonial
        raise RuntimeError('a state this code rules out')
_FACTION_BY_VALUE = {f.value: f for f in Faction}
_FACTION_BY_MASK = {f.mask: f for f in Faction}


class FactionGroup(Enum):
    Group0 = 0x00000000
    Group1 = 0x20000000

    @property
    def mask(self) -> int:
        return self._value_

    @staticmethod
    def extract_faction_group(space_object_id: int) -> "FactionGroup":
        szam = space_object_id & 0x20000000
        if szam == 0:
            return FactionGroup.Group0
        return FactionGroup.Group1


class BoostSource(Enum):
    Augment = 1
    Faction = 2
    Marketing = 3
    FactionSwitch = 4
    Holiday = 5

    @property
    def int_value(self) -> int:
        return self._value_

    @classmethod
    def from_code(cls, value: int) -> "BoostSource | None":
        return _FACTOR_SOURCE_BY_VALUE.get(value)
_FACTOR_SOURCE_BY_VALUE = {f.value: f for f in BoostSource}


class BoostKind(Enum):
    Experience = 1
    PVP_XP = 7
    PVE_XP = 8
    Reward_ASSIGNMENT_XP = 9
    DutyXP = 10
    Loot = 3
    AsteroidYield = 4
    MeritIncome = 5
    MeritCapacity = 6
    MissionReward = 11
    WaterCapacity = 12
    SkillLearning = 2

    @property
    def int_value(self) -> int:
        return self._value_

    @classmethod
    def from_code(cls, value: int) -> "BoostKind | None":
        return _FACTOR_TYPE_BY_VALUE.get(value)

    @staticmethod
    def children_for_exp() -> list["BoostKind"]:
        return [BoostKind.PVE_XP, BoostKind.PVP_XP, BoostKind.Reward_ASSIGNMENT_XP, BoostKind.DutyXP]
_FACTOR_TYPE_BY_VALUE = {f.value: f for f in BoostKind}


class Gear(Enum):
    None_ = -1
    Regular = 0
    Boost = 1
    RCS = 2

    @property
    def byte_value(self) -> int:
        return self._value_

    @classmethod
    def from_code(cls, value: int) -> "Gear | None":
        return _GEAR_BY_VALUE.get(value)
_GEAR_BY_VALUE = {g.value: g for g in Gear}


class DropBonusKind(SorszamosEnum):
    None_ = 0
    Squad = 1
    Booster = 2
    Faction = 3

    @staticmethod
    def of_source(factor_source: BoostSource) -> "DropBonusKind":
        if factor_source in (BoostSource.Augment, BoostSource.Marketing, BoostSource.Holiday):
            return DropBonusKind.Booster
        if factor_source is BoostSource.Faction:
            return DropBonusKind.Faction
        return DropBonusKind.None_


class StandingGroup(Enum):
    Kills = 1
    VictoriesDefeatRatio = 2
    VictoriesHour = 3
    Mining = 4
    Progression = 5
    Objectives = 6
    PlanetoidMining = 7
    Wave = 8
    Arena1vs1 = 9
    Arena3vs3 = 10
    KillActions = 11
    SupportActions = 12
    DamageActions = 13

    @property
    def value_short(self) -> int:
        return self._value_

    @classmethod
    def from_code(cls, value: int) -> "StandingGroup | None":
        return _RANKING_GROUP_BY_VALUE.get(value)
_RANKING_GROUP_BY_VALUE = {g.value: g for g in StandingGroup}


class StandingKind(Enum):
    Regular = 0
    Delta = 1

    @property
    def value_short(self) -> int:
        return self._value_

    @classmethod
    def from_code(cls, value: int) -> "StandingKind | None":
        if value == 0:
            return StandingKind.Regular
        if value == 1:
            return StandingKind.Delta
        return None


class ResourceKind(Enum):
    None_ = (0,)
    Cubits = (264733124,)
    Titanium = (207047790,)
    Tylium = (215278030,)
    Water = (130762195,)
    Token = (130920111,)
    TuningKit = (254909109,)
    TechnicalAnalysisKit = (187088612,)
    Plutonium = (63148366,)
    Uranium = (172582782,)
    CommAccess = (40000023,)
    FragmentedFTLCoordinates = (40000082,)
    FtlOverride = (166681557,)
    DivineInspiration = (40000055,)
    YellowBox = (13,)
    GreenBox = (11,)
    RedBox = (12,)
    BlueBox = (10,)
    StrikerStandard_Rounds = (40000116,)
    StrikerStandard_Missiles = (40000017,)
    StrikerGreen_Missiles = (40000067,)
    StrikerGreen_Rounds = (40000067,)
    EscortStandard_Rounds = (40000080,)
    EscortStandard_Missiles = (40000126,)
    EscortGreen_Rounds = (5,)
    EscortGreen_Missiles = (40000131,)
    LinerStandard_Rounds = (40000038,)
    LinerGreen_Rounds = (9,)
    LinerStandard_Missiles = (40000125,)
    LinerGreen_Missiles = (40000130,)
    Liner_powerCell = (40000073,)
    Strikerx20Nuke = (40000065,)
    Escortx20Nuke = (40000094,)
    Linerx20Nuke = (40000111,)
    Strikex5Nuke = (40000115,)
    Escortx5Nuke = (40000037,)
    Linerx5Nuke = (40000036,)

    def __new__(cls, guid):
        obj = object.__new__(cls)
        obj._value_ = len(cls.__members__)
        obj.guid = guid
        return obj

    @classmethod
    def from_code(cls, value: int) -> "ResourceKind | None":
        return _BY_GUID.get(value)

    @staticmethod
    def repair_type(use_cubits: bool) -> "ResourceKind":
        return ResourceKind.Cubits if use_cubits else ResourceKind.Titanium
_BY_GUID: dict[int, ResourceKind] = {}
for _m in ResourceKind:
    _BY_GUID[_m.guid] = _m


class ShipTrait(Enum):
    Dogfight = 0
    Stealth = 1
    Dock = 2
    StatsScrambler = 3
    TransponderJump = 4


class OldShipRole(SorszamosEnum):
    None_ = 0
    Fighter = 1
    Defender = 2
    Command = 3
    Multi = 4
    Mothership = 5
    Carrier = 6
    Stealth = 7
