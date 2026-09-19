# github.com/Shran21
from __future__ import annotations

import logging

from rebsgo.wire.bytes.outgoing import Outgoing
from rebsgo.world.movement.movers import FixedMover
from rebsgo.world.objects.attachments import ObjectState
from rebsgo.vocabulary.world import ArrivalCause, DepartureCause
from rebsgo.helpers.inheriting import csak_orokosen_at

log = logging.getLogger(__name__)


class WorldObject(Outgoing):
    def __init__(self, object_id: int, owner_card, world_card, space_entity_type, faction,
                 faction_group, space_subscribe_info):
        csak_orokosen_at(self, WorldObject)
        self._object_id = object_id
        self._space_entity_type = space_entity_type
        self._faction = faction
        self._faction_group = faction_group

        self._world_card = world_card
        self._owner_card = owner_card
        self._space_subscribe_info = space_subscribe_info

        self._space_object_state = ObjectState.create_for_object_id(object_id)

        self._creating_cause = ArrivalCause.JumpIn
        self._removing_cause = None
        self._mover = None
        self._collider = None


    def id_in_space(self) -> int:
        return self._object_id

    def pilot_id(self) -> int:
        return -1

    @property
    def faction(self):
        return self._faction

    @property
    def faction_group(self):
        return self._faction_group

    @property
    def space_entity_type(self):
        return self._space_entity_type

    def is_player(self) -> bool:
        return False

    @property
    def is_ship(self) -> bool:
        return False


    def world_card(self):
        return self._world_card

    @property
    def owner_card(self):
        return self._owner_card

    @property
    def prefab_name(self) -> str:
        return self._world_card.prefab_name


    def fresh_mover(self, transform) -> None:
        self._mover = FixedMover(transform)

    def mover_of(self):
        return self._mover

    def transform_of(self):
        return self._mover.transform_of()

    def collider_of(self):
        return self._collider

    @property
    def carries_collider(self) -> bool:
        return self._collider is not None

    def wear_collider(self, collider) -> None:
        self._collider = collider


    def to_wire(self, bw) -> None:
        bw.write_byte(self._creating_cause.value)
        bw.write_uint32(self._owner_card.card_guid_of())
        bw.write_uint32(self._world_card.card_guid_of())

    def space_subscribe_info(self):
        return self._space_subscribe_info

    def world_state_of(self):
        return self._space_object_state

    def is_visible(self) -> bool:
        return True


    @property
    def creating_cause(self):
        return self._creating_cause

    @creating_cause.setter
    def creating_cause(self, creating_cause) -> None:
        self._creating_cause = creating_cause

    def spawned_by(self, kelto) -> bool:
        return False

    def mark_removal(self, removing_cause) -> None:
        if removing_cause is None:
            log.error('departure cause absent')
            return
        if self._removing_cause is not None:
            log.error('departure recorded twice for #%s: was %s, now %s',
                      self._object_id, self._removing_cause, removing_cause)
            return
        self._removing_cause = removing_cause

    def removal_cause_of(self):
        return self._removing_cause

    @property
    def removing_cause_direct(self):
        return self._removing_cause

    def is_removed(self) -> bool:
        return self._removing_cause is not None

    def is_dead(self) -> bool:
        return self._removing_cause == DepartureCause.Death


    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if type(other) is not type(self):
            return NotImplemented
        return self._object_id == other._object_id

    def __hash__(self) -> int:
        return hash(self._object_id)

    def __repr__(self) -> str:
        sorsa = (f'arrived {self._creating_cause}' if self._removing_cause is None
                 else f'left {self._removing_cause}')
        return (f'<{self._space_entity_type} #{self._object_id} of {self._faction}'
                f'/{self._faction_group}, {sorsa}; {self._mover};'
                f' hull {self._collider}; {self._space_subscribe_info};'
                f' {self._space_object_state}>')
