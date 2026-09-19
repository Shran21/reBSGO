# github.com/Shran21

from __future__ import annotations

from abc import ABC, abstractmethod
from rebsgo.geometry.primitives.common import CommonDirections
from rebsgo.geometry.primitives.transform import Transform
from rebsgo.geometry.primitives.frozen import frozen
from rebsgo.geometry.primitives.vector3 import Vector3
from rebsgo.geometry.overlaps.nearest_points import (
    closest_pt_point_obb,
    nearest_between_segments,
    nearest_between_segments_narrowed,
    squared_gap_to_segment,
)
from rebsgo.geometry.maths.decimal import Decimal
from rebsgo.geometry.maths.maths import Maths
from rebsgo.helpers.floats import FLOAT_MAX_VALUE, f32
from rebsgo.helpers.copyable import Copyable


class AABB:
    def __init__(self, min_v: Vector3, max_v: Vector3, copy: bool = True):
        if copy:
            self._min = min_v.copy()
            self._max = max_v.copy()
        else:
            self._min = min_v
            self._max = max_v

    @property
    def center(self) -> Vector3:
        return Vector3.add(self._min, self._max).mult_(0.5)

    def vector_within(self, v: Vector3) -> bool:
        x_in_range = (v.x >= min(self._min.x, self._max.x)) and (
            v.x <= max(self._min.x, self._max.x)
        )
        if not x_in_range:
            return False
        y_in_range = (v.y >= min(self._min.y, self._max.y)) and (
            v.y <= max(self._min.y, self._max.y)
        )
        if not y_in_range:
            return False
        z_in_range = (v.z >= min(self._min.z, self._max.z)) and (
            v.z <= max(self._min.z, self._max.z)
        )
        return z_in_range

    def min(self) -> Vector3:
        return self._min

    def max(self) -> Vector3:
        return self._max

    def __eq__(self, other) -> bool:
        if other is self:
            return True
        if other is None or type(other) is not type(self):
            return False
        return self._min == other._min and self._max == other._max

    def __hash__(self) -> int:
        return hash((self._min, self._max))

    def __repr__(self) -> str:
        return "<AABB " + f"min={self._min}, max={self._max}" + ">"


class Capsule(Copyable["Capsule"]):
    def __init__(self, a: Vector3, b: Vector3, radius: float):
        self._a = a
        self._b = b
        self._radius = radius

    def copy(self) -> "Capsule":
        return Capsule(self._a.copy(), self._b.copy(), self._radius)

    def a(self) -> Vector3:
        return self._a

    def b(self) -> Vector3:
        return self._b

    @property
    def radius(self) -> float:
        return self._radius

    def __eq__(self, other) -> bool:
        if not isinstance(other, Capsule):
            return False
        return self._a == other._a and self._b == other._b and self._radius == other._radius

    def __hash__(self) -> int:
        return hash((self._a, self._b, self._radius))


class Collider(Copyable["Collider"], ABC):
    def __init__(self, szuro_sugar: float, transform: Transform):
        self.transform = transform
        self.prune_sphere_radius = szuro_sugar

    @abstractmethod
    def sync_to_transform(self) -> None:
        ...

    @abstractmethod
    def touch(self, other: "Collider"):
        ...

    @abstractmethod
    def touch_sphere(self, sphere_collider):
        ...

    @abstractmethod
    def touch_obb(self, doboz):
        ...

    @abstractmethod
    def touch_capsule(self, capsule_collider):
        ...

    @abstractmethod
    def overlaps(self, other: "Collider") -> bool:
        ...

    @abstractmethod
    def overlaps_sphere(self, sphere_collider) -> bool:
        ...

    @abstractmethod
    def overlaps_obb(self, doboz) -> bool:
        ...

    @abstractmethod
    def overlaps_capsule(self, capsule_collider) -> bool:
        ...

    def transform_of(self) -> Transform:
        return self.transform

    def cover_radius(self) -> float:
        return self.prune_sphere_radius


def within_radius_sum(negyzetes_tavolsag: float, r1: float, r2: float) -> bool:
    egyutt = r1 + r2
    return negyzetes_tavolsag <= egyutt * egyutt


