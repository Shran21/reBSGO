# github.com/Shran21

from __future__ import annotations

from abc import ABC, abstractmethod
from rebsgo.geometry.primitives.quaternion import Quaternion
from rebsgo.geometry.primitives.transform import Transform
from rebsgo.geometry.primitives.vector3 import Vector3
from rebsgo.helpers.floats import f32, fdiv
import math
from rebsgo.services import Services
from rebsgo.vocabulary.world import ArrivalCause, ObjectKind
from rebsgo.geometry.primitives.euler3 import Euler3
from rebsgo.geometry.primitives.common import CommonDirections
from rebsgo.gamedata.library import Catalogue
from rebsgo.gamedata.object_templates import AsteroidSpec
from rebsgo.geometry.maths.maths import Maths


class GroupSpawn(ABC):
    @abstractmethod
    def parent(self):
        ...

    @abstractmethod
    def children(self):
        ...

    @abstractmethod
    def create(self) -> None:
        ...


class AsteroidBelt(GroupSpawn):
    def __init__(self, sector, aszteroida_darab: int, min_distance: float, max_distance: float, angle_shift: float, kocka, spread_from_centre: int):
        self._catalogue = Services.get(Catalogue)
        self._sector = sector
        self._rnd = kocka
        self._spread_from_centre = spread_from_centre
        self._asteroid_count = aszteroida_darab
        self._min_distance = min_distance
        self._max_distance = max_distance
        self._angle_offset = angle_shift
        self._ring_asteroids = []
        self._parent_transform = None

    def parent(self):
        raise RuntimeError('this ring has no parent')

    def children(self):
        return self._ring_asteroids

    def create(self) -> None:
        all_asteroids_world_cards = self._catalogue.all_asteroid_world_cards
        position_offset = Vector3(
            self._rnd.between_wide(-self._spread_from_centre, self._spread_from_centre),
            self._rnd.between_wide(int(-self._spread_from_centre / 10), int(self._spread_from_centre / 10)),
            self._rnd.between_wide(-self._spread_from_centre, self._spread_from_centre))
        self._shape_parent_transform(position_offset)

        random_angle = self._rnd.frac(0, 30.0)
        eltolas = self._rnd.frac(0, 180.0)
        for i in range(self._asteroid_count + 1):
            rnd_dist = self._rnd.between(self._min_distance, self._max_distance)
            lepes = f32(fdiv(360.0, f32(self._asteroid_count)))
            scaled_angle_offset = f32(f32(fdiv(rnd_dist, self._max_distance)) * self._angle_offset)
            scale = f32(fdiv(i, f32(self._asteroid_count)))
            forgatas = Euler3(
                0,
                lepes * i + eltolas,
                math.sin(scale * math.pi * 2) * random_angle
                + self._rnd.between(-scaled_angle_offset, scaled_angle_offset))
            pos = forgatas.quaternion.mult_(CommonDirections.RIGHT).mult_(rnd_dist).add_(position_offset)

            rnd_asteroid_world_card = self._rnd.pick(all_asteroids_world_cards)
            tmp_asteroid_template = AsteroidSpec(
                rnd_asteroid_world_card.card_guid_of(),
                ObjectKind.Asteroid, ArrivalCause.AlreadyExists,
                1, True, pos,
                Euler3.zero(), self._rnd.between(10.0, 50.0), 0)
            tmp_asteroid = self._sector.ctx.object_forge.hatch_asteroid(tmp_asteroid_template, 20.0)
            self._ring_asteroids.append(tmp_asteroid)

    def _shape_parent_transform(self, position_shift: Vector3) -> None:
        self._parent_transform = Transform(position_shift, Quaternion.identity(), True)


class TendrilCluster(GroupSpawn):
    def __init__(self, sector, aszteroida_darab: int, kar_darab: int, angle_shift: float, kocka, spread_from_centre: int):
        self._catalogue = Services.get(Catalogue)
        self._sector = sector
        self._rnd = kocka
        self._spread_from_centre = spread_from_centre
        self._asteroid_count = aszteroida_darab
        self._tentacle_count = kar_darab
        self._angle_offset = angle_shift
        self._tentacle_asteroids = []
        self._parent_transform = None

    def parent(self):
        raise RuntimeError('this group has no parent')

    def children(self):
        return self._tentacle_asteroids

    def create(self) -> None:
        all_asteroids_world_cards = self._catalogue.all_asteroid_world_cards

        position_offset = Vector3(
            self._rnd.between_wide(-self._spread_from_centre, self._spread_from_centre),
            self._rnd.between_wide(int(-self._spread_from_centre / 10), int(self._spread_from_centre / 10)),
            self._rnd.between_wide(-self._spread_from_centre, self._spread_from_centre))
        self._shape_parent_transform(position_offset)
        for _j in range(self._tentacle_count):
            forgatas = Euler3(0, self._rnd.between_wide(-180, 180), self._rnd.between_wide(-90, 90))
            for _i in range(self._asteroid_count + 1):
                tavolsag = Maths.pow(_i, 2)
                y_tentacle_offset = self._rnd.between(-self._angle_offset, self._angle_offset)
                z_tentacle_offset = self._rnd.between(-self._angle_offset, self._angle_offset)

                forgatas = Euler3.from_quaternion(
                    forgatas.quaternion.mult_(Euler3(0, y_tentacle_offset, z_tentacle_offset).quaternion))

                pos = forgatas.quaternion.mult_(CommonDirections.RIGHT).mult_(tavolsag).add_(position_offset)

                rnd_asteroid_world_card = self._rnd.pick(all_asteroids_world_cards)
                tmp_asteroid_template = AsteroidSpec(
                    rnd_asteroid_world_card.card_guid_of(),
                    ObjectKind.Asteroid, ArrivalCause.AlreadyExists,
                    1, True, pos,
                    Euler3.zero(), self._rnd.between(10.0, 50.0), 0)
                tmp_asteroid = self._sector.ctx.object_forge.hatch_asteroid(tmp_asteroid_template, 20.0)
                self._tentacle_asteroids.append(tmp_asteroid)

    def _shape_parent_transform(self, position_shift: Vector3) -> None:
        self._parent_transform = Transform(position_shift, Quaternion.identity(), True)
