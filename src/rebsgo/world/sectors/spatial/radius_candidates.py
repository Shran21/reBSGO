# github.com/Shran21
from __future__ import annotations

from rebsgo.world.sectors.spatial.uniform_grid import UniformGridSpatialIndex


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

    candidate_ids = {space_object.id_in_space() for space_object in jeloltek}
    if always_include is not None:
        candidate_ids.add(always_include.id_in_space())
    return [space_object for space_object in objects if space_object.id_in_space() in candidate_ids]


def nearest_radius_candidate(candidates, center, radius: float, stats: dict | None = None):
    candidates = list(candidates)
    if not candidates:
        return None

    return _nearest_radius_candidate_python(candidates, center, radius, stats)


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

