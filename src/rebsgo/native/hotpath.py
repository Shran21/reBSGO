# github.com/Shran21
from __future__ import annotations

import logging
import struct
from collections.abc import Iterable, Sequence

from rebsgo.config.config import Config
from rebsgo.helpers.floats import f32

log = logging.getLogger(__name__)
_CONFIG = Config.instance()

_RUST_ENABLED = _CONFIG.bool("rebsgo.native.rust.enabled", True)
_RADIUS_FILTER_ENABLED = _CONFIG.bool("rebsgo.native.rust.radius-filter.enabled", True)
_RADIUS_FILTER_MIN_RECORDS = _CONFIG.int("rebsgo.native.rust.radius-filter.min-records", 32)
_NEAREST_RADIUS_ENABLED = _CONFIG.bool("rebsgo.native.rust.nearest-radius.enabled", True)
_NEAREST_RADIUS_MIN_RECORDS = _CONFIG.int(
    "rebsgo.native.rust.nearest-radius.min-records", _RADIUS_FILTER_MIN_RECORDS)
_OUT_OF_BOUNDS_ENABLED = _CONFIG.bool("rebsgo.native.rust.out-of-bounds.enabled", True)
_OUT_OF_BOUNDS_MIN_RECORDS = _CONFIG.int("rebsgo.native.rust.out-of-bounds.min-records", 32)
_RELATION_PREFILTER_ENABLED = _CONFIG.bool("rebsgo.native.rust.stance-prefilter.enabled", True)
_RELATION_PREFILTER_MIN_RECORDS = _CONFIG.int("rebsgo.native.rust.stance-prefilter.min-records", 32)
_SPATIAL_AABB_FILTER_ENABLED = _CONFIG.bool("rebsgo.native.rust.spatial-aabb-filter.enabled", True)
_SPATIAL_PAIR_GENERATION_ENABLED = _CONFIG.bool("rebsgo.native.rust.spatial-pair-generation.enabled", True)
_SPATIAL_MIN_RECORDS = _CONFIG.int("rebsgo.native.rust.spatial.min-records", 32)
_SPHERE_PAIR_FILTER_ENABLED = _CONFIG.bool("rebsgo.native.rust.sphere-pair-filter.enabled", True)
_SPHERE_PAIR_MIN_RECORDS = _CONFIG.int("rebsgo.native.rust.sphere-pair-filter.min-records", 16)
_RANGE_DISTANCE_ENABLED = _CONFIG.bool("rebsgo.native.rust.range-distance.enabled", True)
_RANGE_DISTANCE_MIN_RECORDS = _CONFIG.int("rebsgo.native.rust.range-distance.min-records", 32)
_FUTURE_POSITIONS_ENABLED = _CONFIG.bool("rebsgo.native.rust.future-positions.enabled", True)
_FUTURE_POSITIONS_MIN_RECORDS = _CONFIG.int("rebsgo.native.rust.future-positions.min-records", 64)
_PACKET_SERIALIZATION_ENABLED = _CONFIG.bool("rebsgo.native.rust.packet-serialization.enabled", True)
_DIAGNOSTICS_ENABLED = _CONFIG.bool("rebsgo.native.rust.diagnostics.enabled", False)
_DIAGNOSTICS_SAMPLE_INTERVAL = _CONFIG.int("rebsgo.native.rust.diagnostics.sample-interval", 1000)
_IMPORT_ERROR: Exception | None = None
_native = None
_LOG_COUNTS: dict[str, int] = {}


def _load_native():
    import importlib.util
    import sysconfig
    from pathlib import Path

    built = Path(__file__).resolve().parents[3] / "native" / "lib"
    suffixes = sysconfig.get_config_var("EXT_SUFFIX") or ".so"
    for jelolt in sorted(built.glob(f"rebsgo_native*{suffixes}")):
        spec = importlib.util.spec_from_file_location("rebsgo_native", jelolt)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        log.info("Native hotpaths loaded from the project: %s", jelolt)
        return module

    import rebsgo_native as installed
    return installed


