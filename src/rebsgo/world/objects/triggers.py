# github.com/Shran21

from __future__ import annotations

from rebsgo.world.objects.world_object import WorldObject
from rebsgo.helpers.floats import f32, fdiv
from enum import Enum
from rebsgo.vocabulary.pilot import Faction, FactionGroup
from rebsgo.vocabulary.world import ObjectKind


class CaptureTrigger(WorldObject):
    def __init__(self, object_id, owner_card, world_card, space_entity_type, faction, faction_group,
                 space_subscribe_info, parent, radius):
        super().__init__(object_id, owner_card, world_card, space_entity_type, faction, faction_group,
                         space_subscribe_info)
        self._parent = parent
        self._radius = f32(radius)

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_uint32(self._parent)
        bw.write_single(self._radius)

    def parent(self) -> int:
        return self._parent

    def radius_of(self) -> float:
        return self._radius


class WorldTrigger(WorldObject):
    def __init__(self, object_id, owner_card, world_card, space_entity_type, faction, faction_group,
                 space_subscribe_info, name, position, radius):
        super().__init__(object_id, owner_card, world_card, space_entity_type, faction, faction_group,
                         space_subscribe_info)
        self._name = name
        self._position = position
        self._radius = f32(radius)

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_string(self._name)
        bw.write_vector3(self._position)
        bw.write_single(self._radius)


class EventZone(WorldObject):
    class RadiationLevel(Enum):
        None_ = 0
        Low = 1
        Medium = 2
        High = 3
        Critical = 4

    class VolumeEventKind(Enum):
        None_ = 0
        SectorBorder = 1
        Capture = 2

    def __init__(self, object_id, owner_card, world_card, space_subscribe_info, radius, inverted,
                 volume_notification_type):
        super().__init__(object_id, owner_card, world_card, ObjectKind.Volume, Faction.Neutral,
                         FactionGroup.Group0, space_subscribe_info)
        self._radius = f32(radius)
        self._inverted = inverted
        self._volume_notification_type = volume_notification_type

    def to_wire(self, bw) -> None:
        super().to_wire(bw)

        bw.write_vector3(self.mover_of().position_of())
        bw.write_single(self._radius)
        bw.write_boolean(self._inverted)
        bw.write_byte(self._volume_notification_type.value)

    SUGARZAS_SAVOK = (
        (0.75, "Low"),
        (0.5, "Medium"),
        (0.25, "High"),
    )

    def _radiation_at(self, distance: float):
        if self._inverted or distance <= 0.0:
            return EventZone.RadiationLevel.None_
        arany = f32(fdiv(distance, self._radius))
        if arany > 1.0:
            return EventZone.RadiationLevel.None_
        for kuszob, szint in EventZone.SUGARZAS_SAVOK:
            if arany > kuszob:
                return getattr(EventZone.RadiationLevel, szint)
        return EventZone.RadiationLevel.Critical


class SectorEvent(WorldObject):
    def __init__(self, object_id, owner_card, world_card, faction, faction_group, space_subscribe_info,
                 sector_event_card):
        super().__init__(object_id, owner_card, world_card, ObjectKind.SectorEvent, faction,
                         faction_group, space_subscribe_info)
        self._sector_event_card = sector_event_card

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_guid(self._sector_event_card.card_guid_of())
