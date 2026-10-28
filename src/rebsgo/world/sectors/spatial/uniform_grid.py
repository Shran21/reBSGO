# github.com/Shran21

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import combinations

from rebsgo.geometry.primitives.vector3 import Vector3


@dataclass(frozen=True)
class SpatialStats:
    indexed_objects: int
    cells: int
    global_objects: int
    raw_pairs: int
    filtered_pairs: int


@dataclass(frozen=True)
class _Aabb:
    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float

    def overlaps(self, other: "_Aabb") -> bool:
        return (
            self.min_x <= other.max_x and self.max_x >= other.min_x
            and self.min_y <= other.max_y and self.max_y >= other.min_y
            and self.min_z <= other.max_z and self.max_z >= other.min_z
        )


@dataclass(frozen=True)
class _Body:
    space_object: object
    object_id: int
    aabb: _Aabb
    min_cell: tuple[int, int, int]
    max_cell: tuple[int, int, int]


class UniformGridSpatialIndex:
    def __init__(self, cell_size: float, max_cells_per_object: int):
        if cell_size <= 0:
            raise ValueError("cell_size must be positive")
        if max_cells_per_object <= 0:
            raise ValueError("max_cells_per_object must be positive")
        self._cell_size = float(cell_size)
        self._max_cells_per_object = int(max_cells_per_object)
        self._cells: dict[tuple[int, int, int], list[_Body]] = {}
        self._global_bodies: list[_Body] = []
        self._bodies: list[_Body] = []
        self._stats = SpatialStats(0, 0, 0, 0, 0)

    def rebuild(self, objektumok) -> None:
        self._cells.clear()
        self._global_bodies.clear()
        self._bodies.clear()

        for space_object in objektumok:
            body = self._body_for_object(space_object)
            if body is None:
                continue

            self._bodies.append(body)
            cell_count = self._cell_count(body)
            if cell_count > self._max_cells_per_object:
                self._global_bodies.append(body)
                continue

            for cell in self._iter_cells(body):
                self._cells.setdefault(cell, []).append(body)

        self._stats = SpatialStats(len(self._bodies), len(self._cells), len(self._global_bodies), 0, 0)

    def pairs(self, needs_pair) -> tuple[list[tuple[object, object]], SpatialStats]:
        return self._pairs_python(needs_pair)

    def _pairs_python(self, needs_pair) -> tuple[list[tuple[object, object]], SpatialStats]:
        raw_pairs = 0
        filtered_pairs: list[tuple[object, object]] = []
        latott: set[tuple[int, int]] = set()

        for bodies in self._cells.values():
            if len(bodies) < 2:
                continue
            for elso, second in combinations(bodies, 2):
                raw_pairs += self._append_if_pair(elso, second, latott, needs_pair, filtered_pairs)

        if self._global_bodies:
            for elso, second in combinations(self._global_bodies, 2):
                raw_pairs += self._append_if_pair(elso, second, latott, needs_pair, filtered_pairs)
            for global_body in self._global_bodies:
                for body in self._bodies:
                    if global_body is body:
                        continue
                    raw_pairs += self._append_if_pair(global_body, body, latott, needs_pair, filtered_pairs)

        self._stats = SpatialStats(
            self._stats.indexed_objects,
            self._stats.cells,
            self._stats.global_objects,
            raw_pairs,
            len(filtered_pairs),
        )
        return filtered_pairs, self._stats

    def query_overlaps(self, space_object, needs_pair) -> list[object]:
        query_body = self._body_for_object(space_object)
        if query_body is None:
            return []

        eredmenyek = []
        latott: set[int] = set()
        if self._cell_count(query_body) > self._max_cells_per_object:
            jeloltek = self._bodies
        else:
            jeloltek = []
            for cell in self._iter_cells(query_body):
                jeloltek.extend(self._cells.get(cell, ()))
            jeloltek.extend(self._global_bodies)

        for jelolt in jeloltek:
            if jelolt.object_id == query_body.object_id or jelolt.object_id in latott:
                continue
            latott.add(jelolt.object_id)
            if not query_body.aabb.overlaps(jelolt.aabb):
                continue
            candidate_object = jelolt.space_object
            if needs_pair(space_object, candidate_object):
                eredmenyek.append(candidate_object)
        return eredmenyek

    def query_radius(self, center: Vector3, radius: float, predicate=None) -> list[object]:
        query_aabb = self._aabb_from_center_radius(center, float(radius))
        min_cell = self._cell_for(query_aabb.min_x, query_aabb.min_y, query_aabb.min_z)
        max_cell = self._cell_for(query_aabb.max_x, query_aabb.max_y, query_aabb.max_z)
        query_cell_count = (
            (max_cell[0] - min_cell[0] + 1)
            * (max_cell[1] - min_cell[1] + 1)
            * (max_cell[2] - min_cell[2] + 1)
        )
        if query_cell_count > self._max_cells_per_object:
            jeloltek = self._bodies
        else:
            jeloltek = []
            for x in range(min_cell[0], max_cell[0] + 1):
                for y in range(min_cell[1], max_cell[1] + 1):
                    for z in range(min_cell[2], max_cell[2] + 1):
                        jeloltek.extend(self._cells.get((x, y, z), ()))
            jeloltek.extend(self._global_bodies)

        eredmenyek = []
        latott: set[int] = set()
        for jelolt in jeloltek:
            if jelolt.object_id in latott:
                continue
            latott.add(jelolt.object_id)
            if not query_aabb.overlaps(jelolt.aabb):
                continue
            candidate_object = jelolt.space_object
            if predicate is None or predicate(candidate_object):
                eredmenyek.append(candidate_object)
        return eredmenyek

    @property
    def stats(self) -> SpatialStats:
        return self._stats

    @staticmethod
    def _append_if_pair(first: _Body, second: _Body, seen: set[tuple[int, int]], needs_pair, pairs) -> int:
        if first.object_id == second.object_id:
            return 0
        pair_key = (first.object_id, second.object_id)
        if pair_key[0] > pair_key[1]:
            pair_key = (pair_key[1], pair_key[0])
        if pair_key in seen:
            return 0
        seen.add(pair_key)

        if not first.aabb.overlaps(second.aabb):
            return 1

        first_object = first.space_object
        second_object = second.space_object
        if needs_pair(first_object, second_object):
            pairs.append((first_object, second_object))
        return 1

    def _body_for_object(self, space_object) -> _Body | None:
        utkozotest = space_object.collider_of()
        if utkozotest is None:
            return None

        aabb = self._aabb_for_collider(utkozotest)
        if aabb is None:
            return None

        return _Body(
            space_object,
            int(space_object.id_in_space()),
            aabb,
            self._cell_for(aabb.min_x, aabb.min_y, aabb.min_z),
            self._cell_for(aabb.max_x, aabb.max_y, aabb.max_z),
        )

    @staticmethod
    def _aabb_for_collider(collider) -> _Aabb | None:
        if hasattr(collider, "center_point") and hasattr(collider, "radius_of"):
            return UniformGridSpatialIndex._aabb_from_center_radius(
                collider.center_point(), float(collider.radius_of()))

        if (hasattr(collider, "end_a") and hasattr(collider, "end_b")
            and hasattr(collider, "radius_of")):
            a, b = collider.end_a(), collider.end_b()
            sugar = float(collider.radius_of())
            return _Aabb(min(a.x, b.x) - sugar, min(a.y, b.y) - sugar, min(a.z, b.z) - sugar,
                         max(a.x, b.x) + sugar, max(a.y, b.y) + sugar, max(a.z, b.z) + sugar)

        if (hasattr(collider, "world_center") and hasattr(collider, "half_extents_of")
            and hasattr(collider, "axis_right") and hasattr(collider, "axis_up")
            and hasattr(collider, "axis_forward")):
            kozeppont = collider.world_center()
            half = collider.half_extents_of()
            tengelyek = (collider.axis_right(), collider.axis_up(),
                         collider.axis_forward())
            nyulas = [sum(abs(getattr(t, irany)) * felt
                          for t, felt in zip(tengelyek, (half.x, half.y, half.z)))
                      for irany in ("x", "y", "z")]
            return _Aabb(kozeppont.x - nyulas[0], kozeppont.y - nyulas[1], kozeppont.z - nyulas[2],
                         kozeppont.x + nyulas[0], kozeppont.y + nyulas[1], kozeppont.z + nyulas[2])

        if not hasattr(collider, "transform_of"):
            return None
        sugar = (float(collider.cover_radius())
                 if hasattr(collider, "cover_radius") else 0.0)
        return UniformGridSpatialIndex._aabb_from_center_radius(
            collider.transform_of().position_of(), sugar)

    @staticmethod
    def _aabb_from_center_radius(center: Vector3, radius: float) -> _Aabb:
        return _Aabb(
            center.x - radius,
            center.y - radius,
            center.z - radius,
            center.x + radius,
            center.y + radius,
            center.z + radius,
        )

    def _cell_for(self, x: float, y: float, z: float) -> tuple[int, int, int]:
        return (
            math.floor(x / self._cell_size),
            math.floor(y / self._cell_size),
            math.floor(z / self._cell_size),
        )

    @staticmethod
    def _cell_count(body: _Body) -> int:
        return (
            (body.max_cell[0] - body.min_cell[0] + 1)
            * (body.max_cell[1] - body.min_cell[1] + 1)
            * (body.max_cell[2] - body.min_cell[2] + 1)
        )

    @staticmethod
    def _iter_cells(body: _Body):
        for x in range(body.min_cell[0], body.max_cell[0] + 1):
            for y in range(body.min_cell[1], body.max_cell[1] + 1):
                for z in range(body.min_cell[2], body.max_cell[2] + 1):
                    yield x, y, z