if _RUST_ENABLED:
    try:
        _native = _load_native()
    except Exception as exc:  # pragma: no cover - environment dependent
        _IMPORT_ERROR = exc
        _native = None

if _DIAGNOSTICS_ENABLED:
    if _native is None:
        log.warning(
            "Native Rust hotpaths unavailable rust_enabled=%s import_error=%r",
            _RUST_ENABLED,
            _IMPORT_ERROR,
        )
    else:
        log.info(
            "Native Rust hotpaths available radius_min_records=%s spatial_min_records=%s",
            _RADIUS_FILTER_MIN_RECORDS,
            _SPATIAL_MIN_RECORDS,
        )


def is_native_available() -> bool:
    return _native is not None


def is_native_radius_filter_enabled() -> bool:
    return _RUST_ENABLED and _RADIUS_FILTER_ENABLED and is_native_available()


def should_use_native_radius_filter(record_count: int) -> bool:
    return is_native_radius_filter_enabled() and record_count >= _RADIUS_FILTER_MIN_RECORDS


def should_use_native_nearest_radius(record_count: int) -> bool:
    return (
        _RUST_ENABLED
        and _NEAREST_RADIUS_ENABLED
        and is_native_available()
        and record_count >= _NEAREST_RADIUS_MIN_RECORDS
        and hasattr(_native, "nearest_radius_id")
    )


def should_use_native_out_of_bounds_filter(record_count: int) -> bool:
    return (
        _RUST_ENABLED
        and _OUT_OF_BOUNDS_ENABLED
        and is_native_available()
        and record_count >= _OUT_OF_BOUNDS_MIN_RECORDS
        and hasattr(_native, "filter_out_of_bounds_ids")
    )


def should_use_native_relation_prefilter(record_count: int) -> bool:
    return (
        _RUST_ENABLED
        and _RELATION_PREFILTER_ENABLED
        and is_native_available()
        and record_count >= _RELATION_PREFILTER_MIN_RECORDS
        and hasattr(_native, "filter_possible_enemy_ids")
    )


def should_use_native_spatial_filter(record_count: int) -> bool:
    return (
        _RUST_ENABLED
        and _SPATIAL_AABB_FILTER_ENABLED
        and is_native_available()
        and record_count >= _SPATIAL_MIN_RECORDS
    )


def should_use_native_spatial_pair_generation(record_count: int) -> bool:
    return (
        _RUST_ENABLED
        and _SPATIAL_PAIR_GENERATION_ENABLED
        and is_native_available()
        and record_count >= _SPATIAL_MIN_RECORDS
    )


def should_use_native_sphere_pair_filter(record_count: int) -> bool:
    return (
        _RUST_ENABLED
        and _SPHERE_PAIR_FILTER_ENABLED
        and is_native_available()
        and record_count >= _SPHERE_PAIR_MIN_RECORDS
        and hasattr(_native, "filter_sphere_pair_indices")
    )


def should_use_native_range_distance(record_count: int) -> bool:
    return (
        _RUST_ENABLED
        and _RANGE_DISTANCE_ENABLED
        and is_native_available()
        and record_count >= _RANGE_DISTANCE_MIN_RECORDS
        and hasattr(_native, "filter_range_distance_sq")
    )


def should_use_native_future_positions(record_count: int) -> bool:
    return (
        _RUST_ENABLED
        and _FUTURE_POSITIONS_ENABLED
        and is_native_available()
        and record_count >= _FUTURE_POSITIONS_MIN_RECORDS
        and hasattr(_native, "future_positions")
    )


def should_use_native_packet_serialization() -> bool:
    return (
        _RUST_ENABLED
        and _PACKET_SERIALIZATION_ENABLED
        and is_native_available()
    )


