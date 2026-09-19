# github.com/Shran21
from __future__ import annotations

from rebsgo.helpers.floats import f32


class DradisChange:
    def __init__(self, time: int, detection_visual_radius: float, detection_inner_radius: float,
                 detection_outer_radius: float):
        self._time = time
        self._detection_visual_radius = f32(detection_visual_radius)
        self._detection_inner_radius = f32(detection_inner_radius)
        self._detection_outer_radius = f32(detection_outer_radius)

    def time(self) -> int:
        return self._time

    @property
    def detection_visual_radius(self) -> float:
        return self._detection_visual_radius

    @property
    def detection_inner_radius(self) -> float:
        return self._detection_inner_radius

    @property
    def detection_outer_radius(self) -> float:
        return self._detection_outer_radius

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not isinstance(other, DradisChange):
            return False
        return (self._time == other._time and self._detection_visual_radius == other._detection_visual_radius
                and self._detection_inner_radius == other._detection_inner_radius
                and self._detection_outer_radius == other._detection_outer_radius)

    def __hash__(self) -> int:
        return hash((self._time, self._detection_visual_radius, self._detection_inner_radius,
                     self._detection_outer_radius))

    def __repr__(self) -> str:
        return (f'<dradis at {self._time}: visual {self._detection_visual_radius},'
                f' inner {self._detection_inner_radius},'
                f' outer {self._detection_outer_radius}>')
