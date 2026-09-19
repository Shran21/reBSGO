# github.com/Shran21
from __future__ import annotations

import logging
import os
import sqlite3
import threading

from rebsgo.config.config import Config
from rebsgo.paths import SEMA

log = logging.getLogger(__name__)

_DEFAULT_SCHEMA_DIR = str(SEMA)
_CONFIG = Config.instance()
_SQLITE_TIMEOUT_SECONDS = _CONFIG.float("rebsgo.sqlite.timeout-seconds", 5.0)
_SQLITE_BUSY_TIMEOUT_MS = _CONFIG.int("rebsgo.sqlite.busy-timeout-ms", 5000)
_SQLITE_WAL_ENABLED = _CONFIG.bool("rebsgo.sqlite.wal.enabled", True)
_SQLITE_SYNCHRONOUS = _CONFIG.string("rebsgo.sqlite.synchronous", "FULL")
_SQLITE_FOREIGN_KEYS_ENABLED = _CONFIG.bool("rebsgo.sqlite.foreign-keys.enabled", False)


class DataSource:
    def __init__(self, db_path: str = "./sqlite/bgo_server.db",
                 migrations_dir: str | None = None):
        self._db_path = db_path
        self._migrations_dir = migrations_dir or os.path.normpath(_DEFAULT_SCHEMA_DIR)
        self._lock = threading.Lock()
        parent = os.path.dirname(self._db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._migrate()

    def connection(self) -> sqlite3.TcpLink:
        conn = sqlite3.connect(self._db_path, timeout=_SQLITE_TIMEOUT_SECONDS)
        conn.row_factory = sqlite3.Row
        self._configure_connection(conn)
        return conn

    @staticmethod
    def _configure_connection(conn: sqlite3.TcpLink) -> None:
        if _SQLITE_FOREIGN_KEYS_ENABLED:
            conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(f'PRAGMA busy_timeout={_SQLITE_BUSY_TIMEOUT_MS}')
        if _SQLITE_WAL_ENABLED:
            conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=" + _SQLITE_SYNCHRONOUS)

    def _migrate(self) -> None:
        with self._lock:
            conn = self.connection()
            try:
                conn.execute("CREATE TABLE IF NOT EXISTS applied_schema_steps ("
                             "step TEXT NOT NULL PRIMARY KEY, applied_at TEXT NOT NULL)")
                kesz = {sor["step"] for sor in conn.execute("SELECT step FROM applied_schema_steps")}
                kesz |= self._adopt_earlier_bookkeeping(conn)
                self._adopt_earlier_shape(conn)
                for step, utvonal in self._schema_steps():
                    if step in kesz:
                        continue
                    with open(utvonal, "r", encoding="utf-8") as handle:
                        conn.executescript(handle.read())
                    log.info("Schema step applied: %s", step)
                    conn.execute(
                        "INSERT INTO applied_schema_steps(step, applied_at) "
                        "VALUES (?, datetime('now'))", (step,))
                conn.commit()
            finally:
                conn.close()

    _EARLIER_ORDER = (
        "base-tables", "containers", "guilds", "hangar", "last-known-position",
        "client-settings", "skill-book", "finished-tutorials",
        "repair-cylon-stealth", "repair-cylon-war-raider",
        "chosen-consumable-per-slot", "player-lookup-indexes",
    )

    def _adopt_earlier_bookkeeping(self, conn) -> set[str]:
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        ).fetchone()
        if table is None:
            return set()
        adopted = set()
        for sor in conn.execute("SELECT version FROM schema_migrations ORDER BY version"):
            sorszam = int(sor["version"]) - 1
            if 0 <= sorszam < len(self._EARLIER_ORDER):
                adopted.add(self._EARLIER_ORDER[sorszam])
        for step in sorted(adopted):
            conn.execute(
                "INSERT OR IGNORE INTO applied_schema_steps(step, applied_at) "
                "VALUES (?, datetime('now'))", (step,))
        conn.execute("DROP TABLE schema_migrations")
        log.info("Adopted %d schema steps from the earlier numbering", len(adopted))
        return adopted

    def _adopt_earlier_shape(self, conn) -> None:
        from rebsgo.store.schema_shape import ELDOBANDO, sorszam, terv, uj_nev

        lepesek = terv(conn)
        if not lepesek:
            return

        elotte = sorszam(conn)
        for lepes in lepesek:
            conn.execute(lepes)

        utana = sorszam(conn)
        varhato = {uj_nev(nev): darab for nev, darab in elotte.items()
                   if nev not in ELDOBANDO}
        if utana != varhato:
            raise RuntimeError(
                "row counts disagree after the migration - "
                f"expected {varhato}, got {utana}")
        log.info('database migrated forward in %d steps', len(lepesek))

    def _schema_steps(self):
        listing = os.path.join(self._migrations_dir, "order.txt")
        if not os.path.isfile(listing):
            return []
        lepesek = []
        with open(listing, "r", encoding="utf-8") as handle:
            for sor in handle:
                step = sor.split("#", 1)[0].strip()
                if not step:
                    continue
                path = os.path.join(self._migrations_dir, step + ".sql")
                if not os.path.isfile(path):
                    raise FileNotFoundError(
                        f"order.txt names a step that is not there: {step}.sql")
                lepesek.append((step, path))
        return lepesek