class Contact:
    def __init__(self, overlap_depth, normal, egyik_pont=None,
                 masik_pont=None, collides: bool = True):
        self._collides = collides
        self._penetration_depth = Maths.abs(overlap_depth)
        self._normal = normal
        self._local_point1 = egyik_pont
        self._local_point2 = masik_pont

    @property
    def no_collision(self) -> "Contact":
        return NO_COLLISION

    def touch(self) -> bool:
        return self._collides

    @property
    def penetration_depth(self) -> float:
        return self._penetration_depth

    @property
    def normal(self) -> Vector3:
        return self._normal

    @property
    def local_point1(self) -> Vector3:
        return self._local_point1

    @property
    def local_point2(self) -> Vector3:
        return self._local_point2

    def __eq__(self, other) -> bool:
        if not isinstance(other, Contact):
            return False
        return (
            self._collides == other._collides
            and self._penetration_depth == other._penetration_depth
            and self._normal == other._normal
            and self._local_point1 == other._local_point1
            and self._local_point2 == other._local_point2
        )

    def __repr__(self) -> str:
        if not self._collides:
            return '<no contact>'
        return (f'<contact {self._penetration_depth} deep along {self._normal},'
                f' at {self._local_point1} / {self._local_point2}>')
NO_COLLISION = Contact(0, None, collides=False)


class LineSegment:
    def __init__(self, a: Vector3, b: Vector3):
        self._a = a
        self._b = b

    def a(self) -> Vector3:
        return self._a

    def b(self) -> Vector3:
        return self._b

    def __eq__(self, other) -> bool:
        if not isinstance(other, LineSegment):
            return False
        return self._a == other._a and self._b == other._b

    def __hash__(self) -> int:
        return hash((self._a, self._b))


class Box(Copyable["Box"]):
    def __init__(self, center: Vector3, half_sizes: Vector3):
        self._center = center
        self._half_width_extents = half_sizes

    def copy(self) -> "Box":
        return Box(self._center.copy(), self._half_width_extents.copy())

    @property
    def center(self) -> Vector3:
        return self._center

    @property
    def half_width_extents(self) -> Vector3:
        return self._half_width_extents

    def __eq__(self, other) -> bool:
        if not isinstance(other, Box):
            return False
        return self._center == other._center and self._half_width_extents == other._half_width_extents

    def __hash__(self) -> int:
        return hash((self._center, self._half_width_extents))


class Ray:
    def __init__(self, origin: Vector3, path_length: float, direction: Vector3):
        self._origin = origin.copy()
        self._direction = direction
        self._travel_distance = path_length

    @staticmethod
    def of_segment(a: Vector3, b: Vector3) -> "Ray":
        return Ray(a, 1.0, Vector3.sub(b, a))

    def point(self, distance: float) -> Vector3:
        return Vector3.add(self._origin, Vector3.mult(self._direction, distance))

    @property
    def origin(self) -> Vector3:
        return self._origin

    def direction(self) -> Vector3:
        return self._direction

    @property
    def travel_distance(self) -> float:
        return self._travel_distance

    def __eq__(self, other) -> bool:
        if not isinstance(other, Ray):
            return False
        return (
            self._origin == other._origin
            and self._direction == other._direction
            and self._travel_distance == other._travel_distance
        )

    def __repr__(self) -> str:
        return "<Ray " + f"origin={self._origin}, direction={self._direction}, length={self._travel_distance}" + ">"


_EPSILON = Maths.EPSILON


def sphere_meets_capsule(s, capsule_collider) -> bool:
    return within_radius_sum(
        squared_gap_to_segment(capsule_collider.end_a(),
                               capsule_collider.end_b(), s.center_point()),
        s.radius_of(), capsule_collider.radius_of(),
    )


def sphere_meets_sphere(a, b) -> bool:
    return within_radius_sum(
        a.center_point().sq_distance_to(b.center_point()),
        a.radius_of(), b.radius_of(),
    )


