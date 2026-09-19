# github.com/Shran21

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAME_ROOT = ROOT.parent

_PANEL_ENV = ROOT / "panel.env"


def _gep_nyelve() -> str:
    beallitas = (os.environ.get("REBSGO_LANG") or os.environ.get("LC_ALL")
                 or os.environ.get("LC_MESSAGES") or os.environ.get("LANG") or "")
    return "hu" if beallitas.lower().startswith("hu") else "en"

_DEFAULTS = {
    "PANEL_HOST": "127.0.0.1",
    "PANEL_PORT": "27055",
    "PANEL_DB": "../sqlite/bgo_server.db",
    "PANEL_LOGIN_ROLES": "Developer,Console",
    "PANEL_SESSION_HOURS": "12",
    "PANEL_BRIDGE_URL": "http://127.0.0.1:27053",
    "PANEL_DEFAULT_LANG": _gep_nyelve(),
    "PANEL_BACKUP_DIR": "/opt/bsgo-backups",
    "PANEL_BACKUP_AT": "",
    "PANEL_BACKUP_KEEP": "7",
    "PANEL_BACKUP_KIND": "db",
}


def raw() -> dict:
    env_overrides = {key: value for key, value in os.environ.items()
                     if key.startswith("PANEL_")}
    return {**_DEFAULTS, **_panel_env(), **env_overrides}


def _parse_env(text: str) -> dict:
    values = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def _panel_env() -> dict:
    if not _PANEL_ENV.exists():
        secret = secrets.token_urlsafe(32)
        lines = ["# The panel's own settings. Written on first start; edit freely.",
                 f"PANEL_SECRET={secret}"]
        lines += [f"{key}={value}" for key, value in _DEFAULTS.items()]
        _PANEL_ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return _parse_env(_PANEL_ENV.read_text(encoding="utf-8"))


def _game_env() -> dict:
    path = GAME_ROOT / ".env"
    if not path.exists():
        return {}
    return _parse_env(path.read_text(encoding="utf-8"))


@dataclass(frozen=True, slots=True)
class Settings:
    host: str
    port: int
    db_path: Path
    secret: bytes
    login_roles: tuple
    session_seconds: int
    bridge_url: str
    bridge_token: str
    default_lang: str

    @staticmethod
    def load() -> "Settings":
        env_overrides = {key: value for key, value in os.environ.items()
                         if key.startswith("PANEL_")}
        own = {**_DEFAULTS, **_panel_env(), **env_overrides}
        game = _game_env()
        db_path = Path(own["PANEL_DB"])
        if not db_path.is_absolute():
            db_path = (ROOT / db_path).resolve()
        roles = tuple(r.strip() for r in own["PANEL_LOGIN_ROLES"].split(",") if r.strip())
        return Settings(
            host=own["PANEL_HOST"],
            port=int(own["PANEL_PORT"]),
            db_path=db_path,
            secret=own["PANEL_SECRET"].encode("utf-8"),
            login_roles=roles,
            session_seconds=int(float(own["PANEL_SESSION_HOURS"]) * 3600),
            bridge_url=own["PANEL_BRIDGE_URL"].rstrip("/"),
            bridge_token=game.get("REBSGO_PANEL_TOKEN", ""),
            default_lang=own.get("PANEL_DEFAULT_LANG", "hu"),
        )
