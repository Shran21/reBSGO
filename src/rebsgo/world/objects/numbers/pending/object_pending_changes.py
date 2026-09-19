# github.com/Shran21
from __future__ import annotations

from rebsgo.world.objects.numbers.pending.pending_changes import PendingChanges
from rebsgo.world.objects.numbers.changes import StatChange
from rebsgo.world.objects.numbers.pending.object_change_kind import ObjectChangeKind
from rebsgo.gamedata.reading import ObjectStat


class ObjectPendingChanges(PendingChanges):
    def property_push_allowed(self, valtozas) -> bool:
        eredmeny = False
        update_type = valtozas.space_update_type
        if update_type in (ObjectChangeKind.HullPoints, ObjectChangeKind.PowerPoints, ObjectChangeKind.TargetID):
            eredmeny = True
        elif update_type == ObjectChangeKind.ObjectStat:
            object_stat_update: StatChange = valtozas
            if (object_stat_update.stat() == ObjectStat.MaxHullPoints
                or object_stat_update.stat() == ObjectStat.MaxPowerPoints):
                eredmeny = True
        return eredmeny
