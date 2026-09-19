// github.com/Shran21
use pyo3::prelude::*;
use pyo3::exceptions::PyValueError;
use std::collections::{HashMap, HashSet};
use std::thread;

type ObjectRecord = (u64, f64, f64, f64);
type Point3 = (f64, f64, f64);
type AabbRecord = (u64, f64, f64, f64, f64, f64, f64);
type AabbTuple = (f64, f64, f64, f64, f64, f64);
type SpherePairRecord = (u64, f64, f64, f64, f64, f64, f64, f64, f64);
type FuturePositionRecord = (u64, f64, f64, f64, f64, f64, f64, f64, f64, f64);
type RelationRecord = (u64, i64, i64);

const PARALLEL_MIN_RECORDS: usize = 4096;

fn worker_count(record_count: usize) -> usize {
    if record_count < PARALLEL_MIN_RECORDS {
        return 1;
    }

    let available = thread::available_parallelism()
        .map(|count| count.get())
        .unwrap_or(1);
    let useful = record_count / PARALLEL_MIN_RECORDS;
    available.min(useful.max(1)).max(1)
}

fn append_u16_le(buffer: &mut Vec<u8>, value: u16) {
    buffer.extend_from_slice(&value.to_le_bytes());
}

fn append_u32_le(buffer: &mut Vec<u8>, value: u32) {
    buffer.extend_from_slice(&value.to_le_bytes());
}

fn append_f32_le(buffer: &mut Vec<u8>, value: f32) {
    buffer.extend_from_slice(&value.to_le_bytes());
}

fn packet_start(protocol_id: u8, message_type: u16, payload_bytes: usize) -> Vec<u8> {
    let mut buffer = Vec::with_capacity(2 + 1 + 2 + payload_bytes);
    buffer.extend_from_slice(&[0, 0, protocol_id]);
    append_u16_le(&mut buffer, message_type);
    buffer
}

fn finish_packet(mut buffer: Vec<u8>) -> PyResult<Vec<u8>> {
    let length = buffer.len().saturating_sub(2);
    if length > u16::MAX as usize {
        return Err(PyValueError::new_err("packet payload too large"));
    }
    buffer[0] = ((length >> 8) & 0xFF) as u8;
    buffer[1] = (length & 0xFF) as u8;
    Ok(buffer)
}

fn distance_sq(record: &ObjectRecord, center: Point3) -> f64 {
    let dx = record.1 - center.0;
    let dy = record.2 - center.1;
    let dz = record.3 - center.2;
    dx * dx + dy * dy + dz * dz
}

fn normalize_range(
    min_radius: f64,
    max_radius: f64,
    include_min: bool,
    include_max: bool,
) -> (f64, f64, bool, bool) {
    if min_radius <= max_radius {
        (min_radius, max_radius, include_min, include_max)
    } else {
        (max_radius, min_radius, include_max, include_min)
    }
}

fn in_range_sq(
    distance_sq: f64,
    min_radius: f64,
    max_radius: f64,
    include_min: bool,
    include_max: bool,
) -> bool {
    let min_sq = min_radius * min_radius;
    let max_sq = max_radius * max_radius;
    let above_min = if include_min {
        distance_sq >= min_sq
    } else {
        distance_sq > min_sq
    };
    let below_max = if include_max {
        distance_sq <= max_sq
    } else {
        distance_sq < max_sq
    };
    above_min && below_max
}

fn aabb_from_record(record: AabbRecord) -> (u64, AabbTuple) {
    (
        record.0,
        (record.1, record.2, record.3, record.4, record.5, record.6),
    )
}

fn aabb_overlaps(first: &AabbTuple, second: &AabbTuple) -> bool {
    first.0 <= second.3
        && first.3 >= second.0
        && first.1 <= second.4
        && first.4 >= second.1
        && first.2 <= second.5
        && first.5 >= second.2
}

fn pair_key(first: u64, second: u64) -> (u64, u64) {
    if first <= second {
        (first, second)
    } else {
        (second, first)
    }
}

fn filter_radius_ids_inner(
    objects: Vec<ObjectRecord>,
    center: Point3,
    radius: f64,
    always_include: Option<u64>,
) -> Vec<u64> {
    let radius_sq = radius * radius;
    let (center_x, center_y, center_z) = center;
    let mut ids = Vec::with_capacity(objects.len());

    for (object_id, x, y, z) in objects {
        if always_include == Some(object_id) {
            ids.push(object_id);
            continue;
        }

        let dx = x - center_x;
        let dy = y - center_y;
        let dz = z - center_z;
        if dx * dx + dy * dy + dz * dz <= radius_sq {
            ids.push(object_id);
        }
    }

    ids
}

