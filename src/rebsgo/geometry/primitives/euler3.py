# github.com/Shran21

from __future__ import annotations

import math

from rebsgo.geometry.primitives.quaternion import Quaternion
from rebsgo.geometry.primitives.vector3 import Vector3
from rebsgo.geometry.maths.maths import Maths
from rebsgo.helpers.floats import f32


class Euler3:


    def __init__(self, pitch=0.0, yaw=0.0, roll=0.0):
        self._pitch = 0.0 if math.isnan(pitch) else f32(pitch)
        self._yaw = 0.0 if math.isnan(yaw) else f32(yaw)
        self._roll = 0.0 if math.isnan(roll) else f32(roll)

    def copy(self) -> "Euler3":
        masolat = Euler3.__new__(Euler3)
        masolat._pitch = self._pitch
        masolat._yaw = self._yaw
        masolat._roll = self._roll
        return masolat

    @staticmethod
    def zero() -> "Euler3":
        return Euler3(0.0, 0.0, 0.0)

    @staticmethod
    def identity() -> "Euler3":
        return Euler3.from_quaternion(Quaternion.identity())

    def from_axes(self, input_vec: Vector3) -> None:
        self._pitch = f32(input_vec.x)
        self._yaw = f32(input_vec.y)
        self._roll = f32(input_vec.z)


    @property
    def pitch(self) -> float:
        return self._pitch

    @property
    def yaw(self) -> float:
        return self._yaw

    @property
    def roll(self) -> float:
        return self._roll

    @staticmethod
    def axes_of(input_vec: Vector3) -> "Euler3":
        return Euler3(input_vec.x, input_vec.y, input_vec.z)

    @property
    def to_axes(self) -> Vector3:
        return Vector3(self._pitch, self._yaw, self._roll)

    @staticmethod
    def direction(direction: Vector3) -> "Euler3":
        yaw = Maths.atan2(direction.x, direction.z) * Maths.RAD_TO_DEG
        pitch = -Maths.atan2(
            direction.y,
            Maths.sqrt(direction.x * direction.x + direction.z * direction.z),
        ) * Maths.RAD_TO_DEG
        return Euler3(pitch, yaw, 0.0)

    def direction_(self) -> Vector3:
        from rebsgo.geometry.primitives.common import CommonDirections

        return self.quaternion.mult_(CommonDirections.FORWARD)


    def pitch_to(self, pitch: float) -> None:
        self._pitch = f32(pitch)

    def yaw_to(self, yaw: float) -> None:
        self._yaw = f32(yaw)

    def roll_to(self, roll: float) -> None:
        self._roll = f32(roll)

    def copy_angles_from(self, pitch, yaw, roll) -> None:
        self._pitch = f32(pitch)
        self._yaw = f32(yaw)
        self._roll = f32(roll)


    @staticmethod
    def add(a: "Euler3", b: "Euler3") -> "Euler3":
        return a.copy().add_(b)

    def add_(self, other: "Euler3") -> "Euler3":
        self._pitch = f32(self._pitch + other._pitch)
        self._yaw = f32(self._yaw + other._yaw)
        self._roll = f32(self._roll + other._roll)
        return self

    @staticmethod
    def sub(a: "Euler3", b: "Euler3") -> "Euler3":
        return Euler3(a._pitch - b._pitch, a._yaw - b._yaw, a._roll - b._roll)

    @staticmethod
    def mult(a: "Euler3", b: float) -> "Euler3":
        return a.copy().mult_(b)

    def mult_(self, num: float) -> "Euler3":
        self._pitch = f32(self._pitch * num)
        self._yaw = f32(self._yaw * num)
        self._roll = f32(self._roll * num)
        return self

    @staticmethod
    def negate_in_place(a: "Euler3") -> "Euler3":
        return Euler3(-a._pitch, -a._yaw, -a._roll)


    def clamp(self, also: "Euler3", felso: "Euler3" = None) -> None:
        also_pitch, also_yaw, also_roll = also._pitch, also._yaw, also._roll
        if felso is None:
            felso = also
            also_pitch, also_yaw, also_roll = -also_pitch, -also_yaw, -also_roll
        self.copy_angles_from(
            Maths.clamp(self._pitch, also_pitch, felso._pitch),
            Maths.clamp(self._yaw, also_yaw, felso._yaw),
            Maths.clamp(self._roll, also_roll, felso._roll))

    def normalized(self, force_straight: bool) -> "Euler3":
        new_pitch = Maths.wrap_angle(self._pitch)
        new_yaw = self._yaw
        new_roll = self._roll
        if force_straight and Maths.abs(new_pitch) > 90.0:
            new_pitch = Maths.wrap_angle(f32(179.99 - new_pitch))
            new_yaw = f32(new_yaw + 179.99)
            new_roll = f32(new_roll + 179.99)
        self.copy_angles_from(new_pitch, Maths.wrap_angle(new_yaw), Maths.wrap_angle(new_roll))
        return self


    @property
    def quaternion(self) -> Quaternion:
        return Quaternion.euler(self._pitch, self._yaw, self._roll)

    @staticmethod
    def from_quaternion(q: Quaternion) -> "Euler3":
        q_x2 = q.x * q.x
        q_y2 = q.y * q.y
        q_z2 = q.z * q.z
        q_w2 = q.w * q.w
        hossz = q_x2 + q_y2 + q_z2 + q_w2
        if hossz < 1e-10:
            return Euler3(0.0, 0.0, 0.0)

        polus = -q.z * q.y + q.x * q.w
        if abs(polus) > 0.499999 * hossz:
            fel = 1.0 if polus > 0.0 else -1.0
            szogek = (fel * Maths.PI_DIV_2, fel * 2.0 * Maths.atan2(-q.z, q.w), 0.0)
        else:
            szogek = (Maths.asin(2.0 * polus / hossz),
                      Maths.atan2(2.0 * q.y * q.w + 2.0 * q.z * q.x, -q_x2 - q_y2 + q_z2 + q_w2),
                      Maths.atan2(2.0 * q.z * q.w + 2.0 * q.y * q.x, -q_x2 + q_y2 - q_z2 + q_w2))

        pitch, yaw, roll = (0.0 if math.isnan(szog) else szog for szog in szogek)
        return Euler3(pitch, yaw, roll).mult_(Maths.RAD_TO_DEG)


    @staticmethod
    def spin_over(start, change_per_second, dt: float):
        if isinstance(start, Quaternion):
            from rebsgo.geometry.primitives.common import CommonTurns

            lhs = Quaternion.slerp(CommonTurns.IDENTITY, change_per_second, dt)
            return lhs.mult_(start)
        vector = change_per_second.to_axes
        lhs = Quaternion.angle_axis(vector.magnitude_ * dt, Vector3.normalize(vector))
        return Euler3.from_quaternion(lhs.mult_(start.quaternion))

    @staticmethod
    def spin_locally(start: "Euler3", change_per_second: "Euler3", dt: float) -> "Euler3":
        rhs = Quaternion.slerp(Quaternion.identity(), change_per_second.quaternion, dt)
        return Euler3.from_quaternion(start.quaternion.mult_(rhs))


    @staticmethod
    def same_as(a: "Euler3", b: "Euler3") -> bool:
        if a is None or b is None:
            return a is b
        return (a._pitch, a._yaw, a._roll) == (b._pitch, b._yaw, b._roll)

    def __eq__(self, other) -> bool:
        if other is None:
            return False
        if isinstance(other, Euler3):
            return Euler3.same_as(self, other)
        return False

    def __hash__(self) -> int:
        return hash((self._pitch, self._yaw, self._roll))

    def __repr__(self) -> str:
        return "<Euler3 " + f"pitch={self._pitch}, yaw={self._yaw}, roll={self._roll}" + ">"


Euler3.ZERO = Euler3(0, 0, 0)
