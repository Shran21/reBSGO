# github.com/Shran21

from __future__ import annotations

from abc import ABC
from rebsgo.gamedata import json_helper as jh
from rebsgo.geometry.collider_shapes import BoxCollider, CapsuleCollider, SphereCollider
from rebsgo.geometry.maths.triangle_face import Face
from rebsgo.geometry.primitives.vector3 import Vector3
from rebsgo.vocabulary.sorszamos_enum import SorszamosEnum
from typing import Optional


class ShapeKind(SorszamosEnum):
    Mesh = 0
    AABB = 1
    Sphere = 2
    Capsule = 3


class ShapePlan(ABC):
    def __init__(self, prefab_name: str, type):
        self.prefab_name = prefab_name
        self.type = type


class AlignedBoxPlan(ShapePlan):
    def __init__(self, prefab_name: str, center, extents):
        super().__init__(prefab_name, ShapeKind.AABB)
        self.center = center
        self.extents = extents

    @classmethod
    def from_json(cls, obj: dict) -> "AlignedBoxPlan":
        return cls(jh.as_text(obj, "prefabName"), jh.get_vector3(obj, "center"), jh.get_vector3(obj, "extents"))

    def center_point(self):
        return self.center


class CapsulePlan(ShapePlan):
    def __init__(self, prefab_name: str, center, axis: int, height: float, radius: float):
        super().__init__(prefab_name, ShapeKind.Capsule)
        self.center = center
        self.axis = axis
        self.height = height
        self.radius = radius

    @classmethod
    def from_json(cls, obj: dict) -> "CapsulePlan":
        return cls(jh.as_text(obj, "prefabName"), jh.get_vector3(obj, "center"),
                   jh.as_int(obj, "axis"), jh.as_float(obj, "height"), jh.as_float(obj, "radius"))

    def center_point(self):
        return self.center

    def radius_of(self) -> float:
        return self.radius


class MeshPlan(ShapePlan):
    def __init__(self, prefab_name: str, faces):
        super().__init__(prefab_name, ShapeKind.Mesh)
        self.faces = faces

    @classmethod
    def from_json(cls, obj: dict) -> "MeshPlan":
        nyers = obj.get("faces")
        faces = None if nyers is None else [
            Face(jh.vector3_from(fc.get("f1")), jh.vector3_from(fc.get("f2")), jh.vector3_from(fc.get("f3")))
            for fc in nyers
        ]
        return cls(jh.as_text(obj, "prefabName"), faces)

    def __repr__(self) -> str:
        return "<MeshPlan " + f"faces={self.faces}, prefab_name='{self.prefab_name}', type={self.type}" + ">"


class SpherePlan(ShapePlan):
    def __init__(self, center, radius: float):
        super().__init__('asteroid', ShapeKind.Sphere)
        self.center = center
        self.radius = radius

    @classmethod
    def from_json(cls, obj: dict) -> "SpherePlan":
        t = cls(jh.get_vector3(obj, "center"), jh.as_float(obj, "radius"))
        t.prefab_name = jh.as_text(obj, "prefabName")
        return t

    def radius_of(self) -> float:
        return self.radius

    def center_point(self):
        return self.center


def of_template(utkozo_sablon, helyzet_ref, scale: float = 1.0):
    if isinstance(utkozo_sablon, SpherePlan):
        return _from_sphere(utkozo_sablon, helyzet_ref, scale)
    if isinstance(utkozo_sablon, CapsulePlan):
        return _from_capsule(utkozo_sablon, helyzet_ref, scale)
    if isinstance(utkozo_sablon, AlignedBoxPlan):
        return _from_aabb(utkozo_sablon, helyzet_ref, scale)
    raise RuntimeError("Could not find ShapePlan instance")


def _from_sphere(t: SpherePlan, helyzet_ref, scale: float) -> SphereCollider:
    center = t.center_point().copy().scale_(scale)
    radius = t.radius_of() * scale
    return SphereCollider(helyzet_ref, center, radius)


_TENGELYEK = ((1, 0, 0), (0, 1, 0), (0, 0, 1))


def _from_capsule(t: CapsulePlan, helyzet_ref, scale: float) -> CapsuleCollider:
    tengely = Vector3(*_TENGELYEK[t.axis]) if 0 <= t.axis < len(_TENGELYEK) \
        else Vector3(0, 0, 0)
    sugar = t.radius_of() * scale
    kozep = t.center_point().copy().scale_(scale)
    veg_fele = Vector3.mult(tengely, t.height * 0.5 * scale - sugar)
    return CapsuleCollider(helyzet_ref,
                           Vector3.add(kozep, veg_fele),
                           Vector3.sub(kozep, veg_fele),
                           sugar)


def _from_aabb(t: AlignedBoxPlan, helyzet_ref, scale: float) -> BoxCollider:
    center = t.center_point().copy().scale_(scale)
    extents = t.extents.copy().scale_(scale)
    return BoxCollider(helyzet_ref, center, extents)


class ShapePlans:
    def __init__(self, utkozo_olvaso):
        self._aabb_map: dict = {}
        self._mesh_map: dict = {}
        self._sphere_map: dict = {}
        self._capsule_map: dict = {}
        self._collider_template_reader = utkozo_olvaso
        self.post_init()

    def post_init(self) -> None:
        for collider_template in self._collider_template_reader.collider_plans():
            self.register_collider(collider_template)

    def register_collider(self, utkozo_sablon) -> None:
        if utkozo_sablon is None:
            return
        t = utkozo_sablon.type
        if t is ShapeKind.Mesh:
            self._mesh_map[utkozo_sablon.prefab_name] = utkozo_sablon
        elif t is ShapeKind.AABB:
            self._aabb_map[utkozo_sablon.prefab_name] = utkozo_sablon
        elif t is ShapeKind.Sphere:
            self._sphere_map[utkozo_sablon.prefab_name] = utkozo_sablon
        elif t is ShapeKind.Capsule:
            self._capsule_map[utkozo_sablon.prefab_name] = utkozo_sablon

    def mesh_collider_template(self, prefab_name: str) -> Optional[object]:
        return self._mesh_map.get(prefab_name)

    def aabb_collider_template(self, prefab_name: str) -> Optional[object]:
        return self._aabb_map.get(prefab_name)

    def sphere_collider_template(self, prefab_name: str) -> Optional[object]:
        return self._sphere_map.get(prefab_name)

    def capsule_collider_template(self, prefab_name: str) -> Optional[object]:
        return self._capsule_map.get(prefab_name)

    def collider_template(self, prefab_name: str) -> Optional[object]:
        if (opt1 := self.sphere_collider_template(prefab_name)) is not None:
            return opt1
        if (opt2 := self.capsule_collider_template(prefab_name)) is not None:
            return opt2
        if (opt3 := self.aabb_collider_template(prefab_name)) is not None:
            return opt3
        return None

    def stand_in_asteroid_colliders(self, prefabs) -> None:
        for prefab in prefabs:
            if "asteroid_" in prefab or "planetoid" in prefab:
                if self.collider_template(prefab) is None:
                    self._sphere_map[prefab] = SpherePlan(Vector3.zero(), 1)
