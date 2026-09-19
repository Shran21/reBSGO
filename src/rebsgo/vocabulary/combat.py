# github.com/Shran21

from __future__ import annotations

from enum import Enum
from rebsgo.helpers.floats import f32
from rebsgo.vocabulary.sorszamos_enum import SorszamosEnum


class AssistMedal(SorszamosEnum):
    None_ = 0
    GoldMedal = 1
    SilverMedal = 2
    BronzeMedal = 3


class KillerMedal(SorszamosEnum):
    None_ = 0
    GoldMedal = 1
    SilverMedal = 2
    BronzeMedal = 3


class ManeuverKind(SorszamosEnum):
    Pulse = 0
    Teleport = 1
    Rest = 2
    Warp = 3
    Directional = 4
    Launch = 5
    Rotation = 6
    Flip = 7
    Turn = 8
    Follow = 9
    DirectionalWithoutRoll = 10
    TurnQweasd = 11
    DirectionTurnPlan = 12
    PitchYawTurnPlan = 13
    TargetLaunch = 14


class PvpMedal(SorszamosEnum):
    None_ = 0
    PvpArena1st = 1
    PvpArena2nd = 2
    PvpArena3rd = 3
    PvpArena4thTo20th = 4
    PvpArena21stTo100th = 5


class SpecialMove(Enum):
    None_ = (0,)
    Assist = (0.5,)
    Killer = (0.7,)
    Saviour = (0,)
    Avenger = (0,)
    Buffer = (0.15,)
    Debuffer = (0.15,)
    AssistCountingAsKill = (1,)
    Tank = (0,)

    def __new__(cls, loot_multiplier):
        obj = object.__new__(cls)
        obj._value_ = len(cls.__members__)
        obj.loot_multiplier = f32(loot_multiplier)
        return obj

    @classmethod
    def from_code(cls, value: int) -> "SpecialMove":
        return list(cls)[value]

    def to_wire(self, bw) -> None:
        bw.write_uint16(self.value)


class SpeedMode(Enum):
    None_ = -1
    Abs = 0
    Delta = 1
    Stop = 2
    Full = 3

    @property
    def int_value(self) -> int:
        return self._value_

    @classmethod
    def from_code(cls, value: int) -> "SpeedMode | None":
        return _SPEED_MODE_BY_VALUE.get(value)
_SPEED_MODE_BY_VALUE = {m.value: m for m in SpeedMode}


class TournamentMedal(SorszamosEnum):
    None_ = 0
    GoldMedal = 1
    SilverMedal = 2


class WeaponEffect(SorszamosEnum):
    Undefined = 0
    Gun = 1
    MissileLauncher = 2
    PointDefence = 3
    Flak = 4
    Shrapnel = 5
    SpotFlak = 6
    AoEFlak = 7
    MachineGun = 8
    Flechete = 9
    Railgun = 10
