# github.com/Shran21

from __future__ import annotations

import re

from pathlib import Path

from panel.settings import GAME_ROOT, ROOT

_REACH_BYTES = 4 * 1024 * 1024

MAX_LINES = 1000

CHANNELS = {
    "server": GAME_ROOT / "logs" / "server.log",
    "sector": GAME_ROOT / "logs" / "sector.log",
    "login": GAME_ROOT / "logs" / "login.log",
    "error": GAME_ROOT / "logs" / "error.log",
    "audit": GAME_ROOT / "logs" / "audit.log",
    "panel": ROOT / "logs" / "panel-audit.log",
}


# The audit trails stay: deleting them from the panel would erase its own record.
DELETABLE = ("server", "sector", "login", "error")

# Archives get indexes from here on: the rotated files keep 1..10.
_ARCHIVE_BASE = 100


def _archives(base: Path) -> list:
    # what the service's start keeps of earlier runs: server-20261027-101218.log
    return sorted(base.parent.glob(f"{base.stem}-*{base.suffix}"), reverse=True)


def files_of(channel: str) -> list:
    base = CHANNELS.get(channel)
    if base is None:
        return []
    found = []
    for index in range(0, 11):
        candidate = base if index == 0 else Path(f"{base}.{index}")
        if candidate.exists():
            found.append({"index": index, "name": candidate.name,
                          "size": candidate.stat().st_size, "path": candidate})
    for offset, candidate in enumerate(_archives(base)):
        try:
            size = candidate.stat().st_size
        except OSError:
            continue
        found.append({"index": _ARCHIVE_BASE + offset, "name": candidate.name, "size": size,
                      "path": candidate})
    return found


def _path_of(channel: str, index: int) -> Path | None:
    base = CHANNELS.get(channel)
    if base is None:
        return None
    if index >= _ARCHIVE_BASE:
        archives = _archives(base)
        return archives[index - _ARCHIVE_BASE] if index - _ARCHIVE_BASE < len(archives) else None
    return base if index == 0 else Path(f"{base}.{index}")


# One file of a channel, by its name: the one being written is emptied, an older one
# deleted. Gives (what was done, bytes freed); ("", 0) for a name the channel lacks.
def remove(channel: str, name: str) -> tuple:
    base = CHANNELS.get(channel)
    if base is None or channel not in DELETABLE:
        return "", 0
    for entry in files_of(channel):
        if entry["name"] != name:
            continue
        path = entry["path"]
        if entry["index"] == 0:
            # the server keeps it open for appending: emptied in place, it carries on writing
            with open(path, "r+b") as handle:
                handle.truncate(0)
            return "cleared", entry["size"]
        path.unlink(missing_ok=True)
        return "deleted", entry["size"]
    return "", 0


# Every file of a channel but the one being written. Gives (files, bytes freed).
# The paths come from the one listing: an archive's index shifts as the others go.
def purge_old(channel: str) -> tuple:
    if channel not in DELETABLE:
        return 0, 0
    files, freed = 0, 0
    for entry in files_of(channel):
        if entry["index"] == 0:
            continue
        try:
            entry["path"].unlink()
        except OSError:
            continue
        files += 1
        freed += entry["size"]
    return files, freed


_LINE_START = re.compile(r"^(?:\d{4}-\d{2}-\d{2} )?\d{2}:\d{2}:\d{2}\.\d{3} ")
_ERROR_MARK = " X "


def is_line_start(line: str) -> bool:
    return bool(_LINE_START.match(line))


def _is_error(line: str) -> bool:
    return is_line_start(line) and _ERROR_MARK in line[:48]


def error_blocks(lines: list) -> list:
    kept, keep = [], False
    for line in lines:
        if is_line_start(line):
            keep = _ERROR_MARK in line[:48]
        if keep:
            kept.append(line)
    return kept


def count_errors(text: str) -> int:
    return sum(1 for line in text.splitlines() if _is_error(line))


def tail(channel: str, index: int = 0, query: str = "",
         limit: int = 200, only: str = "all") -> dict:
    base = CHANNELS.get(channel)
    limit = max(1, min(int(limit), MAX_LINES))
    if base is None:
        return {"lines": [], "truncated": False}
    path = _path_of(channel, int(index))
    if path is None:
        return {"lines": [], "truncated": False}
    try:
        size = path.stat().st_size
        with open(path, "rb") as reader:
            if size > _REACH_BYTES:
                reader.seek(size - _REACH_BYTES)
            raw = reader.read()
    except OSError:
        return {"lines": [], "truncated": False}
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    if size > _REACH_BYTES and lines:
        lines = lines[1:]
    if query:
        needle = query.lower()
        lines = [line for line in lines if needle in line.lower()]
    if only == "errors":
        lines = error_blocks(lines)
    return {"lines": lines[-limit:], "truncated": size > _REACH_BYTES}
