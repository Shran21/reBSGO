# github.com/Shran21

from __future__ import annotations

from rebsgo.helpers.locks import ReentrantLock
from rebsgo.helpers.log_tags import tag
from rebsgo.world.movement.maneuvers import RestManeuver, PulseManeuver
from rebsgo.world.movement.mover import Mover
from rebsgo.world.movement.motion_snapshot import MovementFrame
from rebsgo.geometry.primitives.euler3 import Euler3
from rebsgo.helpers.floats import f32


class FixedMover(Mover):
    def __init__(self, transform):
        super().__init__(transform)
        self.queue_maneuver(RestManeuver(self.position_of(), Euler3.from_quaternion(self.rotation_of())))

    def move(self, tick, dt: float) -> None:
        if self.maneuver is None:
            if (kovetkezo := self.next_maneuver_unsafe) is not None:
                self.maneuver = kovetkezo
                self.maneuver.start_at(tick)
        if self.maneuver.start_tick is None:
            self.maneuver.start_at(tick)
        self.frame_tick = tick
        if self.movement_options_needs_update:
            self._is_new_maneuver = True
            self.movement_options_needs_update = False
            self.maneuver.start_at(tick)

    @property
    def last_frame(self) -> MovementFrame:
        return self.frame

    def frame_at_tick(self, ora_allas) -> MovementFrame:
        return self.frame


class FreeMover(Mover):
    def __init__(self, transform, movement_card):
        super().__init__(transform)
        self.movement_card = movement_card
        self._is_new_maneuver = False
        self._last_frame = None
        self.advance_frame = None

    def move(self, tick, dt: float) -> None:
        next_maneuver = self.queued_maneuver()
        if next_maneuver is None and self.maneuver is None:
            raise RuntimeError('movement without any maneuver')

        if next_maneuver is not None:
            self.forget_queued_maneuver()

            next_maneuver.movement_options = self.movement_options
            self.maneuver = next_maneuver
            self.maneuver.start_at(tick)
            self._is_new_maneuver = True
            self.movement_options_needs_update = False
        if self.movement_options_needs_update:
            self.movement_options_needs_update = False
            self._is_new_maneuver = True
            self.maneuver.start_at(tick)
            self.maneuver.movement_options = self.movement_options
            if isinstance(self.maneuver, PulseManeuver):
                self.maneuver.direction.copy_from(self.frame.linear_speed)

        self.frame_tick = tick
        self._last_frame = self.frame
        if next_maneuver is None and self.advance_frame is not None:
            self.frame = self.advance_frame
        else:
            self.frame = self.maneuver.advance_frame(tick, self._last_frame.full_copy, dt)
        self.advance_frame = None

        self.transform.set_position_rotation(self.frame.position_of(), self.frame.rotation_of())

    def take_movement_stats(self, arg) -> None:
        super().take_movement_stats(arg)
        self.movement_options.fold_in_card(self.movement_card)

    @property
    def is_moving_object(self) -> bool:
        return True

    TICK_MASODPERC = 0.1

    def frame_at_tick(self, ora_allas) -> MovementFrame:
        tavolsag = self.frame_tick.value - ora_allas.value
        if tavolsag == 0:
            return self.frame
        if tavolsag == -1:
            return self._last_frame
        if tavolsag == 1:
            self.advance_frame = self.maneuver.advance_frame(
                ora_allas, self.frame, f32(FreeMover.TICK_MASODPERC))
            return self.advance_frame

        elteres = f32(tavolsag * f32(FreeMover.TICK_MASODPERC))
        return MovementFrame(self.frame.future_position(elteres),
                             self.frame.future_euler3(elteres),
                             self.frame.linear_speed, self.frame.strafe_speed,
                             self.frame.euler3_speed, self.frame.mode, True)

    @property
    def last_frame(self) -> MovementFrame:
        return self._last_frame


class PilotMover(FreeMover):
    def __init__(self, transform, movement_card, user_id: int):
        super().__init__(transform, movement_card)
        self.lock = ReentrantLock()
        tag("userID", str(user_id))
        self.user_id = user_id

    @property
    def frissites_alatt(self):
        return self.lock

    def move(self, tick, dt: float) -> None:
        super().move(tick, dt)