def boxes_meet(a, b) -> bool:
    if not within_radius_sum(a.world_center().sq_distance_to(b.world_center()),
                             a.maximum_radius, b.maximum_radius):
        return False

    vetulet = [[Vector3.dot(a.local_axes(sor), b.local_axes(oszlop))
                for oszlop in range(3)]
               for sor in range(3)]

    kozvetlen = Vector3.sub(b.world_center(), a.world_center())
    eltolas = Vector3(Vector3.dot(kozvetlen, a.local_axes(0)),
                      Vector3.dot(kozvetlen, a.local_axes(1)),
                      Vector3.dot(kozvetlen, a.local_axes(2)))

    parna = [[Maths.abs(vetulet[sor][oszlop]) + _EPSILON
              for oszlop in range(3)]
             for sor in range(3)]

    ha = a.half_extents_of()
    hb = b.half_extents_of()

    for sor in range(3):
        idegen = (hb.index(0) * parna[sor][0] + hb.index(1) * parna[sor][1]
                  + hb.index(2) * parna[sor][2])
        if Maths.abs(eltolas.index(sor)) > ha.index(sor) + idegen:
            return False
    for oszlop in range(3):
        sajat = (ha.index(0) * parna[0][oszlop] + ha.index(1) * parna[1][oszlop]
                 + ha.index(2) * parna[2][oszlop])
        tavolsag = (eltolas.index(0) * vetulet[0][oszlop]
                    + eltolas.index(1) * vetulet[1][oszlop]
                    + eltolas.index(2) * vetulet[2][oszlop])
        if Maths.abs(tavolsag) > sajat + hb.index(oszlop):
            return False

    cross_tests = (
        (ha.index(1) * parna[2][0] + ha.index(2) * parna[1][0],
         hb.index(1) * parna[0][2] + hb.index(2) * parna[0][1],
         Maths.abs(eltolas.index(2) * vetulet[1][0] - eltolas.index(1) * vetulet[2][0])),
        (ha.index(1) * parna[2][1] + ha.index(2) * parna[1][1],
         hb.index(0) * parna[0][2] + hb.index(2) * parna[0][0],
         Maths.abs(eltolas.index(2) * vetulet[1][1] - eltolas.index(1) * vetulet[2][1])),
        (ha.index(1) * parna[2][2] + ha.index(2) * parna[1][2],
         hb.index(0) * parna[0][1] + hb.index(1) * parna[0][0],
         Maths.abs(eltolas.index(2) * vetulet[1][2] - eltolas.index(1) * vetulet[2][2])),
        (ha.index(0) * parna[2][0] + ha.index(2) * parna[0][0],
         hb.index(1) * parna[1][2] + hb.index(2) * parna[1][1],
         Maths.abs(eltolas.index(0) * vetulet[2][0] - eltolas.index(2) * vetulet[0][0])),
        (ha.index(0) * parna[2][1] + ha.index(2) * parna[0][1],
         hb.index(0) * parna[1][2] + hb.index(2) * parna[1][0],
         Maths.abs(eltolas.index(1) * vetulet[2][1] - eltolas.index(2) * vetulet[0][1])),
        (ha.index(0) * parna[2][2] + ha.index(2) * parna[0][2],
         hb.index(0) * parna[1][1] + hb.index(1) * parna[1][0],
         Maths.abs(eltolas.index(1) * vetulet[2][2] - eltolas.index(2) * vetulet[0][2])),
        (ha.index(0) * parna[1][0] + ha.index(1) * parna[0][0],
         hb.index(1) * parna[2][2] + hb.index(2) * parna[2][1],
         Maths.abs(eltolas.index(1) * vetulet[0][0] - eltolas.index(0) * vetulet[1][0])),
        (ha.index(0) * parna[1][1] + ha.index(1) * parna[0][1],
         hb.index(0) * parna[2][2] + hb.index(2) * parna[2][0],
         Maths.abs(eltolas.index(1) * vetulet[0][1] - eltolas.index(0) * vetulet[1][1])),
        (ha.index(0) * parna[1][2] + ha.index(1) * parna[0][2],
         hb.index(0) * parna[2][1] + hb.index(1) * parna[2][0],
         Maths.abs(eltolas.index(1) * vetulet[0][2] - eltolas.index(0) * vetulet[1][2])),
    )
    for sajat, masik, tavolsag in cross_tests:
        if tavolsag > sajat + masik:
            return False
    return True


def ray_hits_box(p: Vector3, d: Vector3, max_travel_distance: float,
                 min_v: Vector3, max_v: Vector3, belepesi_t: Decimal, q: Vector3) -> bool:
    belep, atmegy = _savok_metszete(p, d, max_travel_distance, min_v, max_v)
    belepesi_t.set_value(belep)
    if not atmegy:
        return False
    q.copy_from(Vector3.add(p, Vector3.mult(d, belep)))
    return True


