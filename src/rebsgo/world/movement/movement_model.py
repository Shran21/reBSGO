# github.com/Shran21
from __future__ import annotations

from rebsgo.world.movement.motion_snapshot import MovementFrame
from rebsgo.vocabulary.pilot import Gear
from rebsgo.geometry.primitives.euler3 import Euler3
from rebsgo.geometry.primitives.quaternion import Quaternion
from rebsgo.geometry.primitives.vector3 import Vector3
from rebsgo.geometry.maths.maths import Maths
from rebsgo.helpers.floats import f32, fdiv

_DEFAULT_DT = f32(0.1)


class MovementModel:
    def __init__(self):
        raise RuntimeError("MovementModel is a static utility class")

    @staticmethod
    def _fekezesi_sebesseg(hatra: float, gyorsulas: float) -> float:
        if -Maths.EPSILON <= hatra <= Maths.EPSILON:
            return 0.0
        felfutas = Maths.abs(fdiv(2.0 * hatra, gyorsulas))
        celsebesseg = gyorsulas * felfutas
        return celsebesseg if hatra > 0 else -celsebesseg

    @staticmethod
    def steer_toward(prev_frame: MovementFrame, target_euler3: Euler3, options, dt: float) -> MovementFrame:
        current_euler = prev_frame.euler3()
        hatra_levo = Euler3.sub(target_euler3, current_euler).normalized(False)

        fordulo_utem = (MovementModel._fekezesi_sebesseg(hatra_levo.yaw, options.yaw_acceleration)
                        - prev_frame.euler3_speed.yaw) / dt
        bolinto_utem = (MovementModel._fekezesi_sebesseg(hatra_levo.pitch, options.pitch_acceleration)
                        - prev_frame.euler3_speed.pitch) / dt

        dolesszog = Maths.clamp(-hatra_levo.yaw * options.max_roll / 135.0,
                                -options.max_roll, options.max_roll)
        doles_hianya = Maths.wrap_angle(dolesszog - current_euler.roll)
        dontes_utem = (options.roll_acceleration * (fdiv(doles_hianya, options.max_roll)
                       - fdiv(prev_frame.euler3_speed.roll * options.roll_fading,
                              options.roll_max_speed)))

        uj_szogsebesseg = Euler3(bolinto_utem, fordulo_utem, dontes_utem)
        uj_szogsebesseg.clamp(options.turn_acceleration_ceiling)
        uj_szogsebesseg.mult_(dt)
        uj_szogsebesseg.add_(prev_frame.euler3_speed)
        uj_szogsebesseg.clamp(options.min_euler_speed(current_euler),
                              options.max_euler_speed(current_euler))

        return MovementFrame(prev_frame.future_position(dt), prev_frame.future_euler3(dt),
                             MovementModel.step_forward_speed(prev_frame, options, dt),
                             MovementModel.step_strafe_speed(prev_frame, options, 0.0, 0.0, dt),
                             uj_szogsebesseg, 0)

    @staticmethod
    def steer_without_roll(prev_frame: MovementFrame, target_euler3: Euler3, options, dt: float = _DEFAULT_DT) -> MovementFrame:
        forgatas = prev_frame.euler3_speed.quaternion
        q = Quaternion.rotation_between(prev_frame.euler3().direction_(), target_euler3.direction_())
        lhs = MovementModel.scale_to_ceiling(q, 2.0, options.yaw_max_speed)

        lhs.mult_(Quaternion.inverse(forgatas))

        to = MovementModel.scale_to_ceiling(lhs, 8.0, options.yaw_acceleration)
        change_per_second = Quaternion.rotate_towards(Quaternion.identity(), to, options.yaw_acceleration)
        to2 = Euler3.spin_over(forgatas, change_per_second, dt)
        quat = Quaternion.rotate_towards(Quaternion.identity(), to2, options.yaw_max_speed)
        euler3_speed = Euler3.from_quaternion(quat)
        linear_speed = MovementModel.step_forward_speed(prev_frame, options, dt)
        strafe_speed = MovementModel.step_strafe_speed(prev_frame, options, 0.0, 0.0, dt)

        return MovementFrame(
            prev_frame.future_position(dt), prev_frame.future_euler3(dt),
            linear_speed, strafe_speed, euler3_speed, 2)

    @staticmethod
    def scale_to_ceiling(rotation: Quaternion, scale: float, max_value: float) -> Quaternion:
        q = rotation.copy()
        if q.w < 0.0:
            q.mult_(-1.0)
        axis = Vector3()
        szam = q.to_angle_axis(axis)
        szog = Maths.clamp(szam * scale, 0.0, max_value)
        return Quaternion.angle_axis(szog, axis)

    @staticmethod
    def step_forward_speed(prev_frame: MovementFrame, options, dt: float) -> Vector3:
        if options.gear_of == Gear.RCS:
            return prev_frame.linear_speed.copy()

        previous_linear_velocity = prev_frame.linear_speed
        look_direction = prev_frame.facing
        projected_linear_speed = Vector3.dot(look_direction, previous_linear_velocity)

        projected_linear_velocity_vector = Vector3.mult(look_direction, projected_linear_speed)

        linear_speed_error = Vector3.sub(previous_linear_velocity, projected_linear_velocity_vector)
        magnitude = linear_speed_error.magnitude_
        linear_speed_error.normalize_()
        inertia_compensation_velocity = Vector3.mult(linear_speed_error, MovementModel.new_speed(magnitude, 0.0, options.inertia_compensation, dt))
        target_velocity = look_direction.mult_(MovementModel.new_speed(projected_linear_speed, options.speed, options.acceleration, dt))

        return inertia_compensation_velocity.add_(target_velocity)

    @staticmethod
    def new_speed(current: float, target: float, acceleration: float, dt: float) -> float:
        acceleration_dt = acceleration * dt
        diff_speed = current - target
        if Maths.abs(diff_speed) < acceleration_dt:
            return target
        if diff_speed > 0.0:
            return current - acceleration_dt
        return current + acceleration_dt

    @staticmethod
    def step_strafe_speed(prev_frame: MovementFrame, options, strafe_x: float, strafe_y: float, dt: float) -> Vector3:
        prev_frame_rotation = prev_frame.rotation_of()
        strafe_speed = prev_frame.strafe_speed
        strafe_x = Maths.clamp_min11(strafe_x)
        strafe_y = Maths.clamp_min11(strafe_y)
        point = Quaternion.mult(Quaternion.inverse(prev_frame_rotation), strafe_speed)
        new_strafe_x = strafe_x * options.strafe_max_speed
        new_strafe_y = strafe_y * options.strafe_max_speed

        x = MovementModel.new_speed(point.x, new_strafe_x, (1.0 if (point.x * new_strafe_x >= -1.0) else 2.0) * options.strafe_acceleration, dt)
        y = MovementModel.new_speed(point.y, new_strafe_y, (1.0 if (point.y * new_strafe_y >= -1.0) else 2.0) * options.strafe_acceleration, dt)
        z = MovementModel.new_speed(point.z, 0.0, options.strafe_acceleration, dt)
        tmp_vec = Vector3(x, y, z)

        return Quaternion.mult(prev_frame_rotation, tmp_vec)

    IRANYZOTT_TENGELYEK = (("yaw", "yaw_acceleration", "yaw_fading"),
                           ("pitch", "pitch_acceleration", "pitch_fading"))

    @staticmethod
    def wasd(prev_frame: MovementFrame, pitch: int, yaw: int, options, dt: float = _DEFAULT_DT) -> MovementFrame:
        prev_euler3_speed = prev_frame.euler3_speed
        euler = prev_frame.euler3()
        to = options.max_euler_speed(euler)
        from_e = options.min_euler_speed(euler)

        gyorsulas = Euler3.zero()
        gyorsulas.roll_to(MovementModel._dolesi_gyorsulas(euler, prev_euler3_speed, yaw, options))
        for tengely, gyorsulas_mezo, csillapitas_mezo in MovementModel.IRANYZOTT_TENGELYEK:
            MovementModel._tengely_gyorsulasa(
                tengely, {"yaw": yaw, "pitch": pitch}[tengely], prev_euler3_speed, options,
                gyorsulas_mezo, csillapitas_mezo, gyorsulas, from_e, to)

        euler3_speed = Euler3.add(prev_euler3_speed, Euler3.mult(gyorsulas, dt))
        euler3_speed.clamp(from_e, to)
        return MovementFrame(
            prev_frame.future_position(dt), prev_frame.future_euler3(dt),
            MovementModel.step_forward_speed(prev_frame, options, dt),
            MovementModel.step_strafe_speed(prev_frame, options, 0.0, 0.0, dt),
            euler3_speed,
            1 if pitch != 0 else 0)

    @staticmethod
    def _dolesi_gyorsulas(euler, prev_euler3_speed, yaw: int, options) -> float:
        cel_doles = 0.0
        if yaw > 0:
            cel_doles = -options.max_roll
        if yaw < 0:
            cel_doles = options.max_roll
        elteres = Maths.wrap_angle(cel_doles - euler.roll)
        return options.roll_acceleration * (
            fdiv(elteres, options.max_roll)
            - fdiv(prev_euler3_speed.roll * options.roll_fading, options.roll_max_speed))

    @staticmethod
    def _tengely_gyorsulasa(tengely: str, bemenet: int, prev_euler3_speed, options,
                            gyorsulas_mezo: str, csillapitas_mezo: str,
                            gyorsulas, from_e, to) -> None:
        allit = getattr(gyorsulas, tengely + "_to")
        merteke = getattr(options, gyorsulas_mezo)
        if bemenet != 0:
            allit(bemenet * merteke)
            return

        csillapitas = getattr(options, csillapitas_mezo)
        sebesseg = getattr(prev_euler3_speed, tengely)
        if sebesseg > Maths.EPSILON:
            allit(-merteke * csillapitas)
            getattr(from_e, tengely + "_to")(0.0)
        elif sebesseg < -Maths.EPSILON:
            allit(merteke * csillapitas)
            getattr(to, tengely + "_to")(0.0)

    @staticmethod
    def qweasd(prev_frame: MovementFrame, pitch: float, yaw: float, roll: float, options, dt: float) -> MovementFrame:
        prev_frame_rotation = prev_frame.rotation_of()
        vector = Vector3(pitch, yaw, roll)
        scale_euler3 = Euler3.mult(options.turn_acceleration_ceiling, dt)
        vector.scale_(scale_euler3)
        euler3_speed_vector3 = prev_frame.euler3_speed.to_axes
        vector3 = Quaternion.mult(Quaternion.inverse(prev_frame_rotation), euler3_speed_vector3)
        if vector.x == 0.0:
            vector.x_to(MovementModel.slowing_thrust(vector3.x, scale_euler3.pitch))
        if vector.y == 0.0:
            vector.y_to(MovementModel.slowing_thrust(vector3.y, scale_euler3.yaw))
        if vector.z == 0.0:
            vector.z_to(MovementModel.slowing_thrust(vector3.z, scale_euler3.roll))
        b2 = prev_frame_rotation.mult_(vector)

        v = Vector3.add(euler3_speed_vector3, b2)
        euler3_speed_vector3 = MovementModel.hold_inside_box(v, options.turn_speed_ceiling.to_axes, prev_frame_rotation)

        euler3_speed = Euler3.axes_of(euler3_speed_vector3)
        linear_speed = MovementModel.step_forward_speed(prev_frame, options, dt)
        strafe_speed = MovementModel.step_strafe_speed(prev_frame, options, 0.0, 0.0, dt)

        return MovementFrame(
            prev_frame.future_position(dt), prev_frame.future_euler3(dt),
            linear_speed, strafe_speed, euler3_speed, 2)

    @staticmethod
    def hold_inside_box(v: Vector3, half_side_lengths: Vector3, box_orientation: Quaternion) -> Vector3:
        ertek = Quaternion.mult(Quaternion.inverse(box_orientation), v)
        point = MovementModel._clamp(ertek, Vector3.negated(half_side_lengths), half_side_lengths)
        return Quaternion.mult(box_orientation, point)

    @staticmethod
    def _clamp(ertek: Vector3, min_v: Vector3, max_v: Vector3) -> Vector3:
        return Vector3.min(Vector3.max(ertek, min_v), max_v)

    @staticmethod
    def slowing_thrust(v: float, max_accel_this_frame: float) -> float:
        szam = float(-1 if (v >= 0.0) else 1)
        return szam * Maths.min(Maths.abs(v), Maths.abs(max_accel_this_frame))

    @staticmethod
    def turn_by_strikes(prev_frame: MovementFrame, strike_factor: Vector3,
                        strafe_direction, strafe_magnitude: float, options, dt: float = _DEFAULT_DT) -> MovementFrame:
        pitch_yaw_roll_factor = strike_factor.copy()

        vector = options.turn_acceleration_ceiling.to_axes
        vector2 = options.turn_speed_ceiling.to_axes
        next_position = prev_frame.future_position(dt)
        next_euler = prev_frame.future_euler3(dt)
        forgatas = next_euler.quaternion
        pitch_yaw_roll_factor.clamp_(-1, 1).scale_(vector2)
        vector3 = MovementModel.step_forward_speed(prev_frame, options, dt)
        strafe_x = strafe_direction.x * strafe_magnitude
        strafe_y = strafe_direction.y * strafe_magnitude
        vector4 = MovementModel.step_strafe_speed(prev_frame, options, strafe_x, strafe_y, dt)
        quaternion = Quaternion.inverse(forgatas)
        vector5 = Quaternion.mult(quaternion, prev_frame.euler3_speed.to_axes)

        vector7 = Vector3.sub(pitch_yaw_roll_factor, vector5)
        vector8 = Vector3.mult(vector, dt)
        MovementModel.hold_components(vector7, Vector3.negated(vector8), vector8)
        vector5.add_(vector7)
        if Maths.abs(pitch_yaw_roll_factor.z) < dt:
            vector5.z_to(MovementModel.new_speed(vector5.z, 0.0, options.roll_acceleration, dt))
        vector10 = Quaternion.mult(forgatas, vector5)
        euler = Euler3(vector10.x, vector10.y, vector10.z)
        return MovementFrame(next_position, next_euler, vector3, vector4, euler, 2)

    @staticmethod
    def hold_components(szamharmas: Vector3, min_vector: Vector3, max_vector: Vector3) -> None:
        szamharmas.xyz_to(
            Maths.clamp(szamharmas.x, min_vector.x, max_vector.x),
            Maths.clamp(szamharmas.y, min_vector.y, max_vector.y),
            Maths.clamp(szamharmas.z, min_vector.z, max_vector.z),
        )

    @staticmethod
    def turn_toward_strikes(prev_frame: MovementFrame, target_euler3: Euler3, roll: float,
                            strafe_x: float, strafe_y: float, options, dt: float) -> MovementFrame:
        max_turn_acceleration_vector = options.turn_acceleration_ceiling.to_axes
        max_turn_speed_vector = options.turn_speed_ceiling.to_axes
        vector2 = MovementModel.damping_for(max_turn_acceleration_vector, max_turn_speed_vector)
        szam = 3.0
        vector3 = options.turn_speed_ceiling.to_axes
        next_position = prev_frame.future_position(dt)
        next_euler = prev_frame.future_euler3(dt)
        forgatas = next_euler.quaternion
        vector4 = target_euler3.quaternion.mult_(Vector3.forward())
        roll = Maths.clamp(roll, -1.0, 1.0)
        linear_speed = MovementModel.step_forward_speed(prev_frame, options, dt)
        quaternion = Quaternion.inverse(forgatas)
        to_direction = quaternion.mult_(vector4)
        vector5 = quaternion.mult_(prev_frame.euler3_speed.to_axes)
        euler_angles = Quaternion.rotation_between(Vector3.forward(), to_direction).euler_angles()
        euler_angles = MovementModel.keep_vector_components_within_plus_minus_180(euler_angles)
        vector6 = MovementModel.velocity_for_turn(euler_angles, Vector3.mult(vector2, szam))
        scale = Vector3.one().sub_(Vector3.mult(vector2, dt))
        vector7 = vector5.copy()
        vector7.scale_(scale)
        scale2 = Vector3.one().sub_(Vector3.mult(vector2, szam * dt))
        vector8 = vector5.copy()
        vector8.scale_(scale2)
        flag = False
        flag2 = False
        if Maths.abs(vector7.x) > Maths.abs(vector6.x):
            scale.x_to(Maths.max(scale2.x, vector6.x / vector5.x))
            flag = True
        if Maths.abs(vector7.y) > Maths.abs(vector6.y):
            scale.y_to(Maths.max(scale2.y, vector6.y / vector5.y))
            flag2 = True
        vector5.scale_(scale)
        vector9 = MovementModel.normalize_to_dominant_axis(euler_angles)
        scale3 = max_turn_acceleration_vector.copy()
        vector9.scale_(scale3)
        vector10 = Vector3.sub(vector6, vector5)
        if Maths.abs(vector9.x) > Maths.abs(vector10.x):
            vector9.x_to(vector10.x)
        if Maths.abs(vector9.y) > Maths.abs(vector10.y):
            vector9.y_to(vector10.y)
        if flag:
            vector9.x_to(0.0)
        if flag2:
            vector9.y_to(0.0)
        num2 = max_turn_acceleration_vector.z * roll
        vector5.add_z(num2 * dt)
        ertek = Vector3.add(vector5, Vector3.mult(vector9, dt))
        ertek = MovementModel._clamp(ertek, Vector3.negated(vector3), vector3)
        vector11 = ertek.copy()
        vector12 = forgatas.mult_(vector11)
        euler3_speed = Euler3(vector12.x, vector12.y, vector12.z)
        strafe_speed = MovementModel.step_strafe_speed(prev_frame, options, 0.0, 0.0, dt)
        return MovementFrame(next_position, next_euler, linear_speed, strafe_speed, euler3_speed, 2)

    @staticmethod
    def normalize_to_dominant_axis(vector: Vector3) -> Vector3:
        forras = vector.copy()
        f = Maths.max(Maths.abs(forras.x), Maths.abs(forras.y))
        f = Maths.abs(f)
        if abs(f) < 0.001:
            return forras
        return Vector3(forras.x / f, forras.y / f, 0)

    @staticmethod
    def velocity_for_turn(local_delta_angles: Vector3, damping: Vector3) -> Vector3:
        vector = Vector3()
        szam = Quaternion.euler(local_delta_angles).to_angle_axis(vector)
        almost_rv = Vector3(damping.x * vector.x, damping.y * vector.y, damping.z * vector.z)
        return Vector3.mult(almost_rv, szam)

    @staticmethod
    def keep_vector_components_within_plus_minus_180(vector: Vector3) -> Vector3:
        forras = vector.copy()
        forras.mod(360.0)

        forras.x_to(forras.x if (forras.x <= 180.0) else (forras.x - 360.0))
        forras.x_to(forras.x if (forras.x >= -180.0) else (forras.x + 360.0))
        forras.y_to(forras.y if (forras.y <= 180.0) else (forras.y - 360.0))
        forras.y_to(forras.y if (forras.y >= -180.0) else (forras.y + 360.0))
        forras.z_to(forras.z if (forras.z <= 180.0) else (forras.z - 360.0))
        forras.z_to(forras.z if (forras.z >= -180.0) else (forras.z + 360.0))
        return forras

    @staticmethod
    def damping_for(acceleration: Vector3, maximum_velocity: Vector3) -> Vector3:
        return Vector3(
            fdiv(acceleration.x, maximum_velocity.x),
            fdiv(acceleration.y, maximum_velocity.y),
            fdiv(acceleration.z, maximum_velocity.z),
        )