def native_diagnostics_enabled() -> bool:
    return _DIAGNOSTICS_ENABLED


def log_native_event(logger: logging.Logger, event: str, message: str, *args, force: bool = False) -> None:
    if not _DIAGNOSTICS_ENABLED:
        return

    darab = _LOG_COUNTS.get(event, 0) + 1
    _LOG_COUNTS[event] = darab
    sample_interval = max(0, int(_DIAGNOSTICS_SAMPLE_INTERVAL))
    if not force and darab != 1 and (sample_interval <= 0 or darab % sample_interval != 0):
        return

    logger.info(message + " native_event=%s native_event_count=%s", *args, event, darab)


def _log_native_fallback(event: str, message: str, *args) -> None:
    darab = _LOG_COUNTS.get(event, 0) + 1
    _LOG_COUNTS[event] = darab
    if darab == 1 or (_DIAGNOSTICS_ENABLED and _DIAGNOSTICS_SAMPLE_INTERVAL > 0
                      and darab % _DIAGNOSTICS_SAMPLE_INTERVAL == 0):
        log.exception('%s native_event=%%s native_event_count=%%s', message, *args, event, darab)


def native_status() -> dict[str, object]:
    return {
        "rust_enabled": _RUST_ENABLED,
        "radius_filter_enabled": _RADIUS_FILTER_ENABLED,
        "radius_filter_min_records": _RADIUS_FILTER_MIN_RECORDS,
        "nearest_radius_enabled": _NEAREST_RADIUS_ENABLED,
        "nearest_radius_min_records": _NEAREST_RADIUS_MIN_RECORDS,
        "out_of_bounds_enabled": _OUT_OF_BOUNDS_ENABLED,
        "out_of_bounds_min_records": _OUT_OF_BOUNDS_MIN_RECORDS,
        "relation_prefilter_enabled": _RELATION_PREFILTER_ENABLED,
        "relation_prefilter_min_records": _RELATION_PREFILTER_MIN_RECORDS,
        "spatial_aabb_filter_enabled": _SPATIAL_AABB_FILTER_ENABLED,
        "spatial_pair_generation_enabled": _SPATIAL_PAIR_GENERATION_ENABLED,
        "spatial_min_records": _SPATIAL_MIN_RECORDS,
        "sphere_pair_filter_enabled": _SPHERE_PAIR_FILTER_ENABLED,
        "sphere_pair_min_records": _SPHERE_PAIR_MIN_RECORDS,
        "range_distance_enabled": _RANGE_DISTANCE_ENABLED,
        "range_distance_min_records": _RANGE_DISTANCE_MIN_RECORDS,
        "future_positions_enabled": _FUTURE_POSITIONS_ENABLED,
        "future_positions_min_records": _FUTURE_POSITIONS_MIN_RECORDS,
        "packet_serialization_enabled": _PACKET_SERIALIZATION_ENABLED,
        "diagnostics_enabled": _DIAGNOSTICS_ENABLED,
        "diagnostics_sample_interval": _DIAGNOSTICS_SAMPLE_INTERVAL,
        "available": is_native_available(),
        "loaded_from": getattr(_native, "__file__", None),
        "import_error": None if _IMPORT_ERROR is None else repr(_IMPORT_ERROR),
    }


def filter_radius_ids(
    records: Iterable[Sequence[float | int]],
    center: Sequence[float],
    radius: float,
    always_include_id: int | None = None,
) -> list[int]:
    materialized = [
        (int(feljegyzes[0]), float(feljegyzes[1]), float(feljegyzes[2]), float(feljegyzes[3]))
        for feljegyzes in records
    ]
    center_tuple = (float(center[0]), float(center[1]), float(center[2]))

    if should_use_native_radius_filter(len(materialized)):
        return list(_native.filter_radius_ids(materialized, center_tuple, float(radius), always_include_id))

    return _filter_radius_ids_python(materialized, center_tuple, float(radius), always_include_id)