def _savok_metszete(p: Vector3, d: Vector3, meddig: float,
                    min_v: Vector3, max_v: Vector3) -> tuple[float, bool]:
    belep, kilep = 0.0, meddig
    for tengely in range(3):
        irany = d.index(tengely)
        honnan = p.index(tengely)
        also, felso = min_v.index(tengely), max_v.index(tengely)
        if Maths.abs(irany) < _EPSILON:
            if honnan < also or honnan > felso:
                return belep, False
            continue
        forditott = 1.0 / irany
        innen, addig = (also - honnan) * forditott, (felso - honnan) * forditott
        if innen > addig:
            innen, addig = addig, innen
        belep = f32(Maths.max(belep, innen))
        kilep = Maths.min(kilep, addig)
        if belep > kilep:
            return belep, False
    return belep, True


_KERESZT_PAROK = ((1, 2), (2, 0), (0, 1))


def _elvalik_valamelyik_tengelyen(kp, fv, meret) -> bool:
    nyulas = []
    for hol, fel, iranyban in zip(kp, meret, fv):
        nyulas.append(Maths.abs(iranyban))
        if Maths.abs(hol) > fel + nyulas[-1]:
            return True

    nyulas = [n + _EPSILON for n in nyulas]

    for j, k in _KERESZT_PAROK:
        if Maths.abs(kp[j] * fv[k] - kp[k] * fv[j]) > meret[j] * nyulas[k] + meret[k] * nyulas[j]:
            return True
    return False


def capsule_meets_capsule(a, b) -> bool:
    return within_radius_sum(
        nearest_between_segments(a.end_a(), a.end_b(),
                                 b.end_a(), b.end_b(), Vector3(), Vector3()),
        a.radius_of(), b.radius_of(),
    )


def capsule_meets_box(capsule_collider, doboz, t: Decimal) -> bool:
    vissza = Transform.inverse(doboz.transform_of())
    a_new = vissza.through_transform(capsule_collider.end_a())
    b_new = vissza.through_transform(capsule_collider.end_b())
    return capsule_meets_aligned_box(
        a_new, b_new, capsule_collider.radius_of(),
        doboz.low_corner_at_home(), doboz.high_corner_at_home(), t,
    )


TENGELY_BITEK = (1, 2, 4)
_MIND_A_HAROM = 7


def capsule_meets_aligned_box(end_a: Vector3, end_b: Vector3, radius: float,
                              min_v: Vector3, max_v: Vector3, t: Decimal) -> bool:
    sugar = Ray.of_segment(end_a, end_b)
    doboz = AABB(min_v, max_v, False)
    felfujt = AABB(min_v, max_v)
    felfujt.min().sub_(radius)
    felfujt.max().add_(radius)

    talalat = Vector3()
    if not ray_hits_box(sugar.origin, sugar.direction(),
                                            sugar.travel_distance,
                                            felfujt.min(), felfujt.max(), t, talalat):
        return False
    if t.value > 1.0:
        return False

    alatta, felette = _kilogo_oldalak(talalat, min_v, max_v)
    oldalak = alatta | felette
    szakasz = LineSegment(end_a, end_b)

    if oldalak == _MIND_A_HAROM:
        return _sarok_kozelites(szakasz, doboz, felette, radius, t)
    if (oldalak & (oldalak - 1)) == 0:
        return True
    return segment_meets_capsule(
        szakasz,
        box_corner(doboz, alatta ^ _MIND_A_HAROM),
        box_corner(doboz, felette),
        radius, t)


def _kilogo_oldalak(pont: Vector3, min_v: Vector3, max_v: Vector3) -> tuple[int, int]:
    alatta = felette = 0
    hol = (pont.x, pont.y, pont.z)
    also = (min_v.x, min_v.y, min_v.z)
    felso = (max_v.x, max_v.y, max_v.z)
    for bit, hova, kicsi, nagy in zip(TENGELY_BITEK, hol, also, felso):
        if hova < kicsi:
            alatta |= bit
        if hova > nagy:
            felette |= bit
    return alatta, felette


def _sarok_kozelites(szakasz: "LineSegment", doboz: AABB, sarok: int,
                     sugar: float, t: Decimal) -> bool:
    legkorabbi = FLOAT_MAX_VALUE
    honnan = box_corner(doboz, sarok)
    for bit in TENGELY_BITEK:
        hova = box_corner(doboz, sarok ^ bit)
        if segment_meets_capsule(szakasz, honnan, hova, sugar, t):
            legkorabbi = Maths.min(t.value, legkorabbi)
    if legkorabbi == FLOAT_MAX_VALUE:
        return False
    t.set_value(legkorabbi)
    return True


