# github.com/Shran21

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

RESOURCE_GUIDS = (
    (264733124, "resource.cubit"),
    (215278030, "resource.tylium"),
    (207047790, "resource.titanium"),
    (130762195, "resource.water"),
    (130920111, "resource.token"),
)


class Database:
    def __init__(self, path: Path):
        self._path = str(path)


    def reader(self) -> sqlite3.Connection:
        conn = sqlite3.connect(f"file:{self._path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def writer(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn


    def overview(self) -> dict:
        conn = self.reader()
        try:
            def one(sql):
                try:
                    return conn.execute(sql).fetchone()[0]
                except sqlite3.Error:
                    return None
            return {
                "pilots": one("SELECT COUNT(*) FROM pilots"),
                "passwords": one("SELECT COUNT(*) FROM pilot_passwords"),
                "guilds": one("SELECT COUNT(*) FROM guilds"),
                "tally_rows": one("SELECT COUNT(*) FROM tallies"),
            }
        finally:
            conn.close()


    @staticmethod
    def _clock(raw) -> str | None:
        if not raw:
            return None
        try:
            return datetime.fromisoformat(str(raw)).strftime("%Y.%m.%d %H:%M:%S")
        except ValueError:
            return str(raw)[:19]

    def pilots(self) -> list:
        conn = self.reader()
        try:
            rows = [dict(row) for row in conn.execute(
                "SELECT p.id, p.name, p.faction, p.roles_bits, p.last_logout_date, "
                "       (j.player_id IS NOT NULL) AS has_password "
                "FROM pilots p LEFT JOIN pilot_passwords j ON j.player_id = p.id "
                "ORDER BY p.id")]
        finally:
            conn.close()
        for row in rows:
            row["last_seen"] = self._clock(row.pop("last_logout_date"))
        return rows

    def pilot(self, pilot_id: int) -> dict | None:
        conn = self.reader()
        try:
            row = conn.execute(
                "SELECT p.id, p.name, p.faction, p.roles_bits, p.last_logout_date, "
                "       (j.player_id IS NOT NULL) AS has_password "
                "FROM pilots p LEFT JOIN pilot_passwords j ON j.player_id = p.id "
                "WHERE p.id=?", (pilot_id,)).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        record = dict(row)
        record["last_seen"] = self._clock(record.pop("last_logout_date"))
        return record

    def set_role_bits(self, pilot_id: int, role_bits: int) -> bool:
        conn = self.writer()
        try:
            cursor = conn.execute("UPDATE pilots SET roles_bits=? WHERE id=?",
                                  (int(role_bits), int(pilot_id)))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    _WALLET_CONTAINERS = "1,2"

    def resources(self, pilot_id: int) -> list:
        conn = self.reader()
        try:
            held = {row["guid"]: row["total"] for row in conn.execute(
                "SELECT guid, SUM(count) AS total FROM stacks "
                "WHERE player_id=? AND container_id IN (%s) AND guid IN (%s) GROUP BY guid"
                % (self._WALLET_CONTAINERS,
                   ",".join(str(guid) for guid, _ in RESOURCE_GUIDS)), (pilot_id,))}
        finally:
            conn.close()
        return [{"guid": guid, "key": key, "amount": int(held.get(guid, 0))}
                for guid, key in RESOURCE_GUIDS]

    def set_resource(self, pilot_id: int, guid: int, amount: int) -> tuple:
        amount = max(0, min(int(amount), 2_000_000_000))
        conn = self.writer()
        try:
            old = conn.execute(
                "SELECT COALESCE(SUM(count),0) FROM stacks "
                "WHERE player_id=? AND guid=? AND container_id IN (%s)"
                % self._WALLET_CONTAINERS, (pilot_id, guid)).fetchone()[0]
            old = int(old or 0)
            if old == amount:
                return False, old
            conn.execute(
                "DELETE FROM stacks WHERE player_id=? AND guid=? AND container_id IN (%s)"
                % self._WALLET_CONTAINERS, (pilot_id, guid))
            if amount > 0:
                used = {row[0] for row in conn.execute(
                    "SELECT server_id FROM stacks WHERE player_id=? AND container_id=1",
                    (pilot_id,))}
                used |= {row[0] for row in conn.execute(
                    "SELECT server_id FROM installed_systems "
                    "WHERE player_id=? AND container_id=1", (pilot_id,))}
                item_id = 0
                while item_id in used:
                    item_id += 1
                conn.execute(
                    "INSERT INTO stacks(player_id, container_id, server_id, guid, count) "
                    "VALUES (?, 1, ?, ?, ?)", (pilot_id, item_id, guid, amount))
            conn.commit()
            return True, old
        finally:
            conn.close()


    def create_pilot(self, name: str, faction: int) -> tuple:
        name = str(name or "").strip()
        if not (2 <= len(name) <= 24):
            return 0, "account.bad_name"
        conn = self.writer()
        try:
            taken = conn.execute(
                "SELECT 1 FROM pilots WHERE name=? COLLATE NOCASE", (name,)).fetchone()
            if taken is not None:
                return 0, "account.taken"
            pilot_id = int(conn.execute(
                "SELECT COALESCE(MAX(id), 0) + 1 FROM pilots").fetchone()[0])
            conn.execute(
                "INSERT INTO pilots(id, name, faction, roles_bits,"
                " last_logout_date, last_wof_date) VALUES (?,?,?,0,'','')",
                (pilot_id, name, int(faction)))
            conn.commit()
            return pilot_id, ""
        finally:
            conn.close()

    def erase_pilot(self, pilot_id: int) -> dict:
        removed = {}
        conn = self.writer()
        try:
            tables = [row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'")]
            for table in tables:
                columns = {row["name"] for row in
                           conn.execute('PRAGMA table_info("%s")' % table)}
                hits = 0
                if "player_id" in columns:
                    hits += conn.execute(
                        'DELETE FROM "%s" WHERE player_id=?' % table,
                        (pilot_id,)).rowcount
                if table == "friends" and "friend_id" in columns:
                    hits += conn.execute(
                        "DELETE FROM friends WHERE friend_id=?", (pilot_id,)).rowcount
                if table == "pilots":
                    hits += conn.execute(
                        "DELETE FROM pilots WHERE id=?", (pilot_id,)).rowcount
                if hits:
                    removed[table] = hits
            conn.commit()
            return removed
        finally:
            conn.close()


    _BANS_DDL = ("CREATE TABLE IF NOT EXISTS panel_bans (player_id INTEGER NOT NULL"
                 " PRIMARY KEY, until_utc TEXT NOT NULL, reason TEXT NOT NULL"
                 " DEFAULT '', banned_by TEXT NOT NULL DEFAULT '',"
                 " created_at TEXT NOT NULL DEFAULT '')")

    def set_ban(self, pilot_id: int, until_iso: str, reason: str, by: str) -> None:
        conn = self.writer()
        try:
            conn.execute(self._BANS_DDL)
            conn.execute(
                "INSERT OR REPLACE INTO panel_bans VALUES (?,?,?,?,?)",
                (int(pilot_id), str(until_iso), str(reason)[:200], str(by),
                 datetime.now().astimezone().isoformat()))
            conn.commit()
        finally:
            conn.close()

    def clear_ban(self, pilot_id: int) -> bool:
        conn = self.writer()
        try:
            conn.execute(self._BANS_DDL)
            cursor = conn.execute("DELETE FROM panel_bans WHERE player_id=?",
                                  (int(pilot_id),))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def bans(self) -> dict:
        from datetime import timezone
        conn = self.reader()
        try:
            rows = conn.execute("SELECT player_id, until_utc, reason, banned_by"
                                " FROM panel_bans").fetchall()
        except sqlite3.Error:
            return {}
        finally:
            conn.close()
        now = datetime.now(timezone.utc).isoformat()
        return {row["player_id"]: {"until": row["until_utc"],
                                   "reason": row["reason"], "by": row["banned_by"]}
                for row in rows if row["until_utc"] > now}

    def economy(self) -> dict:
        conn = self.reader()
        try:
            held = {}
            for row in conn.execute(
                    "SELECT s.player_id, p.name, s.guid, SUM(s.count) AS total"
                    " FROM stacks s JOIN pilots p ON p.id = s.player_id"
                    " WHERE s.container_id IN (%s) AND s.guid IN (%s)"
                    " GROUP BY s.player_id, s.guid"
                    % (self._WALLET_CONTAINERS,
                       ",".join(str(guid) for guid, _ in RESOURCE_GUIDS))):
                pilot = held.setdefault(row["player_id"],
                                        {"name": row["name"], "wealth": {}})
                pilot["wealth"][row["guid"]] = int(row["total"])
        finally:
            conn.close()
        totals = {guid: 0 for guid, _ in RESOURCE_GUIDS}
        richest = {guid: None for guid, _ in RESOURCE_GUIDS}
        for pilot_id, pilot in held.items():
            for guid, amount in pilot["wealth"].items():
                totals[guid] += amount
                top = richest[guid]
                if top is None or amount > top[1]:
                    richest[guid] = (pilot["name"], amount)
        return {"pilots": [{"id": pilot_id, **pilot}
                           for pilot_id, pilot in sorted(held.items())],
                "totals": totals, "richest": richest}


    def pilot_tallies(self, pilot_id: int) -> list:
        conn = self.reader()
        try:
            return [{"guid": row["guid"], "value": row["value"]}
                    for row in conn.execute(
                        "SELECT guid, value FROM tallies WHERE player_id=?"
                        " ORDER BY value DESC", (pilot_id,))]
        finally:
            conn.close()

    def tally_guids(self) -> list:
        conn = self.reader()
        try:
            return [row[0] for row in conn.execute(
                "SELECT DISTINCT guid FROM tallies ORDER BY guid")]
        finally:
            conn.close()

    def tally_board(self, guid: int, limit: int = 50) -> list:
        conn = self.reader()
        try:
            return [{"id": row["id"], "name": row["name"], "value": row["value"]}
                    for row in conn.execute(
                        "SELECT p.id, p.name, t.value FROM tallies t"
                        " JOIN pilots p ON p.id = t.player_id"
                        " WHERE t.guid=? ORDER BY t.value DESC LIMIT ?",
                        (int(guid), int(limit)))]
        finally:
            conn.close()

    def snapshot_periods(self) -> list:
        conn = self.reader()
        try:
            return [row[0] for row in conn.execute(
                "SELECT DISTINCT period_key FROM ranking_snapshots"
                " ORDER BY period_key DESC")]
        except sqlite3.Error:
            return []
        finally:
            conn.close()

    def snapshot_board(self, period: str, guid: int, limit: int = 50) -> list:
        conn = self.reader()
        try:
            return [{"id": row["id"], "name": row["name"], "value": row["value"]}
                    for row in conn.execute(
                        "SELECT p.id, p.name, s.value FROM ranking_snapshots s"
                        " JOIN pilots p ON p.id = s.player_id"
                        " WHERE s.period_key=? AND s.guid=?"
                        " ORDER BY s.value DESC LIMIT ?",
                        (str(period), int(guid), int(limit)))]
        except sqlite3.Error:
            return []
        finally:
            conn.close()


    def tables(self) -> list:
        conn = self.reader()
        try:
            names = [row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
            return [{"name": name,
                     "rows": conn.execute('SELECT COUNT(*) FROM "%s"' % name).fetchone()[0]}
                    for name in names]
        finally:
            conn.close()

    def _known_table(self, conn, table: str) -> str:
        found = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,)).fetchone()
        if found is None:
            raise ValueError(f"no such table: {table!r}")
        return found[0]

    def columns(self, table: str) -> list:
        conn = self.reader()
        try:
            table = self._known_table(conn, table)
            return [{"name": row["name"], "type": row["type"] or "",
                     "notnull": bool(row["notnull"]), "pk": bool(row["pk"])}
                    for row in conn.execute('PRAGMA table_info("%s")' % table)]
        finally:
            conn.close()

    def browse(self, table: str, q: str = "", sort: str = "",
               descending: bool = False, page_no: int = 1, size: int = 50) -> dict:
        conn = self.reader()
        try:
            table = self._known_table(conn, table)
            names = [row["name"] for row in conn.execute('PRAGMA table_info("%s")' % table)]
            where, params = "", []
            if q:
                where = " WHERE " + " OR ".join(
                    'CAST("%s" AS TEXT) LIKE ?' % name for name in names)
                params = [f"%{q}%"] * len(names)
            total = conn.execute(
                'SELECT COUNT(*) FROM "%s"%s' % (table, where), params).fetchone()[0]
            order = '"%s" %s' % (sort, "DESC" if descending else "ASC") \
                if sort in names else "rowid"
            page_no = max(1, int(page_no))
            rows = conn.execute(
                'SELECT rowid AS _rid, * FROM "%s"%s ORDER BY %s LIMIT ? OFFSET ?'
                % (table, where, order),
                params + [size, (page_no - 1) * size]).fetchall()
            return {"columns": names, "total": total, "page": page_no,
                    "pages": max(1, -(-total // size)),
                    "rows": [dict(row) for row in rows]}
        finally:
            conn.close()

    def row(self, table: str, rid: int) -> dict | None:
        conn = self.reader()
        try:
            table = self._known_table(conn, table)
            found = conn.execute(
                'SELECT rowid AS _rid, * FROM "%s" WHERE rowid=?' % table,
                (rid,)).fetchone()
            return None if found is None else dict(found)
        finally:
            conn.close()

    def update_row(self, table: str, rid: int, values: dict) -> dict | None:
        conn = self.writer()
        try:
            table = self._known_table(conn, table)
            names = [row["name"] for row in conn.execute('PRAGMA table_info("%s")' % table)]
            keep = {name: values[name] for name in names if name in values}
            old = conn.execute(
                'SELECT * FROM "%s" WHERE rowid=?' % table, (rid,)).fetchone()
            if old is None or not keep:
                return None
            conn.execute(
                'UPDATE "%s" SET %s WHERE rowid=?'
                % (table, ", ".join('"%s"=?' % name for name in keep)),
                list(keep.values()) + [rid])
            conn.commit()
            return dict(old)
        finally:
            conn.close()

    def insert_row(self, table: str, values: dict) -> int:
        conn = self.writer()
        try:
            table = self._known_table(conn, table)
            names = [row["name"] for row in conn.execute('PRAGMA table_info("%s")' % table)]
            keep = {name: values[name] for name in names if name in values}
            if keep:
                cursor = conn.execute(
                    'INSERT INTO "%s" (%s) VALUES (%s)'
                    % (table, ", ".join('"%s"' % name for name in keep),
                       ", ".join("?" for _ in keep)),
                    list(keep.values()))
            else:
                cursor = conn.execute('INSERT INTO "%s" DEFAULT VALUES' % table)
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def delete_row(self, table: str, rid: int) -> dict | None:
        conn = self.writer()
        try:
            table = self._known_table(conn, table)
            old = conn.execute(
                'SELECT * FROM "%s" WHERE rowid=?' % table, (rid,)).fetchone()
            if old is None:
                return None
            conn.execute('DELETE FROM "%s" WHERE rowid=?' % table, (rid,))
            conn.commit()
            return dict(old)
        finally:
            conn.close()
