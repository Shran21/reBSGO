# github.com/Shran21

from __future__ import annotations

from enum import Enum
from rebsgo.geometry.primitives.euler3 import Euler3
from rebsgo.geometry.primitives.vector3 import Vector3
from rebsgo.helpers.floats import f32
from rebsgo.helpers.inheriting import csak_orokosen_at


class NpcGoal:
    def __init__(self, type_, priority: int):
        csak_orokosen_at(self, NpcGoal)
        self._type = type_
        self._priority = priority

    def outranks(self, other: "NpcGoal") -> bool:
        return self._priority < other._priority

    @property
    def type(self):
        return self._type

    @property
    def priority(self) -> int:
        return self._priority


class NpcGoalKind(Enum):
    Kill = 0
    Defend = 1
    Patrol = 2


class KillGoal(NpcGoal):
    def __init__(self, priority: int, kiirtandok):
        super().__init__(NpcGoalKind.Kill, priority)
        self._objectives_to_kill = kiirtandok

    @property
    def objectives_to_kill(self):
        return self._objectives_to_kill


class DefendGoal(NpcGoal):
    def __init__(self, priority: int, vedendok):
        super().__init__(NpcGoalKind.Defend, priority)
        self._objectives_to_defend = vedendok

    @property
    def objectives_to_defend(self):
        return self._objectives_to_defend


class PatrolGoal(NpcGoal):
    def __init__(self, priority: int, jaror_doboz):
        super().__init__(NpcGoalKind.Patrol, priority)
        self._box_to_patrol_in = jaror_doboz

    def within_box(self, sajat_hely: Vector3) -> bool:
        return self._box_to_patrol_in.vector_within(sajat_hely)

    def direction_to_center(self, from_v: Vector3) -> Euler3:
        return Euler3.direction(Vector3.sub(self._box_to_patrol_in.center, from_v))

    @property
    def box_to_patrol_in(self):
        return self._box_to_patrol_in


class Route:
    def __init__(self, way_points, utpont_tavolsag: float):
        if way_points is None:
            raise TypeError('a patrol needs its waypoints')
        if len(way_points) < 1:
            raise ValueError('at least one waypoint is needed')
        self._min_distance_to_way_point = f32(utpont_tavolsag)
        self._way_points = way_points
        self._current_way_point = way_points[0]
        self._current_index = 0

    def step_to_next_point(self) -> None:
        if not self.is_finished:
            self._current_index += 1
            self._current_way_point = self._way_points[self._current_index]

    @property
    def is_finished(self) -> bool:
        return self._current_index == len(self._way_points) - 1

    def reached_way_point(self, mostani_hely: Vector3) -> bool:
        return self._current_way_point.within_reach(mostani_hely)

    def advance_when_arrived(self, mostani_hely: Vector3) -> bool:
        within_reach = self.reached_way_point(mostani_hely)
        if within_reach:
            self.step_to_next_point()
        return within_reach
