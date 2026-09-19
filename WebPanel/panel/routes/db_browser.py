# github.com/Shran21

from __future__ import annotations

import sqlite3

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from panel.app import app, bridge, csrf_ok, database, page
from panel.auditlog import record
from rebsgo.vocabulary.pilot import ServerRoles

_CELL_CUT = 96

_LINE_CUT = 60


def _owner_of(table: str, values: dict):
    key = values.get("id") if table == "pilots" else values.get("player_id")
    try:
        return int(key)
    except (TypeError, ValueError):
        return None


def _locked(table: str, values: dict) -> bool:
    owner = _owner_of(table, values)
    return owner is not None and owner in bridge.online_ids()


def _cell(value) -> dict:
    if value is None:
        return {"null": True, "text": ""}
    if isinstance(value, (bytes, memoryview)):
        return {"null": False, "text": f"‹blob {len(value)} B›"}
    text = str(value)
    if len(text) > _CELL_CUT:
        text = text[:_CELL_CUT] + "…"
    return {"null": False, "text": text}


def _fields(columns: list, values: dict) -> list:
    fields = []
    for column in columns:
        value = values.get(column["name"])
        blob = isinstance(value, (bytes, memoryview))
        text = "" if value is None or blob else str(value)
        fields.append({
            "name": column["name"],
            "type": column["type"],
            "pk": column["pk"],
            "blob": blob,
            "blob_size": len(value) if blob else 0,
            "null": value is None,
            "long": len(text) > _LINE_CUT or "\n" in text,
            "value": text,
        })
    return fields


def _form_values(form, columns: list) -> dict:
    values = {}
    for column in columns:
        name = column["name"]
        if form.get(f"null_{name}") is not None:
            values[name] = None
        elif form.get(f"value_{name}") is not None:
            values[name] = str(form.get(f"value_{name}"))
    return values


def _changes(old: dict, new: dict) -> str:
    parts = []
    for name, value in new.items():
        before = old.get(name)
        if str(before) != str(value) and not (before is None and value is None):
            parts.append(f"{name}: {before!r} -> {value!r}")
    return "; ".join(parts)[:300] or "no change"


@app.get("/db", response_class=HTMLResponse)
async def db_tables(request: Request, notice: str = "", error: str = ""):
    from panel import backups
    from panel import settings as panel_settings
    conf = panel_settings.raw()
    return page(request, "db_tables.html", tables=database.tables(),
                db_backups=backups.db_backups(),
                backup_busy=backups.busy.locked(),
                backup_at=(conf.get("PANEL_BACKUP_AT") or "").strip(),
                backup_kind=(conf.get("PANEL_BACKUP_KIND") or "db").strip(),
                may_backup=request.state.session.wears(ServerRoles.Developer),
                notice=notice, error=error)


@app.post("/db/backup")
async def db_backup_now(request: Request):
    import threading

    from panel import backups
    form = await request.form()
    session = request.state.session
    if not csrf_ok(request, str(form.get("csrf", ""))):
        return RedirectResponse("/db?error=csrf.failed", status_code=303)
    if not session.wears(ServerRoles.Developer):
        return RedirectResponse("/db?error=db.backup.denied", status_code=303)
    if not backups.busy.acquire(blocking=False):
        return RedirectResponse("/db?error=db.backup.busy", status_code=303)

    def _snapshot(who: str) -> None:
        try:
            backups.run_db(who)
        finally:
            backups.busy.release()

    threading.Thread(target=_snapshot, args=(session.name,),
                     name="panel-db-backup", daemon=True).start()
    return RedirectResponse("/db?notice=db.backup.started", status_code=303)


@app.get("/db/backup/{name}")
async def db_backup_download(request: Request, name: str):
    from fastapi.responses import FileResponse

    from panel import backups
    session = request.state.session
    if not session.wears(ServerRoles.Developer):
        return RedirectResponse("/db?error=db.backup.denied", status_code=303)
    listed = {entry["name"] for entry in backups.db_backups()}
    if name not in listed:
        return RedirectResponse("/db?error=db.backup.gone", status_code=303)
    record(session.name, "backup.db.download", target=name)
    return FileResponse(backups.backup_dir() / "db" / name, filename=name,
                        media_type="application/gzip")


@app.get("/db/{table}", response_class=HTMLResponse)
async def db_browse(request: Request, table: str, q: str = "", sort: str = "",
                    desc: int = 0, p: int = 1, notice: str = "", error: str = ""):
    try:
        sheet = database.browse(table, q=q, sort=sort,
                                descending=bool(desc), page_no=p)
    except ValueError:
        return RedirectResponse("/db", status_code=303)
    rows = [{"_rid": row["_rid"],
             "cells": [_cell(row[name]) for name in sheet["columns"]]}
            for row in sheet["rows"]]
    return page(request, "db_rows.html",
                table=table, columns=sheet["columns"], rows=rows,
                total=sheet["total"], page_no=sheet["page"], pages=sheet["pages"],
                q=q, sort=sort, desc=int(bool(desc)),
                may_edit=request.state.session.wears(ServerRoles.Developer),
                notice=notice, error=error)