fn nearest_radius_id_inner(objects: Vec<ObjectRecord>, center: Point3, radius: f64) -> Option<u64> {
    let radius_sq = radius * radius;
    let (center_x, center_y, center_z) = center;
    let mut best_id = None;
    let mut best_distance_sq = f64::INFINITY;

    for (object_id, x, y, z) in objects {
        let dx = x - center_x;
        let dy = y - center_y;
        let dz = z - center_z;
        let distance_sq = dx * dx + dy * dy + dz * dz;
        if distance_sq <= radius_sq && distance_sq < best_distance_sq {
            best_distance_sq = distance_sq;
            best_id = Some(object_id);
        }
    }

    best_id
}

fn filter_out_of_bounds_ids_inner(objects: Vec<ObjectRecord>, limit: f64) -> Vec<u64> {
    let mut ids = Vec::new();
    for (object_id, x, y, z) in objects {
        if x.abs() > limit || y.abs() > limit || z.abs() > limit {
            ids.push(object_id);
        }
    }
    ids
}

fn filter_possible_enemy_ids_inner(
    records: Vec<RelationRecord>,
    against_id: u64,
    against_faction: i64,
    against_group: i64,
    all_enemy: bool,
) -> Vec<u64> {
    let mut ids = Vec::with_capacity(records.len());
    for (object_id, faction, group) in records {
        if object_id == against_id {
            continue;
        }
        if faction == 0 || against_faction == 0 {
            continue;
        }
        if all_enemy || faction != against_faction || group != against_group {
            ids.push(object_id);
        }
    }
    ids
}

#[pyfunction]
fn filter_possible_enemy_ids(
    py: Python<'_>,
    records: Vec<RelationRecord>,
    against_id: u64,
    against_faction: i64,
    against_group: i64,
    all_enemy: bool,
) -> Vec<u64> {
    py.allow_threads(move || {
        filter_possible_enemy_ids_inner(records, against_id, against_faction, against_group, all_enemy)
    })
}

fn filter_range_distance_sq_inner(
    objects: Vec<ObjectRecord>,
    center: Point3,
    min_radius: f64,
    max_radius: f64,
    include_min: bool,
    include_max: bool,
) -> Vec<(u64, f64)> {
    let (min_radius, max_radius, include_min, include_max) =
        normalize_range(min_radius, max_radius, include_min, include_max);
    let workers = worker_count(objects.len());
    if workers <= 1 {
        let mut matches = Vec::with_capacity(objects.len());
        for record in &objects {
            let dist_sq = distance_sq(record, center);
            if in_range_sq(dist_sq, min_radius, max_radius, include_min, include_max) {
                matches.push((record.0, dist_sq));
            }
        }
        return matches;
    }

    let chunk_size = (objects.len() + workers - 1) / workers;
    let mut chunk_results: Vec<Vec<(u64, f64)>> = Vec::new();
    thread::scope(|scope| {
        let mut handles = Vec::new();
        for chunk in objects.chunks(chunk_size) {
            handles.push(scope.spawn(move || {
                let mut matches = Vec::with_capacity(chunk.len());
                for record in chunk {
                    let dist_sq = distance_sq(record, center);
                    if in_range_sq(dist_sq, min_radius, max_radius, include_min, include_max) {
                        matches.push((record.0, dist_sq));
                    }
                }
                matches
            }));
        }
        for handle in handles {
            chunk_results.push(handle.join().unwrap());
        }
    });

    let total = chunk_results.iter().map(Vec::len).sum();
    let mut matches = Vec::with_capacity(total);
    for mut result in chunk_results {
        matches.append(&mut result);
    }
    matches
}

