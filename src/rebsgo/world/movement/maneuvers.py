# github.com/Shran21

from __future__ import annotations

from abc import ABC, abstractmethod
from rebsgo.wire.bytes.outgoing import Outgoing
from rebsgo.world.movement.motion_snapshot import MovementFrame
from rebsgo.world.movement.movement_limits import MovementLimits
from rebsgo.world.movement.movement_model import MovementModel
from rebsgo.world.sectors.heartbeat import Tick
from rebsgo.geometry.primitives.euler3 import Euler3
from rebsgo.geometry.primitives.quaternion import Quaternion
from rebsgo.geometry.primitives.common import CommonDirections
from rebsgo.geometry.primitives.frozen import frozen
from rebsgo.geometry.primitives.vector3 import Vector3
from rebsgo.geometry.maths.geometry3d import point_position_relative_to, relative_rotation_to
from rebsgo.helpers.floats import f32
from rebsgo.vocabulary.combat import ManeuverKind


class Maneuver(Outgoing, ABC):
    def __init__(self, maneuver_type):
        self.start_tick = None
        self._maneuver_type = maneuver_type
        self._movement_options = MovementLimits()

    def to_wire(self, bw) -> None:
        bw.write_byte(self._maneuver_type.value)
        bw.write_int32(self.start_tick.value)

    @abstractmethod
    def advance_frame(self, tick, prev_frame: MovementFrame, dt: float) -> MovementFrame:
        ...

    def __lt__(self, other: "Maneuver") -> bool:
        kulonbseg = self.start_tick.tick_diff(other.start_tick)
        if kulonbseg != 0:
            return kulonbseg < 0
        return self._maneuver_type.value < other._maneuver_type.value

    def steer_toward(self, prev_frame: MovementFrame, direction, dt: float) -> MovementFrame:
        if not prev_frame.usable:
            return MovementFrame.void_frame()
        return MovementModel.steer_toward(prev_frame, direction, self._movement_options, dt)

    def drift(self, prev_frame: MovementFrame) -> MovementFrame:
        if not prev_frame.usable:
            return MovementFrame.void_frame()
        return MovementModel.wasd(prev_frame, 0, 0, self._movement_options)

    @property
    def movement_options(self) -> MovementLimits:
        return self._movement_options

    def start_at(self, start_tick) -> None:
        if start_tick is None:
            raise TypeError("a start_tick is required")
        self.start_tick = start_tick

    @movement_options.setter
    def movement_options(self, movement_options: MovementLimits) -> None:
        self._movement_options = movement_options.copy()

    @property
    def maneuver_type(self):
        return self._maneuver_type


class DirectionalManeuver(Maneuver):
    def __init__(self, direction):
        super().__init__(ManeuverKind.Directional)
        self.direction = direction

    def advance_frame(self, tick, prev_frame: MovementFrame, dt: float) -> MovementFrame:
        return self.steer_toward(prev_frame, self.direction, dt)

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_euler3(self.direction)
        bw.write_desc(self.movement_options)


class NoRollManeuver(Maneuver):
    def __init__(self, direction):
        super().__init__(ManeuverKind.DirectionalWithoutRoll)
        self.direction = direction

    def advance_frame(self, tick, prev_frame: MovementFrame, dt: float) -> MovementFrame:
        return MovementModel.steer_without_roll(prev_frame, self.direction, self.movement_options)

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_euler3(self.direction)
        bw.write_desc(self.movement_options)


class FollowManeuver(Maneuver):
    def __init__(self, kovetett):
        super().__init__(ManeuverKind.Follow)
        self.follow_target = kovetett

    def advance_frame(self, tick, prev_frame: MovementFrame, dt: float) -> MovementFrame:
        if self.follow_target is None:
            return self.drift(prev_frame)
        follower_maneuver = self.follow_target.mover_of().current_maneuver  # noqa: F841

        last_frame = self.follow_target.mover_of().frame_at_tick(Tick.at(tick.value - 1))
        other_prev_pos = last_frame.position_of()
        direction = Euler3.direction(Vector3.sub(other_prev_pos, prev_frame.position_of()))
        return self.steer_toward(prev_frame, direction, dt)

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        if self.follow_target is not None:
            bw.write_uint32(self.follow_target.id_in_space())
        else:
            bw.write_uint32(0)

        bw.write_desc(self.movement_options)


