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


def files_of(channel: str) -> list:
    base = CHANNELS.get(channel)
    if base is None:
        return []
    found = []
    for index in range(0, 11):
        candidate = base if index == 0 else Path(f"{base}.{index}")
        if candidate.exists():
            found.append({"index": index, "name": candidate.name,
                          "size": candidate.stat().st_size})
    return found


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
    path = base if int(index) == 0 else Path(f"{base}.{int(index)}")
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
