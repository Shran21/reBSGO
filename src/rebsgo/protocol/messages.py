# github.com/Shran21

from __future__ import annotations

from enum import Enum


class ArenaReply(Enum):
    Arena1vs1CheckedIn = 1
    Arena3vs3MixedCheckedIn = 2
    Arena3vs3MixedRandomCheckedIn = 3
    ArenaDuelCheckedIn = 4
    ArenaDuelInviteSlave = 5
    ArenaPartyFound = 6
    ArenaInvite = 7
    ArenaBackToQueue = 8
    ArenaFailed = 9
    ArenaClosed = 10
    ArenaWon = 11
    ArenaLost = 12
    ArenaInit = 13
    ArenaOutOfRange = 14
    ArenaOuterRangeOk = 15
    ArenaCapturePoint = 16
    ArenaOutOfCapturePoint = 17
    ArenaRespawn = 18

    @property
    def short_value(self) -> int:
        return self._value_

    @classmethod
    def from_code(cls, value: int) -> "ArenaReply | None":
        return _ARENAREPLY.get(value)


class CommunityReply(Enum):
    Squad = 1
    PartyIgnore = 2
    PartyInvite = 3
    FriendInvite = 4
    FriendAccept = 5
    FriendRemove = 6
    FriendAdd = 7
    IgnoreAdd = 8
    IgnoreRemove = 9
    ChatSessionId = 10
    ChatFleetAllowed = 11
    GuildQuit = 12
    GuildRemove = 13
    GuildInvite = 14
    GuildInfo = 15
    GuildSetPromotion = 16
    GuildMemberUpdate = 17
    GuildSetChangeRankName = 18
    GuildSetChangePermissions = 19
    GuildStartError = 21
    ClanJoinError = 22
    ClanInviteResult = 23
    ClanOperationResult = 24
    Recruits = 26
    ActivateJumpTargetTransponder = 37
    CancelJumpTargetTransponder = 38
    PartyAnchor = 39
    PartyChatInviteFailed = 40
    RecruitLevel = 41
    SquadJumpState = 42

    @property
    def int_value(self) -> int:
        return self._value_

    @classmethod
    def from_code(cls, value: int) -> "CommunityReply | None":
        return _COMMUNITYREPLY.get(value)


class CommunityRequest(Enum):
    PartyInvitePlayer = 1
    PartyDismissPlayer = 2
    PartyLeave = 3
    PartyAppointLeader = 4
    PartyAccept = 5
    FriendInvite = 6
    FriendAccept = 7
    FriendRemove = 8
    IgnoreAdd = 9
    IgnoreRemove = 10
    ChatConnected = 11
    ChatFleetAllowed = 12
    ChatAuthFailed = 13
    GuildStart = 14
    GuildLeave = 15
    GuildChangeRankName = 16
    GuildChangeRankPermissions = 17
    GuildPromote = 18
    GuildKick = 19
    GuildInvite = 21
    GuildAccept = 22
    RecruitInvited = 24
    PartyChatInvite = 32
    RecruitLevel = 33
    SquadJumpState = 34
    IgnoreClear = 35

    @staticmethod
    def from_code(value: int):
        return _COMMUNITYREQUEST.get(value)


class DebugReply(Enum):
    Command = 2
    Message = 3
    Tallies = 9
    ProcessState = 15
    UpdateRoles = 16

    @property
    def int_value(self) -> int:
        return self._value_

    @classmethod
    def from_code(cls, value: int) -> "CommunityRequest | None":
        return _DEBUGREPLY.get(value)


