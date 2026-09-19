# github.com/Shran21
from __future__ import annotations


def carrier_transponder_debug_enabled() -> bool:
    from rebsgo.config.config import Config

    try:
        return Config.instance().bool("BSGO_CARRIER_TRANSPONDER_DEBUG", False)
    except Exception:
        return False


def format_ship_aspects(ship_aspects) -> str:
    raw_aspects = getattr(ship_aspects, "_ship_aspects", None)
    if raw_aspects is None:
        return str(ship_aspects)
    nevek = []
    for aspect in raw_aspects:
        nevek.append(getattr(aspect, "name", str(aspect)))
    return "[" + ",".join(sorted(nevek)) + "]"


def has_ship_aspect(ship_aspects, aspect) -> bool:
    raw_aspects = getattr(ship_aspects, "_ship_aspects", None)
    return raw_aspects is not None and aspect in raw_aspects


def safe_call(obj, method_name: str, default=None):
    method = getattr(obj, method_name, None)
    if method is None:
        return default
    try:
        return method()
    except Exception:
        return default
