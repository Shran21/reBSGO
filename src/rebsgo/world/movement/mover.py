# github.com/Shran21
from __future__ import annotations

import contextlib
from abc import ABC, abstractmethod
from collections import deque
from threading import Lock

from rebsgo.world.movement.motion_snapshot import MovementFrame
from rebsgo.world.movement.movement_limits import MovementLimits
from rebsgo.vocabulary.pilot import Gear
from rebsgo.vocabulary.combat import ManeuverKind
from rebsgo.geometry.primitives.euler3 import Euler3
from rebsgo.gamedata.reading import ObjectStat, ObjectStats


class Mover(ABC):
    def __init__(self, transform):
        self.transform = transform

        self.frame = MovementFrame(self.position_of(), Euler3.from_quaternion(self.rotation_of()))

        self.next_maneuver_queue = deque()
        self._queue_lock = Lock()
        self._is_new_maneuver = False
        self.movement_options = MovementLimits()
        self.movement_options.watch_updates(self)
        self.movement_options_needs_update = False

        self.maneuver = None
        self.next_maneuver = None
        self.next_pulse_maneuver = None

        self.frame_tick = None
        self.last_collision_tick = None
        self.last_movement_update_tick = None


    def position_of(self):
        return self.transform.position_of()

    def rotation_of(self):
        return self.transform.rotation_of()

    def transform_of(self):
        return self.transform

    def place_at(self, kiindulo_helyzet) -> None:
        self.transform.place_at(kiindulo_helyzet)
        self.frame = MovementFrame(kiindulo_helyzet.position_of(), kiindulo_helyzet.rotation_euler3)
        self.flag_movement_dirty()

    @property
    def is_moving_object(self) -> bool:
        return False


    @abstractmethod
    def move(self, tick, dt: float) -> None:
        ...

    def refresh_movement(self) -> None:
        self.flag_movement_dirty()

    @property
    def frissites_alatt(self):
        return contextlib.nullcontext()

    def flag_movement_dirty(self) -> None:
        with self.frissites_alatt:
            self.movement_options_needs_update = True

    def note_movement_tick(self, utolso_mozgas_ora) -> None:
        self.last_movement_update_tick = utolso_mozgas_ora

    def note_collision_tick(self, utolso_utkozes_ora) -> None:
        self.last_collision_tick = utolso_utkozes_ora


    @property
    def current_maneuver(self):
        if self.maneuver is None:
            if (next_maneuver := self.queued_maneuver()) is not None:
                return next_maneuver
        return self.maneuver

    def is_new_maneuver(self) -> bool:
        return self._is_new_maneuver

    def mark_maneuver_fresh(self, value: bool) -> None:
        with self.frissites_alatt:
            self._is_new_maneuver = value


    def queue_maneuver(self, next_maneuver) -> None:
        if next_maneuver is None:
            raise TypeError('the next maneuver is required')
        with self.frissites_alatt:
            if next_maneuver.maneuver_type == ManeuverKind.Pulse:
                self.next_pulse_maneuver = next_maneuver
                self._offer(next_maneuver)
            elif next_maneuver.maneuver_type == ManeuverKind.Teleport:
                self._offer(next_maneuver)
            else:
                self.next_maneuver = next_maneuver
            self.movement_options_needs_update = True

    def queued_maneuver(self):
        if self.next_pulse_maneuver is not None:
            return self.next_pulse_maneuver
        if (next_maneuver_item := self._poll()) is not None:
            return next_maneuver_item
        return self.next_maneuver

    @property
    def has_next_maneuver(self) -> bool:
        return self.next_maneuver_unsafe is not None

    @property
    def next_maneuver_unsafe(self):
        if self.next_pulse_maneuver is not None:
            return self.next_pulse_maneuver
        return self.next_maneuver

    def forget_queued_maneuver(self) -> None:
        if self.next_pulse_maneuver is not None:
            self.next_pulse_maneuver = None
        elif self.next_maneuver is not None:
            self.next_maneuver = None

    def _offer(self, maneuver) -> None:
        with self._queue_lock:
            self.next_maneuver_queue.append(maneuver)

    def _poll(self):
        with self._queue_lock:
            if self.next_maneuver_queue:
                return self.next_maneuver_queue.popleft()
            return None


    @property
    @abstractmethod
    def last_frame(self) -> MovementFrame:
        ...

    _MOZGAS_HATARAI = (
        ("inertia_compensation", ObjectStat.InertiaCompensation),
        ("pitch_acceleration", ObjectStat.PitchAcceleration),
        ("pitch_max_speed", ObjectStat.PitchMaxSpeed),
        ("yaw_acceleration", ObjectStat.YawAcceleration),
        ("yaw_max_speed", ObjectStat.YawMaxSpeed),
        ("roll_acceleration", ObjectStat.RollAcceleration),
        ("roll_max_speed", ObjectStat.RollMaxSpeed),
        ("strafe_acceleration", ObjectStat.StrafeAcceleration),
        ("strafe_max_speed", ObjectStat.StrafeMaxSpeed),
    )

    _SEBESSEG_FORRASA = {
        Gear.Boost: ObjectStat.BoostSpeed,
        Gear.None_: ObjectStat.Speed,
    }

    @abstractmethod
    def frame_at_tick(self, ora_allas) -> MovementFrame:
        ...


    def take_movement_stats(self, arg) -> None:
        if self.movement_options is None:
            raise TypeError('movement limits are required')
        if arg is None:
            raise TypeError('object stats are required')
        mutatok = arg if isinstance(arg, ObjectStats) else arg.stats_of
        hatarok = self.movement_options

        fokozat = hatarok.gear_of
        if fokozat == Gear.Regular:
            hatarok.set_speed(hatarok.throttle_speed)
        elif fokozat in Mover._SEBESSEG_FORRASA:
            hatarok.set_speed(mutatok.stat(Mover._SEBESSEG_FORRASA[fokozat]))

        gyorsulas = mutatok.stat_or_default(ObjectStat.Acceleration)
        if fokozat == Gear.Boost and mutatok.holds_stat(ObjectStat.AccelerationMultiplierOnBoost):
            gyorsulas *= mutatok.stat(ObjectStat.AccelerationMultiplierOnBoost)
        hatarok.accelerate_at(gyorsulas)

        for hatar, mutato in Mover._MOZGAS_HATARAI:
            setattr(hatarok, hatar, mutatok.stat_or_default(mutato))


    def __str__(self) -> str:
        soron = ' -> '.join(str(m) for m in
                        (self.maneuver, self.next_maneuver, self.next_pulse_maneuver) if m)
        return (f'<mover at {self.transform}, frame {self.frame} @{self.frame_tick};'
                f' flying {soron or "nothing"}'
                f'{" (fresh)" if self._is_new_maneuver else ""};'
                f' limits {self.movement_options}'
                f'{" (stale)" if self.movement_options_needs_update else ""};'
                f' last bump {self.last_collision_tick}>')
