# github.com/Shran21

from __future__ import annotations

from rebsgo.geometry.primitives.vector3 import Vector3
from rebsgo.geometry.collider_shapes import Contact
from rebsgo.geometry.maths.maths import Maths
from rebsgo.helpers.floats import FLOAT_MAX_VALUE

_MARADEK = ((1, 2), (2, 0), (0, 1))

_VEZETO_SOR = ((2, 2, 2), (0, 1, 1), (1, 1, 1))


def touches(a, b):
    r = _elfordulas(a, b)
    abs_r = _elfordulas_nagysaga(r)
    t = _b_helye_a_sajat_rendszereben(a, b)
    ha = a.half_extents_of()
    hb = b.half_extents_of()

    legkisebb = FLOAT_MAX_VALUE
    irany = None

    for i in range(3):
        sajat = ha.index(i)
        idegen = hb.index(0) * abs_r[i][0] + hb.index(1) * abs_r[i][1] + hb.index(2) * abs_r[i][2]
        tavolsag = Maths.abs(t.index(i))
        if tavolsag > sajat + idegen:
            return None
        atfedes = Maths.abs(tavolsag - (sajat + idegen))
        if atfedes < legkisebb:
            legkisebb = atfedes
            irany = a.local_axes(i)

    for i in range(3):
        idegen = ha.index(0) * abs_r[0][i] + ha.index(1) * abs_r[1][i] + ha.index(2) * abs_r[2][i]
        sajat = hb.index(i)
        tavolsag = Maths.abs(t.index(0) * r[0][i] + t.index(1) * r[1][i] + t.index(2) * r[2][i])
        if tavolsag > idegen + sajat:
            return None
        atfedes = Maths.abs(tavolsag - (idegen + sajat))
        if atfedes < legkisebb:
            legkisebb = atfedes
            irany = b.local_axes(i)

    for i in range(3):
        i1, i2 = _MARADEK[i]
        for j in range(3):
            j1, j2 = _MARADEK[j]
            a_elerés = ha.index(i1) * abs_r[i2][j] + ha.index(i2) * abs_r[i1][j]
            b_elerés = hb.index(j1) * abs_r[i][j2] + hb.index(j2) * abs_r[i][j1]
            tavolsag = Maths.abs(t.index(_VEZETO_SOR[i][j]) * r[i1][j] - t.index(i1) * r[i2][j])
            if tavolsag > a_elerés + b_elerés:
                return None

    if irany is None:
        return None
    irany = irany.copy()
    irany.normalize_()
    if Vector3.dot(Vector3.sub(b.world_center(), a.world_center()), irany) < 0:
        irany.negate_()
    return Contact(legkisebb, irany)


def _b_helye_a_sajat_rendszereben(a, b) -> Vector3:
    kulonbseg = Vector3.sub(b.world_center(), a.world_center())
    return Vector3(Vector3.dot(kulonbseg, a.local_axes(0)),
                   Vector3.dot(kulonbseg, a.local_axes(1)),
                   Vector3.dot(kulonbseg, a.local_axes(2)))


def _elfordulas(a, b):
    return [[Vector3.dot(a.local_axes(i), b.local_axes(j)) for j in range(3)]
            for i in range(3)]


def _elfordulas_nagysaga(elfordulas):
    return [[Maths.abs(ertek) + Maths.EPSILON for ertek in sor] for sor in elfordulas]
