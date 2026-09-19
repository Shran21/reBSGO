# github.com/Shran21

from __future__ import annotations

from rebsgo.geometry.primitives.vector3 import Vector3
from rebsgo.geometry.maths.maths import Maths
from rebsgo.helpers.floats import f32

_ELHANYAGOLHATO = Maths.EPSILON


def squared_gap_to_segment(a: Vector3, b: Vector3, c: Vector3) -> float:
    ab = Vector3.sub(b, a)
    ac = Vector3.sub(c, a)
    vetulet = Vector3.dot(ac, ab)
    if vetulet <= 0.0:
        return ac.sq_magnitude_
    hossz_negyzet = ab.sq_magnitude_
    if vetulet >= hossz_negyzet:
        return Vector3.sub(c, b).sq_magnitude_
    return ac.sq_magnitude_ - vetulet * vetulet / hossz_negyzet


def nearest_on_segment(c: Vector3, a: Vector3, b: Vector3) -> Vector3:
    ab = Vector3.sub(b, a)
    vetulet = Vector3.dot(Vector3.sub(c, a), ab)
    if vetulet <= 0.0:
        return a.copy()
    hossz_negyzet = ab.sq_magnitude_
    if vetulet >= hossz_negyzet:
        return b.copy()
    return Vector3.add(a, Vector3.mult(ab, vetulet / hossz_negyzet))


def _szakaszok_kozott(p1: Vector3, q1: Vector3, p2: Vector3, q2: Vector3,
                      kerekit) -> tuple[float, float]:
    d1 = Vector3.sub(q1, p1)
    d2 = Vector3.sub(q2, p2)
    r = Vector3.sub(p1, p2)
    elso_hossz = d1.sq_magnitude_
    masodik_hossz = d2.sq_magnitude_
    elso_pont = elso_hossz <= _ELHANYAGOLHATO
    masodik_pont = masodik_hossz <= _ELHANYAGOLHATO

    if elso_pont and masodik_pont:
        return kerekit(0), kerekit(0)

    r_az_elson = Vector3.dot(d1, r)
    r_a_masodikon = Vector3.dot(d2, r)
    hajlas = Vector3.dot(d1, d2)

    if elso_pont:
        return kerekit(0), Maths.clamp01(kerekit(r_a_masodikon / masodik_hossz))

    if masodik_pont:
        vege = 0.0
    else:
        nevezo = elso_hossz * masodik_hossz - hajlas * hajlas
        s = kerekit(Maths.clamp01((hajlas * r_a_masodikon - r_az_elson * masodik_hossz) / nevezo)
                    if nevezo != 0.0 else 0.0)
        t = kerekit((hajlas * s + r_a_masodikon) / masodik_hossz)
        if t < 0.0:
            vege = 0.0
        elif t > 1.0:
            vege = 1.0
        else:
            return s, t

    return (kerekit(Maths.clamp01((hajlas * vege - r_az_elson) / elso_hossz)),
            kerekit(vege))


def _kitolt(p1, q1, p2, q2, s: float, t: float, c1: Vector3, c2: Vector3) -> float:
    c1.copy_from(Vector3.add(p1, Vector3.mult(Vector3.sub(q1, p1), s)))
    c2.copy_from(Vector3.add(p2, Vector3.mult(Vector3.sub(q2, p2), t)))
    kozott = Vector3.sub(c1, c2)
    return Vector3.dot(kozott, kozott)


def nearest_between_segments(p1: Vector3, q1: Vector3, p2: Vector3, q2: Vector3,
                             c1: Vector3, c2: Vector3) -> float:
    s, t = _szakaszok_kozott(p1, q1, p2, q2, float)
    return _kitolt(p1, q1, p2, q2, s, t, c1, c2)


def nearest_between_segments_narrowed(p1: Vector3, q1: Vector3, p2: Vector3, q2: Vector3,
                                      c1: Vector3, c2: Vector3) -> tuple[float, float, float]:
    s, t = _szakaszok_kozott(p1, q1, p2, q2, f32)
    return _kitolt(p1, q1, p2, q2, s, t, c1, c2), s, t


def closest_pt_point_obb(p: Vector3, b) -> Vector3:
    kozeppontbol = Vector3.sub(p, b.world_center())
    q = b.world_center().copy()
    for tengely in range(3):
        nyulas = b.half_extents_of().index(tengely)
        eltolas = Maths.clamp_safe(Vector3.dot(kozeppontbol, b.local_axes(tengely)),
                                   -nyulas, nyulas)
        q.add_(Vector3.mult(b.local_axes(tengely), eltolas))
    return q


def nearest_on_box_to_capsule(pts, egyik_kapszula: Vector3, masik_kapszula: Vector3) -> Vector3 | None:
    return min(pts, key=lambda pt: squared_gap_to_segment(egyik_kapszula, masik_kapszula, pt),
               default=None)
