# github.com/Shran21
from __future__ import annotations

from rebsgo.world.sectors.departures.notes import DepartureNote
from rebsgo.vocabulary.world import DepartureCause


class ObjectLeftJustRemoved(DepartureNote):
    def __init__(self, departed_object):
        super().__init__(departed_object, DepartureCause.JustRemoved)
