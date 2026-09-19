# github.com/Shran21

from __future__ import annotations

import gzip
import logging
import shutil
import sqlite3
import subprocess
import threading
import time
from pathlib import Path

from panel import settings as panel_settings
from panel.auditlog import record
from panel.settings import GAME_ROOT

log = logging.getLogger(__name__)

busy = threading.Lock()

_DB_SUBDIR = "db"
_MARKER = ".auto-backup-date"


def backup_dir() -> Path:
    return Path(panel_settings.raw()["PANEL_BACKUP_DIR"])


def full_backups() -> list:
    return _listing(backup_dir(), "*.tar.gz")


def db_backups() -> list:
    return _listing(backup_dir() / _DB_SUBDIR, "*.db.gz")


def _listing(root: Path, pattern: str) -> list:
    if not root.is_dir():
        return []
    found = []
    for path in sorted(root.glob(pattern), reverse=True):
        stat = path.stat()
        found.append({"name": path.name,
                      "size_mb": round(stat.st_size / (1024 * 1024), 1),
                      "when": time.strftime("%Y.%m.%d %H:%M", time.localtime(stat.st_mtime))})
    return found[:20]


def run_full(who: str) -> None:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = backup_dir() / f"reBSGO-server-{stamp}.tar.gz"
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["tar", "czf", str(target),
             "--exclude=./WebPanel/venv", "--exclude=./venv",
             "--exclude=./logs", "--exclude=./WebPanel/logs",
             "--exclude=./cache", "--exclude=__pycache__",
             "-C", str(GAME_ROOT), "."],
            check=True, capture_output=True, timeout=1200)
        record(who, "backup.create", target=target.name,
               outcome=f"{round(target.stat().st_size / (1024 * 1024), 1)} MB")
    except (subprocess.SubprocessError, OSError) as trouble:
        record(who, "backup.create", target=target.name, outcome=f"failed: {trouble}")
        target.unlink(missing_ok=True)
    finally:
        busy.release()


def run_db(who: str) -> Path | None:
    source = panel_settings.Settings.load().db_path
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = backup_dir() / _DB_SUBDIR / f"bgo_server-{stamp}.db.gz"
    target.parent.mkdir(parents=True, exist_ok=True)
    raw_copy = target.with_suffix("")
    try:
        with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as opened, \
                sqlite3.connect(str(raw_copy)) as snapshot:
            opened.backup(snapshot)
        with open(raw_copy, "rb") as plain, gzip.open(target, "wb") as packed:
            shutil.copyfileobj(plain, packed)
        record(who, "backup.db", target=target.name,
               outcome=f"{round(target.stat().st_size / (1024 * 1024), 1)} MB")
        return target
    except (sqlite3.Error, OSError) as trouble:
        record(who, "backup.db", target=target.name, outcome=f"failed: {trouble}")
        target.unlink(missing_ok=True)
        return None
    finally:
        raw_copy.unlink(missing_ok=True)


def prune(kind: str, keep: int) -> int:
    if keep < 1:
        return 0
    if kind == "full":
        root, pattern = backup_dir(), "reBSGO-server-*.tar.gz"
    else:
        root, pattern = backup_dir() / _DB_SUBDIR, "bgo_server-*.db.gz"
    if not root.is_dir():
        return 0
    stale = sorted(root.glob(pattern))[:-keep]
    for path in stale:
        path.unlink(missing_ok=True)
    return len(stale)


def due(now_hhmm: str, at: str, last_date: str, today: str) -> bool:
    at = (at or "").strip()
    if not at or len(at) != 5 or at[2] != ":":
        return False
    return now_hhmm >= at and last_date != today


def _tick() -> None:
    conf = panel_settings.raw()
    at = conf.get("PANEL_BACKUP_AT", "")
    if not (at or "").strip():
        return
    marker = backup_dir() / _MARKER
    try:
        last = marker.read_text(encoding="utf-8").strip()
    except OSError:
        last = ""
    today = time.strftime("%Y-%m-%d")
    if not due(time.strftime("%H:%M"), at, last, today):
        return
    if not busy.acquire(blocking=False):
        return
    holding = True
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(today + "\n", encoding="utf-8")
        kind = (conf.get("PANEL_BACKUP_KIND") or "db").strip().lower()
        try:
            keep = int(conf.get("PANEL_BACKUP_KEEP") or "7")
        except ValueError:
            keep = 7
        if kind == "full":
            holding = False
            run_full("scheduler")
        else:
            try:
                run_db("scheduler")
            finally:
                busy.release()
                holding = False
        dropped = prune(kind, keep)
        if dropped:
            record("scheduler", "backup.prune", outcome=f"{kind}: {dropped} removed")
    except Exception:
        log.exception("the scheduled backup fell over")
    finally:
        if holding:
            busy.release()


def _loop() -> None:
    while True:
        time.sleep(30)
        try:
            _tick()
        except Exception:
            log.exception("backup clock tick failed")


threading.Thread(target=_loop, name="panel-backup-clock", daemon=True).start()
