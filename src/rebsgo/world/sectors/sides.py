# github.com/Shran21

from __future__ import annotations

from enum import Enum
from rebsgo.gamedata.reading import TargetBracketMode
from rebsgo.vocabulary.pilot import Faction


class Stance(Enum):
    Friend = 1
    Enemy = 2
    Neutral = 3
    Self = 4

    @property
    def int_value(self) -> int:
        return self._value_

    @staticmethod
    def from_code(value: int):
        return _BY_VALUE.get(value)
_BY_VALUE = {r.value: r for r in Stance}


VISZONYOK = (
    (lambda en, o, mod: en == o, Stance.Self),
    (lambda en, o, mod: en.spawned_by(o), Stance.Friend),
    (lambda en, o, mod: Faction.Neutral in (o.faction, en.faction), Stance.Neutral),
    (lambda en, o, mod: mod == TargetBracketMode.AllEnemy, Stance.Enemy),
    (lambda en, o, mod: o.faction == en.faction
     and o.faction_group == en.faction_group, Stance.Friend),
)


def relation(this_object, masik_objektum, target_bracket_mode) -> Stance:
    for rail_e, viszony in VISZONYOK:
        if rail_e(this_object, masik_objektum, target_bracket_mode):
            return viszony
    return Stance.Enemy