def nearest_radius_id(
    records: Iterable[Sequence[float | int]],
    center: Sequence[float],
    radius: float,
) -> int | None:
    materialized = [
        (int(feljegyzes[0]), float(feljegyzes[1]), float(feljegyzes[2]), float(feljegyzes[3]))
        for feljegyzes in records
    ]
    center_tuple = (float(center[0]), float(center[1]), float(center[2]))

    if should_use_native_nearest_radius(len(materialized)):
        eredmeny = _native.nearest_radius_id(materialized, center_tuple, float(radius))
        return None if eredmeny is None else int(eredmeny)

    return _nearest_radius_id_python(materialized, center_tuple, float(radius))


def filter_out_of_bounds_ids(
    records: Iterable[Sequence[float | int]],
    limit: float,
) -> list[int]:
    materialized = [
        (int(feljegyzes[0]), float(feljegyzes[1]), float(feljegyzes[2]), float(feljegyzes[3]))
        for feljegyzes in records
    ]
    if should_use_native_out_of_bounds_filter(len(materialized)):
        return [int(object_id) for object_id in _native.filter_out_of_bounds_ids(materialized, float(limit))]
    return _filter_out_of_bounds_ids_python(materialized, float(limit))


def filter_possible_enemy_ids(
    records: Iterable[Sequence[int]],
    against_id: int,
    against_faction: int,
    against_group: int,
    all_enemy: bool,
) -> list[int]:
    materialized = [
        (int(feljegyzes[0]), int(feljegyzes[1]), int(feljegyzes[2]))
        for feljegyzes in records
    ]
    if should_use_native_relation_prefilter(len(materialized)):
        try:
            return [
                int(object_id)
                for object_id in _native.filter_possible_enemy_ids(
                    materialized,
                    int(against_id),
                    int(against_faction),
                    int(against_group),
                    bool(all_enemy),
                )
            ]
        except Exception:
            _log_native_fallback(
                "native_relation_prefilter_failed",
                "Native relation prefilter failed; falling back to Python records=%s",
                len(materialized),
            )
    return _filter_possible_enemy_ids_python(
        materialized, int(against_id), int(against_faction), int(against_group), bool(all_enemy))


def filter_range_distance_sq(
    records: Iterable[Sequence[float | int]],
    center: Sequence[float],
    min_radius: float,
    max_radius: float,
    include_min: bool = True,
    include_max: bool = True,
) -> list[tuple[int, float]]:
    materialized = [
        (int(feljegyzes[0]), float(feljegyzes[1]), float(feljegyzes[2]), float(feljegyzes[3]))
        for feljegyzes in records
    ]
    center_tuple = (float(center[0]), float(center[1]), float(center[2]))

    if should_use_native_range_distance(len(materialized)):
        try:
            return [
                (int(object_id), float(distance_sq))
                for object_id, distance_sq in _native.filter_range_distance_sq(
                    materialized,
                    center_tuple,
                    float(min_radius),
                    float(max_radius),
                    bool(include_min),
                    bool(include_max),
                )
            ]
        except Exception:
            _log_native_fallback(
                "native_range_distance_failed",
                "Native range-distance filter failed; falling back to Python records=%s",
                len(materialized),
            )

    return _filter_range_distance_sq_python(
        materialized,
        center_tuple,
        float(min_radius),
        float(max_radius),
        bool(include_min),
        bool(include_max),
    )