class LaunchBase(Maneuver):
    def __init__(self, maneuver_type, kilovo, spot_desc, relative_speed: float):
        super().__init__(maneuver_type)
        self.launcher_space_object = kilovo
        self.spot_desc = spot_desc
        self.relative_speed = f32(relative_speed)

    def launch_frame(self, dt: float) -> MovementFrame:
        current_launcher_frame = self.launcher_space_object.mover_of().last_frame

        relative_rotation = relative_rotation_to(
            current_launcher_frame.future_euler3(dt).quaternion, self.spot_desc.local_rotation)
        relative_position = point_position_relative_to(
            self.spot_desc.local_position, current_launcher_frame.future_position(dt),
            current_launcher_frame.rotation_of())
        rot_mult_forward = Quaternion.mult(relative_rotation, Vector3.forward())
        direction = Euler3.direction(rot_mult_forward).normalized(False)
        b = Vector3.mult(rot_mult_forward, self.relative_speed)

        return MovementFrame(relative_position, direction,
                             Vector3.add(current_launcher_frame.linear_speed, b),
                             Vector3.zero(), Euler3.zero(), 0)


class PulseManeuver(Maneuver):
    def __init__(self, direction):
        super().__init__(ManeuverKind.Pulse)
        if direction is None:
            raise TypeError('a direction is required')
        self.direction = direction
        self.euler3_direction = frozen(Euler3.direction(direction))

    def advance_frame(self, tick, prev_frame: MovementFrame, dt: float) -> MovementFrame:
        if tick == self.start_tick:
            eredmeny = self.steer_toward(prev_frame, self.euler3_direction, dt)
            return MovementFrame(eredmeny.position_of(), eredmeny.euler3(), self.direction,
                                 CommonDirections.ZERO, eredmeny.euler3_speed, eredmeny.mode, eredmeny.usable)

        return self.steer_toward(prev_frame, self.euler3_direction, dt)

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_vector3(self.direction)
        bw.write_desc(self.movement_options)


class RestManeuver(Maneuver):
    def __init__(self, position, euler3=None):
        super().__init__(ManeuverKind.Rest)
        if euler3 is None:
            transform = position
            position = transform.position_of()
            euler3 = Euler3.from_quaternion(transform.rotation_of())
        self.position = position.copy()
        self.euler3 = euler3.copy()

    def advance_frame(self, tick, prev_frame: MovementFrame, dt: float) -> MovementFrame:
        return MovementFrame(self.position, self.euler3, Vector3.zero(), Vector3.zero(), Euler3.zero(), 0)

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_vector3(self.position)
        bw.write_euler3(self.euler3)


class TeleportManeuver(Maneuver):
    def __init__(self, position):
        super().__init__(ManeuverKind.Teleport)
        self.position = position

    def advance_frame(self, tick, prev_frame: MovementFrame, dt: float) -> MovementFrame:
        return MovementFrame(self.position, prev_frame.euler3(), Vector3.zero(), Vector3.zero(), Euler3.zero(), 0)


class PitchYawTurnPlan(Maneuver):
    def __init__(self, pitch_yaw_roll_factor, strafe_direction, strafe_magnitude: float):
        super().__init__(ManeuverKind.PitchYawTurnPlan)
        self.pitch_yaw_roll_factor = pitch_yaw_roll_factor
        self.strafe_direction = strafe_direction
        self.strafe_magnitude = f32(strafe_magnitude)

    def advance_frame(self, tick, prev_frame: MovementFrame, dt: float) -> MovementFrame:
        return MovementModel.turn_by_strikes(prev_frame, self.pitch_yaw_roll_factor,
                                             self.strafe_direction, self.strafe_magnitude,
                                             self.movement_options)

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_vector3(self.pitch_yaw_roll_factor)
        bw.write_vector2(self.strafe_direction)
        bw.write_single(self.strafe_magnitude)
        bw.write_desc(self.movement_options)