fn future_positions_inner(records: Vec<FuturePositionRecord>, dt: f64) -> Vec<(u64, f64, f64, f64)> {
    let workers = worker_count(records.len());
    if workers <= 1 {
        let mut positions = Vec::with_capacity(records.len());
        for record in records {
            positions.push(future_position(record, dt));
        }
        return positions;
    }

    let chunk_size = (records.len() + workers - 1) / workers;
    let mut chunk_results: Vec<Vec<(u64, f64, f64, f64)>> = Vec::new();
    thread::scope(|scope| {
        let mut handles = Vec::new();
        for chunk in records.chunks(chunk_size) {
            handles.push(scope.spawn(move || {
                let mut positions = Vec::with_capacity(chunk.len());
                for record in chunk {
                    positions.push(future_position(*record, dt));
                }
                positions
            }));
        }
        for handle in handles {
            chunk_results.push(handle.join().unwrap());
        }
    });

    let total = chunk_results.iter().map(Vec::len).sum();
    let mut positions = Vec::with_capacity(total);
    for mut result in chunk_results {
        positions.append(&mut result);
    }
    positions
}

fn future_position(record: FuturePositionRecord, dt: f64) -> (u64, f64, f64, f64) {
    let (
        object_id,
        px,
        py,
        pz,
        linear_x,
        linear_y,
        linear_z,
        strafe_x,
        strafe_y,
        strafe_z,
    ) = record;
    let dx = ((((linear_x + strafe_x) as f32) as f64 * dt) as f32) as f64;
    let dy = ((((linear_y + strafe_y) as f32) as f64 * dt) as f32) as f64;
    let dz = ((((linear_z + strafe_z) as f32) as f64 * dt) as f32) as f64;
    (object_id, px + dx, py + dy, pz + dz)
}

fn encode_weapon_shot_inner(
    protocol_id: u8,
    message_type: u16,
    from_obj_id: u64,
    obj_point_hash: u16,
    target_obj_id: u64,
    weapon_fx_type: u8,
) -> PyResult<Vec<u8>> {
    let mut buffer = packet_start(protocol_id, message_type, 4 + 2 + 4 + 1);
    append_u32_le(&mut buffer, from_obj_id as u32);
    append_u16_le(&mut buffer, obj_point_hash);
    append_u32_le(&mut buffer, target_obj_id as u32);
    buffer.push(weapon_fx_type);
    finish_packet(buffer)
}

fn encode_object_left_ids_inner(
    protocol_id: u8,
    message_type: u16,
    object_ids: Vec<u64>,
    removing_cause: u8,
) -> PyResult<Vec<u8>> {
    if object_ids.len() > u16::MAX as usize {
        return Err(PyValueError::new_err("object id collection too large"));
    }
    let mut buffer = packet_start(protocol_id, message_type, 2 + object_ids.len() * 9);
    append_u16_le(&mut buffer, object_ids.len() as u16);
    for object_id in object_ids {
        append_u32_le(&mut buffer, object_id as u32);
        append_u32_le(&mut buffer, 0);
        buffer.push(removing_cause);
    }
    finish_packet(buffer)
}

fn encode_combat_info_inner(
    protocol_id: u8,
    message_type: u16,
    dmg_is_from_me: bool,
    object_id: u64,
    damage: f64,
    is_destroyed: bool,
    is_critical_hit: bool,
) -> PyResult<Vec<u8>> {
    let mut buffer = packet_start(protocol_id, message_type, 1 + 4 + 4 + 1);
    buffer.push(if dmg_is_from_me { 1 } else { 0 });
    append_u32_le(&mut buffer, object_id as u32);
    append_f32_le(&mut buffer, -(damage as f32));
    let mut destroyed_and_critical = 0u8;
    if is_destroyed {
        destroyed_and_critical |= 1;
    }
    if is_critical_hit {
        destroyed_and_critical |= 2;
    }
    buffer.push(destroyed_and_critical);
    finish_packet(buffer)
}

#[pyfunction(signature = (objects, center, radius, always_include=None))]
fn filter_radius_ids(
    py: Python<'_>,
    objects: Vec<ObjectRecord>,
    center: Point3,
    radius: f64,
    always_include: Option<u64>,
) -> Vec<u64> {
    py.allow_threads(move || filter_radius_ids_inner(objects, center, radius, always_include))
}

#[pyfunction]
fn nearest_radius_id(
    py: Python<'_>,
    objects: Vec<ObjectRecord>,
    center: Point3,
    radius: f64,
) -> Option<u64> {
    py.allow_threads(move || nearest_radius_id_inner(objects, center, radius))
}

#[pyfunction]
fn filter_out_of_bounds_ids(py: Python<'_>, objects: Vec<ObjectRecord>, limit: f64) -> Vec<u64> {
    py.allow_threads(move || filter_out_of_bounds_ids_inner(objects, limit))
}

