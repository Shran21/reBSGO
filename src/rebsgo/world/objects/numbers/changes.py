# github.com/Shran21

from __future__ import annotations

from rebsgo.wire.bytes.outgoing import Outgoing
from rebsgo.world.objects.numbers.pending.object_change_kind import ObjectChangeKind


class PropertyChange(Outgoing):
    def __init__(self, valtozas_fajta):
        self.space_update_type = valtozas_fajta

    def to_wire(self, bw) -> None:
        bw.write_byte(self.space_update_type.value)

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if type(other) is not type(self):
            return NotImplemented
        return self.space_update_type == other.space_update_type

    def __hash__(self) -> int:
        return hash(self.space_update_type) if self.space_update_type is not None else 0

    def __str__(self) -> str:
        return "<PropertyChange " + f"space_update_type={self.space_update_type}" + ">"


class CombatChange(PropertyChange):
    def __init__(self, under_fire: bool):
        super().__init__(ObjectChangeKind.CombatStatus)
        self._is_in_combat = under_fire

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_boolean(self._is_in_combat)

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not super().__eq__(other):
            return False
        return self._is_in_combat == other._is_in_combat

    def __hash__(self) -> int:
        return hash((self.space_update_type, self._is_in_combat))

    def __str__(self) -> str:
        return "<CombatChange " + f"is_in_combat={self._is_in_combat}, space_update_type={self.space_update_type}" + ">"


class HullChange(PropertyChange):
    def __init__(self, hp: float):
        super().__init__(ObjectChangeKind.HullPoints)
        self._hp = hp

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_single(self._hp)

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not super().__eq__(other):
            return False
        return self._hp == other._hp

    def __hash__(self) -> int:
        return hash((self.space_update_type, self._hp))

    def __str__(self) -> str:
        return "<HullChange " + f"hp={self._hp}, space_update_type={self.space_update_type}" + ">"


class PowerChange(PropertyChange):
    def __init__(self, power_now: float):
        super().__init__(ObjectChangeKind.PowerPoints)
        self._pp = power_now

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_single(self._pp)

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not super().__eq__(other):
            return False
        return self._pp == other._pp

    def __hash__(self) -> int:
        return hash((self.space_update_type, self._pp))

    def __str__(self) -> str:
        return "<PowerChange " + f"pp={self._pp}, space_update_type={self.space_update_type}" + ">"


class ShipTraitChange(PropertyChange):
    def __init__(self, ship_aspects):
        super().__init__(ObjectChangeKind.ShipTrait)
        self._ship_aspects = ship_aspects

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_desc(self._ship_aspects)

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not super().__eq__(other):
            return False
        return self._ship_aspects is other._ship_aspects

    def __hash__(self) -> int:
        return hash(self.space_update_type)

    def __str__(self) -> str:
        return "<ShipTraitChange " + f"ship_aspects={self._ship_aspects}" + ">"


class SlotChange(PropertyChange):
    def __init__(self, slot_id: int, stat, value: float):
        super().__init__(ObjectChangeKind.SlotStat)
        self._slot_id = slot_id
        self._stat = stat
        self._value = value

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_byte(self._slot_id)
        bw.write_uint16(self._stat.value)
        bw.write_single(self._value)

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not super().__eq__(other):
            return False
        return self._slot_id == other._slot_id and self._stat == other._stat

    def __hash__(self) -> int:
        return hash((self.space_update_type, self._slot_id, self._stat))

    def __str__(self) -> str:
        return (f'<slot {self._slot_id}: {self._stat} = {self._value}'
                f' ({self.space_update_type})>')


class StatChange(PropertyChange):
    def __init__(self, stat, value: float):
        super().__init__(ObjectChangeKind.ObjectStat)
        self._stat = stat
        self._value = value

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_uint16(self._stat.value)
        bw.write_single(self._value)

    def stat(self):
        return self._stat

    @property
    def value(self) -> float:
        return self._value

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not super().__eq__(other):
            return False
        return self._value == other._value and self._stat == other._stat

    def __hash__(self) -> int:
        return hash((self.space_update_type, self._stat, self._value))

    def __str__(self) -> str:
        return ("<StatChange " + f"stat={self._stat}, value={self._value},"
                f" space_update_type={self.space_update_type}" + ">")


class TargetChange(PropertyChange):
    def __init__(self, target_id: int):
        super().__init__(ObjectChangeKind.TargetID)
        self._target_id = target_id

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_uint32(self._target_id)

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not super().__eq__(other):
            return False
        return self._target_id == other._target_id

    def __hash__(self) -> int:
        return hash((self.space_update_type, self._target_id))

    def __str__(self) -> str:
        return f'<target now {self._target_id} ({self.space_update_type})>' 


class TweakAdded(PropertyChange):
    def __init__(self, modosito):
        super().__init__(ObjectChangeKind.AddBuff)
        if modosito is None:
            raise TypeError('the modifier being added is required')
        self._new_modifier = modosito

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_desc(self._new_modifier)

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not super().__eq__(other):
            return False
        return self._new_modifier == other._new_modifier

    def __hash__(self) -> int:
        return hash((self.space_update_type, self._new_modifier))


class TweakRemoved(PropertyChange):
    def __init__(self, modifier_id: int):
        super().__init__(ObjectChangeKind.RemoveBuff)
        self._to_remove_id = modifier_id

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_uint32(self._to_remove_id)

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not super().__eq__(other):
            return False
        return self._to_remove_id == other._to_remove_id

    def __hash__(self) -> int:
        return hash((self.space_update_type, self._to_remove_id))
