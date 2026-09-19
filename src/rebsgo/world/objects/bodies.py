# github.com/Shran21

from __future__ import annotations

from rebsgo.world.objects.world_object import WorldObject
from rebsgo.vocabulary.pilot import Faction, FactionGroup
from rebsgo.vocabulary.world import ObjectKind
from rebsgo.helpers.floats import f32
from rebsgo.world.objects.numbers.kinds import SpaceFeed
from rebsgo.gamedata.reading import ObjectStats
from rebsgo.helpers.locks import ReentrantLock
from rebsgo.world.movement.movers import FreeMover
from enum import Enum
from rebsgo.world.objects.ships import Ship


class Asteroid(WorldObject):
    def __init__(self, object_id, owner_card, world_card, subscribe_info, radius,
                 rotation_speed, *, kind=ObjectKind.Asteroid,
                 faction=Faction.Neutral, faction_group=FactionGroup.Group0):
        super().__init__(object_id, owner_card, world_card, kind, faction, faction_group,
                         subscribe_info)
        self._radius = f32(radius)
        self._rotation_speed = f32(rotation_speed)

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_vector3(self._mover.position_of())
        bw.write_single(self._radius)
        bw.write_single(self._rotation_speed)

    def radius_of(self) -> float:
        return self._radius

    @property
    def rotation_speed(self) -> float:
        return self._rotation_speed


class Planet(WorldObject):
    def __init__(self, object_id, owner_card, world_card, position, rotation, scale, color,
                 specular_color, shininess, faction=Faction.Neutral):
        super().__init__(object_id, owner_card, world_card, ObjectKind.Planet, faction,
                         FactionGroup.Group0, SpaceFeed(object_id, ObjectStats()))

        self._position = position
        self._rotation = rotation
        self._scale = f32(scale)
        self._color = color
        self._specular_color = specular_color
        self._shininess = f32(shininess)

    @property
    def color(self):
        return self._color

    @property
    def scale(self) -> float:
        return self._scale

    @property
    def shininess(self) -> float:
        return self._shininess

    @property
    def specular_color(self):
        return self._specular_color

    def position_of(self):
        return self._position

    def rotation_of(self):
        return self._rotation

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_vector3(self._position)
        bw.write_quaternion(self._rotation)
        bw.write_single(self._scale)
        bw.write_color(self._color)
        bw.write_color(self._specular_color)
        bw.write_single(self._shininess)


class Planetoid(Asteroid):
    def __init__(self, object_id, owner_card, world_card, subscribe_info, radius):
        super().__init__(object_id, owner_card, world_card, subscribe_info, radius, 0.0,
                         kind=ObjectKind.Planetoid)
        self._mining_ship = None
        self._last_time_mining_ship_added = 0
        self.lock = ReentrantLock()

    @property
    def last_time_mining_ship_added(self) -> int:
        return self._last_time_mining_ship_added

    def owns_miner(self) -> bool:
        with self.lock:
            if self._mining_ship is not None:
                return not self._mining_ship.is_removed()
            return False

    def set_mining_ship(self, mining_ship, tick) -> None:
        with self.lock:
            self._mining_ship = mining_ship
            self._last_time_mining_ship_added = tick.time_stamp()


class Comet(WorldObject):
    def __init__(self, object_id, owner_card, world_card, movement_card, space_subscribe_info):
        super().__init__(object_id, owner_card, world_card, ObjectKind.Comet, Faction.Neutral,
                         FactionGroup.Group0, space_subscribe_info)
        self._movement_card = movement_card

    def fresh_mover(self, transform) -> None:
        self._mover = FreeMover(transform, self._movement_card)


class DebrisPile(WorldObject):
    def __init__(self, object_id, owner_card, world_card, faction_group, space_subscribe_info,
                 scale, rotation_speed):
        super().__init__(object_id, owner_card, world_card, ObjectKind.Debris, Faction.Neutral,
                         faction_group, space_subscribe_info)
        self._scale = scale
        self._rotation_speed = f32(rotation_speed)

    def to_wire(self, bw) -> None:
        super().to_wire(bw)

        bw.write_vector3(self._mover.position_of())
        bw.write_quaternion(self._mover.rotation_of())
        bw.write_vector3(self._scale)
        bw.write_single(self._rotation_speed)


class CargoInteractionResult(Enum):
    Failed = 0
    Canceled = 1
    Wait = 2
    Empty = 3
    Full = 4
    Range = 5
    Lost = 6
    Success = 7
    Pickup = 8
    Dropoff = 9


class JumpBeacon(Ship):
    def __init__(self, object_id, owner_card, world_card, faction, faction_group, ship_bindings,
                 ship_aspects, hajo_allapot, ship_card):
        super().__init__(object_id, owner_card, world_card, ObjectKind.JumpBeacon, faction,
                         faction_group, ship_bindings, ship_aspects, hajo_allapot, ship_card)


class Transponder(WorldObject):
    def __init__(self, object_id, owner_card, world_card, faction, faction_group, space_subscribe_info,
                 time_when_active, time_when_inactive):
        super().__init__(object_id, owner_card, world_card, ObjectKind.Transponder,
                         faction, faction_group, space_subscribe_info)
        self._time_when_active = time_when_active
        self._time_when_inactive = time_when_inactive

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_date_time(self._time_when_active)
        bw.write_date_time(self._time_when_inactive)

    @property
    def time_when_active(self):
        return self._time_when_active

    @property
    def time_when_inactive(self):
        return self._time_when_inactive


class CargoObject(WorldObject):
    class Interaction(Enum):
        None_ = 0
        Pickup = 1
        Dropoff = 2
        Loot = 3

        def to_wire(self, bw) -> None:
            bw.write_byte(self.value)

        @staticmethod
        def from_code(value: int):
            for interaction in CargoObject.Interaction:
                if interaction.value == value:
                    return interaction
            return None

    def __init__(self, object_id, owner_card, world_card, faction, faction_group, space_subscribe_info,
                 range_, interaction):
        super().__init__(object_id, owner_card, world_card, ObjectKind.CargoObject, faction,
                         faction_group, space_subscribe_info)
        self._range = f32(range_)
        self._interaction = interaction

    @property
    def range(self) -> float:
        return self._range

    @property
    def interaction(self):
        return self._interaction

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        transform = self.transform_of()
        bw.write_vector3(transform.position_of())
        bw.write_quaternion(transform.rotation_of())

        bw.write_single(self._range)
        bw.write_desc(self._interaction)
