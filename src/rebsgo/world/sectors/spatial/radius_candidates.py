# github.com/Shran21
from __future__ import annotations

import logging

from rebsgo.world.sectors.spatial.uniform_grid import UniformGridSpatialIndex
from rebsgo.native.hotpath import (
    filter_radius_ids,
    log_native_event,
    nearest_radius_id,
    should_use_native_nearest_radius,
    should_use_native_radius_filter,
)

log = logging.getLogger(__name__)


def build_complete_spatial_index(objects, cell_size: float, max_cells_per_object: int, log=None, context: str = ""):
    try:
        sorszam = UniformGridSpatialIndex(cell_size, max_cells_per_object)
        sorszam.rebuild(objects)
        if sorszam.stats.indexed_objects != len(objects):
            return None
        return sorszam
    except Exception:
        if log is not None:
            log.exception("%s spatial index build failed; falling back to the plain sweep", context or "Radius")
        return None


def ordered_radius_candidates(objects, spatial_index, center, radius: float, always_include=None, stats: dict | None = None):
    if spatial_index is None:
        return objects

    jeloltek = spatial_index.query_radius(center, radius)
    if stats is not None:
        stats["spatial_queries"] = stats.get("spatial_queries", 0) + 1
        stats["spatial_candidates"] = stats.get("spatial_candidates", 0) + len(jeloltek)

    candidate_ids = _candidate_ids_with_native_radius_filter(jeloltek, center, radius, stats)
    if always_include is not None:
        candidate_ids.add(always_include.id_in_space())
    return [space_object for space_object in objects if space_object.id_in_space() in candidate_ids]


def nearest_radius_candidate(candidates, center, radius: float, stats: dict | None = None):
    candidates = list(candidates)
    if not candidates:
        return None

    if should_use_native_nearest_radius(len(candidates)):
        try:
            feljegyzesek = [_position_record(space_object) for space_object in candidates]
            object_id = nearest_radius_id(feljegyzesek, _center_tuple(center), radius)
            if stats is not None:
                stats["native_nearest_queries"] = stats.get("native_nearest_queries", 0) + 1
                stats["native_nearest_candidates"] = stats.get("native_nearest_candidates", 0) + len(candidates)
            log_native_event(
                log,
                "native_nearest_radius_used",
                "Native nearest radius used candidates=%s matched=%s",
                len(candidates),
                1 if object_id is not None else 0,
            )
            if object_id is None:
                return None
            for space_object in candidates:
                if space_object.id_in_space() == object_id:
                    return space_object
            return None
        except Exception:
            if stats is not None:
                stats["native_nearest_fallbacks"] = stats.get("native_nearest_fallbacks", 0) + 1
            log_native_event(
                log,
                "native_nearest_radius_fallback",
                "Native nearest radius failed; falling back to Python nearest scan",
                force=True,
            )

    return _nearest_radius_candidate_python(candidates, center, radius, stats)


def _candidate_ids_with_native_radius_filter(candidates, center, radius: float, stats: dict | None = None) -> set[int]:
    if not candidates or not should_use_native_radius_filter(len(candidates)):
        return {space_object.id_in_space() for space_object in candidates}

    try:
        feljegyzesek = [_position_record(space_object) for space_object in candidates]
        ids = filter_radius_ids(feljegyzesek, _center_tuple(center), radius)
        if stats is not None:
            stats["native_radius_queries"] = stats.get("native_radius_queries", 0) + 1
            stats["native_radius_candidates"] = stats.get("native_radius_candidates", 0) + len(ids)
        log_native_event(
            log,
            "native_radius_filter_used",
            "Native radius filter used candidates=%s radius_matches=%s",
            len(candidates),
            len(ids),
        )
        return set(ids)
    except Exception:
        if stats is not None:
            stats["native_radius_fallbacks"] = stats.get("native_radius_fallbacks", 0) + 1
        log_native_event(
            log,
            "native_radius_filter_fallback",
            "Native radius filter failed; falling back to broadphase candidates",
            force=True,
        )
        return {space_object.id_in_space() for space_object in candidates}


def _nearest_radius_candidate_python(candidates, center, radius: float, stats: dict | None = None):
    radius_sq = radius * radius
    closest = None
    closest_distance_sq = float("inf")
    for space_object in candidates:
        distance_sq = center.sq_distance_to(space_object.mover_of().position_of())
        if stats is not None:
            stats["distance_checks"] = stats.get("distance_checks", 0) + 1
        if distance_sq < closest_distance_sq and distance_sq < radius_sq:
            closest_distance_sq = distance_sq
            closest = space_object
    return closest


def _position_record(space_object) -> tuple[int, float, float, float]:
    helyzet = _candidate_position(space_object)
    return (int(space_object.id_in_space()), float(helyzet.x), float(helyzet.y), float(helyzet.z))


def _center_tuple(center) -> tuple[float, float, float]:
    return (float(center.x), float(center.y), float(center.z))


def _candidate_position(space_object):
    if hasattr(space_object, "mover_of"):
        mover = space_object.mover_of()
        if mover is not None and hasattr(mover, "position_of"):
            return mover.position_of()

    if hasattr(space_object, "collider_of"):
        if (utkozotest := space_object.collider_of()) is not None:
            if hasattr(utkozotest, "center_point"):
                return utkozotest.center_point()
            if hasattr(utkozotest, "world_center"):
                return utkozotest.world_center()
            if hasattr(utkozotest, "transform_of"):
                return utkozotest.transform_of().position_of()

    raise AttributeError("space object has no movement or collider position")
