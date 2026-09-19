# github.com/Shran21

from __future__ import annotations

from rebsgo.geometry.primitives.quaternion import Quaternion
from rebsgo.geometry.primitives.common import CommonDirections
from rebsgo.geometry.primitives.transform import Transform
from rebsgo.geometry.primitives.vector3 import Vector3


def point_position_relative_to(local_pos: Vector3, world_pos: Vector3, world_rot: Quaternion) -> Vector3:
    return Vector3.add(Quaternion.mult(world_rot, local_pos), world_pos)


def relative_rotation_to(world_rotation: Quaternion, local_rotation: Quaternion) -> Quaternion:
    return Quaternion.mult(world_rotation, local_rotation)


def within_cone(from_v: Vector3, to: Vector3, angle: float) -> bool:
    return angle == 0.0 or Vector3.angle(from_v, to) <= angle


def within_range(from_v: Vector3, to: Vector3, min_distance: float,
                 max_distance: float) -> bool:
    distance_sq = 0.0 if from_v is to else Vector3.squared_distance(from_v, to)
    return within_squared_range(distance_sq,
                                min_distance * min_distance,
                                max_distance * max_distance)


def within_squared_range(tav_negyzet: float, legkisebb_tav_negyzet: float,
                         legnagyobb_tav_negyzet: float) -> bool:
    also, felso = sorted((legkisebb_tav_negyzet, legnagyobb_tav_negyzet))
    return also <= tav_negyzet <= felso


def weapon_reaches(
    hajo_helyzete: Transform,
    fegyver_helye: Transform,
    cel_hely: Vector3,
    fegyver_kozelhatar: float,
    fegyver_tavolhatar: float,
    fegyver_szoge: float,
) -> bool:
    t_final = fegyver_helye.into_world_space(hajo_helyzete)
    to = Vector3.sub(cel_hely, t_final.position_of())
    is_in_range = within_squared_range(to.sq_magnitude_,
                                       fegyver_kozelhatar * fegyver_kozelhatar,
                                       fegyver_tavolhatar * fegyver_tavolhatar)
    if not is_in_range:
        return False
    from_v = Quaternion.mult(t_final.rotation_of(), CommonDirections.FORWARD)
    return within_cone(from_v, to, fegyver_szoge)
