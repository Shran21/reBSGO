# github.com/Shran21
from __future__ import annotations

from enum import Enum


class ObjectChangeKind(Enum):
    ObjectStat = 1
    AddBuff = 2
    CombatStatus = 3
    TargetID = 4
    RemoveBuff = 5
    PowerPoints = 6
    HullPoints = 7
    Reset = 9
    SlotStat = 12
    ShipTrait = 13
    AddToggleBuff = 14
    RemoveToggleBuff = 15
    AddStatsModifier = 16
    RemoveBuffGUID = 17
    ShortCircuited = 18
    ShortRemovedGUID = 19
    CaptureStatus = 20
    AddSectorModifier = 21
    RemoveSectorModifier = 22
    VitalPointsChanged = 23

    @classmethod
    def from_code(cls, value: int) -> "ObjectChangeKind | None":
        return _BY_VALUE.get(value)


_BY_VALUE = {member.value: member for member in ObjectChangeKind}
