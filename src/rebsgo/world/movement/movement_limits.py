# github.com/Shran21

from __future__ import annotations
from rebsgo.helpers.locks import ReentrantLock
from rebsgo.geometry.primitives.euler3 import Euler3
from rebsgo.helpers.floats import f32, fdiv
from rebsgo.wire.bytes.outgoing import Outgoing
from rebsgo.vocabulary.pilot import Gear
from rebsgo.geometry.maths.maths import Maths
from rebsgo.helpers.copyable import Copyable


class MovementLimits(Outgoing, Copyable):
    _RATED = ("speed", "acceleration", "inertia_compensation",
              "pitch_acceleration", "pitch_max_speed",
              "yaw_acceleration", "yaw_max_speed",
              "roll_acceleration", "roll_max_speed",
              "strafe_acceleration", "strafe_max_speed")

    def __init__(self, gear: Gear = Gear.Regular, speed: float = 0.0, acceleration: float = 0.0,
                 inertia_compensation: float = 0.0, pitch_acceleration: float = 0.0,
                 pitch_max_speed: float = 0.0, yaw_acceleration: float = 0.0, yaw_max_speed: float = 0.0,
                 roll_acceleration: float = 0.0, roll_max_speed: float = 0.0,
                 strafe_acceleration: float = 0.0, strafe_max_speed: float = 0.0,
                 movement_card=None):
        self.lock = ReentrantLock()
        self._gear = gear
        for nev, ertek in zip(MovementLimits._RATED,
                              (speed, acceleration, inertia_compensation,
                               pitch_acceleration, pitch_max_speed,
                               yaw_acceleration, yaw_max_speed,
                               roll_acceleration, roll_max_speed,
                               strafe_acceleration, strafe_max_speed)):
            setattr(self, "_" + nev, f32(ertek))
        self._throttle_speed = 0.0
        self._last_gear = Gear.None_
        self._min_yaw_speed = 0.0
        self._max_pitch = 0.0
        self._max_roll = 0.0
        self._pitch_fading = 0.0
        self._yaw_fading = 0.0
        self._roll_fading = 0.0
        self._movement_card = None
        self._update_subscriber = None
        if movement_card is not None:
            self.fold_in_card(movement_card)

    def watch_updates(self, figyelo) -> None:
        self._update_subscriber = figyelo

    def copy(self) -> "MovementLimits":
        c = MovementLimits.__new__(MovementLimits)
        vars(c).update(vars(self))
        c.lock = ReentrantLock()
        return c

    def to_wire(self, bw) -> None:
        bw.write_byte(self._gear.value)
        for nev in MovementLimits._RATED:
            bw.write_single(getattr(self, "_" + nev))

    def fold_in_card(self, card) -> None:
        if card is None:
            raise TypeError('a movement card is required')
        self.min_yaw_speed = f32(card.min_yaw_speed * self.yaw_max_speed)
        self.max_pitch = card.max_pitch
        self.max_roll = card.max_roll
        self.pitch_fading = card.pitch_fading
        self.yaw_fading = card.yaw_fading
        self.roll_fading = card.roll_fading

    @property
    def turn_acceleration_ceiling(self) -> Euler3:
        return Euler3(self.pitch_acceleration, self.yaw_acceleration, self.roll_acceleration)

    @property
    def turn_speed_ceiling(self) -> Euler3:
        return Euler3(self.pitch_max_speed, self.yaw_max_speed, self.roll_max_speed)

    def min_euler_speed(self, euler3: Euler3) -> Euler3:
        return Euler3(
            self.min_pitch_speed(euler3.pitch),
            self.min_yaw_speed_at(euler3.roll, euler3.pitch),
            self.min_roll_speed(euler3.roll),
        )

    def max_euler_speed(self, euler3: Euler3) -> Euler3:
        return Euler3(
            self.max_pitch_speed(euler3.pitch),
            self.max_yaw_speed(euler3.roll, euler3.pitch),
            self.max_roll_speed(euler3.roll),
        )

    def min_yaw_speed_at(self, roll: float, pitch: float) -> float:
        roll_influence = -Maths.clamp(fdiv(Maths.wrap_angle(roll), self.max_roll), -1.0, 1.0)
        base_yaw_speed = Maths.lerp(-self.yaw_max_speed, -self.min_yaw_speed, (roll_influence + 1.0) / 2.0)
        DOLESSZOG_OSZTO = 90.0
        return f32(base_yaw_speed * (1.0 + Maths.abs(Maths.wrap_angle(pitch)) / DOLESSZOG_OSZTO))

    def max_yaw_speed(self, roll: float, pitch: float) -> float:
        szam = -Maths.clamp(fdiv(Maths.wrap_angle(roll), self.max_roll), -1.0, 1.0)
        num2 = Maths.lerp(self.min_yaw_speed, self.yaw_max_speed, (szam + 1.0) / 2.0)
        return f32(num2 * (1.0 + Maths.abs(Maths.wrap_angle(pitch)) / 90.0))

    def min_pitch_speed(self, pitch: float) -> float:
        szam = -self.max_pitch * 0.7
        if pitch < szam:
            return Maths.lerp(-self.pitch_max_speed, 0.0, Maths.clamp01(fdiv(szam - pitch, self.max_pitch * 0.3)))
        return -self.pitch_max_speed

    def max_pitch_speed(self, pitch: float) -> float:
        szam = self._max_pitch * 0.7
        if pitch > szam:
            return Maths.lerp(self._pitch_max_speed, 0.0, Maths.clamp01(fdiv(0.0 - szam + pitch, self._max_pitch * 0.3)))
        return self._pitch_max_speed

    def min_roll_speed(self, roll: float) -> float:
        szam = -self.max_roll * 0.5
        if roll >= szam:
            return -self.roll_max_speed
        return Maths.lerp(-self.roll_max_speed, 0.0, Maths.clamp01(fdiv(szam - roll, self.max_roll * 0.5)))

    def max_roll_speed(self, roll: float) -> float:
        szam = self.max_roll * 0.5
        if roll <= szam:
            return self.roll_max_speed
        return Maths.lerp(self.roll_max_speed, 0.0, Maths.clamp01(fdiv(-szam + roll, self.max_roll * 0.5)))

    def shift_to(self, gear: Gear) -> None:
        self._set_last_gear(self._gear)
        self._gear = gear

    def set_speed(self, speed: float) -> None:
        with self.lock:
            self._speed = f32(speed)
            self._update_subscriber.refresh_movement()

    def drive_at(self, speed: float) -> None:
        self.throttle_to(speed)
        self.set_speed(speed)

    def _set_last_gear(self, last_gear: Gear) -> None:
        if last_gear == Gear.RCS:
            return
        self._last_gear = last_gear

    @property
    def gear_of(self) -> Gear:
        return self._gear

    @property
    def last_gear(self) -> Gear:
        return self._last_gear

    @property
    def speed(self) -> float:
        return self._speed

    @property
    def throttle_speed(self) -> float:
        return self._throttle_speed

    @property
    def acceleration(self) -> float:
        return self._acceleration

    @property
    def inertia_compensation(self) -> float:
        return self._inertia_compensation

    @property
    def pitch_acceleration(self) -> float:
        return self._pitch_acceleration

    @property
    def pitch_max_speed(self) -> float:
        return self._pitch_max_speed

    @property
    def yaw_acceleration(self) -> float:
        return self._yaw_acceleration

    @property
    def yaw_max_speed(self) -> float:
        return self._yaw_max_speed

    @property
    def roll_acceleration(self) -> float:
        return self._roll_acceleration

    @property
    def roll_max_speed(self) -> float:
        return self._roll_max_speed

    @property
    def strafe_acceleration(self) -> float:
        return self._strafe_acceleration

    @property
    def strafe_max_speed(self) -> float:
        return self._strafe_max_speed

    @property
    def min_yaw_speed(self) -> float:
        return self._min_yaw_speed

    @property
    def max_pitch(self) -> float:
        return self._max_pitch

    @property
    def max_roll(self) -> float:
        return self._max_roll

    @property
    def pitch_fading(self) -> float:
        return self._pitch_fading

    @property
    def yaw_fading(self) -> float:
        return self._yaw_fading

    @property
    def roll_fading(self) -> float:
        return self._roll_fading

    def throttle_to(self, v: float) -> None:
        self._throttle_speed = f32(v)

    def accelerate_at(self, v: float) -> None:
        self._acceleration = f32(v)

    @inertia_compensation.setter
    def inertia_compensation(self, v: float) -> None:
        self._inertia_compensation = f32(v)

    @pitch_acceleration.setter
    def pitch_acceleration(self, v: float) -> None:
        self._pitch_acceleration = f32(v)

    @pitch_max_speed.setter
    def pitch_max_speed(self, v: float) -> None:
        self._pitch_max_speed = f32(v)

    @yaw_acceleration.setter
    def yaw_acceleration(self, v: float) -> None:
        self._yaw_acceleration = f32(v)

    @yaw_max_speed.setter
    def yaw_max_speed(self, v: float) -> None:
        self._yaw_max_speed = f32(v)

    @roll_acceleration.setter
    def roll_acceleration(self, v: float) -> None:
        self._roll_acceleration = f32(v)

    @roll_max_speed.setter
    def roll_max_speed(self, v: float) -> None:
        self._roll_max_speed = f32(v)

    @strafe_acceleration.setter
    def strafe_acceleration(self, v: float) -> None:
        self._strafe_acceleration = f32(v)

    @strafe_max_speed.setter
    def strafe_max_speed(self, v: float) -> None:
        self._strafe_max_speed = f32(v)

    @min_yaw_speed.setter
    def min_yaw_speed(self, v: float) -> None:
        self._min_yaw_speed = f32(v)

    @max_pitch.setter
    def max_pitch(self, v: float) -> None:
        self._max_pitch = f32(v)

    @max_roll.setter
    def max_roll(self, v: float) -> None:
        self._max_roll = f32(v)

    @pitch_fading.setter
    def pitch_fading(self, v: float) -> None:
        self._pitch_fading = f32(v)

    @yaw_fading.setter
    def yaw_fading(self, v: float) -> None:
        self._yaw_fading = f32(v)

    @roll_fading.setter
    def roll_fading(self, v: float) -> None:
        self._roll_fading = f32(v)

    def __str__(self) -> str:
        return (f'<{self.gear_of} gear: {self.speed} at {self.acceleration} accel'
                f' (inertia {self.inertia_compensation});'
                f' pitch {self.pitch_max_speed}/{self.pitch_acceleration},'
                f' yaw {self.yaw_max_speed}/{self.yaw_acceleration},'
                f' roll {self.roll_max_speed}/{self.roll_acceleration},'
                f' strafe {self.strafe_max_speed}/{self.strafe_acceleration}>')
