# github.com/Shran21

from __future__ import annotations

from rebsgo.geometry.primitives.vector3 import Vector3
from rebsgo.geometry.maths.maths import Maths
from rebsgo.helpers.floats import f32

EGYSEGHOSSZ_TURES = f32(1e-06)


class Quaternion:


    def __init__(self, x=0.0, y=0.0, z=0.0, w=1.0):
        self._x = f32(x)
        self._y = f32(y)
        self._z = f32(z)
        self._w = f32(w)

    @staticmethod
    def of_vector_and_w(tengelyek: Vector3, w) -> "Quaternion":
        return Quaternion(tengelyek.x, tengelyek.y, tengelyek.z, w)

    def copy(self) -> "Quaternion":
        masolat = Quaternion.__new__(Quaternion)
        masolat._x, masolat._y = self._x, self._y
        masolat._z, masolat._w = self._z, self._w
        return masolat

    @staticmethod
    def identity() -> "Quaternion":
        return Quaternion(0.0, 0.0, 0.0, 1.0)

    @staticmethod
    def right() -> "Quaternion":
        from rebsgo.geometry.primitives.euler3 import Euler3

        return Euler3(0, 89.9999, 0).quaternion

    @staticmethod
    def left() -> "Quaternion":
        from rebsgo.geometry.primitives.euler3 import Euler3

        return Euler3(0, -89.999, 0).quaternion

    @staticmethod
    def any_rotation(num: int) -> "Quaternion":
        cleaned = num % 3
        if cleaned == 0:
            return Quaternion.identity()
        if cleaned == 1:
            return Quaternion.right()
        if cleaned == 2:
            return Quaternion.left()
        return Quaternion.identity()

    @staticmethod
    def rotation_between(start_heading: Vector3, goal_heading: Vector3) -> "Quaternion":
        axis = Vector3.cross(start_heading, goal_heading)
        angle = Vector3.angle(start_heading, goal_heading)
        return Quaternion.angle_axis(angle, axis.normalize_())

    @staticmethod
    def angle_axis(fokszog: float, axis_of: Vector3) -> "Quaternion":
        return Quaternion.axis_angle(axis_of, Maths.DEG_TO_RAD * fokszog)

    @staticmethod
    def axis_angle(axis_of: Vector3, ivertek: float) -> "Quaternion":
        axis = axis_of.copy()
        axis.normalize_()
        rad_final = ivertek * 0.5
        axis.mult_(Maths.sin(rad_final))
        return Quaternion.of_vector_and_w(axis, Maths.cos(rad_final))


    @property
    def x(self) -> float:
        return self._x

    @property
    def y(self) -> float:
        return self._y

    @property
    def z(self) -> float:
        return self._z

    @property
    def w(self) -> float:
        return self._w

    @property
    def xyz(self) -> Vector3:
        return Vector3(self._x, self._y, self._z)

    @property
    def length(self) -> float:
        return Maths.sqrt(self.length_squared)

    @property
    def length_squared(self) -> float:
        return self._x * self._x + self._y * self._y + self._z * self._z + self._w * self._w

    def euler_angles(self) -> Vector3:
        from rebsgo.geometry.primitives.euler3 import Euler3

        return Euler3.from_quaternion(self).to_axes

    @staticmethod
    def direction(quaternion: "Quaternion") -> Vector3:
        from rebsgo.geometry.primitives.common import CommonDirections

        return Quaternion.mult(quaternion, CommonDirections.FORWARD)

    def direction_(self) -> Vector3:
        return Quaternion.direction(self)

    def to_angle_axis(self, axis: Vector3) -> float:
        szog = Quaternion._to_axis_angle_rad(self, axis)
        return szog * Maths.RAD_TO_DEG


    def face_towards(self, vector3: Vector3) -> None:
        self._x = f32(Quaternion._from_euler_rad(vector3.mult_(Maths.DEG_TO_RAD)).x)
        self._y = f32(Quaternion._from_euler_rad(vector3.mult_(Maths.DEG_TO_RAD)).y)
        self._z = f32(Quaternion._from_euler_rad(vector3.mult_(Maths.DEG_TO_RAD)).z)
        self._w = f32(Quaternion._from_euler_rad(vector3.mult_(Maths.DEG_TO_RAD)).w)

    def turn_to(self, new_rotation: "Quaternion") -> "Quaternion":
        if new_rotation is None:
            raise TypeError("a current_rotation quaternion is required")
        self._x = new_rotation._x
        self._y = new_rotation._y
        self._z = new_rotation._z
        self._w = new_rotation._w
        return self


    @staticmethod
    def mult(lhs, rhs):
        if isinstance(rhs, Vector3):
            return lhs._elforgatott_pont(rhs)
        return lhs.copy().mult_(rhs)

    def _elforgatott_pont(self, pont: Vector3) -> Vector3:
        dupla = (self._x * 2.0, self._y * 2.0, self._z * 2.0)
        atlon = (self._x * dupla[0], self._y * dupla[1], self._z * dupla[2])
        vegyes = (self._x * dupla[1], self._x * dupla[2], self._y * dupla[2])
        sulyos = (self._w * dupla[0], self._w * dupla[1], self._w * dupla[2])

        matrix = (
            (1.0 - (atlon[1] + atlon[2]), vegyes[0] - sulyos[2], vegyes[1] + sulyos[1]),
            (vegyes[0] + sulyos[2], 1.0 - (atlon[0] + atlon[2]), vegyes[2] - sulyos[0]),
            (vegyes[1] - sulyos[1], vegyes[2] + sulyos[0], 1.0 - (atlon[0] + atlon[1])),
        )
        return Vector3(*(sor[0] * pont.x + sor[1] * pont.y + sor[2] * pont.z
                         for sor in matrix))

    _SZORZAT_RECEPT = (
        ((3, 0), (0, 3), (1, 2), (2, 1)),
        ((3, 1), (1, 3), (2, 0), (0, 2)),
        ((3, 2), (2, 3), (0, 1), (1, 0)),
        ((3, 3), (0, 0), (1, 1), (2, 2)),
    )
    _SZORZAT_ELOJEL = ((1.0, 1.0, 1.0, -1.0),) * 3 + ((1.0, -1.0, -1.0, -1.0),)

    def mult_(self, arg):
        if isinstance(arg, Quaternion):
            sajat = (self._x, self._y, self._z, self._w)
            masik = (arg._x, arg._y, arg._z, arg._w)
            ki = []
            for recept, elojelek in zip(self._SZORZAT_RECEPT, self._SZORZAT_ELOJEL):
                mienk, ove = recept[0]
                osszeg = sajat[mienk] * masik[ove]
                for (mienk, ove), elojel in zip(recept[1:], elojelek[1:]):
                    osszeg = osszeg + elojel * (sajat[mienk] * masik[ove])
                ki.append(f32(osszeg))
            self._x, self._y, self._z, self._w = ki
            return self
        if isinstance(arg, Vector3):
            return Quaternion.mult(self, arg)
        self._x = f32(self._x * arg)
        self._y = f32(self._y * arg)
        self._z = f32(self._z * arg)
        self._w = f32(self._w * arg)
        return None

    @staticmethod
    def inverse(rotation: "Quaternion") -> "Quaternion":
        return rotation.copy().inverse_()

    def inverse_(self) -> "Quaternion":
        length_sq = self.length_squared
        epsilon_ok = (1.0 - length_sq) <= EGYSEGHOSSZ_TURES
        szam = 1.0 if epsilon_ok else length_sq
        mult = szam / length_sq
        self._x = f32(self._x * -mult)
        self._y = f32(self._y * -mult)
        self._z = f32(self._z * -mult)
        self._w = f32(self._w * mult)
        return self

    def negate_in_place(self) -> None:
        self._x = -self._x
        self._y = -self._y
        self._z = -self._z
        self._w = -self._w

    @staticmethod
    def dot(a: "Quaternion", b: "Quaternion") -> float:
        return a._x * b._x + a._y * b._y + a._z * b._z + a._w * b._w


    @staticmethod
    def normalize(q: "Quaternion") -> "Quaternion":
        res_q = q.copy()
        res_q.normalize_()
        return res_q

    def normalize_(self) -> None:
        scale = 1.0 / self.length
        self.mult_(scale)

    @staticmethod
    def angle(a: "Quaternion", b: "Quaternion") -> float:
        f = Quaternion.dot(a, b)
        return Maths.acos(Maths.min(Maths.abs(f), 1.0)) * 2.0 * Maths.RAD_TO_DEG


    @staticmethod
    def euler(x, y=None, z=None) -> "Quaternion":
        if isinstance(x, Vector3) and y is None and z is None:
            tmp_euler = x.copy()
            tmp_euler.mult_(Maths.DEG_TO_RAD)
            return Quaternion._from_euler_rad(tmp_euler)
        eredmeny = Vector3(x, y, z)
        eredmeny.mult_(Maths.DEG_TO_RAD)
        return Quaternion._from_euler_rad(eredmeny)

    _OSSZETEVOK = ((0b100, 1.0), (0b010, -1.0), (0b001, -1.0), (0b000, 1.0))

    @staticmethod
    def _from_euler_rad(euler: Vector3) -> "Quaternion":
        felszogek = (euler.x * 0.5, euler.y * 0.5, euler.z * 0.5)
        szinusz = tuple(Maths.sin(szog) for szog in felszogek)
        koszinusz = tuple(Maths.cos(szog) for szog in felszogek)

        def szorzat(minta: int) -> float:
            elso = szinusz if minta & 0b100 else koszinusz
            masodik = szinusz if minta & 0b010 else koszinusz
            harmadik = szinusz if minta & 0b001 else koszinusz
            return elso[0] * masodik[1] * harmadik[2]

        return Quaternion(*(szorzat(minta) + elojel * szorzat(minta ^ 0b111)
                            for minta, elojel in Quaternion._OSSZETEVOK))

    _ATLO_RECEPT = (
        ((1, 2), ((1, 0, 1, 1.0), (2, 2, 0, -1.0), (3, 2, 1, -1.0))),
        ((2, 0), ((0, 0, 1, 1.0), (2, 1, 2, 1.0), (3, 0, 2, -1.0))),
        ((0, 1), ((0, 2, 0, 1.0), (1, 1, 2, 1.0), (3, 1, 0, -1.0))),
    )

    @staticmethod
    def from_matrix(matrix) -> "Quaternion":
        trace = matrix.trace
        if trace >= 0.0:
            r = Maths.sqrt(trace + 1.0)
            s = 0.5 / r
            return Quaternion((matrix.at(2, 1) - matrix.at(1, 2)) * s,
                              (matrix.at(0, 2) - matrix.at(2, 0)) * s,
                              (matrix.at(1, 0) - matrix.at(0, 1)) * s,
                              0.5 * r)

        fo = 1 if matrix.at(1, 1) > matrix.at(0, 0) else 0
        if matrix.at(2, 2) > matrix.at(fo, fo):
            fo = 2
        (kiseb1, kiseb2), helyek = Quaternion._ATLO_RECEPT[fo]
        r = Maths.sqrt(matrix.at(fo, fo)
                       - matrix.at(kiseb1, kiseb1) - matrix.at(kiseb2, kiseb2) + 1.0)
        s = 0.5 / r
        tag = [0.0, 0.0, 0.0, 0.0]
        tag[fo] = 0.5 * r
        for hely, sor, oszlop, elojel in helyek:
            tag[hely] = (matrix.at(sor, oszlop) + elojel * matrix.at(oszlop, sor)) * s
        return Quaternion(tag[0], tag[1], tag[2], tag[3])

    @staticmethod
    def _to_axis_angle_rad(q: "Quaternion", axis: Vector3) -> float:
        from rebsgo.geometry.primitives.common import CommonDirections

        if Maths.abs(q._w) > 1.0:
            q.normalize_()
        szog = 2.0 * Maths.acos(q._w)
        den = Maths.sqrt(1.0 - q._w * q._w)
        if den > 0.0001:
            axis.copy_from(Vector3.div(q.xyz, den))
        else:
            axis.copy_from(CommonDirections.RIGHT)
        return szog

    @property
    @staticmethod
    def _normalize_angles(angles: Vector3) -> Vector3:
        return Vector3(
            Quaternion._normalize_angle(angles.x),
            Quaternion._normalize_angle(angles.y),
            Quaternion._normalize_angle(angles.z),
        )

    @staticmethod
    def _normalize_angle(angle: float) -> float:
        while angle > 360:
            angle = f32(angle - 360)
        while angle < 0:
            angle = f32(angle + 360)
        return angle


    @staticmethod
    def slerp(honnan: "Quaternion", hova: "Quaternion", menet: float) -> "Quaternion":
        return Quaternion._slerp_unclamped(honnan, hova, Maths.clamp01(menet))

    @staticmethod
    def _slerp_unclamped(honnan: "Quaternion", hova: "Quaternion", t: float) -> "Quaternion":
        eleje = honnan.copy()
        vege = hova.copy()
        if eleje.length_squared == 0.0:
            return vege if vege.length_squared != 0.0 else Quaternion.identity()
        if vege.length_squared == 0.0:
            return eleje

        egyezes = eleje._w * vege._w + Vector3.dot(eleje.xyz, vege.xyz)
        if egyezes >= 1.0 or egyezes <= -1.0:
            return eleje
        if egyezes < 0.0:
            vege.negate_in_place()
            egyezes = -egyezes

        if egyezes < 0.99:
            felszog = Maths.acos(egyezes)
            hanyad = 1.0 / Maths.sin(felszog)
            sulyok = (Maths.sin(felszog * (1.0 - t)) * hanyad,
                      Maths.sin(felszog * t) * hanyad)
        else:
            sulyok = (1.0 - t, t)

        egyben = Quaternion.of_vector_and_w(
            eleje.xyz.mult_(sulyok[0]).add_(vege.xyz.mult_(sulyok[1])),
            sulyok[0] * eleje._w + sulyok[1] * vege._w)
        return Quaternion.normalize(egyben) if egyben.length_squared > 0.0 else Quaternion.identity()

    @staticmethod
    def rotate_towards(from_q: "Quaternion", to: "Quaternion", turn_cap_degrees: float) -> "Quaternion":
        angle = Quaternion.angle(from_q, to)
        if angle == 0.0:
            return to.copy()
        t = Maths.min(1.0, turn_cap_degrees / angle)
        return Quaternion._slerp_unclamped(from_q, to, t)


    @staticmethod
    def same_as(lhs: "Quaternion", rhs: "Quaternion") -> bool:
        if lhs is None and rhs is None:
            return True
        if lhs is None or rhs is None:
            return False
        return lhs._x == rhs._x and lhs._y == rhs._y and lhs._z == rhs._z and lhs._w == rhs._w

    def __eq__(self, other) -> bool:
        if not isinstance(other, Quaternion):
            return False
        return Quaternion.same_as(self, other)

    def __hash__(self) -> int:
        return hash((self._x, self._y, self._z, self._w))

    def __repr__(self) -> str:
        return "<Quaternion " + f"x={self._x}, y={self._y}, z={self._z}, w={self._w}" + ">"