def box_corner(b: AABB, n: int) -> Vector3:
    return Vector3(
        b.max().x if (n & 1) > 0 else b.min().x,
        b.max().y if (n & 2) > 0 else b.min().y,
        b.max().z if (n & 4) > 0 else b.min().z,
    )


def segment_meets_capsule(szakasz, c_a: Vector3, c_b: Vector3,
                          sugar: float, metszes_t: Decimal) -> bool:
    sq_distance, hol_az_elson, _ = nearest_between_segments_narrowed(
        szakasz.a(), szakasz.b(), c_a, c_b, Vector3(), Vector3())
    metszes_t.set_value(hol_az_elson)
    return sq_distance <= sugar * sugar


def sphere_meets_box(gomb, doboz, p: Vector3) -> bool:
    kozeppont, sugar = gomb.center_point(), gomb.radius_of()
    p.copy_from(closest_pt_point_obb(kozeppont, doboz))
    tavolsag = Vector3.sub(p, kozeppont)
    return tavolsag.sq_magnitude_ <= sugar * sugar


class CapsuleCollider(Collider):
    def __init__(self, transform: Transform, a: Vector3, b: Vector3, radius: float):
        super().__init__(Vector3.distance(a, b) * 0.5 + radius, transform)
        if a is None or b is None:
            raise TypeError('a vector is required')
        self._capsule = Capsule(a, b, radius)
        self._updated_a = a.copy()
        self._updated_b = b.copy()
        self.sync_to_transform()

    def end_a(self) -> Vector3:
        return self._updated_a

    def end_b(self) -> Vector3:
        return self._updated_b

    def radius_of(self) -> float:
        return self._capsule.radius

    def sync_to_transform(self) -> None:
        self._updated_a.copy_from(self.transform.through_transform(self._capsule.a()))
        self._updated_b.copy_from(self.transform.through_transform(self._capsule.b()))

    def touch(self, other: Collider):
        return other.touch_capsule(self)

    def touch_sphere(self, sphere_collider):
        from rebsgo.geometry.overlaps.overlaps import test_sphere_capsule

        return test_sphere_capsule(sphere_collider, self, True)

    def touch_obb(self, doboz):
        from rebsgo.geometry.overlaps.overlaps import test_capsule_obb3

        return test_capsule_obb3(self, doboz, False)

    def touch_capsule(self, capsule_collider):
        from rebsgo.geometry.overlaps.overlaps import test_capsule_capsule

        return test_capsule_capsule(self, capsule_collider)

    def overlaps(self, other: Collider) -> bool:
        return other.overlaps_capsule(self)

    def overlaps_sphere(self, sphere_collider) -> bool:
        return sphere_meets_capsule(sphere_collider, self)

    def overlaps_obb(self, doboz) -> bool:
        from rebsgo.geometry.maths.decimal import Decimal

        return capsule_meets_box(self, doboz, Decimal())

    def overlaps_capsule(self, capsule_collider) -> bool:
        return capsule_meets_capsule(self, capsule_collider)

    def copy(self) -> Collider:
        return CapsuleCollider(self.transform.copy(), self._updated_a.copy(), self._updated_b.copy(), self.radius_of())


