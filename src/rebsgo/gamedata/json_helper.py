# github.com/Shran21
from __future__ import annotations

from typing import Any

from rebsgo.helpers.floats import f32


def _ci_get(obj: dict, key: str):
    if key in obj:
        return obj[key]
    key_lower = key.lower()
    for k in obj:
        if isinstance(k, str) and k.lower() == key_lower:
            return obj[k]
    return None


def as_long(obj: dict, key: str, default: int = 0) -> int:
    v = _ci_get(obj, key)
    return default if v is None else int(v)


def as_int(obj: dict, key: str, default: int = 0) -> int:
    v = _ci_get(obj, key)
    return default if v is None else int(v)


def as_short(obj: dict, key: str, default: int = 0) -> int:
    v = _ci_get(obj, key)
    return default if v is None else int(v)


def as_byte(obj: dict, key: str, default: int = 0) -> int:
    v = _ci_get(obj, key)
    return default if v is None else int(v)


def as_float(obj: dict, key: str, default: float = 0.0) -> float:
    v = _ci_get(obj, key)
    return f32(default) if v is None else f32(v)


def as_double(obj: dict, key: str, default: float = 0.0) -> float:
    v = _ci_get(obj, key)
    return default if v is None else float(v)


def as_flag(obj: dict, key: str, default: bool = False) -> bool:
    v = _ci_get(obj, key)
    return default if v is None else bool(v)


def as_text(obj: dict, key: str, default: str | None = None) -> str | None:
    v = _ci_get(obj, key)
    return default if v is None else str(v)


def as_text_list(obj: dict, key: str, default=None):
    v = _ci_get(obj, key)
    return default if v is None else [str(x) for x in v]


def as_long_list(obj: dict, key: str, default=None):
    v = _ci_get(obj, key)
    return default if v is None else [int(x) for x in v]


def as_int_list(obj: dict, key: str, default=None):
    v = _ci_get(obj, key)
    return default if v is None else [int(x) for x in v]


def as_float_list(obj: dict, key: str, default=None):
    v = _ci_get(obj, key)
    return default if v is None else [f32(x) for x in v]


def as_object(obj: dict, key: str) -> Any:
    return _ci_get(obj, key)


def _enum_from_raw(raw, enum_cls, default=None):
    if raw is None:
        return default
    if isinstance(raw, str):
        nev = "None_" if raw == "None" else raw
        try:
            return enum_cls[nev]
        except KeyError:
            return default
    ertek = int(raw)
    if (kereso := getattr(enum_cls, 'from_code', None)) is not None:
        if (tag := kereso(ertek)) is not None:
            return tag
    tagok = list(enum_cls)
    if 0 <= ertek < len(tagok):
        return tagok[ertek]
    return default


def as_enum_by_name(obj: dict, key: str, enum_cls, default=None):
    return _enum_from_raw(_ci_get(obj, key), enum_cls, default)


def as_enum_list(obj: dict, key: str, enum_cls, default=None):
    v = _ci_get(obj, key)
    if v is None:
        return default
    return [_enum_from_raw(x, enum_cls) for x in v]


def as_object_stats(obj: dict, key: str):
    from rebsgo.gamedata.reading import ObjectStat
    from rebsgo.gamedata.reading import ObjectStats

    v = _ci_get(obj, key)
    if v is None:
        return None
    inner = v.get("stats") or {}
    stats = {}
    for k, ertek in inner.items():
        stat = ObjectStat.None_ if k == "None" else ObjectStat[k]
        stats[stat] = f32(ertek)
    return ObjectStats(stats)


def as_ship_items(obj: dict, key: str):
    from rebsgo.gamedata.decoding.ship_item_parser import ship_item_from_json

    v = _ci_get(obj, key)
    if v is None:
        return None
    return [ship_item_from_json(x) for x in v]


def as_price(obj: dict, key: str):
    from rebsgo.gamedata.reading import Price

    v = _ci_get(obj, key)
    if v is None:
        return None
    inner = v.get("items") or {}
    return Price({int(k): f32(ertek) for k, ertek in inner.items()})


def _f(v, default=0.0):
    return f32(default) if v is None else f32(v)


def _osszerak(v, epito, mezok: str):
    if v is None:
        return None
    return epito(*(_f(v.get(m)) for m in mezok))


def color_from(v):
    from rebsgo.helpers.color import Color
    return _osszerak(v, Color, "rgba")


def vector3_from(v):
    from rebsgo.geometry.primitives.vector3 import Vector3
    return _osszerak(v, Vector3, "xyz")


def vector2_from(v):
    from rebsgo.geometry.primitives.vector2 import Vector2
    return _osszerak(v, Vector2, "xy")


def quaternion_from(v):
    from rebsgo.geometry.primitives.quaternion import Quaternion
    return _osszerak(v, Quaternion, "xyzw")


def get_color(obj: dict, key: str):
    return color_from(_ci_get(obj, key))


def get_vector3(obj: dict, key: str):
    return vector3_from(_ci_get(obj, key))


def get_vector2(obj: dict, key: str):
    return vector2_from(_ci_get(obj, key))


def get_quaternion(obj: dict, key: str):
    return quaternion_from(_ci_get(obj, key))


def euler3_from(v):
    from rebsgo.geometry.primitives.euler3 import Euler3

    if v is None:
        return None
    return Euler3(_f(v.get("pitch")), _f(v.get("yaw")), _f(v.get("roll")))


def euler3(obj: dict, key: str):
    return euler3_from(_ci_get(obj, key))


def aabb_from(v):
    from rebsgo.geometry.collider_shapes import AABB

    if v is None:
        return None
    return AABB(vector3_from(v.get("min")), vector3_from(v.get("max")))