def future_positions(
    records: Iterable[Sequence[float | int]],
    dt: float,
) -> list[tuple[int, float, float, float]]:
    materialized = [
        (
            int(feljegyzes[0]),
            float(feljegyzes[1]),
            float(feljegyzes[2]),
            float(feljegyzes[3]),
            float(feljegyzes[4]),
            float(feljegyzes[5]),
            float(feljegyzes[6]),
            float(feljegyzes[7]),
            float(feljegyzes[8]),
            float(feljegyzes[9]),
        )
        for feljegyzes in records
    ]

    if should_use_native_future_positions(len(materialized)):
        try:
            return [
                (int(object_id), float(x), float(y), float(z))
                for object_id, x, y, z in _native.future_positions(materialized, float(dt))
            ]
        except Exception:
            _log_native_fallback(
                "native_future_positions_failed",
                "Native future-position batch failed; falling back to Python records=%s",
                len(materialized),
            )

    return _future_positions_python(materialized, float(dt))


def encode_weapon_shot_packet(
    protocol_id: int,
    message_type: int,
    from_obj_id: int,
    kilovo_pont: int,
    target_obj_id: int,
    weapon_fx_type: int,
) -> bytes | None:
    if not _PACKET_SERIALIZATION_ENABLED:
        return None
    if should_use_native_packet_serialization() and hasattr(_native, "encode_weapon_shot"):
        try:
            return bytes(_native.encode_weapon_shot(
                int(protocol_id) & 0xFF,
                int(message_type) & 0xFFFF,
                int(from_obj_id),
                int(kilovo_pont) & 0xFFFF,
                int(target_obj_id),
                int(weapon_fx_type) & 0xFF,
            ))
        except Exception:
            _log_native_fallback(
                "native_packet_weapon_shot_failed",
                "Native WeaponShot packet serialization failed; falling back to Python",
            )
    return _encode_weapon_shot_packet_python(
        protocol_id, message_type, from_obj_id, kilovo_pont, target_obj_id, weapon_fx_type)


def encode_object_left_ids_packet(
    protocol_id: int,
    message_type: int,
    object_ids: Iterable[int],
    removing_cause: int,
) -> bytes | None:
    if not _PACKET_SERIALIZATION_ENABLED:
        return None
    materialized_ids = [int(object_id) for object_id in object_ids]
    if should_use_native_packet_serialization() and hasattr(_native, "encode_object_left_ids"):
        try:
            return bytes(_native.encode_object_left_ids(
                int(protocol_id) & 0xFF,
                int(message_type) & 0xFFFF,
                materialized_ids,
                int(removing_cause) & 0xFF,
            ))
        except Exception:
            _log_native_fallback(
                "native_packet_object_left_ids_failed",
                "Native ObjectLeftIds packet serialization failed; falling back to Python count=%s",
                len(materialized_ids),
            )
    return _encode_object_left_ids_packet_python(protocol_id, message_type, materialized_ids, removing_cause)


def encode_combat_info_packet(
    protocol_id: int,
    message_type: int,
    sajat_sebzes: bool,
    object_id: int,
    damage: float,
    wrecked: bool,
    landed_critical: bool,
) -> bytes | None:
    if not _PACKET_SERIALIZATION_ENABLED:
        return None
    if should_use_native_packet_serialization() and hasattr(_native, "encode_combat_info"):
        try:
            return bytes(_native.encode_combat_info(
                int(protocol_id) & 0xFF,
                int(message_type) & 0xFFFF,
                bool(sajat_sebzes),
                int(object_id),
                float(damage),
                bool(wrecked),
                bool(landed_critical),
            ))
        except Exception:
            _log_native_fallback(
                "native_packet_combat_info_failed",
                "Native CombatInfo packet serialization failed; falling back to Python",
            )
    return _encode_combat_info_packet_python(
        protocol_id, message_type, sajat_sebzes, object_id, damage, wrecked, landed_critical)


def filter_aabb_ids(
    records: Iterable[Sequence[float | int]],
    query_aabb: Sequence[float],
    skip_id: int | None = None,
) -> list[int]:
    materialized = [_aabb_record(feljegyzes) for feljegyzes in records]
    query_tuple = _aabb_tuple(query_aabb)

    if should_use_native_spatial_filter(len(materialized)):
        return list(_native.filter_aabb_ids(materialized, query_tuple, skip_id))

    return _filter_aabb_ids_python(materialized, query_tuple, skip_id)


