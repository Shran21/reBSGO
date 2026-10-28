# github.com/Shran21
from __future__ import annotations

import struct
from collections.abc import Iterable, Sequence


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
    return _nearest_radius_id_python(materialized, center_tuple, float(radius))


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
    return _filter_range_distance_sq_python(
        materialized,
        center_tuple,
        float(min_radius),
        float(max_radius),
        bool(include_min),
        bool(include_max),
    )


def encode_weapon_shot_packet(
    protocol_id: int,
    message_type: int,
    from_obj_id: int,
    kilovo_pont: int,
    target_obj_id: int,
    weapon_fx_type: int,
) -> bytes:
    return _encode_weapon_shot_packet_python(
        protocol_id, message_type, from_obj_id, kilovo_pont, target_obj_id, weapon_fx_type)


def encode_object_left_ids_packet(
    protocol_id: int,
    message_type: int,
    object_ids: Iterable[int],
    removing_cause: int,
) -> bytes:
    materialized_ids = [int(object_id) for object_id in object_ids]
    return _encode_object_left_ids_packet_python(protocol_id, message_type, materialized_ids, removing_cause)


def encode_combat_info_packet(
    protocol_id: int,
    message_type: int,
    sajat_sebzes: bool,
    object_id: int,
    damage: float,
    wrecked: bool,
    landed_critical: bool,
) -> bytes:
    return _encode_combat_info_packet_python(
        protocol_id, message_type, sajat_sebzes, object_id, damage, wrecked, landed_critical)


def filter_sphere_pair_indices(records: Iterable[Sequence[float | int]]) -> list[int]:
    materialized = [_sphere_pair_record(feljegyzes) for feljegyzes in records]
    return _filter_sphere_pair_indices_python(materialized)


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
