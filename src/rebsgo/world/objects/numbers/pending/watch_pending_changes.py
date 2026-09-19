# github.com/Shran21
from __future__ import annotations

from rebsgo.world.objects.numbers.pending.pending_changes import PendingChanges
from rebsgo.world.objects.numbers.changes import StatChange
from rebsgo.world.objects.numbers.pending.object_change_kind import ObjectChangeKind
from rebsgo.gamedata.reading import ObjectStat


class WatchPendingChanges(PendingChanges):
    def property_push_allowed(self, valtozas) -> bool:
        update_type = valtozas.space_update_type
        return_type = False
        if update_type in (ObjectChangeKind.AddBuff, ObjectChangeKind.RemoveBuff, ObjectChangeKind.HullPoints):
            return_type = True
        elif update_type == ObjectChangeKind.PowerPoints:
            return_type = True
        elif update_type == ObjectChangeKind.TargetID:
            return_type = True
        elif update_type == ObjectChangeKind.ObjectStat:
            stat_ud: StatChange = valtozas
            if (stat_ud.stat() == ObjectStat.MaxPowerPoints
                or stat_ud.stat() == ObjectStat.MaxHullPoints):
                return_type = True
        return return_type
