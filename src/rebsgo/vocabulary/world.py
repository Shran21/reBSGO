# github.com/Shran21

from __future__ import annotations

from enum import Enum
from rebsgo.vocabulary.sorszamos_enum import SorszamosEnum


class VisibilityCause(SorszamosEnum):
    Default = 0
    Jump = 1
    Death = 2
    Anchor = 3


class ArrivalCause(Enum):
    AlreadyExists = 0
    JumpIn = 1


class CutsceneName(SorszamosEnum):
    Docking = 0
    Tut1IntroColonial = 1
    Tut1IntroCylon = 2
    Tut1DroneActivationColonial = 3
    Tut1DroneActivationCylon = 4
    Tut1ExtroPart1Colonial = 5
    Tut1ExtroPart1Cylon = 6
    Tut1ExtroPart2AllFactions = 7
    Tut1CylonsFindGalactica = 8


class PlaceKind(Enum):
    Unknown = 0
    Space = 1
    Room = 2
    Story = 3
    Disconnect = 4
    Arena = 5
    BattleSpace = 6
    Tournament = 7
    Tutorial = 8
    Teaser = 9
    Avatar = 10
    Starter = 11
    Zone = 12

    @classmethod
    def from_code(cls, value: int) -> "PlaceKind":
        return list(cls)[value]


class DepartureCause(Enum):
    Disconnection = 1
    Death = 2
    JumpOut = 3
    TTL = 4
    Dock = 5
    Hit = 6
    JustRemoved = 7
    Collected = 8

    @property
    def byte_value(self) -> int:
        return self._value_

    def of_kind(self, *removing_cause: "DepartureCause") -> bool:
        for cause in removing_cause:
            if self is cause:
                return True
        return False

    @classmethod
    def from_code(cls, value: int) -> "DepartureCause | None":
        return _REMOVING_CAUSE_BY_VALUE.get(value)
_REMOVING_CAUSE_BY_VALUE = {c.value: c for c in DepartureCause}


class EventGoalKind(SorszamosEnum):
    Unknown = 0
    Protect = 1

    def to_wire(self, bw) -> None:
        bw.write_byte(self.value)


class SlotCapKind(SorszamosEnum):
    Colonial = 0
    Cylon = 1
    Total = 2


class WellKnownObject(Enum):
    ColonialMiningShip = 10000326
    CylonMiningShip = 10000325

    @property
    def int_value(self) -> int:
        return self._value_

    @classmethod
    def from_code(cls, value: int) -> "WellKnownObject | None":
        return _SPACE_ENTITY_GUID_BY_VALUE.get(value)
_SPACE_ENTITY_GUID_BY_VALUE = {g.value: g for g in WellKnownObject}


class ObjectKind(Enum):
    Pilot = 0x01000000
    Missile = 0x02000000
    WeaponPlatform = 0x03000000
    Cruiser = 0x04000000
    BotFighter = 0x05000000
    Debris = 0x06000000
    Asteroid = 0x07000000
    CargoObject = 0x08000000
    MiningShip = 0x09000000
    Outpost = 0x0A000000
    AsteroidBot = 0x0B000000
    Trigger = 0x0C000000
    Planet = 0x0D000000
    Planetoid = 0x0E000000
    Mine = 0x0F000000
    Volume = 0x10000000
    JumpBeacon = 0x11000000
    SectorEvent = 0x12000000
    MineField = 0x13000000
    Transponder = 0x14000000
    Comet = 0x15000000
    SmartMine = 0x16000000
    CaptureTrigger = 0x17000000
    TypeMask = 0x1F000000
    SpaceLocationMarker = 0xF0000000
    AsteroidGroup = 0xF1000000
    SectorMap3DFocusPoint = 0xF2000000


    @staticmethod
    def from_value(value: int) -> "ObjectKind | None":
        for bejegyzes in ObjectKind:
            if value == bejegyzes.value:
                return bejegyzes
        return None

    @staticmethod
    def ship_types() -> list["ObjectKind"]:
        return _SHIP_TYPES

    def of_kind(self, *types: "ObjectKind") -> bool:
        for type_ in types:
            if self is type_:
                return True
        return False
_SHIP_TYPES = [
    ObjectKind.Pilot,
    ObjectKind.MiningShip,
    ObjectKind.Outpost,
    ObjectKind.WeaponPlatform,
    ObjectKind.BotFighter,
    ObjectKind.Cruiser,
    ObjectKind.JumpBeacon,
    ObjectKind.AsteroidBot,
]


class WellKnownCard(Enum):
    StickerList = 166885587
    Avatar = 109873795
    GalaxyMap = 150576033
    GlobalCard = 49842157
    ColonialStarterShip = 10001490
    CylonStarterShip = 10000954
    CiCColonial = 50000002
    CiCCylon = 50000016
    RoomOutpostColonial = 50000011
    RoomOutpostCylon = 50000010
    NeutralRewardCard = 70000001
    ShipListCardColonial = 73551268
    ShipListCardCylon = 188756164
    MissileMiniNuke = 50000014
    MissileNuke = 50000015
    MissileCard = 50000008
    MissileTorpedo = 50000003
    MineCard = 50000013
    cylonstationary1 = 10001165
    cylonstationary2 = 10001166
    cylonstationary3 = 10001167
    cylonstationary4 = 10001168
    cylonstationary5 = 10001169
    cylonstationary6 = 10001170
    humanstationary1 = 10001159
    humanstationary2 = 10001160
    humanstationary3 = 10001161
    humanstationary4 = 10001162
    humanstationary5 = 10001163
    humanstationary6 = 10001164
    OutpostCylon = 10000966
    OutpostColonial = 10000965

    @property
    def int_value(self) -> int:
        return self._value_

    @classmethod
    def from_code(cls, value: int) -> "WellKnownCard | None":
        return _STATIC_CARD_GUID_BY_VALUE.get(value)
_STATIC_CARD_GUID_BY_VALUE = {c.value: c for c in WellKnownCard}


class SceneChange(SorszamosEnum):
    None_ = 0
    Die = 1
    Undock = 2
    Ftl = 3
    Hangar = 4
    CIC = 5
    Recroom = 6
    Outpost = 7
    Minigfacility = 8
    FirstStory = 9
    Dock = 10
    Arena = 11
    Teaser = 12
    Battlespace = 13
    Tournament = 14


class AreaInfoKind(Enum):
    None_ = 0
    Scavenger = 1


class AreaRule(Enum):
    FactionBoard = 1
    ScoreBoard = 2
    FfaScoring = 3

    @property
    def value_byte(self) -> int:
        return self._value_

    def to_wire(self, bw) -> None:
        bw.write_byte(self._value_)