def filter_sphere_pair_indices(records: Iterable[Sequence[float | int]]) -> list[int]:
    materialized = [_sphere_pair_record(feljegyzes) for feljegyzes in records]
    if should_use_native_sphere_pair_filter(len(materialized)):
        return [int(record_id) for record_id in _native.filter_sphere_pair_indices(materialized)]
    return _filter_sphere_pair_indices_python(materialized)


def candidate_pairs_from_cells(
    cell_body_ids: Iterable[Iterable[int]],
    global_body_ids: Iterable[int],
    all_body_ids: Iterable[int],
    aabb_records: Iterable[Sequence[float | int]],
) -> tuple[int, list[tuple[int, int]]]:
    materialized_cells = [[int(object_id) for object_id in body_ids] for body_ids in cell_body_ids]
    materialized_global = [int(object_id) for object_id in global_body_ids]
    materialized_all = [int(object_id) for object_id in all_body_ids]
    materialized_aabbs = [_aabb_record(feljegyzes) for feljegyzes in aabb_records]

    if should_use_native_spatial_pair_generation(len(materialized_all)):
        raw_pairs, parosok = _native.candidate_pairs_from_cells(
            materialized_cells,
            materialized_global,
            materialized_all,
            materialized_aabbs,
        )
        return int(raw_pairs), [(int(elso), int(second)) for elso, second in parosok]

    return _candidate_pairs_from_cells_python(
        materialized_cells,
        materialized_global,
        materialized_all,
        materialized_aabbs,
    )


def _filter_radius_ids_python(
    records: Iterable[tuple[int, float, float, float]],
    center: tuple[float, float, float],
    radius: float,
    always_include_id: int | None,
) -> list[int]:
    radius_sq = radius * radius
    center_x, center_y, center_z = center
    ids: list[int] = []

    for object_id, x, y, z in records:
        if always_include_id is not None and object_id == always_include_id:
            ids.append(object_id)
            continue

        dx = x - center_x
        dy = y - center_y
        dz = z - center_z
        if dx * dx + dy * dy + dz * dz <= radius_sq:
            ids.append(object_id)

    return ids


def _nearest_radius_id_python(
    records: Iterable[tuple[int, float, float, float]],
    center: tuple[float, float, float],
    radius: float,
) -> int | None:
    radius_sq = radius * radius
    center_x, center_y, center_z = center
    best_id: int | None = None
    best_distance_sq = float("inf")

    for object_id, x, y, z in records:
        dx = x - center_x
        dy = y - center_y
        dz = z - center_z
        distance_sq = dx * dx + dy * dy + dz * dz
        if distance_sq <= radius_sq and distance_sq < best_distance_sq:
            best_distance_sq = distance_sq
            best_id = object_id

    return best_id


def _filter_out_of_bounds_ids_python(
    records: Iterable[tuple[int, float, float, float]],
    limit: float,
) -> list[int]:
    ids: list[int] = []
    for object_id, x, y, z in records:
        if abs(x) > limit or abs(y) > limit or abs(z) > limit:
            ids.append(object_id)
    return ids


def _filter_possible_enemy_ids_python(
    records: Iterable[tuple[int, int, int]],
    against_id: int,
    against_faction: int,
    against_group: int,
    all_enemy: bool,
) -> list[int]:
    ids: list[int] = []
    for object_id, frakcio, csoport in records:
        if object_id == against_id or frakcio == 0 or against_faction == 0:
            continue
        if all_enemy or frakcio != against_faction or csoport != against_group:
            ids.append(object_id)
    return ids


