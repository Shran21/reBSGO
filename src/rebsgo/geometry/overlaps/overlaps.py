# github.com/Shran21

from __future__ import annotations

from rebsgo.geometry.primitives.vector3 import Vector3
from rebsgo.geometry.collider_shapes import (
    Contact,
    SphereCollider,
    within_radius_sum,
)
from rebsgo.geometry.overlaps.nearest_points import (
    closest_pt_point_obb,
    nearest_between_segments,
    nearest_on_segment,
)
from rebsgo.geometry.maths.maths import Maths


def _erintkezes(negyzetes_tavolsag: float, hatar: float, irany: Vector3,
                forditva: bool) -> Contact | None:
    if negyzetes_tavolsag > hatar * hatar:
        return None
    irany.normalize_()
    if forditva:
        irany.negate_()
    return Contact(hatar - Maths.sqrt(negyzetes_tavolsag), irany)


def test_sphere_capsule(sphere, capsule, forditott_normal: bool):
    kozeppont = sphere.center_point()
    szakaszon = nearest_on_segment(kozeppont, capsule.end_a(), capsule.end_b())
    ele = Vector3.sub(szakaszon, kozeppont)
    return _erintkezes(ele.sq_magnitude_, sphere.radius_of() + capsule.radius_of(),
                       ele, forditott_normal)


def _gomb_a_ponton(transform, vilagpont: Vector3, sugar: float) -> SphereCollider:
    gomb = SphereCollider(transform, vilagpont, sugar)
    gomb.center_point().copy_from(vilagpont)
    return gomb


def test_capsule_capsule(egyik_alak, masik_alak):
    egyik = Vector3()
    masik = Vector3()
    nearest_between_segments(egyik_alak.end_a(), egyik_alak.end_b(),
                             masik_alak.end_a(), masik_alak.end_b(), egyik, masik)
    return test_sphere_sphere(
        _gomb_a_ponton(egyik_alak.transform_of(), egyik, egyik_alak.radius_of()),
        _gomb_a_ponton(masik_alak.transform_of(), masik, masik_alak.radius_of()))


def test_sphere_sphere(egyik_alak, masik_alak):
    kozott = Vector3.sub(masik_alak.center_point(), egyik_alak.center_point())
    negyzetes = kozott.sq_magnitude_
    egyutt = egyik_alak.radius_of() + masik_alak.radius_of()
    if negyzetes > egyutt * egyutt:
        return None

    def _felszinen(sajat, masik):
        helyben = sajat.transform_of().copy().inverse_().through_transform(
            masik.transform_of().position_of())
        return helyben.normalize_().mult_(sajat.radius_of())

    return Contact(egyutt - Maths.sqrt(negyzetes), kozott.normalize_(),
                   _felszinen(egyik_alak, masik_alak), _felszinen(masik_alak, egyik_alak))


def test_sphere_obb(sphere, box, forditott_normal: bool):
    kozeppont = sphere.center_point()
    dobozon = closest_pt_point_obb(kozeppont, box)
    negyzetes = Vector3.sub(dobozon, kozeppont).sq_magnitude_
    kozott = Vector3.sub(box.world_center(), kozeppont)
    return _erintkezes(negyzetes, sphere.radius_of(), kozott, forditott_normal)


def test_capsule_obb3(capsule, ferde_doboz, ellentett_normal: bool):
    if not within_radius_sum(
            capsule.transform_of().position_of().sq_distance_to(ferde_doboz.world_center()),
            capsule.prune_sphere_radius, ferde_doboz.maximum_radius):
        return None

    dobozon_a = closest_pt_point_obb(capsule.end_a(), ferde_doboz)
    dobozon_b = closest_pt_point_obb(capsule.end_b(), ferde_doboz)
    egyik = Vector3()
    masik = Vector3()
    negyzetes = nearest_between_segments(capsule.end_a(), capsule.end_b(),
                                         dobozon_a, dobozon_b, egyik, masik)
    return _erintkezes(negyzetes, capsule.radius_of(),
                       Vector3.sub(masik, egyik), ellentett_normal)