class BoxCollider(Collider):
    def __init__(self, transform: Transform, center: Vector3, half_sizes: Vector3):
        super().__init__(Maths.max(half_sizes.x, half_sizes.y, half_sizes.z), transform)
        self._obb = Box(center, half_sizes)
        self._updated_center = center.copy()
        self._local_right = Vector3.right()
        self._local_up = Vector3.up()
        self._local_forward = Vector3.forward()
        self.sync_to_transform()

    def sync_to_transform(self) -> None:
        self._updated_center.copy_from(Vector3.add(self.transform.position_of(), self._obb.center))
        self._local_right.copy_from(self.transform.rotation_of().mult_(CommonDirections.RIGHT))
        self._local_up.copy_from(self.transform.rotation_of().mult_(CommonDirections.UP))
        self._local_forward.copy_from(self.transform.rotation_of().mult_(CommonDirections.FORWARD))

    def local_axes(self, index: int) -> Vector3:
        if index == 0:
            return self._local_right
        if index == 1:
            return self._local_up
        if index == 2:
            return self._local_forward
        raise ValueError('index out of range')

    @property
    def maximum_radius(self) -> float:
        return self.prune_sphere_radius

    def touch(self, other: Collider):
        return other.touch_obb(self)

    def touch_sphere(self, sphere_collider):
        from rebsgo.geometry.overlaps.overlaps import test_sphere_obb

        return test_sphere_obb(sphere_collider, self, True)

    def touch_obb(self, doboz):
        from rebsgo.geometry.overlaps.box_overlap import touches

        return touches(self, doboz)

    def touch_capsule(self, capsule_collider):
        from rebsgo.geometry.overlaps.overlaps import test_capsule_obb3

        return test_capsule_obb3(capsule_collider, self, True)

    def overlaps(self, other: Collider) -> bool:
        return other.overlaps_obb(self)

    def overlaps_sphere(self, sphere_collider) -> bool:
        return sphere_meets_box(sphere_collider, self, Vector3())

    def overlaps_obb(self, doboz) -> bool:
        return boxes_meet(self, doboz)

    def overlaps_capsule(self, capsule_collider) -> bool:
        from rebsgo.geometry.maths.decimal import Decimal

        return capsule_meets_box(capsule_collider, self, Decimal())

    def world_center(self) -> Vector3:
        return self._updated_center

    def half_extents_of(self) -> Vector3:
        return self._obb.half_width_extents

    def axis_right(self) -> Vector3:
        return self._local_right

    def axis_up(self) -> Vector3:
        return self._local_up

    def axis_forward(self) -> Vector3:
        return self._local_forward

    def low_corner_at_home(self) -> Vector3:
        return Vector3.sub(self._obb.center, self.half_extents_of())

    def high_corner_at_home(self) -> Vector3:
        return Vector3.add(self._obb.center, self.half_extents_of())

    def min(self) -> Vector3:
        return Vector3.sub(self.world_center(), self.local_half_width_computed)

    def max(self) -> Vector3:
        return Vector3.add(self.world_center(), self.local_half_width_computed)

    @property
    def local_half_width_computed(self) -> Vector3:
        return Vector3(
            Vector3.dot(self.half_extents_of(), self.axis_right()),
            Vector3.dot(self.half_extents_of(), self.axis_up()),
            Vector3.dot(self.half_extents_of(), self.axis_forward()),
        )

    def copy(self) -> Collider:
        return BoxCollider(self.transform.copy(), self._updated_center.copy(), self._obb.half_width_extents.copy())


class Sphere:
    def __init__(self, center: Vector3, radius: float):
        self._center = center
        self._radius = radius

    @property
    def center(self) -> Vector3:
        return frozen(self._center)

    @property
    def radius(self) -> float:
        return self._radius

    def __eq__(self, other) -> bool:
        if not isinstance(other, Sphere):
            return False
        return self._center == other._center and self._radius == other._radius

    def __hash__(self) -> int:
        return hash((self._center, self._radius))


class SphereCollider(Collider):
    def __init__(self, transform: Transform, center: Vector3, radius: float):
        super().__init__(radius, transform)
        self._sphere = Sphere(center, radius)
        self._updated_center = center.copy()
        self.sync_to_transform()

    def center_point(self) -> Vector3:
        return self._updated_center

    def radius_of(self) -> float:
        return self._sphere.radius

    def sync_to_transform(self) -> None:
        self._updated_center.copy_from(Vector3.add(self._sphere.center, self.transform.position_of()))

    def touch(self, other: Collider):
        return other.touch_sphere(self)

    def touch_sphere(self, sphere_collider):
        from rebsgo.geometry.overlaps.overlaps import test_sphere_sphere

        return test_sphere_sphere(self, sphere_collider)

    def touch_obb(self, doboz):
        from rebsgo.geometry.overlaps.overlaps import test_sphere_obb

        return test_sphere_obb(self, doboz, False)

    def touch_capsule(self, capsule_collider):
        from rebsgo.geometry.overlaps.overlaps import test_sphere_capsule

        return test_sphere_capsule(self, capsule_collider, False)

    def overlaps(self, other: Collider) -> bool:
        return other.overlaps_sphere(self)

    def overlaps_sphere(self, sphere_collider) -> bool:
        return sphere_meets_sphere(self, sphere_collider)

    def overlaps_obb(self, doboz) -> bool:
        return sphere_meets_box(self, doboz, Vector3())

    def overlaps_capsule(self, capsule_collider) -> bool:
        return sphere_meets_capsule(self, capsule_collider)

    def copy(self) -> Collider:
        return SphereCollider(self.transform.copy(), self._sphere.center.copy(), self._sphere.radius)
