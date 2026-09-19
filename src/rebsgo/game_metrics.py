# github.com/Shran21
from __future__ import annotations

import logging
import threading

from rebsgo.vocabulary.pilot import Faction
from rebsgo.vocabulary.world import ObjectKind

log = logging.getLogger(__name__)


class _Counter:
    def __init__(self):
        self._value = 0.0
        self._lock = threading.Lock()

    def increment(self, amount: float = 1.0) -> None:
        with self._lock:
            self._value += amount

    def get(self) -> float:
        return self._value


class _MeroTar:

    def __init__(self):
        self._counters = {}
        self._gauges = {}
        self._lock = threading.Lock()

    @staticmethod
    def _key(name, tags):
        return (name, frozenset(tags.items()))

    def counter(self, name, tags=None) -> _Counter:
        tags = tags or {}
        kulcs = self._key(name, tags)
        with self._lock:
            counter = self._counters.get(kulcs)
            if counter is None:
                counter = _Counter()
                self._counters[kulcs] = counter
            return counter

    def gauge(self, name, tags, obj, fn) -> None:
        tags = tags or {}
        with self._lock:
            self._gauges[self._key(name, tags)] = (obj, fn)


class JatekMerok:
    def __init__(self, meter_registry=None, pilot_roster=None):
        self._meter_registry = meter_registry if meter_registry is not None else _MeroTar()
        self._pilot_roster = pilot_roster

    def on_init(self) -> None:
        self.setup_user_cnt()
        self.seed_level_sum()

    def wof_played(self, faction, huzasok: int) -> None:
        self._meter_registry.counter("wheel.spins", {"side": faction.name}).increment(huzasok)

    def watch_sector_headcount(self, sector) -> None:
        try:
            sector_users = sector.ctx.users()
            self._meter_registry.gauge(
                "sector.pilots",
                {"sector": str(sector.id), "side": Faction.Colonial.name},
                sector_users,
                lambda value: value.user_cnt_based_on_faction(Faction.Colonial))
            self._meter_registry.gauge(
                "sector.pilots",
                {"sector": str(sector.id), "side": Faction.Cylon.name},
                sector_users,
                lambda value: value.user_cnt_based_on_faction(Faction.Cylon))

            for space_entity_type in ObjectKind:
                space_objects = sector.ctx.space_objects()
                self._meter_registry.gauge(
                    "sector.objects",
                    {"sector": str(sector.id), "kind": space_entity_type.name},
                    space_objects,
                    lambda value, _t=space_entity_type: len(value.space_objects_of_entity_type(_t)))

            try:
                space_objects = sector.ctx.space_objects()
                self._meter_registry.gauge(
                    "sector.outposts",
                    {"sector": str(sector.id), "side": Faction.Colonial.name},
                    space_objects,
                    lambda value: sum(1 for op in value.space_objects_of_entity_type(ObjectKind.Outpost)
                                      if op.faction == Faction.Colonial))
                self._meter_registry.gauge(
                    "sector.outposts",
                    {"sector": str(sector.id), "side": Faction.Cylon.name},
                    space_objects,
                    lambda value: sum(1 for op in value.space_objects_of_entity_type(ObjectKind.Outpost)
                                      if op.faction == Faction.Cylon))
            except Exception as exception:
                log.error('cause unknown', exc_info=exception)
        except Exception as exception:
            log.error('cause unknown', exc_info=exception)

    def setup_user_cnt(self) -> None:
        if self._pilot_roster is None:
            return
        self._meter_registry.gauge(
            "pilots.online", {"side": Faction.Colonial.name},
            self._pilot_roster.colonial_count, lambda al: al.get())
        self._meter_registry.gauge(
            "pilots.online", {"side": Faction.Cylon.name},
            self._pilot_roster.cylon_count, lambda al: al.get())

    def seed_level_sum(self) -> None:
        if self._pilot_roster is None:
            return
        self._meter_registry.gauge(
            "pilots.level-sum", {"side": Faction.Colonial.name},
            self._pilot_roster.colonial_sum_level, lambda al: al.get())
        self._meter_registry.gauge(
            "pilots.level-sum", {"side": Faction.Cylon.name},
            self._pilot_roster.cylon_sum_level, lambda al: al.get())

    def object_gone(self, sector_id: int, space_entity_type, faction, removing_cause) -> None:
        self._meter_registry.counter(
            "objects.gone",
            {"sector": str(sector_id),
             "kind": space_entity_type.name,
             "side": faction.name,
             "cause": removing_cause.name}).increment()

    def resource_earned(self, sector_id: int, nyersanyag_guid: int, faction, amount: int, zsakmany_forras) -> None:
        self._meter_registry.counter(
            "resources.earned",
            {"sector": str(sector_id),
             "resource": str(nyersanyag_guid),
             "side": faction.name,
             "source": zsakmany_forras.name}).increment(amount)

    def assignment_handed_in(self, faction) -> None:
        self._meter_registry.counter(
            "assignments.handed-in", {"side": faction.name}).increment()