class TurnManeuver(Maneuver):
    def __init__(self, qweasd):
        super().__init__(ManeuverKind.Turn)
        self.qweasd = qweasd

    def advance_frame(self, tick, prev_frame: MovementFrame, dt: float) -> MovementFrame:
        if not prev_frame.usable:
            return MovementFrame.void_frame()
        return MovementModel.wasd(prev_frame, self.qweasd.pitch, self.qweasd.yaw, self.movement_options)

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_byte(self.qweasd.bitmask & 0xFF)
        bw.write_desc(self.movement_options)


class TurnQweasdManeuver(Maneuver):
    def __init__(self, qweasd):
        super().__init__(ManeuverKind.TurnQweasd)
        self.qweasd = qweasd

    def advance_frame(self, tick, prev_frame: MovementFrame, dt: float) -> MovementFrame:
        if not prev_frame.usable:
            return MovementFrame.void_frame()
        return MovementModel.qweasd(prev_frame, self.qweasd.pitch, self.qweasd.yaw,
                                    self.qweasd.roll, self.movement_options, dt)

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_byte(self.qweasd.bitmask & 0xFF)
        bw.write_desc(self.movement_options)


class DirectionTurnPlan(Maneuver):
    def __init__(self, direction, roll: float, slide_x: float, slide_y: float):
        super().__init__(ManeuverKind.DirectionTurnPlan)
        self.direction = direction
        self.roll = f32(roll)
        self.slide_x = f32(slide_x)
        self.slide_y = f32(slide_y)

    def advance_frame(self, tick, prev_frame: MovementFrame, dt: float) -> MovementFrame:
        return MovementModel.turn_toward_strikes(prev_frame, self.direction, self.roll,
                                                 self.slide_x, self.slide_y, self.movement_options, dt)

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_euler3(self.direction)
        bw.write_single(self.roll)
        bw.write_single(self.slide_x)
        bw.write_single(self.slide_y)
        bw.write_desc(self.movement_options)


class LaunchManeuver(LaunchBase):
    def __init__(self, kilovo, spot_desc, relative_speed: float):
        super().__init__(ManeuverKind.Launch, kilovo, spot_desc, relative_speed)

    def advance_frame(self, tick, prev_frame: MovementFrame, dt: float) -> MovementFrame:
        if self.start_tick == tick:
            return self.launch_frame(dt)
        return self.drift(prev_frame)

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_uint32(self.launcher_space_object.id_in_space())
        bw.write_uint16(self.spot_desc.object_point_server_hash)
        bw.write_single(self.relative_speed)
        bw.write_desc(self.movement_options)


class TargetLaunchManeuver(LaunchBase):
    def __init__(self, kilovo, spot_desc, relative_speed: float, cel_objektum):
        super().__init__(ManeuverKind.TargetLaunch, kilovo, spot_desc, relative_speed)
        self.target_space_object = cel_objektum

    def advance_frame(self, tick, prev_frame: MovementFrame, dt: float) -> MovementFrame:
        if self.start_tick == tick:
            return self.launch_frame(dt)

        return self._frame_behind_target(prev_frame, dt)

    def _frame_behind_target(self, prev_frame: MovementFrame, dt: float) -> MovementFrame:
        if self.target_space_object is None or self.target_space_object.removing_cause_direct is not None:
            return self.drift(prev_frame)

        prev_frame_target = self.target_space_object.mover_of().last_frame

        direction = Euler3.direction(Vector3.sub(prev_frame_target.position_of(), prev_frame.position_of()))
        return self.steer_toward(prev_frame, direction, dt)

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_uint32(self.launcher_space_object.id_in_space())
        bw.write_uint32(self.target_space_object.id_in_space())
        bw.write_uint16(self.spot_desc.object_point_server_hash)
        bw.write_single(self.relative_speed)
        bw.write_desc(self.movement_options)

    def locked_target_of(self):
        return self.target_space_object


class StaticLaunchManeuver(TargetLaunchManeuver):
    def __init__(self, kilovo, spot_desc, relative_speed: float, cel_objektum):
        super().__init__(kilovo, spot_desc, relative_speed, cel_objektum)
        self._maneuver_type = ManeuverKind.Follow

    def to_wire(self, bw) -> None:
        Maneuver.to_wire(self, bw)
        bw.write_uint32(self.target_space_object.id_in_space())
        bw.write_desc(self.movement_options)