def _filter_range_distance_sq_python(
    records: Iterable[tuple[int, float, float, float]],
    center: tuple[float, float, float],
    min_radius: float,
    max_radius: float,
    include_min: bool,
    include_max: bool,
) -> list[tuple[int, float]]:
    if min_radius > max_radius:
        min_radius, max_radius = max_radius, min_radius
        include_min, include_max = include_max, include_min
    min_sq = min_radius * min_radius
    max_sq = max_radius * max_radius
    center_x, center_y, center_z = center
    egyezesek: list[tuple[int, float]] = []
    for object_id, x, y, z in records:
        dx = x - center_x
        dy = y - center_y
        dz = z - center_z
        distance_sq = dx * dx + dy * dy + dz * dz
        above_min = distance_sq >= min_sq if include_min else distance_sq > min_sq
        below_max = distance_sq <= max_sq if include_max else distance_sq < max_sq
        if above_min and below_max:
            egyezesek.append((object_id, distance_sq))
    return egyezesek


def _future_positions_python(
    records: Iterable[tuple[int, float, float, float, float, float, float, float, float, float]],
    dt: float,
) -> list[tuple[int, float, float, float]]:
    positions: list[tuple[int, float, float, float]] = []
    for object_id, px, py, pz, lx, ly, lz, sx, sy, sz in records:
        positions.append((
            object_id,
            f32(f32(lx + sx) * dt) + px,
            f32(f32(ly + sy) * dt) + py,
            f32(f32(lz + sz) * dt) + pz,
        ))
    return positions


def _packet_prefix(protocol_id: int, message_type: int, payload_length: int) -> bytes:
    hossz = 1 + 2 + payload_length
    if hossz > 65_535:
        raise ValueError("packet payload too large")
    return struct.pack(">H", hossz) + struct.pack("<BH", int(protocol_id) & 0xFF, int(message_type) & 0xFFFF)


def _encode_weapon_shot_packet_python(
    protocol_id: int,
    message_type: int,
    from_obj_id: int,
    kilovo_pont: int,
    target_obj_id: int,
    weapon_fx_type: int,
) -> bytes:
    return (
        _packet_prefix(protocol_id, message_type, 4 + 2 + 4 + 1)
        + struct.pack(
            "<IHIB",
            int(from_obj_id) & 0xFFFFFFFF,
            int(kilovo_pont) & 0xFFFF,
            int(target_obj_id) & 0xFFFFFFFF,
            int(weapon_fx_type) & 0xFF,
        )
    )


def _encode_object_left_ids_packet_python(
    protocol_id: int,
    message_type: int,
    object_ids: Iterable[int],
    removing_cause: int,
) -> bytes:
    materialized = [int(object_id) for object_id in object_ids]
    if len(materialized) > 65_535:
        raise ValueError("object id collection too large")
    puffer = bytearray(_packet_prefix(protocol_id, message_type, 2 + len(materialized) * 9))
    puffer.extend(struct.pack("<H", len(materialized)))
    for object_id in materialized:
        puffer.extend(struct.pack("<IIB", object_id & 0xFFFFFFFF, 0, int(removing_cause) & 0xFF))
    return bytes(puffer)


def _encode_combat_info_packet_python(
    protocol_id: int,
    message_type: int,
    sajat_sebzes: bool,
    object_id: int,
    damage: float,
    wrecked: bool,
    landed_critical: bool,
) -> bytes:
    destroyed_and_critical = 0
    destroyed_and_critical |= 1 if wrecked else 0
    destroyed_and_critical |= 2 if landed_critical else 0
    return (
        _packet_prefix(protocol_id, message_type, 1 + 4 + 4 + 1)
        + struct.pack(
            "<?IfB",
            bool(sajat_sebzes),
            int(object_id) & 0xFFFFFFFF,
            -float(damage),
            destroyed_and_critical,
        )
    )


def _aabb_record(record: Sequence[float | int]) -> tuple[int, float, float, float, float, float, float]:
    return (
        int(record[0]),
        float(record[1]),
        float(record[2]),
        float(record[3]),
        float(record[4]),
        float(record[5]),
        float(record[6]),
    )