#[pyfunction]
fn filter_range_distance_sq(
    py: Python<'_>,
    objects: Vec<ObjectRecord>,
    center: Point3,
    min_radius: f64,
    max_radius: f64,
    include_min: bool,
    include_max: bool,
) -> Vec<(u64, f64)> {
    py.allow_threads(move || {
        filter_range_distance_sq_inner(objects, center, min_radius, max_radius, include_min, include_max)
    })
}

#[pyfunction]
fn future_positions(
    py: Python<'_>,
    records: Vec<FuturePositionRecord>,
    dt: f64,
) -> Vec<(u64, f64, f64, f64)> {
    py.allow_threads(move || future_positions_inner(records, dt))
}

#[pyfunction]
fn encode_weapon_shot(
    py: Python<'_>,
    protocol_id: u8,
    message_type: u16,
    from_obj_id: u64,
    obj_point_hash: u16,
    target_obj_id: u64,
    weapon_fx_type: u8,
) -> PyResult<Vec<u8>> {
    py.allow_threads(move || {
        encode_weapon_shot_inner(
            protocol_id,
            message_type,
            from_obj_id,
            obj_point_hash,
            target_obj_id,
            weapon_fx_type,
        )
    })
}

#[pyfunction]
fn encode_object_left_ids(
    py: Python<'_>,
    protocol_id: u8,
    message_type: u16,
    object_ids: Vec<u64>,
    removing_cause: u8,
) -> PyResult<Vec<u8>> {
    py.allow_threads(move || encode_object_left_ids_inner(protocol_id, message_type, object_ids, removing_cause))
}

#[pyfunction]
fn encode_combat_info(
    py: Python<'_>,
    protocol_id: u8,
    message_type: u16,
    dmg_is_from_me: bool,
    object_id: u64,
    damage: f64,
    is_destroyed: bool,
    is_critical_hit: bool,
) -> PyResult<Vec<u8>> {
    py.allow_threads(move || {
        encode_combat_info_inner(
            protocol_id,
            message_type,
            dmg_is_from_me,
            object_id,
            damage,
            is_destroyed,
            is_critical_hit,
        )
    })
}

fn filter_aabb_ids_inner(
    records: Vec<AabbRecord>,
    query: AabbTuple,
    skip_id: Option<u64>,
) -> Vec<u64> {
    let mut seen = HashSet::with_capacity(records.len());
    let mut ids = Vec::with_capacity(records.len());

    for record in records {
        let (object_id, aabb) = aabb_from_record(record);
        if skip_id == Some(object_id) || !seen.insert(object_id) {
            continue;
        }
        if aabb_overlaps(&query, &aabb) {
            ids.push(object_id);
        }
    }

    ids
}

#[pyfunction(signature = (records, query, skip_id=None))]
fn filter_aabb_ids(
    py: Python<'_>,
    records: Vec<AabbRecord>,
    query: AabbTuple,
    skip_id: Option<u64>,
) -> Vec<u64> {
    py.allow_threads(move || filter_aabb_ids_inner(records, query, skip_id))
}

fn sphere_pair_overlaps(record: &SpherePairRecord) -> bool {
    let (_record_id, ax, ay, az, ar, bx, by, bz, br) = *record;
    let dx = ax - bx;
    let dy = ay - by;
    let dz = az - bz;
    let radius = ar + br;
    dx * dx + dy * dy + dz * dz <= radius * radius
}

fn filter_sphere_pair_indices_inner(records: Vec<SpherePairRecord>) -> Vec<u64> {
    let workers = worker_count(records.len());
    if workers <= 1 {
        let mut ids = Vec::with_capacity(records.len());
        for record in &records {
            if sphere_pair_overlaps(record) {
                ids.push(record.0);
            }
        }
        return ids;
    }

    let chunk_size = (records.len() + workers - 1) / workers;
    let mut chunk_results: Vec<Vec<u64>> = Vec::new();
    thread::scope(|scope| {
        let mut handles = Vec::new();
        for chunk in records.chunks(chunk_size) {
            handles.push(scope.spawn(move || {
                let mut ids = Vec::with_capacity(chunk.len());
                for record in chunk {
                    if sphere_pair_overlaps(record) {
                        ids.push(record.0);
                    }
                }
                ids
            }));
        }
        for handle in handles {
            chunk_results.push(handle.join().unwrap());
        }
    });

    let total = chunk_results.iter().map(Vec::len).sum();
    let mut ids = Vec::with_capacity(total);
    for mut result in chunk_results {
        ids.append(&mut result);
    }
    ids
}

