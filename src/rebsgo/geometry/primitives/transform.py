# github.com/Shran21

from __future__ import annotations

from enum import Enum

from rebsgo.geometry.primitives.euler3 import Euler3
from rebsgo.geometry.primitives.quaternion import Quaternion
from rebsgo.geometry.primitives.vector3 import Vector3
from rebsgo.helpers.copyable import Copyable


class AxisConvention(Enum):
    World = 0
    Self = 1


class Transform(Copyable["Transform"]):


    def __init__(self, position=None, rotation=None, copy: bool = False):
        if isinstance(position, Transform):
            t = position
            position, rotation, copy = t._position, t._rotation, True
        elif position is None:
            position = Vector3.zero()
            rotation = Quaternion.identity()
        elif rotation is None:
            rotation = Quaternion.identity()
        elif isinstance(rotation, Euler3):
            rotation = rotation.quaternion

        if position is None or rotation is None:
            raise TypeError("both a position and a rotation are required")

        if copy:
            self._position = position.copy()
            self._rotation = rotation.copy()
        else:
            self._position = position
            self._rotation = rotation

    def copy(self) -> "Transform":
        return Transform(self)

    @staticmethod
    def identity() -> "Transform":
        return Transform(Vector3.zero(), Quaternion.identity(), False)


    def position_of(self) -> Vector3:
        return self._position

    def rotation_of(self) -> Quaternion:
        return self._rotation

    @property
    def rotation_euler3(self) -> Euler3:
        return Euler3.from_quaternion(self._rotation)


    def place_at(self, transform: "Transform") -> "Transform":
        self._position.copy_from(transform._position)
        self._rotation.turn_to(transform._rotation)
        return self

    def set_position_rotation(self, position: Vector3, rotation: Quaternion) -> None:
        self._position.copy_from(position)
        self._rotation.turn_to(rotation)

    def rotate(self, arg, frame_kind: AxisConvention) -> None:
        fordulat = Quaternion.euler(arg) if isinstance(arg, Vector3) else arg
        if frame_kind == AxisConvention.Self:
            self._rotation.mult_(fordulat)
            return
        vissza = Quaternion.inverse(self._rotation)
        self._rotation.mult_(vissza.mult_(fordulat).mult_(self._rotation))

    def translate(self, translation: Vector3, relative_to: AxisConvention) -> None:
        if relative_to == AxisConvention.World:
            self._position.add_(translation)
        else:
            self._position.add_(self.transform_direction(translation))


    @staticmethod
    def to_local(world_parent: "Transform", world_child: "Transform") -> "Transform":
        inverse_rotation = Quaternion.inverse(world_parent._rotation)
        relative_position = inverse_rotation.mult_(Vector3.sub(world_child._position, world_parent._position))
        relative_rotation = Quaternion.mult(inverse_rotation, world_child._rotation)
        return Transform(relative_position, relative_rotation)

    def into_world_space(self, global_t: "Transform") -> "Transform":
        relative_rotation = Quaternion.mult(global_t._rotation, self._rotation)
        relative_position = Quaternion.mult(global_t._rotation, self._position)
        relative_position.add_(global_t._position)
        return Transform(relative_position, relative_rotation)

    def through_transform(self, vec: Vector3) -> Vector3:
        new_pos = Quaternion.mult(self._rotation, vec)
        return new_pos.add_(self._position)

    def transform_direction(self, direction: Vector3) -> Vector3:
        return self._rotation.mult_(direction)

    def seen_from_here(self, v: Vector3) -> Vector3:
        atmeneti = Vector3.sub(v, self._position)
        atmeneti.copy_from(Quaternion.inverse(self._rotation).mult_(atmeneti))
        return atmeneti

    @staticmethod
    def inverse(t: "Transform") -> "Transform":
        inv_q = Quaternion.inverse(t.rotation_of())
        inv_pos = Vector3.negated(t.position_of())
        new_pos = inv_q.mult_(inv_pos)
        return Transform(new_pos, inv_q)

    def inverse_(self) -> "Transform":
        inv_t = Transform.inverse(self)
        return self.place_at(inv_t)


    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if type(other) is not type(self):
            return NotImplemented
        if self._position != other._position:
            return False
        return self._rotation == other._rotation

    def __hash__(self) -> int:
        return hash((self._position, self._rotation))

    def __repr__(self) -> str:
        return "<Transform " + f"position={self._position}, rotation={self._rotation}" + ">"