def _aabb_tuple(values: Sequence[float]) -> tuple[float, float, float, float, float, float]:
    return (
        float(values[0]),
        float(values[1]),
        float(values[2]),
        float(values[3]),
        float(values[4]),
        float(values[5]),
    )


def _sphere_pair_record(record: Sequence[float | int]) -> tuple[int, float, float, float, float, float, float, float, float]:
    return (
        int(record[0]),
        float(record[1]),
        float(record[2]),
        float(record[3]),
        float(record[4]),
        float(record[5]),
        float(record[6]),
        float(record[7]),
        float(record[8]),
    )


def _aabb_overlaps(
    first: tuple[float, float, float, float, float, float],
    second: tuple[float, float, float, float, float, float],
) -> bool:
    return (
        first[0] <= second[3]
        and first[3] >= second[0]
        and first[1] <= second[4]
        and first[4] >= second[1]
        and first[2] <= second[5]
        and first[5] >= second[2]
    )


def _filter_aabb_ids_python(
    records: Iterable[tuple[int, float, float, float, float, float, float]],
    query_aabb: tuple[float, float, float, float, float, float],
    skip_id: int | None,
) -> list[int]:
    latott: set[int] = set()
    ids: list[int] = []
    for feljegyzes in records:
        object_id, min_x, min_y, min_z, max_x, max_y, max_z = feljegyzes
        if (skip_id is not None and object_id == skip_id) or object_id in latott:
            continue
        latott.add(object_id)
        if _aabb_overlaps(query_aabb, (min_x, min_y, min_z, max_x, max_y, max_z)):
            ids.append(object_id)
    return ids


def _filter_sphere_pair_indices_python(
    records: Iterable[tuple[int, float, float, float, float, float, float, float, float]],
) -> list[int]:
    ids: list[int] = []
    for record_id, ax, ay, az, ar, bx, by, bz, br in records:
        dx = ax - bx
        dy = ay - by
        dz = az - bz
        sugar = ar + br
        if dx * dx + dy * dy + dz * dz <= sugar * sugar:
            ids.append(record_id)
    return ids


def _candidate_pairs_from_cells_python(
    cell_body_ids: list[list[int]],
    global_body_ids: list[int],
    all_body_ids: list[int],
    aabb_records: list[tuple[int, float, float, float, float, float, float]],
) -> tuple[int, list[tuple[int, int]]]:
    aabbs = {
        object_id: (min_x, min_y, min_z, max_x, max_y, max_z)
        for object_id, min_x, min_y, min_z, max_x, max_y, max_z in aabb_records
    }
    raw_pairs = 0
    parosok: list[tuple[int, int]] = []
    latott: set[tuple[int, int]] = set()

    def append_if_pair(first_id: int, second_id: int) -> None:
        nonlocal raw_pairs
        if first_id == second_id:
            return
        pair_key = (first_id, second_id) if first_id <= second_id else (second_id, first_id)
        if pair_key in latott:
            return
        latott.add(pair_key)
        raw_pairs += 1
        first_aabb = aabbs.get(first_id)
        second_aabb = aabbs.get(second_id)
        if first_aabb is not None and second_aabb is not None and _aabb_overlaps(first_aabb, second_aabb):
            parosok.append((first_id, second_id))

    for body_ids in cell_body_ids:
        for first_index in range(len(body_ids)):
            for second_index in range(first_index + 1, len(body_ids)):
                append_if_pair(body_ids[first_index], body_ids[second_index])

    for first_index in range(len(global_body_ids)):
        for second_index in range(first_index + 1, len(global_body_ids)):
            append_if_pair(global_body_ids[first_index], global_body_ids[second_index])
    for global_id in global_body_ids:
        for body_id in all_body_ids:
            append_if_pair(global_id, body_id)

    return raw_pairs, parosok
