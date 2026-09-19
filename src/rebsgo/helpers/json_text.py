# github.com/Shran21

from __future__ import annotations

import dataclasses
import datetime
import json
from typing import Any


def _atalakit(obj: Any) -> Any:
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in vars(obj).items() if not k.startswith("_")}
    raise TypeError(f"{type(obj).__name__} cannot be rendered as JSON")


def szoveggé(obj: Any) -> str:
    return json.dumps(obj, default=_atalakit, separators=(",", ":"))


def szövegből(szoveg: str) -> Any:
    return json.loads(szoveg)
