# github.com/Shran21

from __future__ import annotations

from rebsgo.vocabulary.world import DepartureCause
from rebsgo.wire.bytes.outgoing import Outgoing
from rebsgo.helpers.inheriting import csak_orokosen_at


class DepartureNote(Outgoing):
    def __init__(self, departed_object, removing_cause):
        csak_orokosen_at(self, DepartureNote)
        self._departed_object = departed_object
        self._removed_space_object_obj_id = departed_object.id_in_space()
        self._removing_cause = removing_cause
        departed_object.mark_removal(removing_cause)

    def to_wire(self, bw) -> None:
        bw.write_uint32(self._removed_space_object_obj_id)
        bw.write_int32(0)
        bw.write_byte(self._removing_cause.byte_value)

    @property
    def departed_object(self):
        return self._departed_object

    @property
    def removed_space_object_obj_id(self) -> int:
        return self._removed_space_object_obj_id

    def removal_cause_of(self):
        return self._removing_cause

    def __repr__(self) -> str:
        return f'<{self._departed_object} left, {self._removing_cause}>' 


class CollectedNote(DepartureNote):
    def __init__(self, departed_object, gyujtes_mp: int):
        super().__init__(departed_object, DepartureCause.Collected)
        self._seconds_collect = gyujtes_mp

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_uint32(self._seconds_collect)


class JumpedOutNote(DepartureNote):
    def __init__(self, departed_object):
        super().__init__(departed_object, DepartureCause.JumpOut)


class KilledNote(DepartureNote):
    def __init__(self, departed_object, gyilkos):
        super().__init__(departed_object, DepartureCause.Death)
        self._killer_object = gyilkos

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_uint32(0)

    def killer_of(self):
        return self._killer_object


class LostLinkNote(DepartureNote):
    def __init__(self, departed_object):
        super().__init__(departed_object, DepartureCause.Disconnection)


class DockedNote(DepartureNote):
    def __init__(self, departed_object):
        super().__init__(departed_object, DepartureCause.Dock)


class HitNote(DepartureNote):
    def __init__(self, departed_object, talalat_erte):
        super().__init__(departed_object, DepartureCause.Hit)
        self._target_hit_object_id = talalat_erte.id_in_space()

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_uint32(self._target_hit_object_id)
