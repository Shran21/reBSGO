# github.com/Shran21
from __future__ import annotations

import os
import re
from pathlib import Path

from rebsgo.config.catalogue import ALIASES, BASELINE, FOLLOWS, PROFILES

_BOOL_TRUE = {"true", "1", "yes", "y", "on"}


def _to_env_name(key: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "_", key).upper()


def _parse_dotenv(text: str) -> dict[str, str]:
    env: dict[str, str] = {}
    for raw_line in text.splitlines():
        sor = raw_line.strip()
        if not sor or sor.startswith("#") or "=" not in sor:
            continue
        kulcs, _, ertek = sor.partition("=")
        ertek = ertek.strip()
        if len(ertek) >= 2 and ertek[0] == ertek[-1] and ertek[0] in ("'", '"'):
            ertek = ertek[1:-1]
        env[kulcs.strip()] = ertek
    return env


class Config:
    _instance: "Config | None" = None

    def __init__(self):
        self._dotenv = self._load_dotenv()
        self._profile = self._resolve_profile()

    @classmethod
    def instance(cls) -> "Config":
        if cls._instance is None:
            cls._instance = Config()
        return cls._instance

    @staticmethod
    def _load_dotenv() -> dict[str, str]:
        mostani = Path.cwd().resolve()
        while True:
            jelolt = mostani / ".env"
            if jelolt.exists():
                try:
                    return _parse_dotenv(jelolt.read_text(encoding="utf-8"))
                except OSError:
                    return {}
            if mostani.parent == mostani:
                return {}
            mostani = mostani.parent

    def _resolve_profile(self) -> str:
        profile = self._raw_env("REBSGO_PROFILE") or self._raw_env("rebsgo.profile")
        return profile if profile else "prod"

    def _raw_env(self, name: str) -> str | None:
        if name in os.environ:
            return os.environ[name]
        if name in self._dotenv:
            return self._dotenv[name]
        return None

    def _resolve_raw(self, key: str) -> str | None:
        env_name = _to_env_name(key)
        ertek = self._raw_env(env_name)
        if ertek is None and env_name != key:
            ertek = self._raw_env(key)
        if ertek is None and key in ALIASES:
            ertek = self._raw_env(ALIASES[key])
        if ertek is None:
            ertek = PROFILES.get(self._profile, {}).get(key)
        if ertek is None and key in FOLLOWS:
            ertek = self._resolve_raw(FOLLOWS[key])
        if ertek is None:
            ertek = BASELINE.get(key)
        return ertek

    def string(self, key: str, default: str | None = None) -> str | None:
        ertek = self._resolve_raw(key)
        return default if ertek is None else ertek

    def int(self, key: str, default: int = 0) -> int:
        ertek = self._resolve_raw(key)
        return default if ertek is None else int(ertek.strip())

    def float(self, key: str, default: float = 0.0) -> float:
        ertek = self._resolve_raw(key)
        return default if ertek is None else float(ertek.strip())

    def f32(self, key: str, default: float = 0.0) -> float:
        from rebsgo.helpers.floats import f32
        ertek = self._resolve_raw(key)
        return f32(default if ertek is None else float(ertek.strip()))

    def bool(self, key: str, default: bool = False) -> bool:
        ertek = self._resolve_raw(key)
        if ertek is None:
            return default
        return ertek.strip().lower() in _BOOL_TRUE

    def set_string(self, key: str) -> set[str]:
        ertek = self._resolve_raw(key)
        if ertek is None:
            return set()
        return {resz.strip() for resz in ertek.split(",") if resz.strip()}

    def set_long(self, key: str) -> set[int]:
        return {int(resz) for resz in self.set_string(key)}