#[pyfunction]
fn filter_sphere_pair_indices(py: Python<'_>, records: Vec<SpherePairRecord>) -> Vec<u64> {
    py.allow_threads(move || filter_sphere_pair_indices_inner(records))
}

fn append_candidate_pair(
    first_id: u64,
    second_id: u64,
    aabbs: &HashMap<u64, AabbTuple>,
    seen: &mut HashSet<(u64, u64)>,
    pairs: &mut Vec<(u64, u64)>,
) -> u64 {
    if first_id == second_id {
        return 0;
    }

    let key = pair_key(first_id, second_id);
    if !seen.insert(key) {
        return 0;
    }

    let Some(first_aabb) = aabbs.get(&first_id) else {
        return 1;
    };
    let Some(second_aabb) = aabbs.get(&second_id) else {
        return 1;
    };
    if aabb_overlaps(first_aabb, second_aabb) {
        pairs.push((first_id, second_id));
    }
    1
}

fn candidate_pairs_from_cells_inner(
    cell_body_ids: Vec<Vec<u64>>,
    global_body_ids: Vec<u64>,
    all_body_ids: Vec<u64>,
    aabb_records: Vec<AabbRecord>,
) -> (u64, Vec<(u64, u64)>) {
    let mut aabbs = HashMap::with_capacity(aabb_records.len());
    for record in aabb_records {
        let (object_id, aabb) = aabb_from_record(record);
        aabbs.insert(object_id, aabb);
    }

    let mut raw_pairs = 0;
    let mut pairs = Vec::new();
    let mut seen = HashSet::new();

    for body_ids in cell_body_ids {
        if body_ids.len() < 2 {
            continue;
        }
        for first_index in 0..body_ids.len() {
            for second_index in first_index + 1..body_ids.len() {
                raw_pairs += append_candidate_pair(
                    body_ids[first_index],
                    body_ids[second_index],
                    &aabbs,
                    &mut seen,
                    &mut pairs,
                );
            }
        }
    }

    if !global_body_ids.is_empty() {
        for first_index in 0..global_body_ids.len() {
            for second_index in first_index + 1..global_body_ids.len() {
                raw_pairs += append_candidate_pair(
                    global_body_ids[first_index],
                    global_body_ids[second_index],
                    &aabbs,
                    &mut seen,
                    &mut pairs,
                );
            }
        }
        for global_id in &global_body_ids {
            for body_id in &all_body_ids {
                raw_pairs += append_candidate_pair(*global_id, *body_id, &aabbs, &mut seen, &mut pairs);
            }
        }
    }

    (raw_pairs, pairs)
}

#[pyfunction]
fn candidate_pairs_from_cells(
    py: Python<'_>,
    cell_body_ids: Vec<Vec<u64>>,
    global_body_ids: Vec<u64>,
    all_body_ids: Vec<u64>,
    aabb_records: Vec<AabbRecord>,
) -> (u64, Vec<(u64, u64)>) {
    py.allow_threads(move || {
        candidate_pairs_from_cells_inner(cell_body_ids, global_body_ids, all_body_ids, aabb_records)
    })
}

#[pymodule]
fn rebsgo_native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(filter_radius_ids, module)?)?;
    module.add_function(wrap_pyfunction!(nearest_radius_id, module)?)?;
    module.add_function(wrap_pyfunction!(filter_out_of_bounds_ids, module)?)?;
    module.add_function(wrap_pyfunction!(filter_possible_enemy_ids, module)?)?;
    module.add_function(wrap_pyfunction!(filter_range_distance_sq, module)?)?;
    module.add_function(wrap_pyfunction!(future_positions, module)?)?;
    module.add_function(wrap_pyfunction!(encode_weapon_shot, module)?)?;
    module.add_function(wrap_pyfunction!(encode_object_left_ids, module)?)?;
    module.add_function(wrap_pyfunction!(encode_combat_info, module)?)?;
    module.add_function(wrap_pyfunction!(filter_aabb_ids, module)?)?;
    module.add_function(wrap_pyfunction!(filter_sphere_pair_indices, module)?)?;
    module.add_function(wrap_pyfunction!(candidate_pairs_from_cells, module)?)?;
    Ok(())
}
