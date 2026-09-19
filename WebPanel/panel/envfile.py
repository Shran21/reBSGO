# github.com/Shran21

from __future__ import annotations

import re
import shutil

from panel.settings import GAME_ROOT, ROOT

ENV_PATH = GAME_ROOT / ".env"
CATALOG_PATH = GAME_ROOT / ".env.example"
PANEL_ENV_PATH = ROOT / "panel.env"

PANEL_KEYS = (
    ("PANEL_HOST", "0.0.0.0", True),
    ("PANEL_PORT", "27055", True),
    ("PANEL_DB", "../sqlite/bgo_server.db", True),
    ("PANEL_LOGIN_ROLES", "Developer,Console", True),
    ("PANEL_SESSION_HOURS", "12", False),
    ("PANEL_BRIDGE_URL", "http://127.0.0.1:27053", True),
    ("PANEL_DEFAULT_LANG", "hu", False),
    ("PANEL_BACKUP_DIR", "/opt/bsgo-backups", False),
    ("PANEL_BACKUP_AT", "", False),
    ("PANEL_BACKUP_KEEP", "7", False),
    ("PANEL_BACKUP_KIND", "db", False),
)

_SECTION = re.compile(r"^# --- ([\w ]+?)(?:\s*\(\d+\))? ---")
_ENTRY = re.compile(r"^#([A-Z][A-Z0-9_]*)=([^#]*?)\s*(?:#\s*(.*))?$")
_LIVE = re.compile(r"^([A-Z][A-Z0-9_]*)=(.*)$")


def catalog() -> list:
    sections = []
    entries = None
    try:
        lines = CATALOG_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        header = _SECTION.match(line)
        if header:
            entries = []
            sections.append({"name": header.group(1).strip(), "entries": entries})
            continue
        found = _ENTRY.match(line)
        if found and entries is not None:
            entries.append({"key": found.group(1),
                            "default": (found.group(2) or "").strip(),
                            "help": (found.group(3) or "").strip()})
    return [section for section in sections if section["entries"]]


def current() -> dict:
    values = {}
    try:
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for line in lines:
        found = _LIVE.match(line.strip())
        if found:
            values[found.group(1)] = found.group(2)
    return values


def panel_current() -> dict:
    values = {}
    try:
        lines = PANEL_ENV_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for line in lines:
        found = _LIVE.match(line.strip())
        if found:
            values[found.group(1)] = found.group(2)
    return values


def panel_apply(changes: dict) -> list:
    return _apply_to(PANEL_ENV_PATH, ".panel.env-bak", changes)


def apply(changes: dict) -> list:
    return _apply_to(ENV_PATH, ".env.panel-bak", changes)


def _apply_to(path, bak_name: str, changes: dict) -> list:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        text = ""
    lines = text.splitlines()
    moved = []
    remaining = dict(changes)

    kept = []
    for line in lines:
        found = _LIVE.match(line.strip())
        if found and found.group(1) in remaining:
            key = found.group(1)
            value = remaining.pop(key)
            if value is None or str(value) == "":
                moved.append(f"{key}: removed (was {found.group(2)!r})")
                continue
            if str(value) != found.group(2):
                moved.append(f"{key}: {found.group(2)!r} -> {str(value)!r}")
            kept.append(f"{key}={value}")
            continue
        kept.append(line)

    added = [f"{key}={value}" for key, value in remaining.items()
             if value is not None and str(value) != ""]
    for line in added:
        moved.append(f"{line.split('=', 1)[0]}: set {line.split('=', 1)[1]!r}")
    if added:
        if kept and kept[-1].strip():
            kept.append("")
        kept.extend(added)

    if not moved:
        return []
    if path.exists():
        shutil.copy2(path, path.with_name(bak_name))
    path.write_text("\n".join(kept).rstrip("\n") + "\n", encoding="utf-8")
    return moved
