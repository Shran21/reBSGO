# github.com/Shran21

from __future__ import annotations

import math

from rebsgo.geometry.maths.maths import Maths
from rebsgo.helpers.floats import f32
from rebsgo.helpers.copyable import Copyable

_EGYSEGHOSSZ_TURES = f32(1e-05)
_VECTOR_NULL_ERROR_MSG = 'a vector is required'


class Vector3(Copyable["Vector3"]):


    def __init__(self, x=0.0, y=0.0, z=0.0):
        if math.isnan(x):
            raise ArithmeticError('x came out NaN')
        if math.isnan(y):
            raise ArithmeticError('y came out NaN')
        if math.isnan(z):
            raise ArithmeticError('z came out NaN')

        self.x = f32(x)
        self.y = f32(y)
        self.z = f32(z)

    @staticmethod
    def of_array(numbers) -> "Vector3":
        return Vector3(numbers[0], numbers[1], numbers[2])

    def copy(self) -> "Vector3":
        masolat = Vector3.__new__(Vector3)
        masolat.x = self.x
        masolat.y = self.y
        masolat.z = self.z
        return masolat

    @staticmethod
    def zero() -> "Vector3":
        return Vector3(0.0, 0.0, 0.0)

    @staticmethod
    def one() -> "Vector3":
        return Vector3(1, 1, 1)

    @staticmethod
    def up() -> "Vector3":
        return Vector3(0.0, 1.0, 0.0)

    @staticmethod
    def down() -> "Vector3":
        return Vector3(0.0, -1.0, 0.0)

    @staticmethod
    def left() -> "Vector3":
        return Vector3(-1.0, 0.0, 0.0)

    @staticmethod
    def right() -> "Vector3":
        return Vector3(1.0, 0.0, 0.0)

    @staticmethod
    def forward() -> "Vector3":
        return Vector3(0.0, 0.0, 1.0)


    def index(self, index: int) -> float:
        if index == 0:
            return self.x
        if index == 1:
            return self.y
        if index == 2:
            return self.z
        raise IndexError(f'Index for vector_access is out of bound: {index}')

    @staticmethod
    def axis_index(i: int) -> "Vector3":
        from rebsgo.geometry.primitives.common import CommonDirections

        if i == 0:
            return CommonDirections.RIGHT
        if i == 1:
            return CommonDirections.UP
        if i == 2:
            return CommonDirections.FORWARD
        raise ValueError(f'index outside 0..2, got {i}')

    @staticmethod
    def to_array(v: "Vector3") -> list[float]:
        return [v.x, v.y, v.z]

    @property
    def to_array_(self) -> list[float]:
        return Vector3.to_array(self)

    @staticmethod
    def magnitude(vec: "Vector3") -> float:
        return Maths.sqrt(Vector3.sq_magnitude(vec))

    @property
    def magnitude_(self) -> float:
        return Vector3.magnitude(self)

    @staticmethod
    def sq_magnitude(vec: "Vector3") -> float:
        return vec.x * vec.x + vec.y * vec.y + vec.z * vec.z

    @property
    def sq_magnitude_(self) -> float:
        return Vector3.sq_magnitude(self)

    @property
    def all_zero(self) -> bool:
        return self.x == 0 and self.y == 0 and self.z == 0

    @property
    def is_origin(self) -> bool:
        return self.magnitude_ < Maths.EPSILON


    def xyz_to(self, x, y, z) -> None:
        self.x = f32(x)
        self.y = f32(y)
        self.z = f32(z)

    def copy_from(self, other: "Vector3") -> None:
        self.x = other.x
        self.y = other.y
        self.z = other.z

    def x_to(self, value: float) -> None:
        self.x = f32(value)

    def y_to(self, value: float) -> None:
        self.y = f32(value)

    def z_to(self, value: float) -> None:
        self.z = f32(value)

    def add_x(self, value: float) -> None:
        self.x = f32(self.x + value)

    def add_y(self, value: float) -> None:
        self.y = f32(self.y + value)

    def add_z(self, value: float) -> None:
        self.z = f32(self.z + value)

    def axis_to(self, index: int, value: float) -> None:
        if index == 0:
            self.x = f32(value)
        elif index == 1:
            self.y = f32(value)
        elif index == 2:
            self.z = f32(value)
        else:
            raise IndexError(f'Index for vector_access is out of bound: {index}')


    @staticmethod
    def add(a: "Vector3", b: "Vector3") -> "Vector3":
        return Vector3(a.x + b.x, a.y + b.y, a.z + b.z)

    def add_(self, arg) -> "Vector3":
        if isinstance(arg, Vector3):
            self.x = f32(self.x + arg.x)
            self.y = f32(self.y + arg.y)
            self.z = f32(self.z + arg.z)
        else:
            self.x = f32(self.x + arg)
            self.y = f32(self.y + arg)
            self.z = f32(self.z + arg)
        return self

    @staticmethod
    def sub(a: "Vector3", b) -> "Vector3":
        if isinstance(b, Vector3):
            return Vector3(a.x - b.x, a.y - b.y, a.z - b.z)
        szam = b
        if math.isnan(szam):
            raise ArithmeticError('the number came out NaN')
        return Vector3(a.x - szam, a.y - szam, a.z - szam)

    def sub_(self, arg) -> "Vector3":
        if isinstance(arg, Vector3):
            self.x = f32(self.x - arg.x)
            self.y = f32(self.y - arg.y)
            self.z = f32(self.z - arg.z)
        else:
            self.x = f32(self.x - arg)
            self.y = f32(self.y - arg)
            self.z = f32(self.z - arg)
        return self

    @staticmethod
    def mult(a, b) -> "Vector3":
        if isinstance(a, Vector3):
            v, szam = a, b
        else:
            v, szam = b, a
        return Vector3(v.x * szam, v.y * szam, v.z * szam)

    def mult_(self, num: float) -> "Vector3":
        self.x = f32(self.x * num)
        self.y = f32(self.y * num)
        self.z = f32(self.z * num)
        return self

    @staticmethod
    def div(vec: "Vector3", b) -> "Vector3":
        if isinstance(b, Vector3):
            return Vector3(vec.x / b.x, vec.y / b.y, vec.z / b.z)
        szam = b
        if szam == 0:
            raise ValueError('a number is required')
        return Vector3.mult(vec, 1.0 / szam)

    def div_(self, oszto: float) -> "Vector3":
        if oszto == 0:
            raise ValueError("div_by cannot be 0!")
        return self.mult_(1.0 / oszto)

    @staticmethod
    def scale(a: "Vector3", b: "Vector3") -> "Vector3":
        return Vector3(a.x * b.x, a.y * b.y, a.z * b.z)

    def scale_(self, scale):
        from rebsgo.geometry.primitives.euler3 import Euler3

        if isinstance(scale, (int, float)):
            self.x = f32(self.x * scale)
            self.y = f32(self.y * scale)
            self.z = f32(self.z * scale)
            return self
        if isinstance(scale, Euler3):
            self.x = f32(self.x * scale.pitch)
            self.y = f32(self.y * scale.yaw)
            self.z = f32(self.z * scale.roll)
            return None
        self.x = f32(self.x * scale.x)
        self.y = f32(self.y * scale.y)
        self.z = f32(self.z * scale.z)
        return self

    @staticmethod
    def negated(vec: "Vector3") -> "Vector3":
        return Vector3(-vec.x, -vec.y, -vec.z)

    def negate_(self) -> "Vector3":
        self.x = -self.x
        self.y = -self.y
        self.z = -self.z
        return self

    def mod(self, value: float) -> "Vector3":
        self.x = f32(math.fmod(self.x, value))
        self.y = f32(math.fmod(self.y, value))
        self.z = f32(math.fmod(self.z, value))
        return self

    @staticmethod
    def abs(v: "Vector3") -> "Vector3":
        return Vector3(abs(v.x), abs(v.y), abs(v.z))

    def abs_(self) -> "Vector3":
        self.x = Maths.abs(self.x)
        self.y = Maths.abs(self.y)
        self.z = Maths.abs(self.z)
        return self


    @staticmethod
    def normalize(vec: "Vector3") -> "Vector3":
        return vec.copy().normalize_()

    def normalize_(self) -> "Vector3":
        hossz = self.magnitude_
        if hossz <= _EGYSEGHOSSZ_TURES:
            self.xyz_to(0.0, 0.0, 0.0)
            return self
        len_inv = 1.0 / hossz
        self.x = f32(self.x * len_inv)
        self.y = f32(self.y * len_inv)
        self.z = f32(self.z * len_inv)
        return self

    @staticmethod
    def dot(a: "Vector3", b: "Vector3") -> float:
        return a.x * b.x + a.y * b.y + a.z * b.z

    @staticmethod
    def cross(a: "Vector3", b: "Vector3") -> "Vector3":
        return Vector3(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x)

    def cross_(self, vec: "Vector3") -> "Vector3":
        return Vector3.cross(self, vec)

    @staticmethod
    def angle(from_v: "Vector3", to: "Vector3") -> float:
        return Maths.acos(Maths.clamp_min11(Vector3.dot(Vector3.normalize(from_v), Vector3.normalize(to)))) * Maths.RAD_TO_DEG

    @staticmethod
    def angle_along_vector(vec: "Vector3") -> float:
        if vec.sq_magnitude_ < 0.01:
            return 0.0
        return Maths.RAD_TO_DEG * Maths.atan2(vec.x, vec.z)

    @staticmethod
    def distance(a: "Vector3", b: "Vector3") -> float:
        return Maths.sqrt(Vector3.squared_distance(a, b))

    def distance_(self, other: "Vector3") -> float:
        return Vector3.distance(self, other)

    def sq_distance_to(self, other: "Vector3") -> float:
        return Vector3.squared_distance(self, other)

    @staticmethod
    def squared_distance(a: "Vector3", b: "Vector3") -> float:
        x = a.x - b.x
        y = a.y - b.y
        z = a.z - b.z
        return x * x + y * y + z * z

    @staticmethod
    def span_between(a: "Vector3", b: "Vector3") -> "Vector3":
        return Vector3.sub(b, a)

    @staticmethod
    def triple_product(a: "Vector3", b: "Vector3", c: "Vector3") -> float:
        return Vector3.dot(Vector3.cross(a, b), c)

    @staticmethod
    def project(vector: "Vector3", vetulet_normal: "Vector3") -> "Vector3":
        szam = vetulet_normal.sq_magnitude_
        if szam < Maths.EPSILON:
            return Vector3.zero()
        return Vector3.mult(vetulet_normal, Vector3.dot(vector, vetulet_normal) / szam)

    @staticmethod
    def perpendicular(length_vec: "Vector3", direction: "Vector3" = None) -> "Vector3":
        if direction is None:
            return Vector3.cross(length_vec, length_vec)
        return Vector3.sub(length_vec, Vector3.project(length_vec, direction))

    @staticmethod
    def flattened_onto(vector: "Vector3", sik_normalis: "Vector3") -> "Vector3":
        return Vector3.sub(vector, Vector3.project(vector, sik_normalis))


    @staticmethod
    def quick_normal(v: "Vector3", normalize: bool) -> "Vector3":
        sqr = v.x * v.x + v.y * v.y
        if sqr > 0.0:
            im = 1.0 / Maths.sqrt(sqr) if normalize else 1.0
            return Vector3(-v.y * im, v.x * im, 0.0)
        sqr = v.y * v.y + v.z * v.z
        im = 1.0 / Maths.sqrt(sqr) if normalize else 1.0
        return Vector3(0.0, -v.z * im, v.y * im)

    @staticmethod
    def acceleration_for(egyik_sebesseg: "Vector3", masik_sebesseg: "Vector3", time: float) -> "Vector3":
        return Vector3.sub(egyik_sebesseg, masik_sebesseg).mult_(1.0 / time)


    @staticmethod
    def clamp(v: "Vector3", min_v: float, max_v: float) -> "Vector3":
        return Vector3(Maths.clamp(v.x, min_v, max_v), Maths.clamp(v.y, min_v, max_v), Maths.clamp(v.z, min_v, max_v))

    def clamp_(self, min_v: float, max_v: float) -> "Vector3":
        self.x = Maths.clamp(self.x, min_v, max_v)
        self.y = Maths.clamp(self.y, min_v, max_v)
        self.z = Maths.clamp(self.z, min_v, max_v)
        return self

    @staticmethod
    def clamp_magnitude(vector: "Vector3", max_length: float) -> "Vector3":
        if vector.sq_magnitude_ > (max_length * max_length):
            return Vector3.normalize(vector).mult_(max_length)
        return vector

    @staticmethod
    def min(lhs: "Vector3", rhs: "Vector3") -> "Vector3":
        return Vector3(Maths.min(lhs.x, rhs.x), Maths.min(lhs.y, rhs.y), Maths.min(lhs.z, rhs.z))

    @staticmethod
    def max(lhs: "Vector3", rhs: "Vector3") -> "Vector3":
        return Vector3(Maths.max(lhs.x, rhs.x), Maths.max(lhs.y, rhs.y), Maths.max(lhs.z, rhs.z))

    @staticmethod
    def between_bounds(point: "Vector3", lower_corner: "Vector3", upper_corner: "Vector3") -> bool:
        return (
            Maths.within_bounds_of(point.x, lower_corner.x, upper_corner.x)
            and Maths.within_bounds_of(point.y, lower_corner.y, upper_corner.y)
            and Maths.within_bounds_of(point.z, lower_corner.z, upper_corner.z)
        )


    @staticmethod
    def lerp(a: "Vector3", b: "Vector3", t) -> "Vector3":
        if isinstance(t, Vector3):
            return Vector3.add(a, Vector3.scale(b, t))
        t = Maths.clamp01(t)
        return Vector3(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t, a.z + (b.z - a.z) * t)


    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not isinstance(other, Vector3):
            return False
        return self.x == other.x and self.y == other.y and self.z == other.z

    def __hash__(self) -> int:
        return hash((self.x, self.y, self.z))

    def __repr__(self) -> str:
        return "<Vector3 " + f"x={self.x}, y={self.y}, z={self.z}" + ">"