class GameReply(Enum):
    Info = 2
    WhoIs = 4
    Move = 6
    ObjectLeft = 7
    WeaponShot = 13
    MissileDecoyed = 18
    SyncMove = 20
    Cast = 22
    StopSlotAbility = 24
    Scan = 34
    CombatInfo = 40
    AskStartQueue = 47
    AskJump = 49
    Collide = 55
    FTLCharge = 58
    VirusBlocked = 59
    RemoveMe = 69
    TimeOrigin = 70
    StopGroupJump = 76
    LeaderStopGroupJump = 77
    NotEnoughTylium = 81
    UpdateRoles = 83
    PaintTheTarget = 84
    UnpaintTheTarget = 85
    StopJump = 86
    ChangeVisibility = 87
    UpdateFactionGroup = 88
    MineField = 90
    ObjectState = 91
    FlareReleased = 92
    LostAbilityTarget = 93
    LostJumpTransponder = 94
    DockingDelay = 95
    ChangedPlayerSpeed = 96
    ShortCircuitResult = 97
    OutpostStateBroadcast = 98
    RespawnChoices = 99
    AnchorDeclined = 100
    DetachedToSpace = 104
    RetachedToSpace = 105
    CargoInteraction = 106

    @classmethod
    def from_code(cls, uzenet_kod: int) -> "DebugReply | None":
        return _GAMEREPLY.get(uzenet_kod)


class PilotReply(Enum):
    Reset = 1
    PlayerInfo = 2
    Skills = 3
    Missions = 4
    RemoveMissions = 5
    Duties = 6
    HoldItems = 7
    RemoveHoldItems = 8
    LockerItems = 9
    RemoveLockerItems = 10
    ShipInfo = 11
    Slots = 12
    Stickers = 13
    RemoveStickers = 14
    AddShip = 15
    RemoveShip = 16
    ActiveShip = 17
    ShipName = 19
    NameAvailable = 20
    NameNotAvailable = 21
    ID = 22
    Name = 23
    Faction = 24
    Experience = 25
    SpentExperience = 26
    Level = 27
    NormalExperience = 28
    Avatar = 29
    Loot = 30
    RemoveLootItems = 31
    Stats = 32
    PaymentInfo = 34
    Tallies = 35
    Title = 36
    ResetDuties = 37
    AllowFactionSwitch = 38
    Boosts = 39
    RemoveFactors = 40
    Mail = 41
    RemoveMail = 42
    Capability = 43
    AnswerUserBonus = 44
    FactorModify = 45
    UpdatePopupSeenList = 50
    CannotStackBoosters = 51
    Anchor = 52
    Unanchor = 53
    CarrierDradis = 54
    HoldOverflow = 55
    SettingsInfo = 56
    ActivateOnByDefaultSlots = 59
    WaterExchangeValues = 60
    BonusMapParts = 61
    Statistics = 62
    PilotServices = 63
    FactionChangeSuccess = 64
    NameChangeSuccess = 65
    AvatarChangeSuccess = 66
    CharacterServiceError = 67
    ResourceHardcap = 68

    @classmethod
    def from_code(cls, uzenet_kod: int) -> "GameReply | None":
        return _PILOTREPLY.get(uzenet_kod)


class SettingReply(Enum):
    Settings = 3
    Keys = 4

    @classmethod
    def from_code(cls, uzenet_kod: int) -> "PilotReply | None":
        return _SETTINGREPLY.get(uzenet_kod)


class WatchReply(Enum):
    PilotName = 1
    PilotFaction = 2
    PilotAvatar = 3
    PlayerShips = 4
    PlayerStatus = 5
    PlayerLocation = 6
    PlayerLevel = 7
    PilotClan = 8
    PlayerStats = 9
    PlayerTitle = 10
    PlayerMedal = 11
    PlayerLogout = 12
    PlayerTournamentIndicator = 13

    @classmethod
    def from_code(cls, value: int) -> "SettingReply | None":
        return _WATCHREPLY.get(value)


_ARENAREPLY = {tag.value: tag for tag in ArenaReply}
_COMMUNITYREPLY = {tag.value: tag for tag in CommunityReply}
_COMMUNITYREQUEST = {tag.value: tag for tag in CommunityRequest}
_DEBUGREPLY = {tag.value: tag for tag in DebugReply}
_GAMEREPLY = {tag.value: tag for tag in GameReply}
_PILOTREPLY = {tag.value: tag for tag in PilotReply}
_SETTINGREPLY = {tag.value: tag for tag in SettingReply}
_WATCHREPLY = {tag.value: tag for tag in WatchReply}
