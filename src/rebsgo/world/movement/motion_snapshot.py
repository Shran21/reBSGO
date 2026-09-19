# github.com/Shran21

from __future__ import annotations

from rebsgo.wire.bytes.outgoing import Outgoing
from rebsgo.geometry.primitives.euler3 import Euler3
from rebsgo.geometry.primitives.quaternion import Quaternion
from rebsgo.geometry.primitives.common import CommonDirections
from rebsgo.geometry.primitives.transform import Transform
from rebsgo.geometry.primitives.frozen import frozen
from rebsgo.geometry.primitives.vector3 import Vector3
from rebsgo.helpers.floats import f32


class MovementFrame(Outgoing):
    def __init__(self, position, euler3, linear_speed=None, strafe_speed=None,
                 euler3_speed=None, mode: int = 0, valid: bool = True):
        if linear_speed is None:
            linear_speed = Vector3.zero()
        if strafe_speed is None:
            strafe_speed = Vector3.zero()
        if euler3_speed is None:
            euler3_speed = Euler3.zero()
        self._position = position
        self._euler3 = euler3
        self._linear_speed = linear_speed
        self._strafe_speed = strafe_speed
        self._euler3_speed = euler3_speed
        self._mode = mode & 0xFF if mode < 0 else int(mode)
        self._valid = valid
        self._rotation_cached = None

    @property
    def facing(self) -> Vector3:
        return self.rotation_of().mult_(CommonDirections.FORWARD)

    @property
    def full_copy(self) -> "MovementFrame":
        return MovementFrame(
            self._position.copy(),
            self._euler3.copy(),
            self._linear_speed.copy(),
            self._strafe_speed.copy(),
            self._euler3_speed.copy(),
            self._mode,
            self._valid,
        )

    @property
    def shallow_copy(self) -> "MovementFrame":
        return MovementFrame(
            self._position,
            self._euler3,
            self._linear_speed,
            self._strafe_speed,
            self._euler3_speed,
            self._mode,
            self._valid,
        )

    def future_position(self, dt: float) -> Vector3:
        return Vector3(
            f32(f32(self._linear_speed.x + self._strafe_speed.x) * dt) + self._position.x,
            f32(f32(self._linear_speed.y + self._strafe_speed.y) * dt) + self._position.y,
            f32(f32(self._linear_speed.z + self._strafe_speed.z) * dt) + self._position.z,
        )

    def rotation_of(self) -> Quaternion:
        if self._rotation_cached is not None:
            return self._rotation_cached
        self._rotation_cached = self._euler3.quaternion
        return frozen(self._rotation_cached)

    @staticmethod
    def void_frame() -> "MovementFrame":
        invalid = MovementFrame(
            Vector3.zero(), Euler3.identity(), Vector3.zero(), Vector3.zero(), Euler3.zero(), 0
        )
        invalid._valid = False
        return invalid

    FORGATASOK = {
        0: lambda e, seb, dt: Euler3.mult(seb, dt).add_(e).normalized(True),
        1: lambda e, seb, dt: Euler3.mult(seb, dt).add_(e).normalized(False),
        2: lambda e, seb, dt: Euler3.spin_over(e, seb, dt),
        3: lambda e, seb, dt: Euler3.spin_locally(e, seb, dt),
    }

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not isinstance(other, MovementFrame):
            return False
        return (self._position == other._position
                and self._euler3 == other._euler3
                and self._linear_speed == other._linear_speed
                and self._strafe_speed == other._strafe_speed
                and self._euler3_speed == other._euler3_speed
                and self._mode == other._mode
                and self._valid == other._valid
                and self._rotation_cached == other._rotation_cached)

    def __hash__(self) -> int:
        return hash((self._position, self._euler3, self._linear_speed, self._strafe_speed,
                     self._euler3_speed, self._mode, self._valid, self._rotation_cached))

    def __repr__(self) -> str:
        return (f"<MovementFrame position={self._position}, euler3={self._euler3}"
                f", linear_speed={self._linear_speed}, strafe_speed={self._strafe_speed}"
                f", euler3_speed={self._euler3_speed}, mode={self._mode}"
                f", valid={self._valid}>")

    @property
    def euler3_speed(self) -> Euler3:
        return frozen(self._euler3_speed)

    @property
    def linear_speed(self) -> Vector3:
        return frozen(self._linear_speed)

    @property
    def mode(self) -> int:
        return self._mode

    @property
    def strafe_speed(self) -> Vector3:
        return frozen(self._strafe_speed)

    @property
    def usable(self) -> bool:
        return self._valid

    def euler3(self) -> Euler3:
        return frozen(self._euler3)

    def future_euler3(self, dt: float) -> Euler3:
        forgat = self.FORGATASOK.get(self._mode)
        if forgat is None:
            return Euler3.zero()
        return forgat(self._euler3, self._euler3_speed, dt)

    def future_rotation(self, t: float) -> Quaternion:
        if self._mode == 2:
            return Euler3.spin_over(self._euler3, self._euler3_speed, t).quaternion
        if self._mode == 3:
            return Euler3.spin_locally(self._euler3, self._euler3_speed, t).quaternion
        return Euler3.add(self._euler3, Euler3.mult(self._euler3_speed, t)).quaternion

    def next_transform(self, dt: float) -> Transform:
        return Transform(self.future_position(dt), self.future_euler3(dt))

    def position_of(self) -> Vector3:
        return frozen(self._position)

    def to_wire(self, bw) -> None:
        bw.write_vector3(self._position)
        bw.write_euler3(self._euler3)
        bw.write_vector3(self._linear_speed)
        bw.write_vector3(self._strafe_speed)
        bw.write_euler3(self._euler3_speed)
        bw.write_byte(self._mode)

    def transform_of(self) -> Transform:
        return Transform(self._position, self.rotation_of(), True)