@app.get("/db/{table}/new", response_class=HTMLResponse)
async def db_new(request: Request, table: str, error: str = "", detail: str = ""):
    try:
        columns = database.columns(table)
    except ValueError:
        return RedirectResponse("/db", status_code=303)
    return page(request, "db_row.html",
                table=table, rid=None, fields=_fields(columns, {}),
                may_edit=request.state.session.wears(ServerRoles.Developer),
                locked=False, error=error, detail=detail)


@app.post("/db/{table}/new")
async def db_insert(request: Request, table: str):
    form = await request.form()
    session = request.state.session
    if not csrf_ok(request, str(form.get("csrf", ""))):
        return RedirectResponse(f"/db/{table}/new?error=csrf.failed", status_code=303)
    if not session.wears(ServerRoles.Developer):
        return RedirectResponse(f"/db/{table}/new?error=db.denied", status_code=303)
    try:
        columns = database.columns(table)
    except ValueError:
        return RedirectResponse("/db", status_code=303)
    values = {name: value
              for name, value in _form_values(form, columns).items()
              if value is not None}
    if _locked(table, values):
        return RedirectResponse(f"/db/{table}/new?error=db.online_locked", status_code=303)
    try:
        rid = database.insert_row(table, values)
    except sqlite3.Error as trouble:
        return RedirectResponse(
            f"/db/{table}/new?error=db.error&detail={trouble}", status_code=303)
    record(session.name, "db.insert", target=f"{table} rid={rid}",
           outcome="; ".join(f"{k}={v!r}" for k, v in values.items())[:300])
    return RedirectResponse(f"/db/{table}?notice=db.inserted", status_code=303)


@app.get("/db/{table}/{rid}", response_class=HTMLResponse)
async def db_row(request: Request, table: str, rid: int,
                 notice: str = "", error: str = "", detail: str = ""):
    try:
        found = database.row(table, rid)
    except ValueError:
        return RedirectResponse("/db", status_code=303)
    if found is None:
        return RedirectResponse(f"/db/{table}?error=db.gone", status_code=303)
    return page(request, "db_row.html",
                table=table, rid=rid,
                fields=_fields(database.columns(table), found),
                may_edit=request.state.session.wears(ServerRoles.Developer),
                locked=_locked(table, found),
                notice=notice, error=error, detail=detail)


@app.post("/db/{table}/{rid}")
async def db_save(request: Request, table: str, rid: int):
    form = await request.form()
    session = request.state.session
    if not csrf_ok(request, str(form.get("csrf", ""))):
        return RedirectResponse(f"/db/{table}/{rid}?error=csrf.failed", status_code=303)
    if not session.wears(ServerRoles.Developer):
        return RedirectResponse(f"/db/{table}/{rid}?error=db.denied", status_code=303)
    try:
        found = database.row(table, rid)
    except ValueError:
        return RedirectResponse("/db", status_code=303)
    if found is None:
        return RedirectResponse(f"/db/{table}?error=db.gone", status_code=303)
    if _locked(table, found):
        return RedirectResponse(f"/db/{table}/{rid}?error=db.online_locked",
                                status_code=303)
    values = _form_values(form, database.columns(table))
    try:
        old = database.update_row(table, rid, values)
    except sqlite3.Error as trouble:
        return RedirectResponse(
            f"/db/{table}/{rid}?error=db.error&detail={trouble}", status_code=303)
    if old is not None:
        record(session.name, "db.update", target=f"{table} rid={rid}",
               outcome=_changes(old, values))
    return RedirectResponse(f"/db/{table}/{rid}?notice=db.saved", status_code=303)


@app.post("/db/{table}/{rid}/delete")
async def db_delete(request: Request, table: str, rid: int):
    form = await request.form()
    session = request.state.session
    if not csrf_ok(request, str(form.get("csrf", ""))):
        return RedirectResponse(f"/db/{table}/{rid}?error=csrf.failed", status_code=303)
    if not session.wears(ServerRoles.Developer):
        return RedirectResponse(f"/db/{table}/{rid}?error=db.denied", status_code=303)
    try:
        found = database.row(table, rid)
    except ValueError:
        return RedirectResponse("/db", status_code=303)
    if found is None:
        return RedirectResponse(f"/db/{table}?error=db.gone", status_code=303)
    if _locked(table, found):
        return RedirectResponse(f"/db/{table}/{rid}?error=db.online_locked",
                                status_code=303)
    old = database.delete_row(table, rid)
    record(session.name, "db.delete", target=f"{table} rid={rid}",
           outcome="; ".join(f"{k}={v!r}" for k, v in (old or {}).items())[:300])
    return RedirectResponse(f"/db/{table}?notice=db.deleted", status_code=303)
