# github.com/Shran21

from __future__ import annotations

from rebsgo.geometry.primitives.euler3 import Euler3
from rebsgo.geometry.primitives.quaternion import Quaternion
from rebsgo.geometry.primitives.vector3 import Vector3

_VEC_MSG = "this vector is read-only"
_QUAT_MSG = "this rotation is read-only"
_EULER_MSG = "these angles are read-only"


class FrozenVector3(Vector3):
    def __init__(self, vec: Vector3):
        super().__init__(vec.x, vec.y, vec.z)

    @property
    def to_array_(self):
        return super().to_array_

    def scale_(self, scale):
        raise TypeError(_VEC_MSG)

    def xyz_to(self, x, y, z):
        raise TypeError(_VEC_MSG)

    def copy_from(self, other):
        raise TypeError(_VEC_MSG)

    def normalize_(self):
        raise TypeError(_VEC_MSG)

    def clamp_(self, min_v, max_v):
        raise TypeError(_VEC_MSG)

    def abs_(self):
        raise TypeError(_VEC_MSG)

    def add_(self, arg):
        raise TypeError(_VEC_MSG)

    def sub_(self, arg):
        raise TypeError(_VEC_MSG)

    def mult_(self, num):
        raise TypeError(_VEC_MSG)

    def add_x(self, value):
        raise TypeError(_VEC_MSG)

    def add_y(self, value):
        raise TypeError(_VEC_MSG)

    def add_z(self, value):
        raise TypeError(_VEC_MSG)

    def x_to(self, value):
        raise TypeError(_VEC_MSG)

    def y_to(self, value):
        raise TypeError(_VEC_MSG)

    def z_to(self, value):
        raise TypeError(_VEC_MSG)

    def negate_(self):
        raise TypeError(_VEC_MSG)


class FrozenQuaternion(Quaternion):
    def __init__(self, quat: Quaternion):
        super().__init__(quat.x, quat.y, quat.z, quat.w)

    def mult_(self, arg):
        if isinstance(arg, Vector3):
            return super().mult_(arg)
        raise TypeError(_QUAT_MSG)

    def inverse_(self):
        raise TypeError(_QUAT_MSG)

    def normalize_(self):
        raise TypeError(_QUAT_MSG)

    def face_towards(self, vector3):
        raise TypeError(_QUAT_MSG)

    def turn_to(self, new_rotation):
        raise TypeError(_QUAT_MSG)


class FrozenEuler3(Euler3):
    def __init__(self, szogek: Euler3):
        super().__init__(szogek.pitch, szogek.yaw, szogek.roll)

    def clamp(self, also, felso=None):
        if felso is None:
            raise TypeError(_EULER_MSG)
        super().clamp(also, felso)

    def pitch_to(self, pitch):
        raise TypeError(_EULER_MSG)

    def yaw_to(self, yaw):
        raise TypeError(_EULER_MSG)

    def copy_angles_from(self, pitch, yaw, roll):
        raise TypeError(_EULER_MSG)

    def roll_to(self, roll):
        raise TypeError(_EULER_MSG)

    def mult_(self, num):
        raise TypeError(_EULER_MSG)

    def add_(self, other):
        raise TypeError(_EULER_MSG)


_BURKOK = ((Quaternion, FrozenQuaternion), (Euler3, FrozenEuler3), (Vector3, FrozenVector3))


def frozen(obj):
    for fajta, burok in _BURKOK:
        if isinstance(obj, fajta):
            return burok(obj)
    raise TypeError(f"nothing wraps a {type(obj).__name__}")
