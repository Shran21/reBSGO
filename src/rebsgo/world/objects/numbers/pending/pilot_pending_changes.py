# github.com/Shran21
from __future__ import annotations

from rebsgo.world.objects.numbers.pending.pending_changes import PendingChanges


class PilotPendingChanges(PendingChanges):
    def property_push_allowed(self, valtozas) -> bool:
        return True
