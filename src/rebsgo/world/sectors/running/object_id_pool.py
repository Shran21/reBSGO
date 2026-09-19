# github.com/Shran21
from __future__ import annotations

import logging

from rebsgo.world.sectors.running.coming_and_going import DepartureWatcher
from rebsgo.world.sectors.running.wraparound import Wraparound
from rebsgo.vocabulary.pilot import FactionGroup
from rebsgo.helpers.locks import ReentrantLock

log = logging.getLogger(__name__)


class ObjectIdPool(DepartureWatcher):
    def __init__(self):
        overall_used_ids = set()
        id_counter_map = {}
        lock = ReentrantLock()
        self._overall_used_ids = overall_used_ids
        self._id_counter_map = id_counter_map
        self._lock = lock

    def free_object_id(self, space_entity_type, faction, faction_group=FactionGroup.Group0) -> int:
        with self._lock:
            ring_counter = self._id_counter_map.get(space_entity_type)
            if ring_counter is None:
                ring_counter = Wraparound(space_entity_type.value, space_entity_type.value + 0x01000000)

            free_id = ring_counter.next_id_for(faction, faction_group)
            while free_id in self._overall_used_ids:
                free_id = ring_counter.next_id_for(faction, faction_group)
            self._overall_used_ids.add(free_id)

            self._id_counter_map[space_entity_type] = ring_counter

            return free_id

    def forget_object(self, id_: int) -> bool:
        with self._lock:
            if id_ in self._overall_used_ids:
                self._overall_used_ids.remove(id_)
                return True
            return False

    def on_update(self, arg) -> None:
        contained = self.forget_object(arg.departed_object.id_in_space())
        if not contained:
            log.error("WorldObject removed id but did not contain! %s", arg)
