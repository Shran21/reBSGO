# github.com/Shran21
from __future__ import annotations

import logging
from abc import abstractmethod

from rebsgo.wire.bytes.outgoing import Outgoing
from rebsgo.world.objects.numbers.changes import TweakAdded, CombatChange, HullChange, StatChange, PowerChange, TweakRemoved, SlotChange, TargetChange
from rebsgo.world.objects.numbers.pending.object_change_kind import ObjectChangeKind
from rebsgo.world.objects.numbers.watchers import StatEntry
from rebsgo.vocabulary.pilot import ShipTrait
from rebsgo.gamedata.reading import ObjectStat
from rebsgo.helpers.carrier_transponder_diagnostics import (
    carrier_transponder_debug_enabled,
    format_ship_aspects,
    has_ship_aspect,
    safe_call,
)
from rebsgo.helpers.locks import ReentrantLock

_log = logging.getLogger(__name__)

_UNIQUE_TYPES = (ObjectChangeKind.HullPoints, ObjectChangeKind.PowerPoints,
                 ObjectChangeKind.TargetID, ObjectChangeKind.CombatStatus)


class PendingChanges(Outgoing):
    def __init__(self, owner, stat_figyelo):
        self._owner = owner
        self.stats_protocol_subscriber = stat_figyelo
        self.property_updates = set()
        self.unique_property_updates: dict = {}
        self._lock = ReentrantLock()

    @staticmethod
    def create(owner, stat_figyelo):
        from rebsgo.protocol.protocol_id import ProtocolID
        from rebsgo.world.objects.numbers.pending.pilot_pending_changes import PilotPendingChanges
        from rebsgo.world.objects.numbers.pending.object_pending_changes import ObjectPendingChanges
        from rebsgo.world.objects.numbers.pending.watch_pending_changes import WatchPendingChanges
        naplok = {
            ProtocolID.Pilot: PilotPendingChanges,
            ProtocolID.Subscribe: WatchPendingChanges,
            ProtocolID.Game: ObjectPendingChanges,
        }
        naplo = naplok.get(stat_figyelo.protocol_id_of())
        return None if naplo is None else naplo(owner, stat_figyelo)

    @abstractmethod
    def property_push_allowed(self, valtozas) -> bool:
        ...

    def _add_update(self, valtozas) -> None:
        if not self.property_push_allowed(valtozas):
            return
        if valtozas.space_update_type in _UNIQUE_TYPES:
            self.unique_property_updates[valtozas.space_update_type] = valtozas
        else:
            if valtozas in self.property_updates:
                self.property_updates.remove(valtozas)
            self.property_updates.add(valtozas)

    @property
    def is_updated(self) -> bool:
        with self._lock:
            return not (len(self.property_updates) == 0 and len(self.unique_property_updates) == 0)

    def _get_all_updates(self) -> list:
        updates = list(self.property_updates)
        self.property_updates.clear()
        updates.extend(self.unique_property_updates.values())
        self.unique_property_updates.clear()
        return updates

    def to_wire(self, bw) -> None:
        with self._lock:
            bw.write_desc_collection(self._get_all_updates())

    def push_ship_aspect_update(self, ship_aspects) -> None:
        from rebsgo.world.objects.numbers.changes import ShipTraitChange
        with self._lock:
            update = ShipTraitChange(ship_aspects)
            if carrier_transponder_debug_enabled() and has_ship_aspect(ship_aspects, ShipTrait.TransponderJump):
                _log.info(
                    "CARRIER_TRANSPONDER_DIAG push_ship_aspect_update owner=%s owner_is_user=%s "
                    "subscriber_protocol=%s buffer=%s allowed=%s aspects=%s",
                    safe_call(self._owner, "owner_id"),
                    safe_call(self._owner, "is_user"),
                    safe_call(self.stats_protocol_subscriber, "protocol_id_of"),
                    type(self).__name__,
                    self.property_push_allowed(update),
                    format_ship_aspects(ship_aspects))
            self._add_update(update)

    def on_stat_moved(self, space_subscribe_info, stat_adat) -> None:
        with self._lock:
            if stat_adat == StatEntry.Hp:
                self._add_update(HullChange(space_subscribe_info.hp))
            elif stat_adat == StatEntry.Pp:
                self._add_update(PowerChange(space_subscribe_info.pp))
            elif stat_adat == StatEntry.Combat:
                self._add_update(CombatChange(space_subscribe_info.is_in_combat))
            elif stat_adat == StatEntry.Target:
                if (celpont := space_subscribe_info.target_object_id) is not None:
                    self._add_update(TargetChange(celpont.get()))
            elif stat_adat == StatEntry.Stats:
                for stat, ertek in space_subscribe_info.stats_of.all_stats.items():
                    self._add_update(StatChange(stat, ertek))

    def on_slot_update(self, space_subscribe_info, slot_id: int) -> None:
        rekeszek = space_subscribe_info.ship_slots
        if rekeszek is None:
            return
        slot = rekeszek.slot(slot_id)
        with self._lock:
            if slot.ship_system is None:
                return
            if slot.ship_ability() is None:
                return
            for stat, ertek in slot.ship_ability().item_buff_add.all_stats.items():
                self._add_update(SlotChange(slot_id, stat, ertek))
            self._add_update(SlotChange(
                slot_id, ObjectStat.MinRange,
                slot.ship_ability().item_buff_add.stat_or_default(ObjectStat.MinRange)))

    def on_modifier_add(self, space_subscribe_info, uj_hatasok) -> None:
        with self._lock:
            for new_buff in uj_hatasok:
                self.property_updates.add(TweakAdded(new_buff))

    def on_modifier_remove(self, space_subscribe_info, removed_buff_ids) -> None:
        with self._lock:
            for removed_buff_id in removed_buff_ids:
                self.property_updates.add(TweakRemoved(removed_buff_id))

    def __str__(self) -> str:
        return ("<PendingChanges " + f"owner={self._owner}, property_updates={self.property_updates},"
                f" unique_property_updates={self.unique_property_updates},"
                f" stats_protocol_subscriber={self.stats_protocol_subscriber}" + ">")

    @property
    def owner(self):
        return self._owner
